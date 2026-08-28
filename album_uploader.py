from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

try:
    import cryptg as _cryptg

    CRYPTG_AVAILABLE = True
except ImportError:
    _cryptg = None
    CRYPTG_AVAILABLE = False

from telethon import TelegramClient
from telethon.sessions import SQLiteSession

from config_utils import BASE_DIR, carregar_config_app, ler_env, resolver_session_path


ALBUM_LIMIT = 10


class UploadCancelledError(RuntimeError):
    pass


def natural_key(value: str | Path) -> list[object]:
    return [int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", str(value))]


def normalise_extension_set(value: str | Iterable[str]) -> set[str]:
    if isinstance(value, str):
        pieces = re.split(r"[,;\s]+", value)
    else:
        pieces = list(value)
    return {
        f".{str(piece).strip().lstrip('.').casefold()}"
        for piece in pieces
        if str(piece).strip().lstrip(".")
    }


def _allowed(path: Path, include: set[str], exclude: set[str]) -> bool:
    extension = path.suffix.casefold()
    if include and extension not in include:
        return False
    return not (exclude and extension in exclude)


def _files_in_tree(root: Path, include: set[str], exclude: set[str]) -> list[Path]:
    return sorted(
        (path for path in root.rglob("*") if path.is_file() and _allowed(path, include, exclude)),
        key=natural_key,
    )


def build_album_groups(
    paths: Sequence[str | Path],
    *,
    mode: str = "selection",
    include_extensions: str = "",
    exclude_extensions: str = "",
) -> list[list[Path]]:
    include = normalise_extension_set(include_extensions)
    exclude = normalise_extension_set(exclude_extensions)
    if include and exclude:
        raise ValueError("Use somente a lista de incluir ou a lista de excluir extensões")

    sources = [Path(value).expanduser().resolve() for value in paths]
    missing = [str(path) for path in sources if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Arquivo ou pasta não encontrado: {missing[0]}")

    groups: list[list[Path]] = []
    if mode == "folder":
        loose_files: list[Path] = []
        for source in sources:
            if source.is_file():
                if _allowed(source, include, exclude):
                    loose_files.append(source)
                continue
            directories = [source] + sorted(
                (path for path in source.rglob("*") if path.is_dir()), key=natural_key
            )
            for directory in directories:
                files = sorted(
                    (
                        path
                        for path in directory.iterdir()
                        if path.is_file() and _allowed(path, include, exclude)
                    ),
                    key=natural_key,
                )
                if files:
                    groups.append(files)
        if loose_files:
            groups.insert(0, loose_files)
    else:
        files: list[Path] = []
        for source in sources:
            if source.is_file():
                if _allowed(source, include, exclude):
                    files.append(source)
            else:
                files.extend(_files_in_tree(source, include, exclude))
        if files:
            groups.append(sorted(files, key=natural_key))

    return [group for group in groups if group]


def chunk_groups(groups: Sequence[Sequence[Path]], size: int = ALBUM_LIMIT) -> list[list[Path]]:
    return [
        list(group[index : index + size])
        for group in groups
        for index in range(0, len(group), size)
    ]


def clone_authorized_session(source_name: str | Path, destination_name: str | Path) -> str:
    source = SQLiteSession(str(source_name))
    destination = SQLiteSession(str(destination_name))
    try:
        if source.auth_key is None:
            raise RuntimeError(
                "A sessão principal do MLD Tools ainda não está autenticada. "
                "Conecte a conta na área Telegram antes de enviar álbuns."
            )
        source_key = getattr(source.auth_key, "key", None)
        destination_key = getattr(destination.auth_key, "key", None)
        if destination.auth_key is None or destination_key != source_key:
            destination.set_dc(source.dc_id, source.server_address, source.port)
            destination.auth_key = source.auth_key
            destination.save()
        return str(destination_name)
    finally:
        source.close()
        destination.close()


def _emit(message: str) -> None:
    print(message, flush=True)


def _cancel_path(config: dict[str, object]) -> Path | None:
    value = str(config.get("_cancel_file", "")).strip()
    return Path(value) if value else None


def ensure_upload_not_cancelled(cancel_path: Path | None) -> None:
    if cancel_path is not None and cancel_path.exists():
        raise UploadCancelledError("Upload cancelado pelo usuário.")


def format_transfer_speed(bytes_per_second: float) -> str:
    speed = max(0.0, float(bytes_per_second)) / 1024.0
    unit = "KiB/s"
    for candidate in ("MiB/s", "GiB/s"):
        if speed < 1024.0:
            break
        speed /= 1024.0
        unit = candidate
    return f"{speed:.1f} {unit}"


async def upload_document_batch(
    client: TelegramClient,
    paths: Sequence[Path],
    *,
    parallelism: int,
    cancel_path: Path | None = None,
    progress_callback: Callable[[float, float], None] | None = None,
) -> list[Any]:
    """Pre-upload documents concurrently while preserving album order."""
    files = [Path(path) for path in paths]
    if not files:
        return []
    limit = max(1, min(int(parallelism), len(files)))
    semaphore = asyncio.Semaphore(limit)
    sizes = [max(0, path.stat().st_size) for path in files]
    current = [0.0] * len(files)
    total_size = float(sum(sizes))

    def report() -> None:
        if progress_callback is not None:
            progress_callback(sum(current), total_size)

    async def upload_one(index: int, path: Path) -> Any:
        async with semaphore:
            ensure_upload_not_cancelled(cancel_path)

            def progress(uploaded: float, _total: float) -> None:
                ensure_upload_not_cancelled(cancel_path)
                expected = float(sizes[index])
                current[index] = min(expected, max(0.0, float(uploaded)))
                report()

            handle = await client.upload_file(
                str(path),
                part_size_kb=512,
                file_name=path.name,
                progress_callback=progress,
            )
            current[index] = float(sizes[index])
            report()
            return handle

    tasks = [
        asyncio.create_task(upload_one(index, path))
        for index, path in enumerate(files)
    ]
    try:
        return list(await asyncio.gather(*tasks))
    except BaseException:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise


def telegram_chat_reference(chat_id: str, chat_type: str = "") -> int | str:
    """Convert a tdl chat ID into the marked ID expected by Telethon.

    tdl reports the raw positive identifier for channels and groups. Telethon
    uses Bot API-style marked IDs to distinguish those peers from users.
    """
    value = str(chat_id).strip()
    if not value:
        return "me"
    if not re.fullmatch(r"-?\d+", value):
        return value

    number = int(value)
    peer_type = str(chat_type).strip().casefold()
    if peer_type in {"channel", "supergroup", "megagroup"}:
        if str(number).startswith("-100"):
            return number
        return int(f"-100{abs(number)}")
    if peer_type in {"group", "basicgroup", "basic_group"}:
        return -abs(number)
    if peer_type in {"private", "user", "bot"}:
        return abs(number)
    return number


def destination_candidates(
    chat_id: str,
    *,
    chat_type: str = "",
    chat_username: str = "",
) -> list[int | str]:
    candidates: list[int | str] = []
    username = str(chat_username).strip()
    if username and username != "-":
        candidates.append(f"@{username.lstrip('@')}")

    reference = telegram_chat_reference(chat_id, chat_type)
    if reference not in candidates:
        candidates.append(reference)
    return candidates


async def resolve_upload_entity(
    client: TelegramClient,
    chat_id: str,
    *,
    chat_type: str = "",
    chat_username: str = "",
):
    """Resolve a destination, refreshing Telethon's entity cache on demand."""
    candidates = destination_candidates(
        chat_id,
        chat_type=chat_type,
        chat_username=chat_username,
    )
    for candidate in candidates:
        try:
            return await client.get_input_entity(candidate)
        except ValueError:
            continue

    _emit("Localizando destino na conta do Telegram…")
    await client.get_dialogs(limit=None)
    for candidate in candidates:
        try:
            return await client.get_input_entity(candidate)
        except ValueError:
            continue

    raise RuntimeError(
        "O destino não foi encontrado na sessão usada para enviar álbuns. "
        "Confirme que a conta conectada na tela principal Telegram é a mesma "
        "conta da Central de mídia e que ela participa da conversa selecionada."
    )


async def upload_albums(config: dict[str, object]) -> None:
    cancel_path = _cancel_path(config)
    ensure_upload_not_cancelled(cancel_path)
    env = ler_env()
    app_config = carregar_config_app()
    api_id = str(env.get("API_ID", "")).strip()
    api_hash = str(env.get("API_HASH", "")).strip()
    if not api_id or not api_hash:
        raise RuntimeError("Configure API ID e API Hash na área Telegram do MLD Tools")

    base_session = resolver_session_path(app_config.get("session_file", "user_session"))
    worker_session = BASE_DIR / "mldtools_upload"
    session_name = clone_authorized_session(base_session, worker_session)

    paths = config.get("paths", [])
    if not isinstance(paths, list) or not paths:
        raise ValueError("Selecione pelo menos um arquivo ou pasta")
    groups = build_album_groups(
        [str(value) for value in paths],
        mode=str(config.get("album_mode", "selection")),
        include_extensions=str(config.get("include_extensions", "")),
        exclude_extensions=str(config.get("exclude_extensions", "")),
    )
    batches = chunk_groups(groups)
    if not batches:
        raise ValueError("Nenhum arquivo corresponde aos filtros informados")

    chat_id = str(config.get("chat_id", "")).strip()
    chat_type = str(config.get("chat_type", "")).strip()
    chat_username = str(config.get("chat_username", "")).strip()
    topic_id = str(config.get("topic_id", "")).strip()
    reply_to = int(topic_id) if topic_id else None
    caption = str(config.get("caption", ""))
    as_photo = bool(config.get("as_photo", False))
    parallel_uploads = max(1, min(int(config.get("parallel_uploads", 1)), ALBUM_LIMIT))
    total_files = sum(len(batch) for batch in batches)
    completed_files = 0
    total_bytes = sum(path.stat().st_size for batch in batches for path in batch)
    completed_bytes = 0
    upload_started_at = time.monotonic()
    last_progress_at = 0.0
    last_progress_percent = -1.0

    def emit_progress(percent: float, speed: str = "", *, force: bool = False) -> None:
        nonlocal last_progress_at, last_progress_percent
        value = min(100.0, max(0.0, float(percent)))
        now = time.monotonic()
        if (
            not force
            and value < 100.0
            and now - last_progress_at < 0.25
            and value - last_progress_percent < 0.2
        ):
            return
        suffix = f" {speed}" if speed else ""
        _emit(f"PROGRESS {value:.1f}%{suffix}")
        last_progress_at = now
        last_progress_percent = value

    client = TelegramClient(session_name, int(api_id), api_hash)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError(
                "A sessão de upload não está autorizada. Reconecte a conta Telegram no MLD Tools."
            )
        ensure_upload_not_cancelled(cancel_path)
        entity = await resolve_upload_entity(
            client,
            chat_id,
            chat_type=chat_type,
            chat_username=chat_username,
        )
        if CRYPTG_AVAILABLE:
            _emit("Aceleração criptográfica ativa (cryptg).")
        else:
            _emit("Aceleração criptográfica indisponível; usando o modo Python.")
        if not as_photo and parallel_uploads > 1:
            _emit(f"Pré-upload paralelo: até {parallel_uploads} arquivos por álbum.")

        for album_index, batch in enumerate(batches, start=1):
            ensure_upload_not_cancelled(cancel_path)
            _emit(
                f"Enviando álbum {album_index}/{len(batches)} "
                f"({len(batch)} arquivo(s))…"
            )
            captions = [caption] + [""] * (len(batch) - 1)
            if as_photo:
                def progress(current: float, total: float) -> None:
                    ensure_upload_not_cancelled(cancel_path)
                    fraction = (float(current) / float(total)) if total else 0.0
                    percent = (
                        (completed_files + fraction * len(batch)) / total_files
                    ) * 100.0
                    emit_progress(percent)

                await client.send_file(
                    entity,
                    [str(path) for path in batch],
                    caption=captions,
                    force_document=False,
                    reply_to=reply_to,
                    progress_callback=progress,
                )
            else:
                batch_bytes = sum(path.stat().st_size for path in batch)
                batch_base = completed_bytes

                def byte_progress(current: float, _total: float) -> None:
                    ensure_upload_not_cancelled(cancel_path)
                    uploaded = min(float(total_bytes), batch_base + float(current))
                    percent = (uploaded / total_bytes * 100.0) if total_bytes else 0.0
                    elapsed = max(0.001, time.monotonic() - upload_started_at)
                    speed = format_transfer_speed(uploaded / elapsed)
                    emit_progress(percent, speed)

                handles = await upload_document_batch(
                    client,
                    batch,
                    parallelism=parallel_uploads,
                    cancel_path=cancel_path,
                    progress_callback=byte_progress,
                )
                ensure_upload_not_cancelled(cancel_path)
                await client.send_file(
                    entity,
                    handles,
                    caption=captions,
                    force_document=True,
                    reply_to=reply_to,
                )
                completed_bytes += batch_bytes
            completed_files += len(batch)
            emit_progress(
                (completed_files / total_files) * 100.0,
                force=True,
            )
    finally:
        await client.disconnect()

    _emit(f"Upload concluído: {total_files} arquivo(s) em {len(batches)} álbum(ns).")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Uploader de álbuns do MLD Tools")
    parser.add_argument("--config", required=True, help="Arquivo JSON temporário da tarefa")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    config_path = Path(args.config).expanduser().resolve()
    cancel_path = config_path.with_suffix(config_path.suffix + ".cancel")
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            raise ValueError("Configuração de upload inválida")
        config["_cancel_file"] = str(cancel_path)
        asyncio.run(upload_albums(config))
        return 0
    except UploadCancelledError as exc:
        _emit(str(exc))
        return 2
    except Exception as exc:
        _emit(f"ERRO: {exc}")
        return 1
    finally:
        config_path.unlink(missing_ok=True)
        cancel_path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
