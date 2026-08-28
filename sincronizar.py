import argparse
import asyncio
import sys
import os

from dotenv import load_dotenv
from telethon import TelegramClient, utils
from telethon.errors import FloodWaitError, MediaCaptionTooLongError
from telethon.tl.types import MessageMediaWebPage


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
    selecionar_rotas,
)
from media_transfer import (
    TransferenciaInterrompida,
    configurar_armazenamento_temporario,
    enviar_album_baixado,
    enviar_mensagem_baixada,
    tem_midia_baixavel,
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
configurar_armazenamento_temporario(CONFIG_APP)

TAMANHO_LOTE = CONFIG_NORMAL["tamanho_lote"]
INTERVALO = CONFIG_NORMAL["intervalo"]

SESSION_FILE = str(resolver_session_path(CONFIG_APP["session_file"]))


# ============================================================
# ARGUMENTOS
# ============================================================

def carregar_argumentos(argumentos=None):
    parser = argparse.ArgumentParser(
        description=(
            "Sincronização contínua de mensagens novas."
        )
    )

    parser.add_argument(
        "--canal",
        dest="canais",
        action="append",
        help=(
            "Chave de uma rota a sincronizar. Pode ser repetido para "
            "iniciar várias rotas. Se omitido, inicia todas."
        )
    )

    return parser.parse_args(argumentos)


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


def verificar_parada_transferencia():

    if parada_solicitada():
        raise TransferenciaInterrompida


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

async def enviar_texto_formatado(
    client,
    destino,
    texto,
    entidades=None,
    topico_destino_id=None,
    link_preview=True
):

    if not texto:
        return

    for trecho, entidades_trecho in utils.split_text(
        texto,
        entidades or [],
        limit=4096
    ):

        await client.send_message(
            destino,
            trecho,
            formatting_entities=entidades_trecho,
            parse_mode=None,
            link_preview=link_preview,
            reply_to=topico_destino_id
        )


def obter_texto_previa_link(mensagem):

    if mensagem.message:
        return mensagem.message

    pagina = getattr(
        mensagem.media,
        "webpage",
        None
    )

    return (
        getattr(pagina, "url", "")
        or getattr(pagina, "display_url", "")
    )


async def enviar_mensagem(
    client,
    destino,
    mensagem,
    topico_destino_id=None,
    baixar_reenviar=False,
    chave_rota=None
):

    if isinstance(
        mensagem.media,
        MessageMediaWebPage
    ):

        await enviar_texto_formatado(
            client,
            destino,
            obter_texto_previa_link(mensagem),
            mensagem.entities or [],
            topico_destino_id,
            link_preview=True
        )

        return

    if mensagem.media:

        if (
            baixar_reenviar
            and tem_midia_baixavel(mensagem)
        ):
            await enviar_mensagem_baixada(
                client,
                destino,
                mensagem,
                chave_rota,
                topico_destino_id,
                verificar_parada_transferencia
            )
            return

        try:

            await client.send_file(
                destino,
                mensagem.media,
                caption=mensagem.message or "",
                formatting_entities=mensagem.entities or [],
                parse_mode=None,
                reply_to=topico_destino_id
            )

        except MediaCaptionTooLongError:

            await client.send_file(
                destino,
                mensagem.media,
                caption="",
                reply_to=topico_destino_id
            )

            await enviar_texto_formatado(
                client,
                destino,
                mensagem.message or "",
                mensagem.entities or [],
                topico_destino_id,
                link_preview=False
            )

            print(
                f"  Aviso: legenda da mensagem "
                f"{mensagem.id} enviada como texto separado."
            )

        return

    if mensagem.message:

        await enviar_texto_formatado(
            client,
            destino,
            mensagem.message,
            mensagem.entities or [],
            topico_destino_id,
            link_preview=True
        )


async def enviar_album(
    client,
    destino,
    mensagens,
    topico_destino_id=None,
    baixar_reenviar=False,
    chave_rota=None
):

    if baixar_reenviar:
        await enviar_album_baixado(
            client,
            destino,
            mensagens,
            chave_rota,
            topico_destino_id,
            verificar_parada_transferencia
        )
        return

    arquivos = []
    legendas = []
    entidades = []
    mensagens_com_midia = []

    for mensagem in mensagens:

        if (
            not mensagem.media
            or isinstance(
                mensagem.media,
                MessageMediaWebPage
            )
        ):
            continue

        mensagens_com_midia.append(
            mensagem
        )

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

        await enviar_mensagem(
            client,
            destino,
            mensagens_com_midia[0],
            topico_destino_id,
            baixar_reenviar,
            chave_rota
        )

        return

    try:

        await client.send_file(
            destino,
            arquivos,
            caption=legendas,
            formatting_entities=entidades,
            parse_mode=None,
            reply_to=topico_destino_id
        )

    except MediaCaptionTooLongError:

        await client.send_file(
            destino,
            arquivos,
            reply_to=topico_destino_id
        )

        for mensagem in mensagens_com_midia:

            await enviar_texto_formatado(
                client,
                destino,
                mensagem.message or "",
                mensagem.entities or [],
                topico_destino_id,
                link_preview=False
            )

        print(
            "  Aviso: legendas longas do álbum "
            "enviadas como texto separado."
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
    baixar_reenviar,
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
                    topico_destino_id,
                    baixar_reenviar,
                    chave_rota
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
                    topico_destino_id,
                    baixar_reenviar,
                    chave_rota
                )

                print(
                    f"  ✓ {mensagem.id}"
                )

            atualizar_last_id(
                progresso,
                chave_rota,
                ultimo_id
            )

        except TransferenciaInterrompida:

            print(
                "  Transferência interrompida. O temporário será "
                "reutilizado na próxima execução."
            )

            return False

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
    baixar_reenviar,
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
        baixar_reenviar,
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

    argumentos = carregar_argumentos()

    if not CHANNELS:

        raise RuntimeError(
            "Nenhuma rota configurada em channels.json."
        )

    canais_ativos = selecionar_rotas(
        CHANNELS,
        argumentos.canais
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

    print(
        f"Rotas ativas nesta execução: {len(canais_ativos)}"
    )

    for dados in canais_ativos.values():
        print(
            f"  • {dados['name']}"
        )

    rotas_reupload = sum(
        1
        for dados in canais_ativos.values()
        if dados.get("download_reupload", False)
    )

    if rotas_reupload:
        print(
            f"Rotas com download e reenvio: {rotas_reupload}"
        )

    print()

    try:

        while not parada_solicitada():

            for chave_rota, dados in canais_ativos.items():

                if parada_solicitada():
                    break

                await sincronizar_canal(
                    client,
                    chave_rota,
                    dados["source_id"],
                    dados.get("topic_id"),
                    dados["target_id"],
                    dados.get("target_topic_id"),
                    dados.get("download_reupload", False),
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
