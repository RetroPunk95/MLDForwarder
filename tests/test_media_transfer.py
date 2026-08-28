import asyncio
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from telethon.tl import functions, types

import media_transfer


def criar_mensagem(message_id, conteudo, nome="episodio.mkv", tamanho=None):
    tamanho = len(conteudo) if tamanho is None else tamanho
    atributos = [
        types.DocumentAttributeFilename(nome),
        types.DocumentAttributeVideo(
            duration=120,
            w=1920,
            h=1080,
            supports_streaming=False
        ),
    ]
    documento = types.Document(
        id=message_id,
        access_hash=1,
        file_reference=b"ref",
        date=datetime.now(timezone.utc),
        mime_type="video/x-matroska",
        size=tamanho,
        dc_id=1,
        attributes=atributos
    )

    return SimpleNamespace(
        id=message_id,
        media=types.MessageMediaDocument(
            document=documento,
            video=True
        ),
        file=SimpleNamespace(
            name=nome,
            ext=Path(nome).suffix,
            size=tamanho
        ),
        message="Legenda em **texto puro**",
        entities=[]
    )


class ClienteFalso:

    def __init__(self, dados, premium=True):
        self.dados = dados
        self.premium = premium
        self.offsets = []
        self.envios = []
        self.iteracoes = 0
        self.uploads = []
        self.partes_upload = {}
        self.tamanhos_download = []
        self.atraso_download = 0
        self.downloads_ativos = 0
        self.max_downloads_ativos = 0
        self.atraso_upload = 0
        self.uploads_ativos = 0
        self.max_uploads_ativos = 0

    async def get_me(self):
        return SimpleNamespace(premium=self.premium)

    async def iter_download(
        self,
        _media,
        offset=0,
        stride=None,
        limit=None,
        chunk_size=None,
        request_size=None,
        file_size=None,
        dc_id=None
    ):
        self.offsets.append(offset)
        self.iteracoes += 1
        self.tamanhos_download.append(request_size)
        dados = (
            self.dados.get(_media.document.id, b"")
            if isinstance(self.dados, dict)
            else self.dados
        )
        tamanho_trecho = chunk_size or request_size or 3
        passo = stride or tamanho_trecho
        maximo = limit if limit is not None else float("inf")
        enviados = 0

        self.downloads_ativos += 1
        self.max_downloads_ativos = max(
            self.max_downloads_ativos,
            self.downloads_ativos
        )

        try:

            if self.atraso_download:
                await asyncio.sleep(self.atraso_download)

            for inicio in range(offset, len(dados), passo):

                if enviados >= maximo:
                    break

                yield dados[inicio:inicio + tamanho_trecho]
                enviados += 1

        finally:
            self.downloads_ativos -= 1

    async def send_file(self, destino, arquivo, **kwargs):

        if isinstance(arquivo, list):
            self.envios.append(
                {
                    "destino": destino,
                    "album": arquivo,
                    "kwargs": kwargs
                }
            )
            return [SimpleNamespace(id=999)]

        if isinstance(
            arquivo,
            (types.InputFile, types.InputFileBig)
        ):
            partes = self.partes_upload.get(arquivo.id, {})
            conteudo = b"".join(
                partes[indice]
                for indice in sorted(partes)
            )
            nome = arquivo.name
        else:
            caminho = Path(arquivo)
            conteudo = caminho.read_bytes()
            nome = caminho.name

        self.envios.append(
            {
                "destino": destino,
                "conteudo": conteudo,
                "nome": nome,
                "kwargs": kwargs
            }
        )
        return SimpleNamespace(id=999)

    async def send_message(self, *args, **kwargs):
        self.envios.append(
            {
                "texto": args,
                "kwargs": kwargs
            }
        )

    async def get_input_entity(self, _destino):
        return types.InputPeerChannel(
            channel_id=123,
            access_hash=456
        )

    async def upload_file(
        self,
        arquivo,
        part_size_kb=None,
        file_size=None,
        file_name=None,
        progress_callback=None
    ):
        caminho = Path(arquivo)
        self.uploads.append(caminho.read_bytes())

        if progress_callback:
            progress_callback(file_size, file_size)

        return types.InputFile(
            id=len(self.uploads),
            parts=1,
            name=caminho.name,
            md5_checksum=""
        )

    async def __call__(self, request):

        if isinstance(
            request,
            (
                functions.upload.SaveFilePartRequest,
                functions.upload.SaveBigFilePartRequest,
            )
        ):
            self.uploads_ativos += 1
            self.max_uploads_ativos = max(
                self.max_uploads_ativos,
                self.uploads_ativos
            )

            try:

                if self.atraso_upload:
                    await asyncio.sleep(self.atraso_upload)

                self.partes_upload.setdefault(
                    request.file_id,
                    {}
                )[request.file_part] = bytes(request.bytes)
                return True

            finally:
                self.uploads_ativos -= 1

        entrada = request.media
        partes = self.partes_upload.get(entrada.file.id, {})
        self.uploads.append(
            b"".join(
                partes[indice]
                for indice in sorted(partes)
            )
        )
        nome = next(
            (
                atributo.file_name
                for atributo in entrada.attributes
                if isinstance(
                    atributo,
                    types.DocumentAttributeFilename
                )
            ),
            "arquivo.bin"
        )
        documento = types.Document(
            id=len(self.uploads),
            access_hash=1,
            file_reference=b"ref",
            date=datetime.now(timezone.utc),
            mime_type=entrada.mime_type,
            size=len(self.uploads[-1]),
            dc_id=1,
            attributes=[types.DocumentAttributeFilename(nome)]
        )

        return types.MessageMediaDocument(document=documento)


class MediaTransferTests(unittest.IsolatedAsyncioTestCase):

    async def test_retoma_download_parcial(self):
        dados = b"0123456789"
        mensagem = criar_mensagem(42, dados)
        cliente = ClienteFalso(dados)

        with tempfile.TemporaryDirectory() as temporario:
            raiz = Path(temporario) / "temp_transferencias"

            with patch.object(media_transfer, "TEMP_MEDIA_DIR", raiz):
                diretorio = media_transfer._diretorio_mensagem(
                    "rota-teste",
                    mensagem.id
                )
                diretorio.mkdir(parents=True)
                parcial = diretorio / "episodio.mkv.part"
                parcial.write_bytes(dados[:3])

                midia = await media_transfer.baixar_midia(
                    cliente,
                    mensagem,
                    "rota-teste"
                )

                self.assertEqual(cliente.offsets, [3])
                self.assertEqual(midia.caminho.read_bytes(), dados)
                self.assertFalse(parcial.exists())

    async def test_reenvia_e_remove_temporario_apos_confirmacao(self):
        dados = b"arquivo-de-teste"
        mensagem = criar_mensagem(77, dados, "video.mkv")
        cliente = ClienteFalso(dados)

        with tempfile.TemporaryDirectory() as temporario:
            raiz = Path(temporario) / "temp_transferencias"

            with patch.object(media_transfer, "TEMP_MEDIA_DIR", raiz):
                await media_transfer.enviar_mensagem_baixada(
                    cliente,
                    -100123,
                    mensagem,
                    "rota-teste"
                )

                self.assertEqual(len(cliente.envios), 1)
                envio = cliente.envios[0]
                self.assertEqual(envio["destino"], -100123)
                self.assertEqual(envio["conteudo"], dados)
                self.assertEqual(envio["nome"], "video.mkv")
                self.assertEqual(
                    envio["kwargs"]["caption"],
                    mensagem.message
                )
                self.assertFalse(raiz.exists())

    async def test_bloqueia_upload_acima_de_2gb_sem_premium(self):
        dados = b"nao-deve-ser-baixado"
        mensagem = criar_mensagem(
            88,
            dados,
            tamanho=media_transfer.LIMITE_UPLOAD_GRATUITO + 1
        )
        cliente = ClienteFalso(dados, premium=False)

        with tempfile.TemporaryDirectory() as temporario:
            raiz = Path(temporario) / "temp_transferencias"

            with patch.object(media_transfer, "TEMP_MEDIA_DIR", raiz):

                with self.assertRaisesRegex(
                    RuntimeError,
                    "Telegram Premium"
                ):
                    await media_transfer.baixar_midia(
                        cliente,
                        mensagem,
                        "rota-teste"
                    )

                self.assertEqual(cliente.iteracoes, 0)
                self.assertFalse(raiz.exists())

    async def test_album_e_reenviado_como_um_novo_album(self):
        dados = {
            101: b"primeiro-video",
            102: b"segundo-video"
        }
        mensagens = [
            criar_mensagem(101, dados[101], "E01.mkv"),
            criar_mensagem(102, dados[102], "E02.mkv"),
        ]
        cliente = ClienteFalso(dados)

        with tempfile.TemporaryDirectory() as temporario:
            raiz = Path(temporario) / "temp_transferencias"

            with patch.object(media_transfer, "TEMP_MEDIA_DIR", raiz):
                await media_transfer.enviar_album_baixado(
                    cliente,
                    -100123,
                    mensagens,
                    "rota-album"
                )

                self.assertEqual(cliente.uploads, list(dados.values()))
                self.assertEqual(len(cliente.envios), 1)
                self.assertEqual(
                    len(cliente.envios[0]["album"]),
                    2
                )
                self.assertEqual(
                    cliente.envios[0]["kwargs"]["caption"],
                    [mensagem.message for mensagem in mensagens]
                )
                self.assertFalse(raiz.exists())

    async def test_album_valida_limite_antes_de_baixar_qualquer_arquivo(self):
        dados = {
            201: b"primeiro-video",
            202: b"segundo-video"
        }
        mensagens = [
            criar_mensagem(201, dados[201], "E01.mkv"),
            criar_mensagem(202, dados[202], "E02.mkv"),
        ]
        cliente = ClienteFalso(dados)

        with tempfile.TemporaryDirectory() as temporario:
            raiz = Path(temporario) / "temp_transferencias"

            with (
                patch.object(media_transfer, "TEMP_MEDIA_DIR", raiz),
                patch.object(
                    media_transfer,
                    "LIMITE_TEMPORARIO_BYTES",
                    20
                )
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "álbum.*limite temporário"
                ):
                    await media_transfer.enviar_album_baixado(
                        cliente,
                        -100123,
                        mensagens,
                        "rota-album"
                    )

                self.assertEqual(cliente.iteracoes, 0)
                self.assertFalse(raiz.exists())

    async def test_limite_considera_arquivos_retidos_de_falhas_anteriores(self):
        dados = b"novo-arquivo"
        mensagem = criar_mensagem(301, dados, "novo.mkv")
        cliente = ClienteFalso(dados)

        with tempfile.TemporaryDirectory() as temporario:
            raiz = Path(temporario) / "temp_transferencias"

            with (
                patch.object(media_transfer, "TEMP_MEDIA_DIR", raiz),
                patch.object(
                    media_transfer,
                    "LIMITE_TEMPORARIO_BYTES",
                    20
                )
            ):
                media_transfer.preparar_raiz_temporaria()
                rota = raiz / "0123456789abcdef" / "1"
                rota.mkdir(parents=True)
                (rota / "retido.mkv").write_bytes(b"1234567890")

                with self.assertRaisesRegex(
                    RuntimeError,
                    "limite temporário"
                ):
                    await media_transfer.baixar_midia(
                        cliente,
                        mensagem,
                        "rota-nova"
                    )

                self.assertEqual(cliente.iteracoes, 0)

    async def test_download_grande_mantem_varias_partes_em_voo(self):
        dados = b"x" * (
            media_transfer.TAMANHO_PARTE_TRANSFERENCIA * 5 + 17
        )
        mensagem = criar_mensagem(
            401,
            dados,
            "download-paralelo.mkv"
        )
        cliente = ClienteFalso(dados)
        cliente.atraso_download = 0.01

        with tempfile.TemporaryDirectory() as temporario:
            raiz = Path(temporario) / "temp_transferencias"

            with patch.object(media_transfer, "TEMP_MEDIA_DIR", raiz):
                midia = await media_transfer.baixar_midia(
                    cliente,
                    mensagem,
                    "rota-rapida"
                )

                self.assertEqual(midia.caminho.read_bytes(), dados)

        self.assertGreaterEqual(cliente.max_downloads_ativos, 2)
        self.assertTrue(cliente.tamanhos_download)
        self.assertEqual(
            set(cliente.tamanhos_download),
            {media_transfer.TAMANHO_PARTE_TRANSFERENCIA}
        )

    async def test_upload_grande_mantem_varias_partes_em_voo(self):
        dados = b"y" * (
            media_transfer.TAMANHO_PARTE_TRANSFERENCIA * 5 + 17
        )
        cliente = ClienteFalso(b"")
        cliente.atraso_upload = 0.01
        progresso = []

        with tempfile.TemporaryDirectory() as temporario:
            caminho = Path(temporario) / "upload-paralelo.mkv"
            caminho.write_bytes(dados)
            arquivo = await media_transfer._upload_arquivo_acelerado(
                cliente,
                caminho,
                len(dados),
                lambda atual, total: progresso.append((atual, total))
            )

        partes = cliente.partes_upload[arquivo.id]
        reconstruido = b"".join(
            partes[indice]
            for indice in sorted(partes)
        )

        self.assertEqual(reconstruido, dados)
        self.assertEqual(arquivo.parts, 6)
        self.assertGreaterEqual(cliente.max_uploads_ativos, 2)
        self.assertEqual(progresso[-1], (len(dados), len(dados)))

    def test_limpeza_recusa_pasta_nao_administrada(self):
        with tempfile.TemporaryDirectory() as temporario:
            raiz = Path(temporario) / "temp_transferencias"
            raiz.mkdir()
            alheio = raiz / "arquivo-do-usuario.txt"
            alheio.write_text("não remover", encoding="utf-8")

            with patch.object(media_transfer, "TEMP_MEDIA_DIR", raiz):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "não parecem pertencer"
                ):
                    media_transfer.limpar_armazenamento_temporario()

            self.assertEqual(
                alheio.read_text(encoding="utf-8"),
                "não remover"
            )


if __name__ == "__main__":
    unittest.main()
