"""Motor Telethon do MLDForwarder Android.

A interface Java chama somente funções que retornam JSON. As sincronizações
longas recebem um objeto Java com ``onLog(str)`` e usam uma flag em disco para
parada cooperativa, retomada e encerramento seguro do serviço Android.
"""

import asyncio
import copy
import hashlib
import json
import threading
from functools import wraps
from pathlib import Path

from telethon import TelegramClient, utils
from telethon.errors import (
    DocumentInvalidError,
    FileReferenceEmptyError,
    FileReferenceExpiredError,
    FileReferenceInvalidError,
    FloodWaitError,
    MediaEmptyError,
    MediaInvalidError,
    MediaCaptionTooLongError,
    PasswordHashInvalidError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberInvalidError,
    PhotoInvalidError,
    PremiumAccountRequiredError,
    SessionPasswordNeededError,
)
from telethon.tl.functions.channels import GetForumTopicsRequest
from telethon.tl.types import MessageEntityCustomEmoji, MessageMediaWebPage

from delivery_state import (
    DeliveryContext, DeliveryJournal, DeliveryStopped,
    DeliveryStorageError,
)


RECOVERABLE_MEDIA_ERRORS = (
    DocumentInvalidError, FileReferenceEmptyError, FileReferenceExpiredError,
    FileReferenceInvalidError, MediaEmptyError, MediaInvalidError,
    PhotoInvalidError, PremiumAccountRequiredError,
)


class SourceMessageUnavailable(Exception):
    pass


_SYNC_LOCK = threading.Lock()


def _single_sync(function):
    @wraps(function)
    def wrapped(raw_config, listener=None):
        if not _SYNC_LOCK.acquire(blocking=False):
            _emit(listener, "O motor anterior ainda está encerrando. Aguarde antes de iniciar novamente.")
            return _result(ok=False, error="Sincronização já em execução.")
        try:
            return function(raw_config, listener)
        finally:
            _SYNC_LOCK.release()
    return wrapped


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
    try:
        temporary.write_text(
            json.dumps(progress, indent=2, ensure_ascii=False), encoding="utf-8",
        )
        temporary.replace(path)
    except OSError as error:
        raise DeliveryStorageError("Falha ao salvar progresso; sincronização interrompida.") from error


def _without_custom_emoji(entities):
    # Não alterar o texto: o emoji Unicode já ocupa os offsets UTF-16 originais.
    return [entity for entity in entities or [] if not isinstance(entity, MessageEntityCustomEmoji)]


async def _send_text(client, target, text, entities, target_topic, context, key, link_preview=True):
    if not text:
        return
    for index, (part, part_entities) in enumerate(utils.split_text(text, entities or [], limit=4096)):
        async def send():
            return await client.send_message(
                target, part, formatting_entities=part_entities, parse_mode=None,
                link_preview=link_preview, reply_to=target_topic,
            )
        try:
            await context.operation(f"{key}:{index}", send)
        except (DocumentInvalidError, PremiumAccountRequiredError):
            clean = _without_custom_emoji(part_entities)
            if len(clean) == len(part_entities):
                raise
            context.log("Compatibilidade: tentando trecho de texto com emojis comuns; demais estilos mantidos.")
            part_entities = clean
            await context.operation(f"{key}:{index}", send)


async def _send_message(client, route, message, context):
    target = route["target"]
    target_topic = route["target_topic"]

    if isinstance(message.media, MessageMediaWebPage):
        webpage = getattr(message.media, "webpage", None)
        text = message.message or getattr(webpage, "url", "") or getattr(webpage, "display_url", "")
        await _send_text(client, target, text, message.entities or [], target_topic, context, "text", True)
        return

    if message.media:
        if not context.entry["split_caption"]:
            try:
                await context.operation("media", lambda: client.send_file(
                    target, message.media, caption=message.message or "",
                    formatting_entities=message.entities or [], parse_mode=None,
                    reply_to=target_topic,
                ))
            except MediaCaptionTooLongError:
                context.journal.update(context.entry, split_caption=True)
        if context.entry["split_caption"]:
            await context.operation("media", lambda: client.send_file(
                target, message.media, caption="", parse_mode=None, reply_to=target_topic,
            ))
            await _send_text(
                client,
                target,
                message.message or "",
                message.entities or [],
                target_topic,
                context,
                "caption",
                False,
            )
        return

    await _send_text(
        client,
        target,
        message.message or "",
        message.entities or [],
        target_topic,
        context,
        "text",
        True,
    )


async def _send_album(client, route, messages, context):
    media_messages = [
        message
        for message in messages
        if message.media and not isinstance(message.media, MessageMediaWebPage)
    ]
    if not media_messages:
        return
    if len(media_messages) == 1:
        await _send_message(client, route, media_messages[0], context)
        return

    files = [message.media for message in media_messages]
    captions = [message.message or "" for message in media_messages]
    entities = [message.entities or [] for message in media_messages]
    if not context.entry["split_caption"]:
        try:
            await context.operation("album", lambda: client.send_file(
                route["target"], files, caption=captions, formatting_entities=entities,
                parse_mode=None, reply_to=route["target_topic"],
            ))
        except MediaCaptionTooLongError:
            context.journal.update(context.entry, split_caption=True)
    if context.entry["split_caption"]:
        await context.operation("album", lambda: client.send_file(
            route["target"], files, caption=[""] * len(files),
            formatting_entities=[[] for _ in files], parse_mode=None,
            reply_to=route["target_topic"],
        ))
        for message in media_messages:
            await _send_text(
                client,
                route["target"],
                message.message or "",
                message.entities or [],
                route["target_topic"],
                context,
                f"caption:{message.id}",
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


async def _collect(client, route, min_id, limit, cfg=None):
    messages = []
    async for message in client.iter_messages(
        route["source"],
        min_id=min_id,
        limit=limit,
        reverse=True,
        reply_to=route["source_topic"],
    ):
        if cfg is not None and _stop_requested(cfg):
            raise DeliveryStopped()
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
            if cfg is not None and _stop_requested(cfg):
                raise DeliveryStopped()
            extra.append(message)
        if not extra:
            break
        for message in extra:
            if message.grouped_id != grouped_id:
                return messages
            messages.append(message)
            cursor = message.id
    return messages


async def _collect_with_retry(client, cfg, route, min_id, limit, listener):
    while not _stop_requested(cfg):
        try:
            return await _collect(client, route, min_id, limit, cfg)
        except FloodWaitError as error:
            _emit(listener, f"[{route['name']}] FloodWait na busca: {error.seconds} segundos.")
            if not await _sleep(cfg, error.seconds):
                break
    raise DeliveryStopped()


async def _send_group_with_retry(client, cfg, route, kind, messages, listener):
    journal = cfg["_delivery"]
    entry = journal.begin(route, kind, messages)
    label = f"[{route['name']}] IDs {', '.join(map(str, entry['ids']))}"
    if entry["status"] == "sent":
        return True
    fingerprint = hashlib.sha256(json.dumps([
        [m.id, m.message or "", [e.to_dict() for e in m.entities or []]]
        for m in messages
    ], sort_keys=True, default=str).encode("utf-8")).hexdigest()
    if entry.get("fingerprint", fingerprint) != fingerprint and entry["confirmed"]:
        journal.update(entry, status="review", error="Origem editada após envio parcial; conferir destino.")
    if entry["status"] == "review" or entry.get("in_flight"):
        _emit(listener, f"{label}: pendente de conferência no destino; envio incerto não será repetido automaticamente.")
        return True
    if entry["key"] in cfg["_attempted"]:
        return True  # No máximo uma sequência de recuperação por execução.
    cfg["_attempted"].add(entry["key"])
    context = DeliveryContext(
        journal, entry, lambda: _stop_requested(cfg),
        lambda seconds: _sleep(cfg, seconds),
        lambda text: _emit(listener, f"{label}: {text}"),
    )
    journal.update(entry, attempts=entry["attempts"] + 1, status="ready", fingerprint=fingerprint)
    refreshed = False
    simplified = False
    try:
        while not _stop_requested(cfg):
            try:
                if kind == "album":
                    await _send_album(client, route, messages, context)
                else:
                    await _send_message(client, route, messages[0], context)
                journal.update(entry, status="sent", error=None)
                cfg["_attempted"].discard(entry["key"])
                _emit(listener, f"{label}: ✓ {'Álbum' if kind == 'album' else 'Mensagem'} enviado(a).")
                return True
            except RECOVERABLE_MEDIA_ERRORS as error:
                _emit(listener, f"{label}: {type(error).__name__}. Mídia: "
                      f"{', '.join(type(m.media).__name__ for m in messages)}; "
                      f"emojis personalizados: {sum(isinstance(e, MessageEntityCustomEmoji) for m in messages for e in m.entities or [])}.")
                if not refreshed:
                    refreshed = True
                    _emit(listener, f"{label}: renovando referência da mídia e tentando novamente.")
                    fresh = await _fetch_ids(client, cfg, route, entry["ids"], listener)
                    renewed = []
                    for original, current in zip(messages, fresh):
                        message = copy.copy(original)
                        # Manter texto/partes já confirmadas; renovar somente a mídia.
                        message.media = current.media
                        renewed.append(message)
                    messages = renewed
                    continue
                if not simplified and any(
                    isinstance(e, MessageEntityCustomEmoji) for m in messages for e in m.entities or []
                ) and isinstance(error, (DocumentInvalidError, PremiumAccountRequiredError)):
                    simplified = True
                    messages = [copy.copy(m) for m in messages]
                    for message in messages:
                        message.entities = _without_custom_emoji(message.entities)
                    _emit(listener, f"{label}: compatibilidade — tentando com emojis comuns, mantendo mídia, texto e demais estilos.")
                    continue
                raise
        raise DeliveryStopped()
    except DeliveryStopped:
        journal.update(entry, status="pending", error="Parada solicitada antes de concluir o envio.")
        return False
    except (RECOVERABLE_MEDIA_ERRORS + (SourceMessageUnavailable,)) as error:
        journal.update(entry, status="pending", error=f"{type(error).__name__}: {error}")
        _emit(listener, f"{label}: ⚠ PENDENTE — {type(error).__name__}. Salvo para nova tentativa; seguindo a rota.")
        return True
    except DeliveryStorageError:
        raise
    except Exception as error:
        # Permissão/autenticação/rede não são mídia inválida: interromper a rota.
        status = "review" if entry.get("in_flight") else "pending"
        journal.update(entry, status=status, error=f"{type(error).__name__}: {error}")
        _emit(listener, f"{label}: pendência salva ({status}); rota interrompida: {type(error).__name__}.")
        raise


async def _fetch_ids(client, cfg, route, ids, listener):
    while not _stop_requested(cfg):
        try:
            messages = await client.get_messages(route["source"], ids=ids)
            by_id = {m.id: m for m in messages if m is not None and hasattr(m, "media")}
            missing = [i for i in ids if i not in by_id]
            if missing:
                raise SourceMessageUnavailable(f"IDs indisponíveis na origem: {missing}")
            return [by_id[i] for i in ids]
        except FloodWaitError as error:
            _emit(listener, f"[{route['name']}] FloodWait na leitura: {error.seconds} segundos.")
            if not await _sleep(cfg, error.seconds):
                break
    raise DeliveryStopped()


async def _setup_delivery(client, cfg, mode):
    me = await client.get_me()
    # Pendências de outra conta nunca são reenviadas na conta conectada.
    cfg["_delivery"] = DeliveryJournal(cfg["files_dir"] / f"{mode}_delivery_{me.id}.json")
    cfg["_attempted"] = set()


async def _process_batch(client, cfg, route, messages, listener, progress, progress_path):
    key = _route_key(route)
    for kind, group in _groups(messages):
        if _stop_requested(cfg):
            break
        entry = cfg["_delivery"].begin(route, kind, group)
        if not await _send_group_with_retry(client, cfg, route, kind, group, listener):
            break
        # Cursor = último item examinado. Pendências são salvas ANTES do avanço.
        progress[key] = max(int(progress.get(key, 0)), group[-1].id)
        _save_progress(progress_path, progress)
        cfg["_delivery"].ack(entry)


async def _retry_pending(client, cfg, route, listener, cursor):
    journal = cfg["_delivery"]
    for entry in list(journal.entries.values()):
        if entry["route_key"] == _route_key(route) and entry["status"] == "sent" and max(entry["ids"]) <= cursor:
            journal.ack(entry)
    for entry in journal.pending(route):
        if _stop_requested(cfg):
            return
        if entry["status"] == "review" or entry.get("in_flight"):
            _emit(listener, f"[{route['name']}] IDs {entry['ids']}: pendente de conferência manual (resultado incerto).")
            continue
        try:
            _emit(listener, f"[{route['name']}] tentando pendência IDs {entry['ids']}.")
            messages = await _fetch_ids(client, cfg, route, entry["ids"], listener)
            await _send_group_with_retry(client, cfg, route, entry["kind"], messages, listener)
            if entry["status"] == "sent" and max(entry["ids"]) <= cursor:
                journal.ack(entry)
        except SourceMessageUnavailable as error:
            journal.update(entry, status="pending", error=str(error))
            _emit(listener, f"[{route['name']}] pendência mantida: {error}")
        except DeliveryStopped:
            return


def _delivery_summary(cfg, routes, listener):
    journal = cfg.get("_delivery")
    if journal is None:
        return
    keys = {_route_key(route) for route in routes}
    entries = [e for e in journal.entries.values() if e["route_key"] in keys and e["status"] != "sent"]
    count = sum(len(e["ids"]) for e in entries)
    review = sum(len(e["ids"]) for e in entries if e["status"] == "review" or e.get("in_flight"))
    _emit(listener, f"Pendências: {count} mensagem(ns), incluindo {review} para conferência manual. "
          "Pendentes não contam como enviadas; rejeições serão tentadas na próxima execução.")


async def _authorized_client(cfg):
    client = _client(cfg)
    await client.connect()
    if not await client.is_user_authorized():
        await client.disconnect()
        raise RuntimeError("A sessão não está autenticada.")
    return client


@_single_sync
def run_normal(raw_config, listener=None):
    async def task():
        cfg = _config(raw_config)
        routes = _routes(cfg)
        configured_routes = list(routes)
        progress, progress_path = _load_progress(cfg, "normal_progress.json")
        _clear_stop(cfg)
        client = await _authorized_client(cfg)
        _emit(listener, f"Modo normal conectado · {len(routes)} rota(s).")
        try:
            await _setup_delivery(client, cfg, "normal")
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
                    await _retry_pending(client, cfg, route, listener, int(progress.get(key, 0)))
                    active_routes.append(route)
                except DeliveryStorageError:
                    raise
                except Exception as error:
                    _emit(listener, f"[{route['name']}] rota ignorada: {error}")
            routes = active_routes
            if not routes:
                raise RuntimeError("Nenhuma rota pôde ser iniciada.")

            blocked_routes = set()
            while not _stop_requested(cfg):
                found_messages = False
                for route in routes:
                    if _stop_requested(cfg):
                        break
                    key = _route_key(route)
                    if key in blocked_routes:
                        continue
                    try:
                        messages = await _collect_with_retry(
                            client, cfg, route, int(progress.get(key, 0)),
                            int(cfg.get("batch_size", 100)), listener,
                        )
                        found_messages = found_messages or bool(messages)
                        await _process_batch(client, cfg, route, messages, listener, progress, progress_path)
                    except FloodWaitError as error:
                        _emit(listener, f"FloodWait geral: {error.seconds} segundos.")
                        await _sleep(cfg, error.seconds)
                    except DeliveryStopped:
                        break
                    except Exception as error:
                        if isinstance(error, DeliveryStorageError):
                            raise
                        blocked_routes.add(key)
                        _emit(listener, f"[{route['name']}] rota pausada nesta execução: {error}")
                if all(_route_key(route) in blocked_routes for route in routes):
                    _emit(listener, "Todas as rotas foram pausadas por erro; revise a Atividade antes de reiniciar.")
                    break
                if not found_messages:
                    await _sleep(cfg, int(cfg.get("interval", 5)))
        finally:
            _delivery_summary(cfg, configured_routes, listener)
            await client.disconnect()
            _emit(listener, "Conta desconectada do motor normal.")

    try:
        asyncio.run(task())
        return _result(ok=True, stopped=True)
    except Exception as error:
        _emit(listener, f"Erro fatal: {error}")
        return _result(ok=False, error=str(error))


@_single_sync
def run_retro(raw_config, listener=None):
    async def task():
        cfg = _config(raw_config)
        routes = _routes(cfg)
        progress, progress_path = _load_progress(cfg, "retro_progress.json")
        _clear_stop(cfg)
        client = await _authorized_client(cfg)
        _emit(listener, f"Modo retroativo conectado · {len(routes)} rota(s).")
        try:
            await _setup_delivery(client, cfg, "retro")
            for route in routes:
                if _stop_requested(cfg):
                    break
                try:
                    key = _route_key(route)
                    await _retry_pending(client, cfg, route, listener, int(progress.get(key, 0)))
                    if _stop_requested(cfg):
                        break
                    start_id = max(
                        route["retro_start_id"], int(progress.get(key, 0))
                    )
                    _emit(listener, f"[{route['name']}] carregando após o ID {start_id}.")
                    messages = await _collect_with_retry(
                        client, cfg, route, start_id, route["retro_limit"], listener,
                    )
                    if not messages:
                        _emit(listener, f"[{route['name']}] nenhuma mensagem encontrada.")
                        continue
                    _emit(listener, f"[{route['name']}] {len(messages)} mensagem(ns) carregada(s).")
                    await _process_batch(client, cfg, route, messages, listener, progress, progress_path)
                except DeliveryStorageError:
                    raise
                except DeliveryStopped:
                    break
                except Exception as error:
                    _emit(listener, f"[{route['name']}] erro: {error}")
        finally:
            _delivery_summary(cfg, routes, listener)
            await client.disconnect()
            _emit(listener, "Conta desconectada do motor retroativo.")

    try:
        asyncio.run(task())
        return _result(ok=True, stopped=True)
    except Exception as error:
        _emit(listener, f"Erro fatal: {error}")
        return _result(ok=False, error=str(error))
