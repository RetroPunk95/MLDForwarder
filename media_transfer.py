import asyncio
import hashlib
import os
import re
import shutil
from collections import deque
from dataclasses import dataclass
from pathlib import Path

try:
    import cryptg as _cryptg

    CRYPTG_DISPONIVEL = True
except ImportError:
    _cryptg = None
    CRYPTG_DISPONIVEL = False

from telethon import helpers, utils
from telethon.errors import MediaCaptionTooLongError
from telethon.tl import functions, types

from config_utils import BASE_DIR, resolver_temp_media_dir


TEMP_MEDIA_DIR = BASE_DIR / "temp_transferencias"
LIMITE_TEMPORARIO_BYTES = 0
NOME_MARCADOR_TEMP = ".mldforwarder-managed"
CONTEUDO_MARCADOR_TEMP = "MLDForwarder temporary storage\n"

LIMITE_UPLOAD_GRATUITO = 2 * 1024 ** 3
LIMITE_UPLOAD_PREMIUM = 4 * 1024 ** 3
MARGEM_DISCO = 64 * 1024 ** 2
LIMITE_LEGENDA_SEGURO = 1024
TAMANHO_PARTE_TRANSFERENCIA = 512 * 1024
PARALELISMO_TRANSFERENCIA = 4
LIMITE_ARQUIVO_GRANDE = 10 * 1024 ** 2


class TransferenciaInterrompida(Exception):
    """Interrompe download/upload sem descartar o arquivo temporário."""


@dataclass
class MidiaTemporaria:
    mensagem: object
    caminho: Path
    diretorio: Path
    tamanho: int
    mime_type: str | None
    attributes: list
    foto: bool
    force_document: bool
    voice_note: bool
    video_note: bool
    supports_streaming: bool
    spoiler: bool
    thumb: Path | None


class ProgressoPercentual:

    def __init__(self, rotulo, verificar_parada=None, passo=25):
        self.rotulo = rotulo
        self.verificar_parada = verificar_parada
        self.passo = passo
        self.proximo = passo

    def atualizar(self, atual, total):

        _verificar_parada(self.verificar_parada)

        if not total:
            return

        percentual = min(100, int((atual / total) * 100))

        if percentual < self.proximo and percentual < 100:
            return

        print(
            f"    {self.rotulo}: {percentual}%",
            flush=True
        )

        while self.proximo <= percentual:
            self.proximo += self.passo


def tem_midia_baixavel(mensagem):
    return isinstance(
        getattr(mensagem, "media", None),
        (types.MessageMediaPhoto, types.MessageMediaDocument)
    )


def _verificar_parada(callback):

    if callback is None:
        return

    resultado = callback()

    if resultado is False:
        raise TransferenciaInterrompida


def _informar_modo_rapido(client):

    if getattr(client, "_mldtools_transferencia_rapida", False):
        return

    setattr(client, "_mldtools_transferencia_rapida", True)
    acelerador = (
        "cryptg ativo"
        if CRYPTG_DISPONIVEL
        else "cryptg indisponível"
    )

    print(
        "    Modo rápido: até "
        f"{PARALELISMO_TRANSFERENCIA} partes simultâneas de 512 KB; "
        f"{acelerador}.",
        flush=True
    )


async def _cancelar_tarefas(tarefas):

    tarefas = list(tarefas)

    for tarefa in tarefas:

        if not tarefa.done():
            tarefa.cancel()

    if tarefas:
        await asyncio.gather(
            *tarefas,
            return_exceptions=True
        )


async def _executar_em_paralelo(corrotinas):
    tarefas = [
        asyncio.create_task(corrotina)
        for corrotina in corrotinas
    ]

    try:
        return list(await asyncio.gather(*tarefas))

    except BaseException:
        await _cancelar_tarefas(tarefas)
        raise


def formatar_tamanho(tamanho):

    valor = float(max(0, tamanho))

    for unidade in ("B", "KB", "MB", "GB", "TB"):

        if valor < 1024 or unidade == "TB":
            return f"{valor:.1f} {unidade}"

        valor /= 1024


def configurar_armazenamento_temporario(config_app=None):
    """Aplica as preferências gerais carregadas de app_config.json."""
    global TEMP_MEDIA_DIR, LIMITE_TEMPORARIO_BYTES

    config_app = config_app or {}
    TEMP_MEDIA_DIR = resolver_temp_media_dir(
        config_app.get("temp_parent_dir", "")
    )

    try:
        limite_gb = float(
            config_app.get("limite_temporario_gb", 0)
        )
    except (TypeError, ValueError) as erro:
        raise RuntimeError(
            "O limite temporário precisa ser um número."
        ) from erro

    if limite_gb < 0:
        raise RuntimeError(
            "O limite temporário não pode ser negativo."
        )

    LIMITE_TEMPORARIO_BYTES = int(limite_gb * 1024 ** 3)

    return TEMP_MEDIA_DIR


def _caminho_marcador_temp():
    return TEMP_MEDIA_DIR / NOME_MARCADOR_TEMP


def _estrutura_legada_compativel():
    """Reconhece exclusivamente a árvore criada pela versão 2.9.0."""
    if not TEMP_MEDIA_DIR.exists():
        return True

    for rota in TEMP_MEDIA_DIR.iterdir():

        if (
            rota.is_symlink()
            or not rota.is_dir()
            or not re.fullmatch(r"[0-9a-f]{16}", rota.name)
        ):
            return False

        for mensagem in rota.iterdir():

            if (
                mensagem.is_symlink()
                or not mensagem.is_dir()
                or not mensagem.name.isdigit()
            ):
                return False

            for item in mensagem.iterdir():

                if item.is_symlink() or not item.is_file():
                    return False

    return True


def preparar_raiz_temporaria():
    """
    Cria/valida a pasta administrada. Uma pasta já existente sem marcador
    só é adotada se tiver exatamente o formato legado do MLDForwarder.
    """
    if TEMP_MEDIA_DIR.exists() and not TEMP_MEDIA_DIR.is_dir():
        raise RuntimeError(
            f"O caminho temporário não é uma pasta: {TEMP_MEDIA_DIR}"
        )

    TEMP_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    marcador = _caminho_marcador_temp()

    if marcador.exists():

        try:
            conteudo = marcador.read_text(encoding="utf-8")
        except OSError as erro:
            raise RuntimeError(
                "Não foi possível validar a pasta temporária."
            ) from erro

        if conteudo != CONTEUDO_MARCADOR_TEMP:
            raise RuntimeError(
                "A pasta temp_transferencias possui um marcador inválido. "
                "Escolha outra pasta-pai."
            )

        return TEMP_MEDIA_DIR

    if not _estrutura_legada_compativel():
        raise RuntimeError(
            "A subpasta temp_transferencias já contém arquivos que não "
            "parecem pertencer ao MLD Tools. Escolha outra pasta-pai "
            "para evitar alterações em dados alheios."
        )

    marcador.write_text(
        CONTEUDO_MARCADOR_TEMP,
        encoding="utf-8"
    )

    return TEMP_MEDIA_DIR


def _marcador_temp_valido():
    marcador = _caminho_marcador_temp()

    try:
        return (
            marcador.is_file()
            and marcador.read_text(encoding="utf-8")
            == CONTEUDO_MARCADOR_TEMP
        )
    except OSError:
        return False


def uso_armazenamento_temporario():
    if not TEMP_MEDIA_DIR.exists():
        return 0

    total = 0

    for atual, diretorios, arquivos in os.walk(
        TEMP_MEDIA_DIR,
        followlinks=False
    ):
        atual = Path(atual)
        diretorios[:] = [
            nome
            for nome in diretorios
            if not (atual / nome).is_symlink()
        ]

        for nome in arquivos:
            caminho = atual / nome

            if caminho == _caminho_marcador_temp():
                continue

            if caminho.is_symlink():
                continue

            try:
                total += caminho.stat().st_size
            except OSError:
                continue

    return total


def quantidade_arquivos_temporarios():
    if not TEMP_MEDIA_DIR.exists():
        return 0

    total = 0

    for atual, diretorios, arquivos in os.walk(
        TEMP_MEDIA_DIR,
        followlinks=False
    ):
        atual = Path(atual)
        diretorios[:] = [
            nome
            for nome in diretorios
            if not (atual / nome).is_symlink()
        ]

        for nome in arquivos:
            caminho = atual / nome

            if (
                caminho != _caminho_marcador_temp()
                and not caminho.is_symlink()
            ):
                total += 1

    return total


def estado_armazenamento_temporario():
    pai = TEMP_MEDIA_DIR.parent

    if not pai.exists() or not pai.is_dir():
        raise RuntimeError(
            f"A pasta-pai temporária não existe: {pai}"
        )

    ancora = TEMP_MEDIA_DIR if TEMP_MEDIA_DIR.exists() else pai

    return {
        "pasta": TEMP_MEDIA_DIR,
        "uso": uso_armazenamento_temporario(),
        "arquivos": quantidade_arquivos_temporarios(),
        "livre": shutil.disk_usage(ancora).free,
        "limite": LIMITE_TEMPORARIO_BYTES,
    }


def limpar_armazenamento_temporario():
    """Remove somente o conteúdo da subpasta administrada e marcada."""
    if not TEMP_MEDIA_DIR.exists():
        return 0

    preparar_raiz_temporaria()

    if not _marcador_temp_valido():
        raise RuntimeError(
            "A limpeza foi cancelada porque a pasta não pôde ser validada."
        )

    removidos = uso_armazenamento_temporario()
    marcador = _caminho_marcador_temp()

    for item in TEMP_MEDIA_DIR.iterdir():

        if item == marcador:
            continue

        if item.is_symlink() or item.is_file():
            item.unlink()
        elif item.is_dir():
            shutil.rmtree(item)
        else:
            raise RuntimeError(
                f"Item temporário desconhecido; limpeza cancelada: {item}"
            )

    marcador.unlink()
    TEMP_MEDIA_DIR.rmdir()

    return removidos


def _nome_original(mensagem):

    arquivo = getattr(mensagem, "file", None)
    nome = getattr(arquivo, "name", None)

    documento = getattr(
        getattr(mensagem, "media", None),
        "document",
        None
    )

    if not nome and documento:

        for atributo in getattr(documento, "attributes", []) or []:

            if isinstance(atributo, types.DocumentAttributeFilename):
                nome = atributo.file_name
                break

    extensao = getattr(arquivo, "ext", None) or ""

    if not nome:

        if isinstance(
            getattr(mensagem, "media", None),
            types.MessageMediaPhoto
        ):
            extensao = extensao or ".jpg"

        nome = f"mensagem_{mensagem.id}{extensao or '.bin'}"

    return str(nome)


def _nome_seguro(nome):

    nome = Path(str(nome).replace("\\", "/")).name
    nome = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", nome)
    nome = nome.rstrip(" .") or "arquivo.bin"

    base = Path(nome).stem
    extensao = Path(nome).suffix

    reservados = {
        "CON", "PRN", "AUX", "NUL",
        *(f"COM{numero}" for numero in range(1, 10)),
        *(f"LPT{numero}" for numero in range(1, 10)),
    }

    if base.upper() in reservados:
        base = f"_{base}"

    maximo_base = max(1, 180 - len(extensao))

    return f"{base[:maximo_base]}{extensao}"


def _diretorio_mensagem(chave_rota, mensagem_id):

    identificador = hashlib.sha256(
        str(chave_rota).encode("utf-8")
    ).hexdigest()[:16]

    return TEMP_MEDIA_DIR / identificador / str(int(mensagem_id))


def _tamanho_esperado(mensagem):

    arquivo = getattr(mensagem, "file", None)
    tamanho = getattr(arquivo, "size", None)

    if tamanho is None:

        documento = getattr(
            getattr(mensagem, "media", None),
            "document",
            None
        )
        tamanho = getattr(documento, "size", None)

    return int(tamanho) if tamanho is not None else None


def _metadados_midia(mensagem, caminho):

    media = mensagem.media
    documento = getattr(media, "document", None)
    attributes = list(
        getattr(documento, "attributes", []) or []
    )
    mime_type = getattr(documento, "mime_type", None)

    video = next(
        (
            atributo
            for atributo in attributes
            if isinstance(atributo, types.DocumentAttributeVideo)
        ),
        None
    )
    audio = next(
        (
            atributo
            for atributo in attributes
            if isinstance(atributo, types.DocumentAttributeAudio)
        ),
        None
    )
    foto = isinstance(media, types.MessageMediaPhoto)
    force_document = (
        isinstance(media, types.MessageMediaDocument)
        and not video
        and not audio
    )

    return MidiaTemporaria(
        mensagem=mensagem,
        caminho=caminho,
        diretorio=caminho.parent,
        tamanho=caminho.stat().st_size,
        mime_type=mime_type,
        attributes=attributes,
        foto=foto,
        force_document=force_document,
        voice_note=bool(getattr(audio, "voice", False)),
        video_note=bool(getattr(video, "round_message", False)),
        supports_streaming=bool(
            getattr(video, "supports_streaming", False)
        ),
        spoiler=bool(getattr(media, "spoiler", False)),
        thumb=(
            caminho.parent / "miniatura.jpg"
            if (caminho.parent / "miniatura.jpg").exists()
            else None
        ),
    )


async def _garantir_miniatura(
    client,
    mensagem,
    midia,
    verificar_parada=None
):

    if midia.foto or midia.thumb is not None:
        return midia

    documento = getattr(mensagem.media, "document", None)
    thumbs = getattr(documento, "thumbs", None) or []

    if not thumbs:
        return midia

    _verificar_parada(verificar_parada)
    caminho = midia.diretorio / "miniatura.jpg"

    try:
        _validar_armazenamento(0, "miniatura")
        resultado = await client.download_media(
            mensagem,
            file=str(caminho),
            thumb=-1
        )

        if resultado and caminho.exists() and caminho.stat().st_size:
            _validar_armazenamento(0, "miniatura")
            midia.thumb = caminho

    except Exception as erro:

        if caminho.exists():

            try:
                caminho.unlink()
            except OSError:
                pass

        print(
            f"    Aviso: miniatura do ID {mensagem.id} "
            f"não pôde ser preservada: {erro}",
            flush=True
        )

    return midia


async def _finalizar_midia(
    client,
    mensagem,
    caminho,
    verificar_parada=None
):
    midia = _metadados_midia(mensagem, caminho)

    return await _garantir_miniatura(
        client,
        mensagem,
        midia,
        verificar_parada
    )


def _validar_armazenamento(faltam, contexto="arquivo"):
    pai = TEMP_MEDIA_DIR.parent

    if not pai.exists() or not pai.is_dir():
        raise RuntimeError(
            f"A pasta-pai temporária não existe: {pai}"
        )

    ancora = TEMP_MEDIA_DIR if TEMP_MEDIA_DIR.exists() else pai
    livre = shutil.disk_usage(ancora).free
    necessario = max(0, int(faltam)) + MARGEM_DISCO

    if livre < necessario:
        raise RuntimeError(
            f"Espaço insuficiente para o {contexto}. "
            f"Necessário agora: {formatar_tamanho(necessario)}; "
            f"disponível: {formatar_tamanho(livre)}."
        )

    if LIMITE_TEMPORARIO_BYTES <= 0:
        return

    uso = uso_armazenamento_temporario()
    uso_final = uso + max(0, int(faltam))

    if uso_final <= LIMITE_TEMPORARIO_BYTES:
        return

    raise RuntimeError(
        f"O {contexto} ultrapassaria o limite temporário configurado. "
        f"Em uso: {formatar_tamanho(uso)}; "
        f"novo download: {formatar_tamanho(faltam)}; "
        f"limite: {formatar_tamanho(LIMITE_TEMPORARIO_BYTES)}."
    )


async def _conta_premium(client):

    cache = getattr(client, "_mldforwarder_premium", None)

    if cache is not None:
        return bool(cache)

    usuario = await client.get_me()
    premium = bool(getattr(usuario, "premium", False))
    setattr(client, "_mldforwarder_premium", premium)

    return premium


async def _validar_limite_upload(client, tamanho):

    if tamanho > LIMITE_UPLOAD_PREMIUM:
        raise RuntimeError(
            "O arquivo ultrapassa o limite de upload de 4 GB do Telegram."
        )

    if (
        tamanho > LIMITE_UPLOAD_GRATUITO
        and not await _conta_premium(client)
    ):
        raise RuntimeError(
            "O arquivo ultrapassa 2 GB. A conta conectada precisa ser "
            "Telegram Premium para reenviá-lo."
        )


async def _fechar_iterador_download(iterador):
    fechar = getattr(iterador, "aclose", None)

    if fechar is None:
        fechar = getattr(iterador, "close", None)

    if fechar is not None:

        try:
            await fechar()
        except AttributeError:
            # O cancelamento pode ocorrer enquanto o iterador do Telethon
            # ainda está criando o sender e antes de inicializar seus campos.
            pass


async def _baixar_parte(
    client,
    media,
    offset,
    tamanho_total,
    semaforo,
    verificar_parada=None
):

    async with semaforo:
        _verificar_parada(verificar_parada)
        iterador = client.iter_download(
            media,
            offset=offset,
            limit=1,
            chunk_size=TAMANHO_PARTE_TRANSFERENCIA,
            request_size=TAMANHO_PARTE_TRANSFERENCIA,
            file_size=tamanho_total
        )

        try:

            try:
                trecho = await iterador.__anext__()
            except StopAsyncIteration:
                trecho = b""

            _verificar_parada(verificar_parada)
            return bytes(trecho)

        finally:
            await _fechar_iterador_download(iterador)


async def _baixar_em_partes(
    client,
    media,
    arquivo,
    offset,
    tamanho_total,
    progresso,
    verificar_parada=None,
    semaforo=None
):
    semaforo = semaforo or asyncio.Semaphore(
        PARALELISMO_TRANSFERENCIA
    )
    pendentes = deque()
    proximo_offset = offset

    def agendar():
        nonlocal proximo_offset

        while (
            proximo_offset < tamanho_total
            and len(pendentes) < PARALELISMO_TRANSFERENCIA
        ):
            inicio = proximo_offset
            tarefa = asyncio.create_task(
                _baixar_parte(
                    client,
                    media,
                    inicio,
                    tamanho_total,
                    semaforo,
                    verificar_parada
                )
            )
            pendentes.append((inicio, tarefa))
            proximo_offset += TAMANHO_PARTE_TRANSFERENCIA

    agendar()

    try:

        while pendentes:
            inicio, tarefa = pendentes.popleft()
            trecho = await tarefa
            esperado = min(
                TAMANHO_PARTE_TRANSFERENCIA,
                tamanho_total - inicio
            )

            if len(trecho) != esperado:
                raise RuntimeError(
                    "O Telegram retornou uma parte incompleta no offset "
                    f"{inicio}: esperados {esperado} bytes, "
                    f"recebidos {len(trecho)}."
                )

            arquivo.write(trecho)
            offset += len(trecho)
            progresso.atualizar(offset, tamanho_total)
            agendar()

        return offset

    except BaseException:
        await _cancelar_tarefas(
            tarefa
            for _, tarefa in pendentes
        )
        raise


async def _enviar_parte(
    client,
    requisicao,
    semaforo,
    verificar_parada=None
):

    async with semaforo:
        _verificar_parada(verificar_parada)
        resultado = await client(requisicao)
        _verificar_parada(verificar_parada)

        if not resultado:
            raise RuntimeError(
                "O Telegram não confirmou uma parte do upload."
            )

        return resultado


async def _upload_arquivo_acelerado(
    client,
    caminho,
    tamanho,
    progresso=None,
    verificar_parada=None,
    semaforo=None
):
    caminho = Path(caminho)
    tamanho = int(tamanho)

    if tamanho <= 0:
        return await client.upload_file(
            str(caminho),
            part_size_kb=512,
            file_size=tamanho,
            file_name=caminho.name,
            progress_callback=progresso
        )

    semaforo = semaforo or asyncio.Semaphore(
        PARALELISMO_TRANSFERENCIA
    )
    arquivo_id = helpers.generate_random_long()
    quantidade_partes = (
        tamanho + TAMANHO_PARTE_TRANSFERENCIA - 1
    ) // TAMANHO_PARTE_TRANSFERENCIA
    arquivo_grande = tamanho > LIMITE_ARQUIVO_GRANDE
    soma_md5 = hashlib.md5()
    pendentes = deque()
    confirmados = 0

    async def confirmar_primeira():
        nonlocal confirmados
        tarefa, tamanho_parte = pendentes.popleft()
        await tarefa
        confirmados += tamanho_parte

        if progresso is not None:
            progresso(confirmados, tamanho)

    try:

        with caminho.open("rb") as arquivo:

            for indice in range(quantidade_partes):
                _verificar_parada(verificar_parada)
                trecho = arquivo.read(TAMANHO_PARTE_TRANSFERENCIA)
                esperado = min(
                    TAMANHO_PARTE_TRANSFERENCIA,
                    tamanho - indice * TAMANHO_PARTE_TRANSFERENCIA
                )

                if len(trecho) != esperado:
                    raise RuntimeError(
                        f"O arquivo {caminho.name} mudou durante o upload."
                    )

                if not arquivo_grande:
                    soma_md5.update(trecho)

                if arquivo_grande:
                    requisicao = functions.upload.SaveBigFilePartRequest(
                        arquivo_id,
                        indice,
                        quantidade_partes,
                        trecho
                    )
                else:
                    requisicao = functions.upload.SaveFilePartRequest(
                        arquivo_id,
                        indice,
                        trecho
                    )

                pendentes.append(
                    (
                        asyncio.create_task(
                            _enviar_parte(
                                client,
                                requisicao,
                                semaforo,
                                verificar_parada
                            )
                        ),
                        len(trecho)
                    )
                )

                if len(pendentes) >= PARALELISMO_TRANSFERENCIA:
                    await confirmar_primeira()

            while pendentes:
                await confirmar_primeira()

    except BaseException:
        await _cancelar_tarefas(
            tarefa
            for tarefa, _ in pendentes
        )
        raise

    if arquivo_grande:
        return types.InputFileBig(
            arquivo_id,
            quantidade_partes,
            caminho.name
        )

    return types.InputFile(
        arquivo_id,
        quantidade_partes,
        caminho.name,
        soma_md5.hexdigest()
    )


async def baixar_midia(
    client,
    mensagem,
    chave_rota,
    verificar_parada=None,
    _semaforo_rede=None
):

    if not tem_midia_baixavel(mensagem):
        raise RuntimeError(
            f"A mensagem {mensagem.id} não contém um arquivo baixável."
        )

    _informar_modo_rapido(client)

    tamanho_esperado = _tamanho_esperado(mensagem)

    if tamanho_esperado is not None:
        await _validar_limite_upload(
            client,
            tamanho_esperado
        )

    preparar_raiz_temporaria()

    diretorio = _diretorio_mensagem(
        chave_rota,
        mensagem.id
    )
    diretorio.mkdir(parents=True, exist_ok=True)

    caminho = diretorio / _nome_seguro(
        _nome_original(mensagem)
    )
    parcial = caminho.with_suffix(caminho.suffix + ".part")

    if caminho.exists():

        tamanho_atual = caminho.stat().st_size

        if (
            tamanho_esperado is None
            or tamanho_atual == tamanho_esperado
        ):
            print(
                f"    Reutilizando temporário do ID {mensagem.id}: "
                f"{caminho.name}",
                flush=True
            )
            return await _finalizar_midia(
                client,
                mensagem,
                caminho,
                verificar_parada
            )

        caminho.unlink()

    offset = parcial.stat().st_size if parcial.exists() else 0

    if tamanho_esperado is not None and offset > tamanho_esperado:
        parcial.unlink()
        offset = 0

    if tamanho_esperado is not None and offset == tamanho_esperado:
        os.replace(parcial, caminho)
        return await _finalizar_midia(
            client,
            mensagem,
            caminho,
            verificar_parada
        )

    faltam = (
        tamanho_esperado - offset
        if tamanho_esperado is not None
        else MARGEM_DISCO
    )
    _validar_armazenamento(faltam)
    _verificar_parada(verificar_parada)

    tamanho_texto = (
        formatar_tamanho(tamanho_esperado)
        if tamanho_esperado is not None
        else "tamanho desconhecido"
    )
    acao = "Retomando" if offset else "Baixando"

    print(
        f"    {acao} ID {mensagem.id}: {caminho.name} "
        f"({tamanho_texto})",
        flush=True
    )

    progresso = ProgressoPercentual(
        f"Download ID {mensagem.id}",
        verificar_parada
    )

    with parcial.open("ab") as arquivo:

        if tamanho_esperado is not None:
            offset = await _baixar_em_partes(
                client,
                mensagem.media,
                arquivo,
                offset,
                tamanho_esperado,
                progresso,
                verificar_parada,
                _semaforo_rede
            )
        else:

            async for trecho in client.iter_download(
                mensagem.media,
                offset=offset,
                chunk_size=TAMANHO_PARTE_TRANSFERENCIA,
                request_size=TAMANHO_PARTE_TRANSFERENCIA,
                file_size=tamanho_esperado
            ):
                _verificar_parada(verificar_parada)
                _validar_armazenamento(
                    len(trecho),
                    "arquivo de tamanho desconhecido"
                )

                arquivo.write(bytes(trecho))
                offset += len(trecho)
                progresso.atualizar(offset, offset)

        arquivo.flush()
        os.fsync(arquivo.fileno())

    if (
        tamanho_esperado is not None
        and parcial.stat().st_size != tamanho_esperado
    ):
        raise RuntimeError(
            f"Download incompleto no ID {mensagem.id}: "
            f"esperado {formatar_tamanho(tamanho_esperado)}, "
            f"recebido {formatar_tamanho(parcial.stat().st_size)}."
        )

    os.replace(parcial, caminho)

    return await _finalizar_midia(
        client,
        mensagem,
        caminho,
        verificar_parada
    )


def _legenda_cabe(texto, entidades):

    if not texto:
        return True

    try:
        partes = list(
            utils.split_text(
                texto,
                entidades or [],
                limit=LIMITE_LEGENDA_SEGURO
            )
        )
    except Exception:
        return False

    return len(partes) <= 1


async def _enviar_texto_formatado(
    client,
    destino,
    texto,
    entidades,
    topico_destino_id
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
            link_preview=False,
            reply_to=topico_destino_id
        )


def _parametros_midia(midia, thumb=None):
    return {
        "force_document": midia.force_document,
        "mime_type": midia.mime_type,
        "file_size": midia.tamanho,
        "attributes": midia.attributes or None,
        "voice_note": midia.voice_note,
        "video_note": midia.video_note,
        "supports_streaming": midia.supports_streaming,
        "thumb": thumb,
    }


def limpar_midia_temporaria(midia):

    diretorio = midia.diretorio.resolve()
    raiz = TEMP_MEDIA_DIR.resolve()

    if not _marcador_temp_valido():
        raise RuntimeError(
            "A limpeza foi cancelada porque a pasta temporária "
            "não pôde ser validada."
        )

    if diretorio == raiz or raiz not in diretorio.parents:
        raise RuntimeError(
            "Diretório temporário inválido; a limpeza foi cancelada."
        )

    if diretorio.exists():

        for item in diretorio.iterdir():

            if item.is_file():
                item.unlink()

        diretorio.rmdir()

    pai = diretorio.parent

    if pai != raiz and pai.exists() and not any(pai.iterdir()):
        pai.rmdir()

    marcador = _caminho_marcador_temp()

    if (
        raiz.exists()
        and not any(
            item != marcador
            for item in raiz.iterdir()
        )
    ):
        marcador.unlink()
        raiz.rmdir()


async def enviar_mensagem_baixada(
    client,
    destino,
    mensagem,
    chave_rota,
    topico_destino_id=None,
    verificar_parada=None
):

    midia = await baixar_midia(
        client,
        mensagem,
        chave_rota,
        verificar_parada
    )
    await _validar_limite_upload(client, midia.tamanho)

    legenda = mensagem.message or ""
    entidades = mensagem.entities or []
    legenda_separada = not _legenda_cabe(
        legenda,
        entidades
    )
    progresso = ProgressoPercentual(
        f"Upload ID {mensagem.id}",
        verificar_parada
    )

    print(
        f"    Reenviando ID {mensagem.id}: {midia.caminho.name}",
        flush=True
    )

    arquivo = await _upload_arquivo_acelerado(
        client,
        midia.caminho,
        midia.tamanho,
        progresso.atualizar,
        verificar_parada
    )
    thumb = None

    if midia.thumb:
        thumb = await client.upload_file(
            str(midia.thumb),
            part_size_kb=512
        )

    parametros_midia = _parametros_midia(midia, thumb)

    try:
        await client.send_file(
            destino,
            arquivo,
            caption="" if legenda_separada else legenda,
            formatting_entities=(
                None if legenda_separada else entidades
            ),
            parse_mode=None,
            reply_to=topico_destino_id,
            **parametros_midia
        )

    except MediaCaptionTooLongError:
        legenda_separada = True
        await client.send_file(
            destino,
            arquivo,
            caption="",
            parse_mode=None,
            reply_to=topico_destino_id,
            **parametros_midia
        )

    if legenda_separada:
        await _enviar_texto_formatado(
            client,
            destino,
            legenda,
            entidades,
            topico_destino_id
        )
        print(
            f"    Aviso: legenda do ID {mensagem.id} "
            "enviada como texto separado.",
            flush=True
        )

    limpar_midia_temporaria(midia)


async def _upload_album(
    client,
    destino,
    midias,
    verificar_parada=None
):

    peer = await client.get_input_entity(destino)
    resultado = []
    total = len(midias)
    semaforo = asyncio.Semaphore(
        PARALELISMO_TRANSFERENCIA
    )

    for midia in midias:
        _verificar_parada(verificar_parada)
        await _validar_limite_upload(client, midia.tamanho)

    async def enviar_arquivo(indice, midia):
        progresso = ProgressoPercentual(
            f"Upload do álbum {indice}/{total}",
            verificar_parada
        )

        return await _upload_arquivo_acelerado(
            client,
            midia.caminho,
            midia.tamanho,
            progresso.atualizar,
            verificar_parada,
            semaforo
        )

    arquivos = await _executar_em_paralelo(
        enviar_arquivo(indice, midia)
        for indice, midia in enumerate(midias, 1)
    )

    for midia, arquivo in zip(midias, arquivos):
        _verificar_parada(verificar_parada)

        if midia.foto:
            entrada = types.InputMediaUploadedPhoto(
                arquivo,
                spoiler=midia.spoiler or None
            )
        else:
            thumb = None

            if midia.thumb:
                thumb = await client.upload_file(
                    str(midia.thumb),
                    part_size_kb=512
                )

            entrada = types.InputMediaUploadedDocument(
                arquivo,
                mime_type=(
                    midia.mime_type or "application/octet-stream"
                ),
                attributes=midia.attributes,
                force_file=midia.force_document or None,
                spoiler=midia.spoiler or None,
                thumb=thumb
            )

        media_servidor = await client(
            functions.messages.UploadMediaRequest(
                peer=peer,
                media=entrada
            )
        )

        if midia.foto:
            entrada_final = utils.get_input_media(
                media_servidor.photo
            )
        else:
            entrada_final = utils.get_input_media(
                media_servidor.document,
                supports_streaming=midia.supports_streaming
            )

        resultado.append(entrada_final)

    return resultado


def _bytes_restantes_download(mensagem, chave_rota):
    esperado = _tamanho_esperado(mensagem)
    diretorio = _diretorio_mensagem(
        chave_rota,
        mensagem.id
    )
    caminho = diretorio / _nome_seguro(
        _nome_original(mensagem)
    )
    parcial = caminho.with_suffix(caminho.suffix + ".part")

    if caminho.exists():
        atual = caminho.stat().st_size

        if esperado is None or atual == esperado:
            return 0

    if esperado is None:
        return MARGEM_DISCO

    offset = parcial.stat().st_size if parcial.exists() else 0

    if offset < 0 or offset > esperado:
        offset = 0

    return max(0, esperado - offset)


async def _prevalidar_album(client, mensagens, chave_rota):
    faltam_total = 0

    for mensagem in mensagens:
        tamanho = _tamanho_esperado(mensagem)

        if tamanho is not None:
            await _validar_limite_upload(client, tamanho)

        faltam_total += _bytes_restantes_download(
            mensagem,
            chave_rota
        )

    _validar_armazenamento(
        faltam_total,
        f"álbum com {len(mensagens)} arquivos"
    )


async def enviar_album_baixado(
    client,
    destino,
    mensagens,
    chave_rota,
    topico_destino_id=None,
    verificar_parada=None
):

    mensagens = [
        mensagem
        for mensagem in mensagens
        if tem_midia_baixavel(mensagem)
    ]

    if not mensagens:
        return

    if len(mensagens) == 1:
        await enviar_mensagem_baixada(
            client,
            destino,
            mensagens[0],
            chave_rota,
            topico_destino_id,
            verificar_parada
        )
        return

    await _prevalidar_album(
        client,
        mensagens,
        chave_rota
    )

    semaforo = asyncio.Semaphore(
        PARALELISMO_TRANSFERENCIA
    )
    midias = await _executar_em_paralelo(
        (
            baixar_midia(
                client,
                mensagem,
                chave_rota,
                verificar_parada,
                semaforo
            )
            for mensagem in mensagens
        )
    )

    print(
        f"    Preparando reenvio do álbum com {len(midias)} arquivos.",
        flush=True
    )

    arquivos_servidor = await _upload_album(
        client,
        destino,
        midias,
        verificar_parada
    )
    legendas = [mensagem.message or "" for mensagem in mensagens]
    entidades = [mensagem.entities or [] for mensagem in mensagens]
    legendas_separadas = not all(
        _legenda_cabe(legenda, entidade)
        for legenda, entidade in zip(legendas, entidades)
    )

    try:
        await client.send_file(
            destino,
            arquivos_servidor,
            caption=([] if legendas_separadas else legendas),
            formatting_entities=(
                None if legendas_separadas else entidades
            ),
            parse_mode=None,
            reply_to=topico_destino_id
        )

    except MediaCaptionTooLongError:
        legendas_separadas = True
        await client.send_file(
            destino,
            arquivos_servidor,
            caption=[],
            parse_mode=None,
            reply_to=topico_destino_id
        )

    if legendas_separadas:

        for mensagem in mensagens:
            await _enviar_texto_formatado(
                client,
                destino,
                mensagem.message or "",
                mensagem.entities or [],
                topico_destino_id
            )

        print(
            "    Aviso: legendas longas do álbum enviadas "
            "como texto separado.",
            flush=True
        )

    for midia in midias:
        limpar_midia_temporaria(midia)
