import tempfile
import unittest
from pathlib import Path

from mldtools_media.models import DownloadTask
from mldtools_media.task_store import TaskStore


class TaskStoreTests(unittest.TestCase):
    def make_task(self) -> DownloadTask:
        return DownloadTask(
            title="Teste",
            source_type="links",
            source={"links": ["https://t.me/telegram/1"]},
            destination="C:/Downloads",
            options={},
        )

    def test_add_update_and_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tasks.json"
            store = TaskStore(path)
            task = store.add(self.make_task())
            store.update(task.id, status="running", progress=20.0)
            reloaded = TaskStore(path).get(task.id)
            self.assertIsNotNone(reloaded)
            self.assertEqual(reloaded.status, "paused")
            self.assertTrue(reloaded.resume_mode)

    def test_remove_finished_keeps_failed_tasks(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tasks.json"
            store = TaskStore(path)
            completed = store.add(self.make_task())
            failed = self.make_task()
            failed.title = "Falha"
            store.add(failed)
            store.update(completed.id, status="completed")
            store.update(failed.id, status="failed")
            self.assertEqual(store.remove_finished(), 1)
            self.assertIsNotNone(store.get(failed.id))

    def test_interrupted_queued_upload_becomes_paused_and_restarts_from_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tasks.json"
            store = TaskStore(path)
            upload = self.make_task()
            upload.operation_type = "upload"
            upload.source_type = "upload"
            upload.source = {"paths": ["C:/video.mkv"], "chat_id": ""}
            upload.status = "running"
            store.add(upload)

            reloaded = TaskStore(path).get(upload.id)

            self.assertIsNotNone(reloaded)
            self.assertEqual(reloaded.operation_type, "upload")
            self.assertEqual(reloaded.status, "paused")
            self.assertFalse(reloaded.resume_mode)
            self.assertFalse(reloaded.finished_at)

    def test_legacy_interrupted_upload_without_destination_is_cancelled(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tasks.json"
            store = TaskStore(path)
            upload = self.make_task()
            upload.operation_type = "upload"
            upload.source_type = "upload"
            upload.status = "running"
            store.add(upload)

            reloaded = TaskStore(path).get(upload.id)

            self.assertEqual(reloaded.status, "cancelled")
            self.assertTrue(reloaded.finished_at)

    def test_upload_record_is_returned_by_shared_queue(self):
        with tempfile.TemporaryDirectory() as directory:
            store = TaskStore(Path(directory) / "tasks.json")
            upload = self.make_task()
            upload.operation_type = "upload"
            upload.source_type = "upload"
            store.add(upload)

            queued = store.next_queued()

            self.assertIsNotNone(queued)
            self.assertEqual(queued.id, upload.id)


if __name__ == "__main__":
    unittest.main()
