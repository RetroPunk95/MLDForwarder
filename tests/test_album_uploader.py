import asyncio
from pathlib import Path

import pytest

from album_uploader import (
    UploadCancelledError,
    build_album_groups,
    chunk_groups,
    destination_candidates,
    ensure_upload_not_cancelled,
    natural_key,
    resolve_upload_entity,
    telegram_chat_reference,
    upload_document_batch,
)


def test_natural_key_orders_numbered_files() -> None:
    values = ["10.jpg", "2.jpg", "01.jpg"]
    assert sorted(values, key=natural_key) == ["01.jpg", "2.jpg", "10.jpg"]


def test_selection_mode_groups_recursive_files(tmp_path: Path) -> None:
    folder = tmp_path / "temporada"
    folder.mkdir()
    (folder / "10.jpg").write_bytes(b"10")
    (folder / "2.jpg").write_bytes(b"2")
    (folder / "ignorar.txt").write_text("x", encoding="utf-8")

    groups = build_album_groups([folder], include_extensions="jpg")

    assert [[path.name for path in group] for group in groups] == [["2.jpg", "10.jpg"]]


def test_folder_mode_creates_one_group_per_directory(tmp_path: Path) -> None:
    root = tmp_path / "colecao"
    first = root / "album 1"
    second = root / "album 2"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    (first / "1.jpg").write_bytes(b"1")
    (second / "1.jpg").write_bytes(b"1")

    groups = build_album_groups([root], mode="folder")

    assert len(groups) == 2
    assert [group[0].parent.name for group in groups] == ["album 1", "album 2"]


def test_album_groups_are_split_at_telegram_limit(tmp_path: Path) -> None:
    files = []
    for index in range(23):
        path = tmp_path / f"{index:02}.jpg"
        path.write_bytes(b"x")
        files.append(path)

    assert [len(group) for group in chunk_groups([files])] == [10, 10, 3]


def test_tdl_channel_id_is_marked_for_telethon() -> None:
    assert telegram_chat_reference("1896946597", "channel") == -1001896946597
    assert telegram_chat_reference("1896946597", "group") == -1896946597
    assert telegram_chat_reference("1896946597", "private") == 1896946597
    assert telegram_chat_reference("-1001896946597", "channel") == -1001896946597


def test_username_is_preferred_over_numeric_destination() -> None:
    assert destination_candidates(
        "1896946597",
        chat_type="channel",
        chat_username="plexbkp",
    ) == ["@plexbkp", -1001896946597]


def test_entity_resolution_refreshes_dialog_cache_after_a_miss() -> None:
    class Client:
        def __init__(self) -> None:
            self.cache_ready = False
            self.dialog_refreshes = 0

        async def get_input_entity(self, candidate):
            if not self.cache_ready:
                raise ValueError("entity cache miss")
            return ("resolved", candidate)

        async def get_dialogs(self, *, limit):
            assert limit is None
            self.cache_ready = True
            self.dialog_refreshes += 1
            return []

    client = Client()
    result = asyncio.run(
        resolve_upload_entity(client, "1896946597", chat_type="channel")
    )

    assert result == ("resolved", -1001896946597)
    assert client.dialog_refreshes == 1


def test_album_upload_honours_cancel_signal(tmp_path: Path) -> None:
    cancel_file = tmp_path / "album-upload-test.json.cancel"
    ensure_upload_not_cancelled(cancel_file)
    cancel_file.touch()

    with pytest.raises(UploadCancelledError, match="cancelado pelo usuário"):
        ensure_upload_not_cancelled(cancel_file)


def test_document_batch_uploads_in_parallel_and_preserves_order(tmp_path: Path) -> None:
    files = []
    for index, size in enumerate((10, 20, 30)):
        path = tmp_path / f"{index}.mkv"
        path.write_bytes(b"x" * size)
        files.append(path)

    class Client:
        def __init__(self) -> None:
            self.active = 0
            self.maximum_active = 0

        async def upload_file(
            self,
            filename,
            *,
            part_size_kb,
            file_name,
            progress_callback,
        ):
            assert part_size_kb == 512
            self.active += 1
            self.maximum_active = max(self.maximum_active, self.active)
            size = Path(filename).stat().st_size
            progress_callback(size / 2, size)
            await asyncio.sleep(0.01 * (4 - int(Path(filename).stem)))
            progress_callback(size, size)
            self.active -= 1
            return f"handle:{file_name}"

    client = Client()
    progress = []
    handles = asyncio.run(
        upload_document_batch(
            client,
            files,
            parallelism=2,
            progress_callback=lambda current, total: progress.append((current, total)),
        )
    )

    assert client.maximum_active == 2
    assert handles == ["handle:0.mkv", "handle:1.mkv", "handle:2.mkv"]
    assert progress[-1] == (60.0, 60.0)
