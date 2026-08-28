import json
import math
import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent

CHANNELS_FILE = BASE_DIR / "channels.json"
NORMAL_CONFIG_FILE = BASE_DIR / "normal_config.json"
RETRO_CONFIG_FILE = BASE_DIR / "retro_config.json"
APP_CONFIG_FILE = BASE_DIR / "app_config.json"

SYNC_PROGRESS_FILE = BASE_DIR / "sync_progress.json"
HISTORICO_PROGRESS_FILE = BASE_DIR / "historico_progress.json"

SYNC_STOP_FILE = BASE_DIR / "sync_stop.flag"
RETRO_STOP_FILE = BASE_DIR / "retro_stop.flag"

ENV_FILE = BASE_DIR / ".env"

DEFAULT_NORMAL_CONFIG = {
    "tamanho_lote": 100,
    "intervalo": 5
}

DEFAULT_RETRO_CONFIG = {
    "limite": 1000,
    "a_partir_do_id": 0,
    "tamanho_lote": 100,
    "tentativas_erro": 3
}

DEFAULT_APP_CONFIG = {
    "session_file": "user_session",
    "temp_parent_dir": "",
    "limite_temporario_gb": 0,
    "window_geometry": "",
    "window_maximized": False,
}


def carregar_json(caminho, padrao):
    caminho = Path(caminho)

    if not caminho.exists():
        return padrao.copy() if isinstance(padrao, dict) else padrao

    try:
        with caminho.open("r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except (json.JSONDecodeError, OSError) as erro:
        raise RuntimeError(
            f"Não foi possível ler {caminho.name}: {erro}"
        ) from erro

    return dados


def salvar_json(caminho, dados):
    caminho = Path(caminho)
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")

    with temporario.open("w", encoding="utf-8") as arquivo:
        json.dump(
            dados,
            arquivo,
            indent=4,
            ensure_ascii=False
        )

    os.replace(temporario, caminho)


def normalizar_peer(valor):
    """
    Converte IDs numéricos para int e preserva @usernames como str.
    """
    if isinstance(valor, int):
        return valor

    texto = str(valor).strip()

    if not texto:
        raise ValueError("Canal vazio.")

    try:
        return int(texto)
    except ValueError:
        return texto


def normalizar_topico(valor):
    """
    Converte o ID opcional de um tópico em inteiro positivo.
    None ou string vazia significam sincronizar o canal/grupo inteiro.
    """
    if valor is None:
        return None

    texto = str(valor).strip()

    if not texto:
        return None

    try:
        topico_id = int(texto)
    except ValueError as erro:
        raise ValueError(
            "O ID do tópico precisa ser um número inteiro."
        ) from erro

    if topico_id <= 0:
        raise ValueError(
            "O ID do tópico precisa ser maior que zero."
        )

    return topico_id


def normalizar_booleano(valor, padrao=False):
    """Normaliza opções booleanas vindas do JSON ou de edição manual."""

    if valor is None:
        return bool(padrao)

    if isinstance(valor, bool):
        return valor

    if isinstance(valor, (int, float)):
        return bool(valor)

    texto = str(valor).strip().lower()

    if texto in {"1", "true", "sim", "yes", "on"}:
        return True

    if texto in {"0", "false", "nao", "não", "no", "off", ""}:
        return False

    raise ValueError(
        f"Valor booleano inválido: {valor}."
    )


def montar_chave_rota(origem, topico_id=None):
    """
    Gera uma chave única para o progresso e para channels.json.

    Rotas antigas continuam usando apenas o ID da origem. Rotas de
    tópico usam o formato "origem:topico", permitindo vários tópicos
    do mesmo grupo sem colisão de configuração ou progresso.
    """
    origem_normalizada = normalizar_peer(origem)
    topico_normalizado = normalizar_topico(topico_id)

    if topico_normalizado is None:
        return str(origem_normalizada)

    return f"{origem_normalizada}:{topico_normalizado}"


def _separar_chave_rota(chave):
    """
    Entende uma chave composta mesmo quando source_id/topic_id ainda
    não existem dentro do objeto. Isso facilita edições manuais do JSON.
    """
    texto = str(chave).strip()

    if ":" not in texto:
        return texto, None

    origem, possivel_topico = texto.rsplit(":", 1)

    try:
        topico_id = normalizar_topico(possivel_topico)
    except ValueError:
        return texto, None

    return origem, topico_id


def carregar_canais():
    dados = carregar_json(CHANNELS_FILE, {})

    if not isinstance(dados, dict):
        raise RuntimeError(
            "channels.json precisa conter um objeto JSON."
        )

    canais = {}

    for chave_armazenada, configuracao in dados.items():

        if not isinstance(configuracao, dict):
            raise RuntimeError(
                f"Configuração inválida para a rota {chave_armazenada}."
            )

        if "target_id" not in configuracao:
            raise RuntimeError(
                f"target_id não encontrado para a rota {chave_armazenada}."
            )

        origem_da_chave, topico_da_chave = _separar_chave_rota(
            chave_armazenada
        )

        origem_normalizada = normalizar_peer(
            configuracao.get("source_id", origem_da_chave)
        )
        topico_id = normalizar_topico(
            configuracao.get("topic_id", topico_da_chave)
        )
        destino_normalizado = normalizar_peer(
            configuracao["target_id"]
        )
        topico_destino_id = normalizar_topico(
            configuracao.get("target_topic_id")
        )
        download_reupload = normalizar_booleano(
            configuracao.get("download_reupload", False)
        )

        nome = str(
            configuracao.get("name", origem_normalizada)
        ).strip()

        chave_rota = montar_chave_rota(
            origem_normalizada,
            topico_id
        )

        if chave_rota in canais:
            raise RuntimeError(
                f"A rota {chave_rota} está duplicada em channels.json."
            )

        canais[chave_rota] = {
            "source_id": origem_normalizada,
            "target_id": destino_normalizado,
            "topic_id": topico_id,
            "target_topic_id": topico_destino_id,
            "download_reupload": download_reupload,
            "name": nome or chave_rota
        }

    return canais


def selecionar_rotas(canais, chaves_selecionadas=None):
    """
    Filtra rotas mantendo a ordem de channels.json.

    None ou uma lista vazia preserva o comportamento histórico e seleciona
    todas as rotas. Chaves desconhecidas causam erro em vez de iniciar uma
    execução diferente da solicitada.
    """
    if not chaves_selecionadas:
        return dict(canais)

    chaves = {
        str(chave)
        for chave in chaves_selecionadas
    }
    desconhecidas = sorted(
        chave
        for chave in chaves
        if chave not in canais
    )

    if desconhecidas:
        raise RuntimeError(
            "Rota(s) não encontrada(s): "
            + ", ".join(desconhecidas)
        )

    return {
        chave: dados
        for chave, dados in canais.items()
        if chave in chaves
    }


def carregar_config_normal():
    dados = carregar_json(
        NORMAL_CONFIG_FILE,
        DEFAULT_NORMAL_CONFIG
    )

    config = DEFAULT_NORMAL_CONFIG.copy()
    config.update(dados)

    config["tamanho_lote"] = int(config["tamanho_lote"])
    config["intervalo"] = int(config["intervalo"])

    return config


def carregar_config_retro():
    dados = carregar_json(
        RETRO_CONFIG_FILE,
        DEFAULT_RETRO_CONFIG
    )

    config = DEFAULT_RETRO_CONFIG.copy()
    config.update(dados)

    config["limite"] = int(config["limite"])
    config["a_partir_do_id"] = int(
        config["a_partir_do_id"]
    )
    config["tamanho_lote"] = int(
        config["tamanho_lote"]
    )
    config["tentativas_erro"] = int(
        config["tentativas_erro"]
    )

    return config


def carregar_config_app():
    dados = carregar_json(
        APP_CONFIG_FILE,
        DEFAULT_APP_CONFIG
    )

    config = DEFAULT_APP_CONFIG.copy()
    config.update(dados)

    session_file = str(
        config.get("session_file", "user_session")
    ).strip()

    config["session_file"] = (
        session_file or "user_session"
    )

    config["temp_parent_dir"] = str(
        config.get("temp_parent_dir", "")
    ).strip()

    config["window_geometry"] = str(
        config.get("window_geometry", "")
    ).strip()

    config["window_maximized"] = normalizar_booleano(
        config.get("window_maximized", False)
    )

    try:
        limite_temporario_gb = float(
            config.get("limite_temporario_gb", 0)
        )
    except (TypeError, ValueError) as erro:
        raise RuntimeError(
            "limite_temporario_gb precisa ser um número."
        ) from erro

    if (
        not math.isfinite(limite_temporario_gb)
        or limite_temporario_gb < 0
    ):
        raise RuntimeError(
            "limite_temporario_gb precisa ser zero ou um número positivo."
        )

    config["limite_temporario_gb"] = limite_temporario_gb

    return config


def resolver_temp_parent_dir(temp_parent_dir=""):
    """
    Resolve a pasta escolhida pelo usuário sem conceder ao programa
    propriedade sobre o conteúdo dela. Os arquivos administrados ficam
    exclusivamente na subpasta ``temp_transferencias``.
    """
    texto = str(temp_parent_dir or "").strip()

    if not texto:
        return BASE_DIR.resolve()

    caminho = Path(
        os.path.expandvars(texto)
    ).expanduser()

    if not caminho.is_absolute():
        caminho = BASE_DIR / caminho

    return caminho.resolve()


def resolver_temp_media_dir(temp_parent_dir=""):
    return (
        resolver_temp_parent_dir(temp_parent_dir)
        / "temp_transferencias"
    )


def ler_env():
    resultado = {}

    if not ENV_FILE.exists():
        return resultado

    try:
        linhas = ENV_FILE.read_text(
            encoding="utf-8"
        ).splitlines()
    except OSError:
        return resultado

    for linha in linhas:
        texto = linha.strip()

        if (
            not texto
            or texto.startswith("#")
            or "=" not in texto
        ):
            continue

        chave, valor = texto.split("=", 1)

        resultado[chave.strip()] = (
            valor.strip().strip('"').strip("'")
        )

    return resultado


def atualizar_env(valores):
    """
    Atualiza chaves específicas do .env preservando outras linhas.
    """
    existentes = []

    if ENV_FILE.exists():
        existentes = ENV_FILE.read_text(
            encoding="utf-8"
        ).splitlines()

    pendentes = dict(valores)
    novas_linhas = []

    for linha in existentes:
        texto = linha.strip()

        if (
            texto
            and not texto.startswith("#")
            and "=" in texto
        ):
            chave = texto.split("=", 1)[0].strip()

            if chave in pendentes:
                novas_linhas.append(
                    f"{chave}={pendentes.pop(chave)}"
                )
                continue

        novas_linhas.append(linha)

    if novas_linhas and novas_linhas[-1] != "":
        novas_linhas.append("")

    for chave, valor in pendentes.items():
        novas_linhas.append(f"{chave}={valor}")

    ENV_FILE.write_text(
        "\n".join(novas_linhas).rstrip() + "\n",
        encoding="utf-8"
    )



def resolver_session_path(session_file):
    """
    Resolve o arquivo de sessão sempre dentro da pasta do projeto,
    a menos que um caminho absoluto seja fornecido.
    """
    caminho = Path(str(session_file).strip() or "user_session")

    if caminho.is_absolute():
        return caminho

    return BASE_DIR / caminho
