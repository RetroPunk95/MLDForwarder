"""Motor Telethon do MLDForwarder Android.

A interface Java chama somente funções que retornam JSON. As sincronizações
longas recebem um objeto Java com ``onLog(str)`` e usam uma flag em disco para
parada cooperativa, retomada e encerramento seguro do serviço Android.
"""

import asyncio
import json
from pathlib import Path

from telethon import TelegramClient, utils
from telethon.errors import (
    FloodWaitError,
    MediaCaptionTooLongError,
    PasswordHashInvalidError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberInvalidError,
    SessionPasswordNeededError,
)
from telethon.tl.functions.channels import GetForumTopicsRequest
from telethon.tl.types import MessageMediaWebPage


def _result(**values):
    return json.dumps(values, ensure_ascii=False)


def _config(raw):
    data = json.loads(raw)
    files_dir = Path(data["files_dir"])
    files_dir.mkdir(parents=True, exist_ok=True)
    data["files_dir"] = files_dir
    data["api_id"] = int(data["api_id"])
    if not data.get("api_hash"):
        raise ValueError("API Hash não informado.")
    return data


def _peer(value):
    text = str(value).strip()
    if not text:
        raise ValueError("Origem ou destino vazio.")
    try:
        return int(text)
    except ValueError:
        return text


def _topic(value):
    if value in (None, "", 0, "0"):
        return None
    topic_id = int(value)
    if topic_id <= 0:
        raise ValueError("O ID do tópico precisa ser maior que zero.")
    return topic_id


def _client(cfg):
    session = cfg["files_dir"] / "mld_android_session"
    return TelegramClient(str(session), cfg["api_id"], cfg["api_hash"])


def _stop_file(files_dir):
    return Path(files_dir) / "sync_stop.flag"


def _stop_requested(cfg):
    return _stop_file(cfg["files_dir"]).exists()


def _clear_stop(cfg):
    _stop_file(cfg["files_dir"]).unlink(missing_ok=True)


def request_stop(files_dir):
    path = _stop_file(files_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("stop", encoding="utf-8")
    return _result(ok=True)


def _emit(listener, message):
    if listener is not None:
        listener.onLog(str(message))


async def _sleep(cfg, seconds):
    remaining = max(0, int(seconds))
    while remaining > 0:
        if _stop_requested(cfg):
            return False
        step = min(1, remaining)
        await asyncio.sleep(step)
        remaining -= step
    return not _stop_requested(cfg)


def check_session(raw_config):
    async def task():
        cfg = _config(raw_config)
        client = _client(cfg)
        await client.connect()
        try:
            if not await client.is_user_authorized():
                return _result(ok=True, authorized=False, message="Sessão ainda não autenticada.")
            me = await client.get_me()
            name = " ".join(filter(None, [me.first_name, me.last_name])) if me else ""
            username = f"@{me.username}" if me and me.username else ""
            label = " ".join(filter(None, [name, username])).strip()
            return _result(ok=True, authorized=True, message=f"Conta conectada: {label or 'Telegram'}")
        finally:
            await client.disconnect()

    return asyncio.run(task())


def send_code(raw_config, phone):
    async def task():
        cfg = _config(raw_config)
        client = _client(cfg)
        await client.connect()
        try:
            if await client.is_user_authorized():
                return _result(ok=True, already_authorized=True, message="A conta já está conectada.")
            try:
                sent = await client.send_code_request(phone)
            except PhoneNumberInvalidError:
                return _result(ok=False, error="Número inválido. Use o código do país, como +55.")
            return _result(
                ok=True,
                already_authorized=False,
                phone_code_hash=sent.phone_code_hash,
                message="Código enviado. Confira o Telegram e informe-o abaixo.",
            )
        finally:
            await client.disconnect()

    return asyncio.run(task())


def confirm_code(raw_config, phone, code, phone_code_hash):
    async def task():
        cfg = _config(raw_config)
        client = _client(cfg)
        await client.connect()
        try:
            if await client.is_user_authorized():
                return _result(ok=True, authorized=True, message="A conta já está conectada.")
            try:
                await client.sign_in(
                    phone=phone,
                    code=code,
                    phone_code_hash=phone_code_hash,
                )
            except SessionPasswordNeededError:
                return _result(ok=True, authorized=False, need_password=True)
            except PhoneCodeInvalidError:
                return _result(ok=False, error="O código informado é inválido.")
            except PhoneCodeExpiredError:
                return _result(ok=False, error="O código expirou. Solicite um novo código.")
            return _result(ok=True, authorized=True, message="Conta conectada com sucesso.")
        finally:
            await client.disconnect()

    return asyncio.run(task())


def confirm_password(raw_config, password):
    async def task():
        cfg = _config(raw_config)
        client = _client(cfg)
        await client.connect()
        try:
            try:
                await client.sign_in(password=password)
            except PasswordHashInvalidError:
                return _result(ok=False, error="Senha de verificação em duas etapas incorreta.")
            return _result(ok=True, authorized=True, message="Conta conectada com sucesso.")
        finally:
            await client.disconnect()

    return asyncio.run(task())


def list_dialogs(raw_config):
    async def task():
        cfg = _config(raw_config)
        client = _client(cfg)
        await client.connect()
        try:
            if not await client.is_user_authorized():
                return _result(ok=False, error="Conecte a conta antes de listar os chats.")
            dialogs = []
            async for dialog in client.iter_dialogs(ignore_migrated=True):
                if not (getattr(dialog, "is_channel", False) or getattr(dialog, "is_group", False)):
                    continue
                entity = getattr(dialog, "entity", None)
                if getattr(entity, "left", False) or getattr(entity, "deactivated", False):
                    continue
                kind = "Grupo" if getattr(dialog, "is_group", False) else "Canal"
                forum = " · fórum" if getattr(entity, "forum", False) else ""
                dialogs.append((str(dialog.name or dialog.id).strip(), int(dialog.id), kind, forum))
            dialogs.sort(key=lambda item: item[0].casefold())
            items = [
                {
                    "name": name,
                    "id": peer_id,
                    "kind": kind,
                    "forum": bool(forum),
                    "label": f"{name} · {kind}{forum}",
                }
                for name, peer_id, kind, forum in dialogs
            ]
            return _result(ok=True, count=len(items), items=items)
        finally:
            await client.disconnect()

    try:
        return asyncio.run(task())
    except Exception as error:
        return _result(ok=False, error=f"Não foi possível listar os chats: {error}")


def list_topics(raw_config, group):
    async def task():
        cfg = _config(raw_config)
        client = _client(cfg)
        await client.connect()
        try:
            if not await client.is_user_authorized():
                return _result(ok=False, error="Conecte a conta antes de listar os tópicos.")
            entity = await client.get_entity(_peer(group))
            if not getattr(entity, "forum", False):
                return _result(ok=True, count=0, items=[])

            input_entity = await client.get_input_entity(entity)
            topics = []
            seen = set()
            offset_date = None
            offset_id = 0
            offset_topic = 0

            while True:
                response = await client(
                    GetForumTopicsRequest(
                        channel=input_entity,
                        offset_date=offset_date,
                        offset_id=offset_id,
                        offset_topic=offset_topic,
                        limit=100,
                        q="",
                    )
                )
                batch = list(getattr(response, "topics", []))
                if not batch:
                    break
                added = 0
                for topic in batch:
                    topic_id = int(topic.id)
                    if topic_id in seen:
                        continue
                    seen.add(topic_id)
                    topics.append((str(getattr(topic, "title", topic_id)), topic_id))
                    added += 1
                last = batch[-1]
                offset_date = getattr(last, "date", None)
                offset_id = int(getattr(last, "top_message", 0) or 0)
                offset_topic = int(getattr(last, "id", 0) or 0)
                if len(batch) < 100 or added == 0:
                    break

            topics.sort(key=lambda item: item[0].casefold())
            items = [
                {"title": title, "id": topic_id, "label": title}
                for title, topic_id in topics
            ]
            return _result(ok=True, count=len(items), items=items)
        finally:
            await client.disconnect()

    try:
        return asyncio.run(task())
    except Exception as error:
        return _result(ok=False, error=f"Não foi possível listar os tópicos: {error}")


def _route(cfg):
    return {
        "name": cfg.get("name") or cfg.get("route_name") or "Rota Android",
        "source": _peer(cfg["source"]),
        "source_topic": _topic(cfg.get("source_topic")),
        "target": _peer(cfg["target"]),
        "target_topic": _topic(cfg.get("target_topic")),
        "retro_limit": max(1, int(cfg.get("retro_limit", 100))),
        "retro_start_id": max(0, int(cfg.get("retro_start_id", 0))),
    }


def _routes(cfg):
    raw_routes = cfg.get("routes")
    if isinstance(raw_routes, list) and raw_routes:
        return [_route(item) for item in raw_routes]
    return [_route(cfg)]


def _route_key(route):
    return (
        f"{route['source']}:{route['source_topic'] or 0}"
        f"->{route['target']}:{route['target_topic'] or 0}"
    )


def _load_progress(cfg, filename):
    path = cfg["files_dir"] / filename
    if not path.exists():
        return {}, path
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return (value if isinstance(value, dict) else {}), path
    except (OSError, json.JSONDecodeError):
        return {}, path


def _save_progress(path, progress):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(progress, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    temporary.replace(path)


async def _send_text(client, target, text, entities, target_topic, link_preview=True):
    if not text:
        return
    for part, part_entities in utils.split_text(text, entities or [], limit=4096):
        await client.send_message(
            target,
            part,
            formatting_entities=part_entities,
            parse_mode=None,
            link_preview=link_preview,
            reply_to=target_topic,
        )


async def _send_message(client, route, message):
    target = route["target"]
    target_topic = route["target_topic"]

    if isinstance(message.media, MessageMediaWebPage):
        webpage = getattr(message.media, "webpage", None)
        text = message.message or getattr(webpage, "url", "") or getattr(webpage, "display_url", "")
        await _send_text(client, target, text, message.entities or [], target_topic, True)
        return

    if message.media:
        try:
            await client.send_file(
                target,
                message.media,
                caption=message.message or "",
                formatting_entities=message.entities or [],
                parse_mode=None,
                reply_to=target_topic,
            )
        except MediaCaptionTooLongError:
            await client.send_file(target, message.media, caption="", reply_to=target_topic)
            await _send_text(
                client,
                target,
                message.message or "",
                message.entities or [],
                target_topic,
                False,
            )
        return

    await _send_text(
        client,
        target,
        message.message or "",
        message.entities or [],
        target_topic,
        True,
    )


async def _send_album(client, route, messages):
    media_messages = [
        message
        for message in messages
        if message.media and not isinstance(message.media, MessageMediaWebPage)
    ]
    if not media_messages:
        return
    if len(media_messages) == 1:
        await _send_message(client, route, media_messages[0])
        return

    files = [message.media for message in media_messages]
    captions = [message.message or "" for message in media_messages]
    entities = [message.entities or [] for message in media_messages]
    try:
        await client.send_file(
            route["target"],
            files,
            caption=captions,
            formatting_entities=entities,
            parse_mode=None,
            reply_to=route["target_topic"],
        )
    except MediaCaptionTooLongError:
        await client.send_file(
            route["target"],
            files,
            reply_to=route["target_topic"],
        )
        for message in media_messages:
            await _send_text(
                client,
                route["target"],
                message.message or "",
                message.entities or [],
                route["target_topic"],
                False,
            )


def _groups(messages):
    result = []
    index = 0
    while index < len(messages):
        first = messages[index]
        if not first.grouped_id:
            result.append(("message", [first]))
            index += 1
            continue
        album = [first]
        index += 1
        while index < len(messages) and messages[index].grouped_id == first.grouped_id:
            album.append(messages[index])
            index += 1
        result.append(("album", album))
    return result


async def _collect(client, route, min_id, limit):
    messages = []
    async for message in client.iter_messages(
        route["source"],
        min_id=min_id,
        limit=limit,
        reverse=True,
        reply_to=route["source_topic"],
    ):
        messages.append(message)

    if not messages or not messages[-1].grouped_id:
        return messages

    grouped_id = messages[-1].grouped_id
    cursor = messages[-1].id
    while True:
        extra = []
        async for message in client.iter_messages(
            route["source"],
            min_id=cursor,
            limit=20,
            reverse=True,
            reply_to=route["source_topic"],
        ):
            extra.append(message)
        if not extra:
            break
        for message in extra:
            if message.grouped_id != grouped_id:
                return messages
            messages.append(message)
            cursor = message.id
    return messages


async def _send_group_with_retry(client, cfg, route, kind, messages, listener):
    while not _stop_requested(cfg):
        try:
            if kind == "album":
                await _send_album(client, route, messages)
                _emit(listener, f"[{route['name']}] ✓ Álbum {messages[0].id}-{messages[-1].id}")
            else:
                await _send_message(client, route, messages[0])
                _emit(listener, f"[{route['name']}] ✓ Mensagem {messages[0].id}")
            return True
        except FloodWaitError as error:
            _emit(listener, f"FloodWait: aguardando {error.seconds} segundos.")
            if not await _sleep(cfg, error.seconds):
                return False
    return False


async def _authorized_client(cfg):
    client = _client(cfg)
    await client.connect()
    if not await client.is_user_authorized():
        await client.disconnect()
        raise RuntimeError("A sessão não está autenticada.")
    return client


def run_normal(raw_config, listener=None):
    async def task():
        cfg = _config(raw_config)
        routes = _routes(cfg)
        progress, progress_path = _load_progress(cfg, "normal_progress.json")
        _clear_stop(cfg)
        client = await _authorized_client(cfg)
        _emit(listener, f"Modo normal conectado · {len(routes)} rota(s).")
        try:
            active_routes = []
            for route in routes:
                try:
                    key = _route_key(route)
                    if key not in progress:
                        latest = await client.get_messages(
                            route["source"], limit=1, reply_to=route["source_topic"]
                        )
                        progress[key] = latest[0].id if latest else 0
                        _save_progress(progress_path, progress)
                        _emit(
                            listener,
                            f"[{route['name']}] primeiro uso: monitorando após o ID {progress[key]}.",
                        )
                    active_routes.append(route)
                except Exception as error:
                    _emit(listener, f"[{route['name']}] rota ignorada: {error}")
            routes = active_routes
            if not routes:
                raise RuntimeError("Nenhuma rota pôde ser iniciada.")

            while not _stop_requested(cfg):
                found_messages = False
                for route in routes:
                    if _stop_requested(cfg):
                        break
                    key = _route_key(route)
                    try:
                        messages = await _collect(
                            client,
                            route,
                            int(progress.get(key, 0)),
                            int(cfg.get("batch_size", 100)),
                        )
                        found_messages = found_messages or bool(messages)
                        for kind, group in _groups(messages):
                            if _stop_requested(cfg):
                                break
                            if await _send_group_with_retry(
                                client, cfg, route, kind, group, listener
                            ):
                                progress[key] = group[-1].id
                                _save_progress(progress_path, progress)
                    except FloodWaitError as error:
                        _emit(listener, f"FloodWait geral: {error.seconds} segundos.")
                        await _sleep(cfg, error.seconds)
                    except Exception as error:
                        _emit(listener, f"[{route['name']}] erro temporário: {error}")
                if not found_messages:
                    await _sleep(cfg, int(cfg.get("interval", 5)))
        finally:
            await client.disconnect()
            _emit(listener, "Conta desconectada do motor normal.")

    try:
        asyncio.run(task())
        return _result(ok=True, stopped=True)
    except Exception as error:
        _emit(listener, f"Erro fatal: {error}")
        return _result(ok=False, error=str(error))


def run_retro(raw_config, listener=None):
    async def task():
        cfg = _config(raw_config)
        routes = _routes(cfg)
        progress, progress_path = _load_progress(cfg, "retro_progress.json")
        _clear_stop(cfg)
        client = await _authorized_client(cfg)
        _emit(listener, f"Modo retroativo conectado · {len(routes)} rota(s).")
        try:
            for route in routes:
                if _stop_requested(cfg):
                    break
                try:
                    key = _route_key(route)
                    start_id = max(
                        route["retro_start_id"], int(progress.get(key, 0))
                    )
                    _emit(listener, f"[{route['name']}] carregando após o ID {start_id}.")
                    messages = await _collect(
                        client, route, start_id, route["retro_limit"]
                    )
                    if not messages:
                        _emit(listener, f"[{route['name']}] nenhuma mensagem encontrada.")
                        continue
                    _emit(listener, f"[{route['name']}] {len(messages)} mensagem(ns) carregada(s).")
                    for kind, group in _groups(messages):
                        if _stop_requested(cfg):
                            break
                        if await _send_group_with_retry(
                            client, cfg, route, kind, group, listener
                        ):
                            progress[key] = group[-1].id
                            _save_progress(progress_path, progress)
                except Exception as error:
                    _emit(listener, f"[{route['name']}] erro: {error}")
        finally:
            await client.disconnect()
            _emit(listener, "Conta desconectada do motor retroativo.")

    try:
        asyncio.run(task())
        return _result(ok=True, stopped=True)
    except Exception as error:
        _emit(listener, f"Erro fatal: {error}")
        return _result(ok=False, error=str(error))
