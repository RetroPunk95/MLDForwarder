"""Regressões offline com os tipos e erros reais do Telethon 1.40.0.

Não conecta ao Telegram nem usa credenciais. Execute python -m unittest discover -s tests -v.
"""

import asyncio
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app/src/main/python"))

import mobile_engine as engine
from delivery_state import DeliveryJournal, DeliveryStorageError
from telethon.errors import (
    ChatWriteForbiddenError, DocumentInvalidError, FileReferenceExpiredError,
    FloodWaitError, MediaCaptionTooLongError,
)
from telethon.tl.types import (
    MessageEntityBold, MessageEntityBlockquote, MessageEntityCustomEmoji,
    MessageMediaPhoto, PhotoEmpty, MessageMediaWebPage, WebPageEmpty,
)


def message(mid, text="🍿 CUBO\nSinopse", entities=None, album=None, photo_id=None):
    return SimpleNamespace(
        id=mid, message=text, entities=entities or [], grouped_id=album,
        media=MessageMediaPhoto(photo=PhotoEmpty(id=photo_id or mid)),
    )


def styled_message(mid, album=None):
    return message(mid, entities=[
        MessageEntityCustomEmoji(0, 2, 123456),
        MessageEntityBold(3, 4), MessageEntityBlockquote(8, 7, collapsed=True),
    ], album=album)


class Listener:
    def __init__(self):
        self.logs = []

    def onLog(self, text):
        self.logs.append(text)


class Client:
    def __init__(self, messages=(), account=7):
        self.messages = {m.id: m for m in messages}
        self.sources = {}
        self.account = account
        self.calls = []
        self.sent = []
        self.gets = []
        self.file_hook = None
        self.text_hook = None
        self.disconnected = False
        self.after_iter = None

    async def connect(self):
        pass

    async def disconnect(self):
        self.disconnected = True

    async def is_user_authorized(self):
        return True

    async def get_me(self):
        return SimpleNamespace(id=self.account)

    async def get_messages(self, source, ids=None, **kwargs):
        self.gets.append((source, ids))
        items = self.sources.get(source, self.messages)
        if ids is not None:
            return [items.get(i) for i in ids]
        return sorted(items.values(), key=lambda m: m.id, reverse=True)[:kwargs.get("limit", 1)]

    async def iter_messages(self, source, **kwargs):
        items = self.sources.get(source, self.messages)
        items = [m for m in items.values() if m.id > kwargs.get("min_id", 0)]
        items.sort(key=lambda m: m.id, reverse=not kwargs.get("reverse", False))
        for item in items[:kwargs.get("limit", 100)]:
            yield item
        if self.after_iter:
            self.after_iter()

    async def send_file(self, target, files, **kwargs):
        self.calls.append(("file", target, files, copy.deepcopy(kwargs)))
        if self.file_hook:
            self.file_hook(target, files, kwargs)
        self.sent.append(self.calls[-1])
        return SimpleNamespace(id=1000 + len(self.sent))

    async def send_message(self, target, text, **kwargs):
        self.calls.append(("text", target, text, copy.deepcopy(kwargs)))
        if self.text_hook:
            self.text_hook(target, text, kwargs)
        self.sent.append(self.calls[-1])
        return SimpleNamespace(id=1000 + len(self.sent))


class DeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cfg = {"files_dir": self.root}
        self.route = engine._route({"name": "Teste", "source": "-1001", "target": "-1002", "target_topic": 55})
        self.client = Client()
        self.listener = Listener()
        self.progress = {}
        self.progress_path = self.root / "retro_progress.json"
        await engine._setup_delivery(self.client, self.cfg, "retro")

    async def send(self, msg, kind="message"):
        items = msg if isinstance(msg, list) else [msg]
        self.client.messages.update({m.id: m for m in items})
        return await engine._send_group_with_retry(self.client, self.cfg, self.route, kind, items, self.listener)

    async def batch(self, messages):
        self.client.messages.update({m.id: m for m in messages})
        await engine._process_batch(self.client, self.cfg, self.route, messages, self.listener, self.progress, self.progress_path)

    def entries(self):
        return list(self.cfg["_delivery"].entries.values())

    async def restart(self):
        await engine._setup_delivery(self.client, self.cfg, "retro")

    async def test_photo_custom_emoji_fallback_preserves_styles_and_unicode(self):
        msg = styled_message(28843)
        def reject_custom(target, files, kw):
            if any(isinstance(e, MessageEntityCustomEmoji) for e in kw["formatting_entities"]):
                raise DocumentInvalidError(None)
        self.client.file_hook = reject_custom
        self.assertTrue(await self.send(msg))
        self.assertEqual(len(self.client.calls), 3)
        sent = self.client.sent[0]
        self.assertIs(sent[2], msg.media)
        self.assertEqual(sent[3]["caption"], msg.message)
        self.assertEqual(sent[3]["reply_to"], 55)
        self.assertEqual([type(e) for e in sent[3]["formatting_entities"]], [MessageEntityBold, MessageEntityBlockquote])
        self.assertIsInstance(msg.entities[0], MessageEntityCustomEmoji)
        self.assertEqual(self.entries()[0]["status"], "sent")

    async def test_refresh_reference_without_simplifying_entities(self):
        original = styled_message(1)
        refreshed = styled_message(1)
        refreshed.media = MessageMediaPhoto(photo=PhotoEmpty(id=999))
        self.client.messages[1] = refreshed
        def stale(target, files, kw):
            if files.photo.id != 999:
                raise FileReferenceExpiredError(None)
        self.client.file_hook = stale
        await engine._send_group_with_retry(self.client, self.cfg, self.route, "message", [original], self.listener)
        self.assertEqual(len(self.client.sent), 1)
        self.assertEqual(len(self.client.sent[0][3]["formatting_entities"]), 3)

    async def test_permanent_error_saved_before_cursor_and_next_message_delivered(self):
        def reject_one(target, files, kw):
            if files.photo.id == 10:
                raise DocumentInvalidError(None)
        self.client.file_hook = reject_one
        await self.batch([message(10), message(11)])
        self.assertEqual(self.progress[engine._route_key(self.route)], 11)
        self.assertEqual(self.entries()[0]["ids"], [10])
        self.assertEqual(self.entries()[0]["status"], "pending")
        self.assertEqual(len(self.client.sent), 1)
        self.assertFalse(any("IDs 10: ✓" in line for line in self.listener.logs))
        disk = json.loads(self.cfg["_delivery"].path.read_text())
        self.assertEqual(len(disk["entries"]), 1)

    async def test_pending_retried_after_restart_without_rewinding_cursor(self):
        self.client.file_hook = lambda *args: (_ for _ in ()).throw(DocumentInvalidError(None))
        await self.batch([message(10)])
        self.client.file_hook = None
        await self.restart()
        await engine._retry_pending(self.client, self.cfg, self.route, self.listener, 10)
        self.assertEqual(self.entries(), [])
        self.assertEqual(self.progress[engine._route_key(self.route)], 10)
        self.assertEqual(len(self.client.sent), 1)

    async def test_album_fallback_keeps_group_and_each_caption(self):
        items = [styled_message(10, album=1), styled_message(11, album=1)]
        def reject_custom(target, files, kw):
            if any(isinstance(e, MessageEntityCustomEmoji) for ents in kw["formatting_entities"] for e in ents):
                raise DocumentInvalidError(None)
        self.client.file_hook = reject_custom
        await self.send(items, "album")
        self.assertEqual(len(self.client.sent), 1)
        self.assertEqual(len(self.client.sent[0][2]), 2)
        self.assertEqual(self.client.sent[0][3]["caption"], [m.message for m in items])
        self.assertEqual(self.client.sent[0][3]["reply_to"], 55)

    async def test_long_caption_resume_does_not_resend_photo(self):
        def long_caption(target, files, kw):
            if kw.get("caption"):
                raise MediaCaptionTooLongError(None)
        self.client.file_hook = long_caption
        self.client.text_hook = lambda *args: (_ for _ in ()).throw(DocumentInvalidError(None))
        await self.batch([message(10, text="a" * 1300)])
        self.assertEqual([s[0] for s in self.client.sent], ["file"])
        self.assertEqual(self.entries()[0]["status"], "pending")
        self.client.text_hook = None
        await self.restart()
        await engine._retry_pending(self.client, self.cfg, self.route, self.listener, 10)
        self.assertEqual([s[0] for s in self.client.sent], ["file", "text"])
        self.assertEqual(self.entries(), [])

    async def test_album_partial_caption_resumes_only_unconfirmed_text(self):
        def long_caption(target, files, kw):
            if any(kw.get("caption", [])):
                raise MediaCaptionTooLongError(None)
        self.client.file_hook = long_caption
        def fail_second(target, text, kw):
            if text == "segunda":
                raise DocumentInvalidError(None)
        self.client.text_hook = fail_second
        await self.batch([message(10, "primeira", album=5), message(11, "segunda", album=5)])
        self.assertEqual([s[0] for s in self.client.sent], ["file", "text"])
        self.client.text_hook = None
        await self.restart()
        await engine._retry_pending(self.client, self.cfg, self.route, self.listener, 11)
        self.assertEqual([s[0] for s in self.client.sent], ["file", "text", "text"])
        self.assertEqual([s[2] for s in self.client.sent if s[0] == "text"], ["primeira", "segunda"])

    async def test_floodwait_retries_only_current_operation(self):
        def flood_once(*args):
            if len(self.client.calls) == 1:
                raise FloodWaitError(None, capture=3)
        self.client.file_hook = flood_once
        with patch.object(engine, "_sleep", return_value=True) as sleep:
            await self.send(message(1))
        sleep.assert_awaited_once_with(self.cfg, 3)
        self.assertEqual(len(self.client.sent), 1)

    async def test_stop_during_flood_does_not_advance_cursor(self):
        self.client.file_hook = lambda *args: (_ for _ in ()).throw(FloodWaitError(None, capture=5))
        with patch.object(engine, "_sleep", return_value=False):
            await self.batch([message(1), message(2)])
        self.assertEqual(self.progress, {})
        self.assertEqual(self.entries()[0]["status"], "pending")
        self.assertEqual(len(self.client.calls), 1)

    async def test_timeout_not_blindly_retried_after_restart(self):
        self.client.file_hook = lambda *args: (_ for _ in ()).throw(TimeoutError("uncertain"))
        with self.assertRaises(TimeoutError):
            await self.batch([message(1)])
        self.assertEqual(self.entries()[0]["status"], "review")
        self.assertEqual(self.progress, {})
        self.client.file_hook = None
        await self.restart()
        await self.batch([message(1), message(2)])
        self.assertEqual(len(self.client.calls), 2)  # failed 1, sent 2; no retry of 1
        self.assertEqual(self.client.sent[0][2].photo.id, 2)
        self.assertEqual(self.entries()[0]["ids"], [1])

    async def test_journal_corruption_fails_closed(self):
        self.cfg["_delivery"].path.write_text("{broken", encoding="utf-8")
        with self.assertRaises(DeliveryStorageError):
            await self.restart()
        self.assertEqual(self.cfg["_delivery"].path.read_text(), "{broken")

    async def test_disk_failure_prevents_sending(self):
        with patch.object(DeliveryJournal, "save", side_effect=DeliveryStorageError("disk full")):
            with self.assertRaises(DeliveryStorageError):
                await self.send(message(1))
        self.assertEqual(self.client.calls, [])

    async def test_progress_write_failure_keeps_receipt_to_prevent_duplicate(self):
        with patch.object(engine, "_save_progress", side_effect=DeliveryStorageError("disk full")):
            with self.assertRaises(DeliveryStorageError):
                await self.batch([message(1)])
        self.assertEqual(self.entries()[0]["status"], "sent")
        await self.restart()
        await self.batch([message(1)])
        self.assertEqual(len(self.client.sent), 1)
        self.assertEqual(self.entries(), [])

    async def test_missing_source_stays_pending(self):
        self.client.file_hook = lambda *args: (_ for _ in ()).throw(DocumentInvalidError(None))
        await self.batch([message(1)])
        self.client.messages.clear()
        await self.restart()
        await engine._retry_pending(self.client, self.cfg, self.route, self.listener, 1)
        self.assertEqual(self.entries()[0]["status"], "pending")
        self.assertIn("indisponíveis", self.entries()[0]["error"])

    async def test_permissions_are_not_skipped_as_invalid_media(self):
        self.client.file_hook = lambda *args: (_ for _ in ()).throw(ChatWriteForbiddenError(None))
        with self.assertRaises(ChatWriteForbiddenError):
            await self.batch([message(1), message(2)])
        self.assertEqual(self.progress, {})
        self.assertEqual(len(self.client.calls), 1)
        self.assertIsNone(self.entries()[0]["in_flight"])

    async def test_plain_text_custom_emoji_compatibility(self):
        item = styled_message(1)
        item.media = None
        def reject_custom(target, text, kw):
            if any(isinstance(e, MessageEntityCustomEmoji) for e in kw["formatting_entities"]):
                raise DocumentInvalidError(None)
        self.client.text_hook = reject_custom
        await self.send(item)
        self.assertEqual(len(self.client.calls), 2)
        self.assertEqual(len(self.client.sent[0][3]["formatting_entities"]), 2)

    async def test_pending_account_and_mode_isolation(self):
        self.client.file_hook = lambda *args: (_ for _ in ()).throw(DocumentInvalidError(None))
        await self.batch([message(1)])
        original_path = self.cfg["_delivery"].path
        self.client.account = 8
        await self.restart()
        self.assertEqual(self.entries(), [])
        self.assertNotEqual(original_path, self.cfg["_delivery"].path)
        await engine._setup_delivery(self.client, self.cfg, "normal")
        self.assertIn("normal_delivery_8", str(self.cfg["_delivery"].path))

    async def test_edited_partial_source_requires_review(self):
        self.client.file_hook = lambda target, files, kw: (
            (_ for _ in ()).throw(MediaCaptionTooLongError(None)) if kw.get("caption") else None
        )
        self.client.text_hook = lambda *args: (_ for _ in ()).throw(DocumentInvalidError(None))
        await self.batch([message(1, "texto original")])
        self.client.messages[1].message = "texto editado"
        before = len(self.client.calls)
        await self.restart()
        await engine._retry_pending(self.client, self.cfg, self.route, self.listener, 1)
        self.assertEqual(self.entries()[0]["status"], "review")
        self.assertEqual(len(self.client.calls), before)

    async def test_pending_attempt_not_repeated_when_encountered_in_batch(self):
        self.client.file_hook = lambda *args: (_ for _ in ()).throw(DocumentInvalidError(None))
        await self.send(message(1))  # pending before cursor checkpoint
        await self.restart()
        await engine._retry_pending(self.client, self.cfg, self.route, self.listener, 0)
        before = len(self.client.calls)
        await self.batch([message(1)])
        self.assertEqual(len(self.client.calls), before)
        self.assertEqual(self.progress[engine._route_key(self.route)], 1)

    async def test_journal_inflight_after_crash_requires_review(self):
        entry = self.cfg["_delivery"].begin(self.route, "message", [message(1)])
        self.cfg["_delivery"].update(entry, in_flight="media")
        await self.restart()
        await self.send(message(1))
        self.assertEqual(self.client.calls, [])
        self.assertEqual(self.entries()[0]["status"], "review")

    async def test_collect_order_limit_and_album_completion(self):
        self.client.messages = {m.id: m for m in [message(1), message(2, album=8), message(3, album=8), message(4)]}
        collected = await engine._collect(self.client, self.route, 1, 1)
        self.assertEqual([m.id for m in collected], [2, 3])
        self.assertEqual(engine._route({"source": 1, "target": 2, "retro_limit": 0})["retro_limit"], 1)

    async def test_stop_during_collection(self):
        self.client.messages = {1: message(1)}
        engine.request_stop(str(self.root))
        with self.assertRaises(engine.DeliveryStopped):
            await engine._collect_with_retry(self.client, self.cfg, self.route, 0, 100, self.listener)

    async def test_flood_while_collecting_retries_before_any_send(self):
        self.client.messages = {1: message(1)}
        original = engine._collect
        calls = 0
        async def collect(*args):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise FloodWaitError(None, capture=2)
            return await original(*args)
        with patch.object(engine, "_collect", side_effect=collect), patch.object(engine, "_sleep", return_value=True):
            items = await engine._collect_with_retry(self.client, self.cfg, self.route, 0, 100, self.listener)
        self.assertEqual([m.id for m in items], [1])
        self.assertEqual(self.client.sent, [])

    async def test_web_preview_uses_text_not_send_file(self):
        item = styled_message(1)
        item.media = MessageMediaWebPage(webpage=WebPageEmpty(id=10))
        await self.send(item)
        self.assertEqual(self.client.sent[0][0], "text")
        self.assertTrue(self.client.sent[0][3]["link_preview"])

    async def test_unsupported_document_preserves_non_emoji_formatting(self):
        item = message(1, entities=[MessageEntityBold(0, 2)])
        self.client.file_hook = lambda *args: (_ for _ in ()).throw(DocumentInvalidError(None))
        await self.send(item)
        self.assertEqual(len(self.client.calls), 2)
        self.assertTrue(all(len(c[3]["formatting_entities"]) == 1 for c in self.client.calls))
        self.assertEqual(self.entries()[0]["status"], "pending")

    async def test_pending_route_isolation(self):
        self.client.file_hook = lambda *args: (_ for _ in ()).throw(DocumentInvalidError(None))
        await self.batch([message(1)])
        before = len(self.client.calls)
        other = dict(self.route, target=-1003)
        await self.restart()
        await engine._retry_pending(self.client, self.cfg, other, self.listener, 1)
        self.assertEqual(len(self.client.calls), before)
        self.assertEqual(len(self.entries()), 1)

    async def test_receipt_cleanup_after_cursor_committed(self):
        await self.send(message(1))
        self.assertEqual(self.entries()[0]["status"], "sent")
        await self.restart()
        await engine._retry_pending(self.client, self.cfg, self.route, self.listener, 1)
        self.assertEqual(self.entries(), [])
        self.assertEqual(len(self.client.sent), 1)


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.listener = Listener()
        self.client = Client()
        self.routes = [engine._route({"name": f"Rota {i}", "source": i, "target": 99}) for i in (1, 2)]
        self.raw = json.dumps({"files_dir": str(self.root), "api_id": 1, "api_hash": "test", "routes": self.routes})

    def test_retro_bad_message_does_not_abort_route_or_following_routes(self):
        self.client.sources = {1: {1: message(1), 2: message(2)}, 2: {3: message(3)}}
        def reject_one(target, files, kw):
            if files.photo.id == 1:
                raise DocumentInvalidError(None)
        self.client.file_hook = reject_one
        with patch.object(engine, "_client", return_value=self.client):
            result = json.loads(engine.run_retro(self.raw, self.listener))
        self.assertTrue(result["ok"])
        self.assertTrue(self.client.disconnected)
        self.assertEqual([s[2].photo.id for s in self.client.sent], [2, 3])
        progress = json.loads((self.root / "retro_progress.json").read_text())
        self.assertEqual(progress[engine._route_key(self.routes[0])], 2)
        self.assertTrue(any("Pendências: 1" in s for s in self.listener.logs))

    def test_retro_permission_error_pauses_only_one_route(self):
        self.client.sources = {1: {1: message(1), 2: message(2)}, 2: {3: message(3)}}
        def reject_one(target, files, kw):
            if files.photo.id == 1:
                raise ChatWriteForbiddenError(None)
        self.client.file_hook = reject_one
        with patch.object(engine, "_client", return_value=self.client):
            engine.run_retro(self.raw, self.listener)
        self.assertEqual([s[2].photo.id for s in self.client.sent], [3])

    def test_existing_progress_resumes_forward_after_saved_id(self):
        self.client.sources = {1: {1: message(1), 2: message(2)}}
        (self.root / "retro_progress.json").write_text(json.dumps({engine._route_key(self.routes[0]): 1}))
        with patch.object(engine, "_client", return_value=self.client):
            engine.run_retro(self.raw, self.listener)
        self.assertEqual([s[2].photo.id for s in self.client.sent], [2])

    def test_concurrent_run_rejected_before_clearing_stop_flag(self):
        engine.request_stop(str(self.root))
        engine._SYNC_LOCK.acquire()
        try:
            result = json.loads(engine.run_retro(self.raw, self.listener))
        finally:
            engine._SYNC_LOCK.release()
        self.assertFalse(result["ok"])
        self.assertTrue((self.root / "sync_stop.flag").exists())

    def test_normal_permanent_media_error_keeps_next_message_and_other_routes(self):
        self.client.sources = {1: {1: message(1), 2: message(2)}, 2: {3: message(3)}}
        (self.root / "normal_progress.json").write_text(json.dumps({engine._route_key(r): 0 for r in self.routes}))
        def reject_one(target, files, kw):
            if files.photo.id == 1:
                raise DocumentInvalidError(None)
            if files.photo.id == 3:
                engine.request_stop(str(self.root))
        self.client.file_hook = reject_one
        with patch.object(engine, "_client", return_value=self.client):
            result = json.loads(engine.run_normal(self.raw, self.listener))
        self.assertTrue(result["ok"])
        self.assertEqual([s[2].photo.id for s in self.client.sent], [2, 3])
        self.assertTrue((self.root / "normal_delivery_7.json").exists())

    def test_normal_permission_error_does_not_busy_loop(self):
        self.client.sources = {1: {1: message(1)}, 2: {2: message(2)}}
        (self.root / "normal_progress.json").write_text(json.dumps({engine._route_key(r): 0 for r in self.routes}))
        self.client.file_hook = lambda *args: (_ for _ in ()).throw(ChatWriteForbiddenError(None))
        with patch.object(engine, "_client", return_value=self.client):
            engine.run_normal(self.raw, self.listener)
        self.assertEqual(len(self.client.calls), 2)
        self.assertTrue(self.client.disconnected)

    def test_second_retro_run_retries_only_old_pending_then_new_messages(self):
        self.client.sources = {1: {1: message(1), 2: message(2)}}
        def reject_one(target, files, kw):
            if files.photo.id == 1:
                raise DocumentInvalidError(None)
        self.client.file_hook = reject_one
        with patch.object(engine, "_client", return_value=self.client):
            engine.run_retro(self.raw, self.listener)
            self.client.file_hook = None
            self.client.sources[1][3] = message(3)
            engine.run_retro(self.raw, self.listener)
        self.assertEqual([s[2].photo.id for s in self.client.sent], [2, 1, 3])


if __name__ == "__main__":
    unittest.main()
