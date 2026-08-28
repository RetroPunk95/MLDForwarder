import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from mldtools_media.config_store import ConfigStore
from mldtools_media.tdl_client import TDLClient
from mldtools_media.tool_runner import ToolRunner


class FakeTDLClient(TDLClient):
    @property
    def executable(self) -> Path:
        return Path(sys.executable)


class ToolRunnerTests(unittest.TestCase):
    def test_one_shot_tool_reports_progress_and_releases_engine(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "fake_tool.py"
            script.write_text(
                'print("Enviando álbum… 50% 1.0 MiB/s")\n'
                'print("Upload concluído 100% 2.0 MiB/s")\n',
                encoding="utf-8",
            )
            client = FakeTDLClient(ConfigStore(root / "config.json"))
            events = []
            runner = ToolRunner(client, events.append)
            self.assertTrue(
                runner.start("upload", "o upload de teste", [sys.executable, str(script)])
            )
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if any(event.get("type") == "tool_finished" for event in events):
                    break
                time.sleep(0.05)
            runner.shutdown()
            self.assertTrue(any(event.get("type") == "tool_progress" for event in events))
            self.assertTrue(any(event.get("type") == "tool_finished" for event in events))
            self.assertTrue(
                any(
                    event.get("type") == "tool_log"
                    and "Enviando álbum…" in event.get("message", "")
                    for event in events
                )
            )
            self.assertEqual(client.active_operation, "")

    def test_album_cancel_signal_stops_the_worker_and_cleans_task_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "album-upload-test.json"
            marker = root / "upload-finished.txt"
            script = root / "fake_album.py"
            config.write_text("{}", encoding="utf-8")
            script.write_text(
                "import argparse, time\n"
                "from pathlib import Path\n"
                "parser = argparse.ArgumentParser()\n"
                "parser.add_argument('--config', required=True)\n"
                "args = parser.parse_args()\n"
                "cancel = Path(args.config + '.cancel')\n"
                "print('upload started', flush=True)\n"
                "for _ in range(200):\n"
                "    if cancel.exists():\n"
                "        print('upload cancelled', flush=True)\n"
                "        raise SystemExit(2)\n"
                "    time.sleep(0.01)\n"
                f"Path({str(marker)!r}).write_text('finished', encoding='utf-8')\n",
                encoding="utf-8",
            )
            client = FakeTDLClient(ConfigStore(root / "config.json"))
            events = []
            runner = ToolRunner(client, events.append)
            self.assertTrue(
                runner.start(
                    "upload",
                    "o upload de teste",
                    [sys.executable, str(script), "--config", str(config)],
                )
            )

            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                if any(
                    event.get("type") == "tool_log"
                    and "upload started" in event.get("message", "")
                    for event in events
                ):
                    break
                time.sleep(0.02)
            self.assertTrue(runner.cancel())

            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if any(event.get("type") == "tool_cancelled" for event in events):
                    break
                time.sleep(0.02)
            runner.shutdown()

            self.assertTrue(any(event.get("type") == "tool_cancelled" for event in events))
            self.assertFalse(marker.exists())
            self.assertFalse(config.exists())
            self.assertFalse(Path(str(config) + ".cancel").exists())
            self.assertEqual(client.active_operation, "")

    def test_cancel_fallback_terminates_a_non_responsive_process_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "album-upload-hung.json"
            marker = root / "child-survived.txt"
            script = root / "hung_album.py"
            config.write_text("{}", encoding="utf-8")
            child_code = (
                "import time\n"
                "from pathlib import Path\n"
                "time.sleep(1)\n"
                f"Path({str(marker)!r}).write_text('alive', encoding='utf-8')\n"
            )
            script.write_text(
                "import subprocess, sys, time\n"
                f"subprocess.Popen([sys.executable, '-c', {child_code!r}])\n"
                "print('hung upload started', flush=True)\n"
                "time.sleep(10)\n",
                encoding="utf-8",
            )
            client = FakeTDLClient(ConfigStore(root / "config.json"))
            events = []
            runner = ToolRunner(client, events.append)
            with patch("mldtools_media.tool_runner.CANCEL_GRACE_SECONDS", 0.1):
                self.assertTrue(
                    runner.start(
                        "upload",
                        "o upload travado",
                        [sys.executable, str(script), "--config", str(config)],
                    )
                )
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    if any(
                        event.get("type") == "tool_log"
                        and "hung upload started" in event.get("message", "")
                        for event in events
                    ):
                        break
                    time.sleep(0.02)
                self.assertTrue(runner.cancel())
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    if any(event.get("type") == "tool_cancelled" for event in events):
                        break
                    time.sleep(0.02)
                runner.shutdown()

            time.sleep(1.1)
            self.assertTrue(any(event.get("type") == "tool_cancelled" for event in events))
            self.assertFalse(marker.exists())
            self.assertEqual(client.active_operation, "")


if __name__ == "__main__":
    unittest.main()
