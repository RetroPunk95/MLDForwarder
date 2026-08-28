import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from mldtools_media.config_store import ConfigStore
from mldtools_media.models import DownloadTask
from mldtools_media.tdl_client import (
    EngineBusyError,
    TDLClient,
    ORIGINAL_FILENAME_TEMPLATE,
    estimate_media_bytes,
    extract_json,
    friendly_tdl_error,
    is_database_in_use_error,
    normalise_chat_rows,
)


class TDLClientTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        config_path = Path(self.temporary.name) / "config.json"
        self.config = ConfigStore(config_path)
        self.config.update({"workspace_dir": self.temporary.name, "proxy": ""})
        self.client = TDLClient(self.config)

    def make_link_task(self) -> DownloadTask:
        return DownloadTask(
            title="Links",
            source_type="links",
            source={"links": ["https://t.me/teste/1", "https://t.me/teste/2?comment=3"]},
            destination="C:/Downloads Telegram",
            options={
                "threads_per_file": 8,
                "parallel_downloads": 4,
                "group_albums": True,
                "skip_same": True,
                "include_extensions": ".jpg, .png",
            },
        )

    def test_build_download_command_keeps_each_link_as_one_argument(self):
        task = self.make_link_task()
        command = self.client.build_download_command(task)
        self.assertIn("https://t.me/teste/2?comment=3", command)
        self.assertIn("C:/Downloads Telegram", command)
        self.assertIn("jpg,png", command)
        self.assertIn("--group", command)
        self.assertIn("--skip-same", command)

    def test_build_download_command_can_keep_original_filename(self):
        task = self.make_link_task()
        task.options["keep_original_filename"] = True

        command = self.client.build_download_command(task)

        self.assertEqual(
            command[command.index("--template") + 1],
            ORIGINAL_FILENAME_TEMPLATE,
        )
        self.assertNotIn(".DialogID", command[command.index("--template") + 1])

    def test_build_chat_export_for_topic_and_id_range(self):
        task = DownloadTask(
            title="Canal",
            source_type="chat",
            source={
                "chat_id": "-100123",
                "topic_id": "456",
                "scope": "id",
                "scope_value": "100, 500",
            },
            destination="C:/Downloads",
            options={},
        )
        command = self.client.build_export_command(task, Path(self.temporary.name) / "messages.json")
        self.assertEqual(command[command.index("--topic") + 1], "456")
        self.assertEqual(command[command.index("-T") + 1], "id")
        self.assertEqual(command[command.index("-i") + 1], "100,500")

    def test_extract_and_normalise_chat_json(self):
        payload = extract_json('log anterior\n[{"ID": 1, "VisibleName": "Canal", "Type": "channel", "Topics": [{"ID": 9, "Title": "Filmes"}]}]')
        rows = normalise_chat_rows(payload)
        self.assertEqual(rows[0]["name"], "Canal")
        self.assertEqual(rows[0]["topics"][0]["id"], "9")

    def test_normalise_current_tdl_snake_case_chat_json(self):
        rows = normalise_chat_rows(
            [
                {
                    "id": 1173420740,
                    "type": "channel",
                    "visible_name": "Filmes MLD",
                    "username": "filmes_mld",
                    "topics": [{"id": 42, "title": "Lançamentos"}],
                }
            ]
        )
        self.assertEqual(rows[0]["name"], "Filmes MLD")
        self.assertEqual(rows[0]["username"], "filmes_mld")
        self.assertEqual(rows[0]["topics"][0]["name"], "Lançamentos")

    def test_estimate_media_bytes_handles_both_export_styles(self):
        payload = {
            "messages": [
                {"file": "a.mkv", "file_size": 1000},
                {"Media": {"Name": "b.mkv", "Size": 2000}},
            ]
        }
        self.assertEqual(estimate_media_bytes(payload), 3000)

    def test_engine_operation_is_exclusive_and_can_be_released_by_waiter(self):
        token = self.client.acquire_operation("a autenticação do Telegram")
        self.assertEqual(self.client.active_operation, "a autenticação do Telegram")
        with self.assertRaisesRegex(EngineBusyError, "autenticação"):
            self.client.acquire_operation("a verificação da conta")

        waiter = threading.Thread(target=lambda: self.client.release_operation(token))
        waiter.start()
        waiter.join(timeout=1)
        self.assertFalse(waiter.is_alive())
        with self.client.operation("a verificação da conta"):
            self.assertEqual(self.client.active_operation, "a verificação da conta")
        self.assertEqual(self.client.active_operation, "")

    def test_database_lock_error_has_recovery_guidance(self):
        raw = "Current database is used by another process, please terminate it first"
        self.assertTrue(is_database_in_use_error(raw))
        message = friendly_tdl_error(raw)
        self.assertIn("tdl.exe", message)
        self.assertIn("reinicie o Windows", message)

    def test_build_message_and_user_export_commands(self):
        messages = self.client.build_message_export_command(
            "1173420740",
            Path(self.temporary.name) / "mensagens.json",
            topic_id="42",
            scope="last",
            scope_value="50",
            include_non_media=True,
            with_content=True,
            filter_expression="Views > 10",
        )
        self.assertIn("export", messages)
        self.assertIn("--topic", messages)
        self.assertIn("--all", messages)
        self.assertIn("--with-content", messages)
        self.assertIn("Views > 10", messages)

        users = self.client.build_user_export_command(
            "1173420740", Path(self.temporary.name) / "membros.json", raw=True
        )
        self.assertIn("users", users)
        self.assertIn("--raw", users)

    def test_build_upload_command_uses_literal_caption_and_topic(self):
        upload_file = Path(self.temporary.name) / "vídeo teste.mkv"
        upload_file.write_bytes(b"test")
        command = self.client.build_upload_command(
            [upload_file],
            chat_id="1173420740",
            topic_id="42",
            caption='Texto com "aspas"',
            exclude_extensions=".txt, .nfo",
        )
        self.assertIn("upload", command)
        self.assertEqual(command[command.index("--caption") + 1], '"Texto com \\"aspas\\""')
        self.assertEqual(command[command.index("--topic") + 1], "42")
        self.assertEqual(command[command.index("-e") + 1], "txt,nfo")

    def test_album_payload_preserves_chat_type_and_username(self):
        upload_file = Path(self.temporary.name) / "episódio 01.mkv"
        upload_file.write_bytes(b"test")
        task_directory = Path(self.temporary.name) / "album-tasks"
        with patch("mldtools_media.tdl_client.TASK_WORK_DIR", task_directory):
            command = self.client.build_album_upload_command(
                [upload_file],
                chat_id="1896946597",
                chat_type="channel",
                chat_username="plexbkp",
            )

        config_path = Path(command[-1])
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        config_path.unlink()
        self.assertEqual(payload["chat_id"], "1896946597")
        self.assertEqual(payload["chat_type"], "channel")
        self.assertEqual(payload["chat_username"], "plexbkp")
        self.assertEqual(payload["parallel_uploads"], 4)

    def test_persistent_upload_task_rebuilds_tdl_command(self):
        upload_file = Path(self.temporary.name) / "episódio.mkv"
        upload_file.write_bytes(b"test")
        task = DownloadTask(
            title="Upload",
            source_type="upload",
            source={
                "paths": [str(upload_file)],
                "chat_id": "1173420740",
                "chat_type": "channel",
                "chat_username": "teste",
                "topic_id": "42",
            },
            destination="Canal / Tópico",
            options={
                "caption": "Legenda",
                "group_albums": False,
                "as_photo": False,
            },
            operation_type="upload",
        )

        command = self.client.build_upload_task_command(task)

        self.assertIn("upload", command)
        self.assertEqual(command[command.index("-c") + 1], "1173420740")
        self.assertEqual(command[command.index("--topic") + 1], "42")

    def test_legacy_upload_record_requires_destination_selection(self):
        upload_file = Path(self.temporary.name) / "episódio.mkv"
        upload_file.write_bytes(b"test")
        task = DownloadTask(
            title="Upload antigo",
            source_type="upload",
            source={"paths": [str(upload_file)]},
            destination="Destino antigo",
            options={},
            operation_type="upload",
        )

        with self.assertRaisesRegex(ValueError, "versão anterior"):
            self.client.validate_upload_task(task)


if __name__ == "__main__":
    unittest.main()
