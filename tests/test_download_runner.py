import sys
import tempfile
import time
import unittest
from pathlib import Path

from mldtools_media.config_store import ConfigStore
from mldtools_media.models import DownloadTask
from mldtools_media.runner import DownloadRunner
from mldtools_media.task_store import TaskStore
from mldtools_media.tdl_client import TDLClient


class FakeTDLClient(TDLClient):
    def __init__(self, config: ConfigStore, script: Path):
        super().__init__(config)
        self.script = script

    @property
    def executable(self) -> Path:
        return Path(sys.executable)

    def _global_args(self):
        return [sys.executable, str(self.script)]


class RunnerTests(unittest.TestCase):
    def test_chat_export_and_download_complete_end_to_end(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "fake_tdl.py"
            script.write_text(
                """
import json
import pathlib
import sys

args = sys.argv[1:]
if args[:2] == ["chat", "export"]:
    output = pathlib.Path(args[args.index("-o") + 1])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"messages": [{"file_size": 1024}]}), encoding="utf-8")
    print("export 100%")
    raise SystemExit(0)
if args and args[0] == "dl":
    print("download 25% 1.0 MiB/s")
    print("download 100% 1.0 MiB/s")
    raise SystemExit(0)
raise SystemExit(2)
""".strip(),
                encoding="utf-8",
            )
            config = ConfigStore(root / "config.json")
            config.update({"workspace_dir": str(root / "work")})
            store = TaskStore(root / "tasks.json")
            task = DownloadTask(
                title="Canal de teste",
                source_type="chat",
                source={"chat_id": "-1001", "topic_id": "", "scope": "last", "scope_value": "5"},
                destination=str(root / "downloads"),
                options={"threads_per_file": 2, "parallel_downloads": 1},
            )
            store.add(task)
            events = []
            runner = DownloadRunner(store, FakeTDLClient(config, script), events.append)
            runner.start()
            self.assertTrue(runner.start_queue())
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                current = store.get(task.id)
                if current and current.status in {"completed", "failed"}:
                    break
                time.sleep(0.05)
            runner.shutdown()
            current = store.get(task.id)
            self.assertIsNotNone(current)
            self.assertEqual(current.status, "completed", current.error)
            self.assertEqual(current.progress, 100.0)
            self.assertEqual(current.estimated_bytes, 1024)
            self.assertTrue(any(event.get("type") == "estimate" for event in events))

    def test_queued_task_waits_for_manual_start(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "fake_tdl.py"
            script.write_text("raise SystemExit(0)\n", encoding="utf-8")
            config = ConfigStore(root / "config.json")
            store = TaskStore(root / "tasks.json")
            task = DownloadTask(
                title="Aguardando confirmação",
                source_type="links",
                source={"links": ["https://t.me/c/1/1"]},
                destination=str(root / "downloads"),
                options={},
            )
            store.add(task)
            runner = DownloadRunner(store, FakeTDLClient(config, script))
            runner.start()
            runner.notify()
            time.sleep(0.2)
            self.assertEqual(store.get(task.id).status, "queued")
            runner.shutdown()

    def test_download_and_upload_share_creation_order_and_manual_start(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "fake_tdl.py"
            operations = root / "operations.txt"
            upload_file = root / "video.mkv"
            upload_file.write_bytes(b"video")
            script.write_text(
                "import sys\n"
                "from pathlib import Path\n"
                f"output = Path({str(operations)!r})\n"
                "args = sys.argv[1:]\n"
                "with output.open('a', encoding='utf-8') as stream:\n"
                "    stream.write(args[0] + '\\n')\n"
                "print('transfer 50% 1.0 MiB/s', flush=True)\n"
                "print('transfer 100% 2.0 MiB/s', flush=True)\n",
                encoding="utf-8",
            )
            config = ConfigStore(root / "config.json")
            store = TaskStore(root / "tasks.json")
            upload = DownloadTask(
                title="Upload primeiro",
                source_type="upload",
                source={
                    "paths": [str(upload_file)],
                    "chat_id": "",
                    "chat_type": "private",
                    "chat_username": "",
                    "topic_id": "",
                },
                destination="Mensagens Salvas",
                options={"caption": "", "group_albums": False},
                operation_type="upload",
            )
            download = DownloadTask(
                title="Download depois",
                source_type="links",
                source={"links": ["https://t.me/c/1/1"]},
                destination=str(root / "downloads"),
                options={},
            )
            store.add(upload)
            store.add(download)
            runner = DownloadRunner(store, FakeTDLClient(config, script))
            runner.start()
            runner.notify()
            time.sleep(0.2)
            self.assertEqual(store.get(upload.id).status, "queued")
            self.assertEqual(store.get(download.id).status, "queued")

            self.assertTrue(runner.start_queue())
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if all(
                    store.get(task.id).status == "completed"
                    for task in (upload, download)
                ):
                    break
                time.sleep(0.05)
            runner.shutdown()

            self.assertEqual(store.get(upload.id).status, "completed")
            self.assertEqual(store.get(download.id).status, "completed")
            self.assertEqual(
                operations.read_text(encoding="utf-8").splitlines(),
                ["upload", "dl"],
            )

    def test_queued_album_upload_can_be_cancelled_cooperatively(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "album-upload-queued.json"
            marker = root / "finished.txt"
            script = root / "fake_album.py"
            upload_file = root / "video.mkv"
            config_path.write_text("{}", encoding="utf-8")
            upload_file.write_bytes(b"video")
            script.write_text(
                "import argparse, time\n"
                "from pathlib import Path\n"
                "parser = argparse.ArgumentParser()\n"
                "parser.add_argument('--config', required=True)\n"
                "args = parser.parse_args()\n"
                "cancel = Path(args.config + '.cancel')\n"
                "print('album started', flush=True)\n"
                "for _ in range(300):\n"
                "    if cancel.exists():\n"
                "        print('album cancelled', flush=True)\n"
                "        raise SystemExit(2)\n"
                "    time.sleep(0.01)\n"
                f"Path({str(marker)!r}).write_text('finished', encoding='utf-8')\n",
                encoding="utf-8",
            )

            class AlbumClient(FakeTDLClient):
                def build_upload_task_command(self, _task):
                    return [
                        sys.executable,
                        str(script),
                        "--config",
                        str(config_path),
                    ]

            config = ConfigStore(root / "config.json")
            store = TaskStore(root / "tasks.json")
            task = DownloadTask(
                title="Álbum",
                source_type="upload",
                source={
                    "paths": [str(upload_file)],
                    "chat_id": "",
                    "topic_id": "",
                },
                destination="Mensagens Salvas",
                options={"group_albums": True},
                operation_type="upload",
            )
            store.add(task)
            events = []
            runner = DownloadRunner(store, AlbumClient(config, script), events.append)
            runner.start()
            self.assertTrue(runner.start_queue())
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                if any(
                    event.get("type") == "log"
                    and "album started" in event.get("message", "")
                    for event in events
                ):
                    break
                time.sleep(0.02)
            self.assertTrue(runner.cancel(task.id))
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if store.get(task.id).status == "cancelled":
                    break
                time.sleep(0.02)
            runner.shutdown()

            self.assertEqual(store.get(task.id).status, "cancelled")
            self.assertFalse(marker.exists())
            self.assertFalse(config_path.exists())
            self.assertFalse(Path(str(config_path) + ".cancel").exists())


if __name__ == "__main__":
    unittest.main()
