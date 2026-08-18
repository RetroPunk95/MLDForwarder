import asyncio

from telethon import TelegramClient
from telethon.errors import (
    PasswordHashInvalidError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberInvalidError,
    SessionPasswordNeededError,
)
from telethon.tl.functions.channels import GetForumTopicsRequest

from config_utils import resolver_session_path


def _session_path(session_file):
    return str(
        resolver_session_path(
            session_file
        )
    )


async def verificar_sessao(
    api_id,
    api_hash,
    session_file
):
    client = TelegramClient(
        _session_path(session_file),
        int(api_id),
        api_hash
    )

    await client.connect()

    try:
        autorizado = await client.is_user_authorized()

        if not autorizado:
            return {
                "ok": True,
                "authorized": False
            }

        me = await client.get_me()

        nome = ""

        if me:
            nome = me.first_name or ""

            if me.last_name:
                nome += f" {me.last_name}"

        username = (
            f"@{me.username}"
            if me and me.username
            else ""
        )

        return {
            "ok": True,
            "authorized": True,
            "name": nome.strip(),
            "username": username
        }

    finally:
        await client.disconnect()


async def enviar_codigo(
    api_id,
    api_hash,
    session_file,
    telefone
):
    client = TelegramClient(
        _session_path(session_file),
        int(api_id),
        api_hash
    )

    await client.connect()

    try:
        if await client.is_user_authorized():
            return {
                "ok": True,
                "already_authorized": True
            }

        try:
            enviado = await client.send_code_request(
                telefone
            )

        except PhoneNumberInvalidError:
            return {
                "ok": False,
                "error": (
                    "Número de telefone inválido. "
                    "Use o código do país, por exemplo +55..."
                )
            }

        return {
            "ok": True,
            "already_authorized": False,
            "phone_code_hash": enviado.phone_code_hash
        }

    finally:
        await client.disconnect()


async def confirmar_codigo(
    api_id,
    api_hash,
    session_file,
    telefone,
    codigo,
    phone_code_hash
):
    client = TelegramClient(
        _session_path(session_file),
        int(api_id),
        api_hash
    )

    await client.connect()

    try:
        if await client.is_user_authorized():
            return {
                "ok": True,
                "authorized": True,
                "need_password": False
            }

        try:
            await client.sign_in(
                phone=telefone,
                code=codigo,
                phone_code_hash=phone_code_hash
            )

        except SessionPasswordNeededError:
            return {
                "ok": True,
                "authorized": False,
                "need_password": True
            }

        except PhoneCodeInvalidError:
            return {
                "ok": False,
                "error": "O código informado é inválido."
            }

        except PhoneCodeExpiredError:
            return {
                "ok": False,
                "error": (
                    "O código expirou. "
                    "Solicite um novo código."
                )
            }

        return {
            "ok": True,
            "authorized": True,
            "need_password": False
        }

    finally:
        await client.disconnect()


async def confirmar_senha(
    api_id,
    api_hash,
    session_file,
    senha
):
    client = TelegramClient(
        _session_path(session_file),
        int(api_id),
        api_hash
    )

    await client.connect()

    try:
        if await client.is_user_authorized():
            return {
                "ok": True,
                "authorized": True
            }

        try:
            await client.sign_in(
                password=senha
            )

        except PasswordHashInvalidError:
            return {
                "ok": False,
                "error": "Senha de verificação em duas etapas incorreta."
            }

        return {
            "ok": True,
            "authorized": True
        }

    finally:
        await client.disconnect()


async def sair_da_conta(
    api_id,
    api_hash,
    session_file
):
    client = TelegramClient(
        _session_path(session_file),
        int(api_id),
        api_hash
    )

    await client.connect()

    try:
        if not await client.is_user_authorized():
            return {
                "ok": True,
                "authorized": False
            }

        await client.log_out()

        return {
            "ok": True,
            "authorized": False
        }

    finally:
        if client.is_connected():
            await client.disconnect()


async def listar_topicos(
    api_id,
    api_hash,
    session_file,
    grupo
):
    """
    Lista os tópicos visíveis de um grupo com fórum.

    A consulta usa a mesma sessão já autenticada pela GUI e pagina os
    resultados para não limitar grupos que tenham mais de 100 tópicos.
    """
    client = TelegramClient(
        _session_path(session_file),
        int(api_id),
        api_hash
    )

    await client.connect()

    try:
        if not await client.is_user_authorized():
            return {
                "ok": False,
                "error": (
                    "A sessão do Telegram não está autenticada. "
                    "Entre na aba Telegram e conecte sua conta."
                )
            }

        try:
            entidade = await client.get_entity(grupo)
        except (TypeError, ValueError):
            return {
                "ok": False,
                "error": (
                    "Não foi possível localizar esse grupo. "
                    "Confira o ID ou @username da origem."
                )
            }

        titulo_grupo = (
            getattr(entidade, "title", None)
            or str(grupo)
        )

        if not getattr(entidade, "forum", False):
            return {
                "ok": True,
                "is_forum": False,
                "group_title": titulo_grupo,
                "topics": []
            }

        entrada = await client.get_input_entity(entidade)
        topicos = []
        ids_vistos = set()

        offset_date = None
        offset_id = 0
        offset_topic = 0
        marcador_anterior = None

        while True:
            resultado = await client(
                GetForumTopicsRequest(
                    channel=entrada,
                    offset_date=offset_date,
                    offset_id=offset_id,
                    offset_topic=offset_topic,
                    limit=100,
                    q=""
                )
            )

            lote = list(
                getattr(resultado, "topics", [])
            )

            if not lote:
                break

            novos = 0

            for topico in lote:
                topico_id = getattr(
                    topico,
                    "id",
                    None
                )
                titulo = getattr(
                    topico,
                    "title",
                    None
                )

                if (
                    topico_id is None
                    or titulo is None
                    or topico_id in ids_vistos
                ):
                    continue

                ids_vistos.add(topico_id)
                novos += 1
                topicos.append(
                    {
                        "id": int(topico_id),
                        "title": str(titulo)
                    }
                )

            ultimo = lote[-1]
            marcador = (
                getattr(ultimo, "date", None),
                int(getattr(ultimo, "top_message", 0) or 0),
                int(getattr(ultimo, "id", 0) or 0)
            )

            if (
                len(lote) < 100
                or novos == 0
                or marcador == marcador_anterior
            ):
                break

            marcador_anterior = marcador
            offset_date, offset_id, offset_topic = marcador

        return {
            "ok": True,
            "is_forum": True,
            "group_title": titulo_grupo,
            "topics": topicos
        }

    except Exception as erro:
        return {
            "ok": False,
            "error": (
                "Não foi possível consultar os tópicos: "
                f"{erro}"
            )
        }

    finally:
        if client.is_connected():
            await client.disconnect()


def executar(coroutine):
    """
    Executa uma operação assíncrona em uma thread de trabalho da GUI.
    """
    return asyncio.run(coroutine)
