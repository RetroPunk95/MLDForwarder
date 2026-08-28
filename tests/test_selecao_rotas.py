import os
import unittest

os.environ.setdefault("API_ID", "1")
os.environ.setdefault("API_HASH", "hash-de-teste")

from config_utils import selecionar_rotas
from sincronizar import carregar_argumentos


class SelecaoRotasTests(unittest.TestCase):

    def setUp(self):
        self.canais = {
            "-1001": {"name": "Filmes"},
            "-1002:55": {"name": "Séries — tópico 55"},
            "-1003": {"name": "Documentários"},
        }

    def test_sem_argumentos_seleciona_todas_as_rotas(self):
        selecionadas = selecionar_rotas(self.canais)

        self.assertEqual(
            list(selecionadas),
            list(self.canais)
        )

    def test_filtra_varias_rotas_e_mantem_ordem_original(self):
        selecionadas = selecionar_rotas(
            self.canais,
            ["-1003", "-1001"]
        )

        self.assertEqual(
            list(selecionadas),
            ["-1001", "-1003"]
        )

    def test_rejeita_rota_que_nao_existe(self):
        with self.assertRaisesRegex(
            RuntimeError,
            "Rota.*não encontrada"
        ):
            selecionar_rotas(
                self.canais,
                ["-9999"]
            )

    def test_argumento_canal_pode_ser_repetido(self):
        argumentos = carregar_argumentos(
            [
                "--canal=-1001",
                "--canal=-1002:55",
            ]
        )

        self.assertEqual(
            argumentos.canais,
            ["-1001", "-1002:55"]
        )


if __name__ == "__main__":
    unittest.main()
