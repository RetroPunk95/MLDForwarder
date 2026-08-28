import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import auth_service


class FakeClient:

    def __init__(self, dialogs=(), authorized=True):
        self.dialogs = list(dialogs)
        self.authorized = authorized
        self.connected = False
        self.disconnected = False

    async def connect(self):
        self.connected = True

    async def is_user_authorized(self):
        return self.authorized

    async def iter_dialogs(self, **_kwargs):
        for dialog in self.dialogs:
            yield dialog

    def is_connected(self):
        return self.connected and not self.disconnected

    async def disconnect(self):
        self.disconnected = True


def dialog(
    peer_id,
    name,
    *,
    is_channel=False,
    is_group=False,
    username=None,
    forum=False,
    left=False
):
    return SimpleNamespace(
        id=peer_id,
        name=name,
        is_channel=is_channel,
        is_group=is_group,
        entity=SimpleNamespace(
            title=name,
            username=username,
            forum=forum,
            left=left,
            deactivated=False
        )
    )


class ListarCanaisGruposTests(unittest.TestCase):

    def test_lista_apenas_canais_e_grupos_com_nome_e_id(self):
        client = FakeClient(
            [
                dialog(25, "Contato", username="contato"),
                dialog(
                    -1002,
                    "Zulu Canal",
                    is_channel=True,
                    username="zulu"
                ),
                dialog(
                    -1001,
                    "Alpha Grupo",
                    is_channel=True,
                    is_group=True,
                    forum=True
                ),
                dialog(
                    -1003,
                    "Canal removido",
                    is_channel=True,
                    left=True
                )
            ]
        )

        with patch.object(
            auth_service,
            "TelegramClient",
            return_value=client
        ):
            result = asyncio.run(
                auth_service.listar_canais_grupos(
                    1,
                    "hash",
                    "sessao"
                )
            )

        self.assertTrue(result["ok"])
        self.assertEqual(
            [item["id"] for item in result["dialogs"]],
            [-1001, -1002]
        )
        self.assertEqual(result["dialogs"][0]["title"], "Alpha Grupo")
        self.assertEqual(result["dialogs"][0]["type"], "Grupo")
        self.assertTrue(result["dialogs"][0]["is_forum"])
        self.assertEqual(result["dialogs"][1]["type"], "Canal")
        self.assertEqual(result["dialogs"][1]["username"], "@zulu")
        self.assertTrue(client.disconnected)

    def test_informa_quando_a_sessao_nao_esta_autenticada(self):
        client = FakeClient(authorized=False)

        with patch.object(
            auth_service,
            "TelegramClient",
            return_value=client
        ):
            result = asyncio.run(
                auth_service.listar_canais_grupos(
                    1,
                    "hash",
                    "sessao"
                )
            )

        self.assertFalse(result["ok"])
        self.assertIn("não está autenticada", result["error"])
        self.assertTrue(client.disconnected)


if __name__ == "__main__":
    unittest.main()
