import asyncio
import sys
import os

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import FloodWaitError


# Mantém o log em tempo real quando o motor é executado
# como helper empacotado e sua saída é capturada pela GUI.
if (
    sys.stdout is not None
    and hasattr(sys.stdout, "reconfigure")
):
    sys.stdout.reconfigure(
        encoding="utf-8",
        errors="replace",
        line_buffering=True
    )

if (
    sys.stderr is not None
    and hasattr(sys.stderr, "reconfigure")
):
    sys.stderr.reconfigure(
        encoding="utf-8",
        errors="replace",
        line_buffering=True
    )

from config_utils import (
    ENV_FILE,
    SYNC_PROGRESS_FILE,
    SYNC_STOP_FILE,
    carregar_canais,
    carregar_config_app,
    carregar_config_normal,
    carregar_json,
    salvar_json,
    resolver_session_path,
)


# ============================================================
# CONFIGURAÇÃO
# ============================================================

load_dotenv(dotenv_path=ENV_FILE)

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")

if not API_ID or not API_HASH:
    raise RuntimeError(
        "API_ID e API_HASH não encontrados no arquivo .env."
    )

API_ID = int(API_ID)

CHANNELS = carregar_canais()

CONFIG_NORMAL = carregar_config_normal()
CONFIG_APP = carregar_config_app()

TAMANHO_LOTE = CONFIG_NORMAL["tamanho_lote"]
INTERVALO = CONFIG_NORMAL["intervalo"]

SESSION_FILE = str(resolver_session_path(CONFIG_APP["session_file"]))


# ============================================================
# PROGRESSO
# ============================================================

def carregar_progresso():

    dados = carregar_json(
        SYNC_PROGRESS_FILE,
        {}
    )

    if not isinstance(dados, dict):
        print(
            "Aviso: sync_progress.json inválido. "
            "Um progresso vazio será usado."
        )
        return {}

    return dados


def salvar_progresso(progresso):

    salvar_json(
        SYNC_PROGRESS_FILE,
        progresso
    )


def obter_last_id(
    progresso,
    chave_rota
):

    chave = str(chave_rota)

    if chave not in progresso:
        return None

    valor = progresso[chave]

    # Compatibilidade com uma versão anterior que usava
    # objetos em vez de apenas o ID.
    if isinstance(valor, dict):
        valor = valor.get(
            "last_synced_id",
            valor.get("last_id")
        )

    if valor is None:
        return None

    return int(valor)


def atualizar_last_id(
    progresso,
    chave_rota,
    last_id
):

    progresso[str(chave_rota)] = int(last_id)

    salvar_progresso(
        progresso
    )


# ============================================================
# PARADA CONTROLADA
# ============================================================

def parada_solicitada():

    return SYNC_STOP_FILE.exists()


def limpar_pedido_parada():

    try:
        SYNC_STOP_FILE.unlink()
    except FileNotFoundError:
        pass


async def esperar_com_parada(segundos):

    restante = max(0, int(segundos))

    while restante > 0:

        if parada_solicitada():
            return False

        passo = min(1, restante)

        await asyncio.sleep(
            passo
        )

        restante -= passo

    return not parada_solicitada()


# ============================================================
# INICIALIZAÇÃO
# ============================================================

async def inicializar_canal(
    client,
    chave_rota,
    origem,
    topico_id,
    nome,
    progresso
):

    ultimo_id = obter_last_id(
        progresso,
        chave_rota
    )

    if ultimo_id is not None:
        return ultimo_id

    print()
    print(
        f"[{nome}] Primeiro uso detectado."
    )

    print(
        "Localizando a mensagem mais recente..."
    )

    mensagem = await client.get_messages(
        origem,
        limit=1,
        reply_to=topico_id
    )

    if not mensagem:

        print(
            "Canal sem mensagens."
        )

        atualizar_last_id(
            progresso,
            chave_rota,
            0
        )

        return 0

    ultimo_id = mensagem[0].id

    atualizar_last_id(
        progresso,
        chave_rota,
        ultimo_id
    )

    print(
        f"Último ID atual: {ultimo_id}"
    )

    print(
        "Histórico existente não será reenviado."
    )

    print(
        "Aguardando novas mensagens..."
    )

    return ultimo_id


# ============================================================
# ENVIO
# ============================================================

async def enviar_mensagem(
    client,
    destino,
    mensagem,
    topico_destino_id=None
):

    if mensagem.media:

        await client.send_file(
            destino,
            mensagem.media,
            caption=mensagem.message or "",
            formatting_entities=mensagem.entities or [],
            reply_to=topico_destino_id
        )

        return

    if mensagem.message:

        await client.send_message(
            destino,
            mensagem.message,
            formatting_entities=mensagem.entities or [],
            reply_to=topico_destino_id
        )


async def enviar_album(
    client,
    destino,
    mensagens,
    topico_destino_id=None
):

    arquivos = []
    legendas = []
    entidades = []

    for mensagem in mensagens:

        if not mensagem.media:
            continue

        arquivos.append(
            mensagem.media
        )

        legendas.append(
            mensagem.message or ""
        )

        entidades.append(
            mensagem.entities or []
        )

    if not arquivos:
        return

    if len(arquivos) == 1:

        await client.send_file(
            destino,
            arquivos[0],
            caption=legendas[0],
            formatting_entities=entidades[0],
            reply_to=topico_destino_id
        )

        return

    await client.send_file(
        destino,
        arquivos,
        caption=legendas,
        formatting_entities=entidades,
        reply_to=topico_destino_id
    )


# ============================================================
# BUSCA DE MENSAGENS NOVAS
# ============================================================

async def buscar_mensagens_novas(
    client,
    origem,
    ultimo_id,
    topico_id=None
):

    mensagens = []

    async for mensagem in client.iter_messages(
        origem,
        limit=TAMANHO_LOTE,
        min_id=ultimo_id,
        reverse=True,
        reply_to=topico_id
    ):

        mensagens.append(
            mensagem
        )

    if not mensagens:
        return []

    ultima = mensagens[-1]

    if ultima.grouped_id:

        grouped_id = ultima.grouped_id
        proximo_id = ultima.id

        while True:

            extras = []

            async for mensagem in client.iter_messages(
                origem,
                limit=20,
                min_id=proximo_id,
                reverse=True,
                reply_to=topico_id
            ):

                extras.append(
                    mensagem
                )

            if not extras:
                break

            encontrou_album = False

            for mensagem in extras:

                if mensagem.grouped_id != grouped_id:
                    return mensagens

                mensagens.append(
                    mensagem
                )

                proximo_id = mensagem.id
                encontrou_album = True

            if not encontrou_album:
                break

    return mensagens


# ============================================================
# AGRUPAMENTO
# ============================================================

def separar_mensagens(mensagens):

    grupos = []
    indice = 0

    while indice < len(mensagens):

        mensagem = mensagens[indice]

        if not mensagem.grouped_id:

            grupos.append(
                {
                    "tipo": "mensagem",
                    "mensagens": [mensagem]
                }
            )

            indice += 1
            continue

        album = [mensagem]
        grouped_id = mensagem.grouped_id
        proximo = indice + 1

        while proximo < len(mensagens):

            outra = mensagens[proximo]

            if outra.grouped_id != grouped_id:
                break

            album.append(
                outra
            )

            proximo += 1

        grupos.append(
            {
                "tipo": "album",
                "mensagens": album
            }
        )

        indice = proximo

    return grupos


# ============================================================
# PROCESSAMENTO
# ============================================================

async def processar_mensagens(
    client,
    chave_rota,
    destino,
    topico_destino_id,
    mensagens,
    progresso
):

    grupos = separar_mensagens(
        mensagens
    )

    for grupo in grupos:

        if parada_solicitada():
            return False

        grupo_mensagens = grupo["mensagens"]

        primeiro_id = grupo_mensagens[0].id
        ultimo_id = grupo_mensagens[-1].id

        try:

            if grupo["tipo"] == "album":

                await enviar_album(
                    client,
                    destino,
                    grupo_mensagens,
                    topico_destino_id
                )

                print(
                    f"  ✓ Álbum "
                    f"{primeiro_id}-{ultimo_id}"
                )

            else:

                mensagem = grupo_mensagens[0]

                if (
                    not mensagem.media
                    and not mensagem.message
                ):

                    atualizar_last_id(
                        progresso,
                        chave_rota,
                        mensagem.id
                    )

                    continue

                await enviar_mensagem(
                    client,
                    destino,
                    mensagem,
                    topico_destino_id
                )

                print(
                    f"  ✓ {mensagem.id}"
                )

            atualizar_last_id(
                progresso,
                chave_rota,
                ultimo_id
            )

        except FloodWaitError as error:

            print()
            print(
                f"FloodWait: aguardando "
                f"{error.seconds} segundos."
            )

            continuar = await esperar_com_parada(
                error.seconds
            )

            if not continuar:
                return False

            return False

        except Exception as error:

            print()
            print(
                f"  ✗ Erro no ID "
                f"{primeiro_id}: {error}"
            )

            print(
                "  Será tentado novamente."
            )

            return False

    return True


# ============================================================
# SINCRONIZAÇÃO DE UM CANAL
# ============================================================

async def sincronizar_canal(
    client,
    chave_rota,
    origem,
    topico_id,
    destino,
    topico_destino_id,
    nome,
    progresso
):

    ultimo_id = obter_last_id(
        progresso,
        chave_rota
    )

    if ultimo_id is None:

        await inicializar_canal(
            client,
            chave_rota,
            origem,
            topico_id,
            nome,
            progresso
        )

        return

    mensagens = await buscar_mensagens_novas(
        client,
        origem,
        ultimo_id,
        topico_id
    )

    if not mensagens:
        return

    print(
        f"[{nome}] "
        f"{len(mensagens)} nova(s) mensagem(ns)."
    )

    await processar_mensagens(
        client,
        chave_rota,
        destino,
        topico_destino_id,
        mensagens,
        progresso
    )


# ============================================================
# MAIN
# ============================================================

async def main():

    print()
    print("=" * 60)
    print(" SINCRONIZADOR TELEGRAM")
    print("=" * 60)
    print()

    if not CHANNELS:

        raise RuntimeError(
            "Nenhuma rota configurada em channels.json."
        )

    if TAMANHO_LOTE <= 0:

        raise RuntimeError(
            "TAMANHO_LOTE precisa ser maior que zero."
        )

    if INTERVALO <= 0:

        raise RuntimeError(
            "INTERVALO precisa ser maior que zero."
        )

    limpar_pedido_parada()

    progresso = carregar_progresso()

    client = TelegramClient(
        SESSION_FILE,
        API_ID,
        API_HASH
    )

    await client.start()

    print(
        "Conectado ao Telegram."
    )

    print(
        f"Rotas configuradas: {len(CHANNELS)}"
    )

    print()

    try:

        while not parada_solicitada():

            for chave_rota, dados in CHANNELS.items():

                if parada_solicitada():
                    break

                await sincronizar_canal(
                    client,
                    chave_rota,
                    dados["source_id"],
                    dados.get("topic_id"),
                    dados["target_id"],
                    dados.get("target_topic_id"),
                    dados["name"],
                    progresso
                )

            if parada_solicitada():
                break

            continuar = await esperar_com_parada(
                INTERVALO
            )

            if not continuar:
                break

    finally:

        await client.disconnect()
        limpar_pedido_parada()

        print()
        print(
            "Sincronização encerrada."
        )

        print(
            "Conexão encerrada."
        )


if __name__ == "__main__":

    try:

        asyncio.run(main())

    except KeyboardInterrupt:

        print()
        print(
            "Programa encerrado."
        )

    except Exception as error:

        print()
        print("=" * 60)
        print("ERRO")
        print("=" * 60)
        print()
        print(error)
        print()

        raise
