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
    HISTORICO_PROGRESS_FILE,
    RETRO_STOP_FILE,
    carregar_canais,
    carregar_config_app,
    carregar_config_retro,
    carregar_json,
    normalizar_peer,
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
CONFIG_APP = carregar_config_app()

SESSION_FILE = str(resolver_session_path(CONFIG_APP["session_file"]))

LIMITE = 1000
A_PARTIR_DO_ID = 0
TAMANHO_LOTE = 100
TENTATIVAS_ERRO = 3


# ============================================================
# ARGUMENTOS
# ============================================================

def carregar_argumentos():

    parser = argparse.ArgumentParser(
        description=(
            "Sincronização retroativa de mensagens."
        )
    )

    parser.add_argument(
        "--canal",
        help=(
            "Chave da rota ou origem específica. "
            "Se omitido, processa todas."
        )
    )

    parser.add_argument(
        "--limite",
        type=int
    )

    parser.add_argument(
        "--a-partir-do-id",
        type=int
    )

    parser.add_argument(
        "--tamanho-lote",
        type=int
    )

    parser.add_argument(
        "--tentativas-erro",
        type=int
    )

    return parser.parse_args()


def aplicar_configuracao(args):

    global LIMITE
    global A_PARTIR_DO_ID
    global TAMANHO_LOTE
    global TENTATIVAS_ERRO

    config = carregar_config_retro()

    LIMITE = (
        args.limite
        if args.limite is not None
        else config["limite"]
    )

    A_PARTIR_DO_ID = (
        args.a_partir_do_id
        if args.a_partir_do_id is not None
        else config["a_partir_do_id"]
    )

    TAMANHO_LOTE = (
        args.tamanho_lote
        if args.tamanho_lote is not None
        else config["tamanho_lote"]
    )

    TENTATIVAS_ERRO = (
        args.tentativas_erro
        if args.tentativas_erro is not None
        else config["tentativas_erro"]
    )


# ============================================================
# PARADA CONTROLADA
# ============================================================

class ParadaSolicitada(Exception):
    pass


def parada_solicitada():

    return RETRO_STOP_FILE.exists()


def limpar_pedido_parada():

    try:
        RETRO_STOP_FILE.unlink()
    except FileNotFoundError:
        pass


def verificar_parada():

    if parada_solicitada():
        raise ParadaSolicitada


async def esperar_com_parada(segundos):

    restante = max(0, int(segundos))

    while restante > 0:

        verificar_parada()

        passo = min(1, restante)

        await asyncio.sleep(
            passo
        )

        restante -= passo

    verificar_parada()


# ============================================================
# PROGRESSO
# ============================================================

def carregar_progresso():

    dados = carregar_json(
        HISTORICO_PROGRESS_FILE,
        {}
    )

    if not isinstance(dados, dict):
        print(
            "Aviso: historico_progress.json inválido. "
            "Um progresso vazio será usado."
        )
        return {}

    return dados


def salvar_progresso(progresso):

    salvar_json(
        HISTORICO_PROGRESS_FILE,
        progresso
    )


def obter_canal_progress(
    progresso,
    chave_rota
):

    chave = str(chave_rota)

    if chave not in progresso:

        progresso[chave] = {
            "last_id": A_PARTIR_DO_ID,
            "failed_messages": []
        }

    dados = progresso[chave]

    if "last_id" not in dados:
        dados["last_id"] = A_PARTIR_DO_ID

    if "failed_messages" not in dados:
        dados["failed_messages"] = []

    return dados


def atualizar_last_id(
    progresso,
    chave_rota,
    last_id
):

    dados = obter_canal_progress(
        progresso,
        chave_rota
    )

    dados["last_id"] = last_id

    salvar_progresso(
        progresso
    )


# ============================================================
# REGISTRO DE FALHAS
# ============================================================

def registrar_falha(
    progresso,
    chave_rota,
    message_id,
    grouped_id=None,
    erro=""
):

    dados = obter_canal_progress(
        progresso,
        chave_rota
    )

    falhas = dados["failed_messages"]

    for item in falhas:

        if item["id"] == message_id:

            item["attempts"] = (
                item.get("attempts", 0) + 1
            )

            if erro:
                item["error"] = erro

            salvar_progresso(
                progresso
            )

            return

    falhas.append(
        {
            "id": message_id,
            "grouped_id": grouped_id,
            "attempts": 1,
            "error": erro
        }
    )

    salvar_progresso(
        progresso
    )


def remover_falha(
    progresso,
    chave_rota,
    message_id
):

    dados = obter_canal_progress(
        progresso,
        chave_rota
    )

    dados["failed_messages"] = [
        item
        for item in dados["failed_messages"]
        if item["id"] != message_id
    ]

    salvar_progresso(
        progresso
    )


# ============================================================
# FLOOD WAIT
# ============================================================

async def esperar_floodwait(error):

    segundos = error.seconds

    print()
    print("=" * 60)
    print("FLOOD WAIT")
    print("=" * 60)

    print(
        f"Telegram solicitou uma pausa de "
        f"{segundos} segundos."
    )

    print("Aguardando...")
    print()

    await esperar_com_parada(
        segundos
    )


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
    topico_destino_id=None
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
    topico_destino_id=None
):

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
            topico_destino_id
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
# BUSCA DE LOTE
# ============================================================

async def buscar_lote(
    client,
    origem,
    ultimo_id,
    quantidade,
    topico_id=None
):

    verificar_parada()

    mensagens = []

    async for mensagem in client.iter_messages(
        origem,
        limit=quantidade,
        min_id=ultimo_id,
        reverse=True,
        reply_to=topico_id
    ):

        verificar_parada()

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

            verificar_parada()

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

            adicionou = False

            for mensagem in extras:

                if mensagem.grouped_id != grouped_id:
                    return mensagens

                mensagens.append(
                    mensagem
                )

                proximo_id = mensagem.id
                adicionou = True

            if not adicionou:
                break

    return mensagens


# ============================================================
# PROCESSAMENTO DO LOTE
# ============================================================

async def processar_lote(
    client,
    chave_rota,
    destino,
    topico_destino_id,
    mensagens,
    progresso,
    processadas,
    total
):

    indice = 0

    while indice < len(mensagens):

        verificar_parada()

        mensagem = mensagens[indice]

        if not mensagem.media and not mensagem.message:

            atualizar_last_id(
                progresso,
                chave_rota,
                mensagem.id
            )

            processadas += 1

            print(
                f"Progresso: "
                f"{processadas}/"
                f"{total if total > 0 else '?'}",
                flush=True
            )

            indice += 1
            continue

        if mensagem.grouped_id:

            album = [mensagem]
            proximo = indice + 1

            while proximo < len(mensagens):

                outra = mensagens[proximo]

                if outra.grouped_id != mensagem.grouped_id:
                    break

                album.append(
                    outra
                )

                proximo += 1

            try:

                await enviar_album(
                    client,
                    destino,
                    album,
                    topico_destino_id
                )

                atualizar_last_id(
                    progresso,
                    chave_rota,
                    album[-1].id
                )

                for item in album:

                    remover_falha(
                        progresso,
                        chave_rota,
                        item.id
                    )

                processadas += len(album)

                print(
                    f"Progresso: "
                    f"{processadas}/"
                    f"{total if total > 0 else '?'}",
                    flush=True
                )

            except FloodWaitError as error:

                await esperar_floodwait(
                    error
                )

                continue

            except ParadaSolicitada:
                raise

            except Exception as error:

                print()
                print(
                    f"Erro no álbum "
                    f"{album[0].id}-"
                    f"{album[-1].id}: {error}"
                )

                for item in album:

                    registrar_falha(
                        progresso,
                        chave_rota,
                        item.id,
                        item.grouped_id,
                        str(error)
                    )

                atualizar_last_id(
                    progresso,
                    chave_rota,
                    album[-1].id
                )

                processadas += len(album)

            indice = proximo
            continue

        try:

            await enviar_mensagem(
                client,
                destino,
                mensagem,
                topico_destino_id
            )

            atualizar_last_id(
                progresso,
                chave_rota,
                mensagem.id
            )

            remover_falha(
                progresso,
                chave_rota,
                mensagem.id
            )

            processadas += 1

            print(
                f"Progresso: "
                f"{processadas}/"
                f"{total if total > 0 else '?'}",
                flush=True
            )

        except FloodWaitError as error:

            await esperar_floodwait(
                error
            )

            continue

        except ParadaSolicitada:
            raise

        except Exception as error:

            print()
            print(
                f"Erro na mensagem "
                f"{mensagem.id}: {error}"
            )

            registrar_falha(
                progresso,
                chave_rota,
                mensagem.id,
                None,
                str(error)
            )

            atualizar_last_id(
                progresso,
                chave_rota,
                mensagem.id
            )

            processadas += 1

        indice += 1

    return processadas


# ============================================================
# IMPORTAÇÃO PRINCIPAL
# ============================================================

async def importar_historico(
    client,
    chave_rota,
    origem,
    topico_id,
    destino,
    topico_destino_id,
    nome,
    progresso
):

    verificar_parada()

    print()
    print("=" * 60)
    print("IMPORTAÇÃO DE HISTÓRICO")
    print("=" * 60)

    print(f"Rota   : {nome}")
    print(f"Origem : {origem}")
    if topico_id is not None:
        print(f"Tópico : {topico_id}")
    print(f"Destino: {destino}")
    if topico_destino_id is not None:
        print(f"Tópico de destino: {topico_destino_id}")

    dados = obter_canal_progress(
        progresso,
        chave_rota
    )

    ultimo_id = dados["last_id"]

    if ultimo_id > A_PARTIR_DO_ID:

        print()
        print(
            f"Progresso encontrado: ID {ultimo_id}"
        )

        print(
            "Continuando a partir dele."
        )

    else:

        ultimo_id = A_PARTIR_DO_ID

        print()
        print(
            f"Iniciando a partir do ID {ultimo_id}."
        )

    if LIMITE == 0:

        print(
            "Limite: todo o histórico disponível."
        )

    else:

        print(
            f"Limite: {LIMITE} mensagens."
        )

    print(
        f"Lote: {TAMANHO_LOTE} mensagens."
    )

    print()

    processadas = 0

    while True:

        verificar_parada()

        if LIMITE == 0:

            quantidade = TAMANHO_LOTE

        else:

            restantes = LIMITE - processadas

            if restantes <= 0:
                break

            quantidade = min(
                TAMANHO_LOTE,
                restantes
            )

        mensagens = await buscar_lote(
            client,
            origem,
            ultimo_id,
            quantidade,
            topico_id
        )

        if not mensagens:
            break

        ultimo_id_anterior = ultimo_id

        processadas = await processar_lote(
            client,
            chave_rota,
            destino,
            topico_destino_id,
            mensagens,
            progresso,
            processadas,
            LIMITE if LIMITE > 0 else 0
        )

        ultimo_id = mensagens[-1].id

        if ultimo_id <= ultimo_id_anterior:

            print()
            print(
                "Erro: o ID não avançou."
            )

            break

        await esperar_com_parada(
            1
        )

    print()
    print("=" * 60)
    print("IMPORTAÇÃO PRINCIPAL CONCLUÍDA")
    print("=" * 60)

    print(
        f"Mensagens processadas: {processadas}"
    )

    print(
        f"Último ID: {ultimo_id}"
    )

    print()


# ============================================================
# RETENTATIVA DE FALHAS
# ============================================================

async def tentar_falhas(
    client,
    chave_rota,
    origem,
    destino,
    topico_destino_id,
    progresso
):

    verificar_parada()

    dados = obter_canal_progress(
        progresso,
        chave_rota
    )

    falhas = list(
        dados["failed_messages"]
    )

    if not falhas:

        print(
            "Nenhuma mensagem pendente."
        )

        return

    print()
    print("=" * 60)
    print("TENTATIVA DAS MENSAGENS COM ERRO")
    print("=" * 60)

    print(
        f"Pendentes: {len(falhas)}"
    )

    print()

    grupos = {}
    individuais = []

    for item in falhas:

        grouped_id = item.get(
            "grouped_id"
        )

        if grouped_id:

            grupos.setdefault(
                str(grouped_id),
                []
            ).append(item)

        else:

            individuais.append(
                item
            )

    for grouped_id, itens in grupos.items():

        verificar_parada()

        ids = [
            item["id"]
            for item in itens
        ]

        try:

            mensagens = await client.get_messages(
                origem,
                ids=ids
            )

            mensagens = [
                mensagem
                for mensagem in mensagens
                if mensagem
            ]

            if not mensagens:

                raise RuntimeError(
                    "Álbum não encontrado."
                )

            mensagens.sort(
                key=lambda mensagem: mensagem.id
            )

            await enviar_album(
                client,
                destino,
                mensagens,
                topico_destino_id
            )

            for mensagem in mensagens:

                remover_falha(
                    progresso,
                    chave_rota,
                    mensagem.id
                )

            print(
                f"✓ Álbum {grouped_id} recuperado."
            )

        except FloodWaitError as error:

            await esperar_floodwait(
                error
            )

        except ParadaSolicitada:
            raise

        except Exception as error:

            print(
                f"✗ Álbum {grouped_id}: "
                f"{error}"
            )

    for item in individuais:

        verificar_parada()

        message_id = item["id"]
        tentativas = item.get(
            "attempts",
            1
        )

        if tentativas >= TENTATIVAS_ERRO:

            print(
                f"✗ ID {message_id}: "
                f"limite de tentativas atingido."
            )

            continue

        try:

            mensagem = await client.get_messages(
                origem,
                ids=message_id
            )

            if not mensagem:

                raise RuntimeError(
                    "Mensagem não encontrada."
                )

            await enviar_mensagem(
                client,
                destino,
                mensagem,
                topico_destino_id
            )

            remover_falha(
                progresso,
                chave_rota,
                message_id
            )

            print(
                f"✓ ID {message_id} recuperado."
            )

        except FloodWaitError as error:

            await esperar_floodwait(
                error
            )

        except ParadaSolicitada:
            raise

        except Exception as error:

            item["attempts"] = (
                tentativas + 1
            )

            item["error"] = str(error)

            salvar_progresso(
                progresso
            )

            print(
                f"✗ ID {message_id}: "
                f"{error}"
            )

    dados = obter_canal_progress(
        progresso,
        chave_rota
    )

    pendentes = len(
        dados["failed_messages"]
    )

    print()

    if pendentes:

        print(
            f"{pendentes} mensagem(ns) "
            f"ainda pendente(s)."
        )

    else:

        print(
            "Todas as mensagens com erro "
            "foram recuperadas."
        )


# ============================================================
# SELEÇÃO DE CANAIS
# ============================================================

def selecionar_canais(canal_solicitado):

    if not canal_solicitado:
        return CHANNELS

    chave_solicitada = str(
        canal_solicitado
    ).strip()

    if chave_solicitada in CHANNELS:
        return {
            chave_solicitada: CHANNELS[chave_solicitada]
        }

    origem = normalizar_peer(chave_solicitada)

    rotas = {
        chave_rota: dados
        for chave_rota, dados in CHANNELS.items()
        if dados["source_id"] == origem
    }

    if not rotas:

        raise RuntimeError(
            f"A rota ou origem {canal_solicitado} "
            "não existe em channels.json."
        )

    return rotas


# ============================================================
# MAIN
# ============================================================

async def main():

    args = carregar_argumentos()
    aplicar_configuracao(args)

    print()
    print("=" * 60)
    print(" SINCRONIZADOR DE MENSAGENS ANTIGAS")
    print("=" * 60)
    print()

    if not CHANNELS:

        raise RuntimeError(
            "Nenhuma rota configurada em channels.json."
        )

    if LIMITE < 0:

        raise RuntimeError(
            "LIMITE não pode ser negativo."
        )

    if A_PARTIR_DO_ID < 0:

        raise RuntimeError(
            "A_PARTIR_DO_ID não pode ser negativo."
        )

    if TAMANHO_LOTE <= 0:

        raise RuntimeError(
            "TAMANHO_LOTE precisa ser maior que zero."
        )

    if TENTATIVAS_ERRO <= 0:

        raise RuntimeError(
            "TENTATIVAS_ERRO precisa ser maior que zero."
        )

    canais = selecionar_canais(
        args.canal
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

    me = await client.get_me()

    if me:

        nome = me.first_name or ""

        if me.last_name:
            nome += f" {me.last_name}"

        print(
            f"Usuário: {nome}"
        )

    print(
        f"Rotas selecionadas: {len(canais)}"
    )

    print()

    try:

        for chave_rota, dados in canais.items():

            verificar_parada()

            await importar_historico(
                client,
                chave_rota,
                dados["source_id"],
                dados.get("topic_id"),
                dados["target_id"],
                dados.get("target_topic_id"),
                dados["name"],
                progresso
            )

            await tentar_falhas(
                client,
                chave_rota,
                dados["source_id"],
                dados["target_id"],
                dados.get("target_topic_id"),
                progresso
            )

    except ParadaSolicitada:

        print()
        print(
            "Importação interrompida pelo usuário."
        )

    finally:

        await client.disconnect()
        limpar_pedido_parada()

        print()
        print(
            "Conexão encerrada."
        )


if __name__ == "__main__":

    try:

        asyncio.run(main())

    except KeyboardInterrupt:

        print()
        print(
            "Importação interrompida pelo usuário."
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
