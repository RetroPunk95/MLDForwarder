import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config_utils


class ConfigUtilsTests(unittest.TestCase):

    def test_config_app_antigo_recebe_padrao_de_armazenamento(self):
        with tempfile.TemporaryDirectory() as temporario:
            arquivo = Path(temporario) / "app_config.json"
            arquivo.write_text(
                json.dumps({"session_file": "minha_sessao"}),
                encoding="utf-8"
            )

            with patch.object(config_utils, "APP_CONFIG_FILE", arquivo):
                config = config_utils.carregar_config_app()

        self.assertEqual(config["session_file"], "minha_sessao")
        self.assertEqual(config["temp_parent_dir"], "")
        self.assertEqual(config["limite_temporario_gb"], 0)

    def test_resolve_subpasta_temporaria_dentro_da_pasta_escolhida(self):
        with tempfile.TemporaryDirectory() as temporario:
            pai = Path(temporario).resolve()
            pasta = config_utils.resolver_temp_media_dir(pai)

        self.assertEqual(pasta, pai / "temp_transferencias")

    def test_rota_antiga_mantem_modo_direto(self):
        dados = {
            "-1001": {
                "target_id": -1002,
                "name": "Rota antiga"
            }
        }

        with tempfile.TemporaryDirectory() as temporario:
            arquivo = Path(temporario) / "channels.json"
            arquivo.write_text(
                json.dumps(dados),
                encoding="utf-8"
            )

            with patch.object(config_utils, "CHANNELS_FILE", arquivo):
                canais = config_utils.carregar_canais()

        self.assertFalse(canais["-1001"]["download_reupload"])

    def test_rota_pode_ativar_download_e_reenvio(self):
        dados = {
            "-1001": {
                "target_id": -1002,
                "download_reupload": True,
                "name": "Rota com reupload"
            }
        }

        with tempfile.TemporaryDirectory() as temporario:
            arquivo = Path(temporario) / "channels.json"
            arquivo.write_text(
                json.dumps(dados),
                encoding="utf-8"
            )

            with patch.object(config_utils, "CHANNELS_FILE", arquivo):
                canais = config_utils.carregar_canais()

        self.assertTrue(canais["-1001"]["download_reupload"])

    def test_permite_mesma_origem_com_destinos_diferentes(self):
        dados = {
            "rota-1": {
                "source_id": -1001,
                "target_id": -1002,
                "name": "Destino 1"
            },
            "rota-2": {
                "source_id": -1001,
                "target_id": -1003,
                "name": "Destino 2"
            }
        }

        with tempfile.TemporaryDirectory() as temporario:
            arquivo = Path(temporario) / "channels.json"
            arquivo.write_text(
                json.dumps(dados),
                encoding="utf-8"
            )

            with patch.object(config_utils, "CHANNELS_FILE", arquivo):
                canais = config_utils.carregar_canais()

        self.assertEqual(len(canais), 2)

    def test_rejeita_mesma_combinacao_de_origem_e_destino(self):
        dados = {
            "rota-1": {
                "source_id": -1001,
                "target_id": -1002
            },
            "rota-2": {
                "source_id": -1001,
                "target_id": -1002
            }
        }

        with tempfile.TemporaryDirectory() as temporario:
            arquivo = Path(temporario) / "channels.json"
            arquivo.write_text(
                json.dumps(dados),
                encoding="utf-8"
            )

            with patch.object(config_utils, "CHANNELS_FILE", arquivo):
                with self.assertRaises(RuntimeError):
                    config_utils.carregar_canais()


if __name__ == "__main__":
    unittest.main()
