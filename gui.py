import os
import re
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox, ttk

import auth_service

from config_utils import (
    APP_CONFIG_FILE,
    CHANNELS_FILE,
    HISTORICO_PROGRESS_FILE,
    NORMAL_CONFIG_FILE,
    RETRO_CONFIG_FILE,
    RETRO_STOP_FILE,
    SYNC_PROGRESS_FILE,
    SYNC_STOP_FILE,
    atualizar_env,
    carregar_canais,
    carregar_config_app,
    carregar_config_normal,
    carregar_config_retro,
    carregar_json,
    ler_env,
    montar_chave_rota,
    normalizar_peer,
    normalizar_topico,
    salvar_json,
)


if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent
VERSION = "2.8.1-exe"
API_PORTAL_URL = "https://my.telegram.org/"


COLORS = {
    # Paleta principal
    "bg": "#232323",
    "sidebar": "#13191B",
    "panel": "#20282B",
    "panel_2": "#273135",
    "line": "#344044",

    # Tipografia
    "text": "#F2F4FF",
    "muted": "#9EA8AC",

    # Identidade / seleção
    "accent": "#0083E8",
    "accent_hover": "#0073CC",

    # Estados positivos / execução
    "success": "#9AFF26",
    "success_hover": "#B2FF5B",

    # Estados destrutivos / atenção
    "danger": "#8C0021",
    "danger_bg": "#2E171D",
    "danger_hover": "#442029",
    "warning": "#D7FF9E",
}


# ============================================================
# DIÁLOGO DE CANAL
# ============================================================

class ChannelDialog(tk.Toplevel):

    def __init__(
        self,
        parent,
        titulo,
        dados=None,
        settings_provider=None
    ):

        super().__init__(parent)

        self.resultado = None
        self.parent = parent
        self.settings_provider = settings_provider
        self.topic_busy = {
            "source": False,
            "target": False
        }
        self.topic_maps = {
            "source": {},
            "target": {}
        }

        self.title(titulo)
        self.configure(bg=COLORS["panel"])
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        dados = dados or {}

        frame = tk.Frame(
            self,
            bg=COLORS["panel"],
            padx=22,
            pady=22
        )
        frame.pack(fill="both", expand=True)

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

        origem_frame = tk.Frame(
            frame,
            bg=COLORS["panel"]
        )
        origem_frame.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=(0, 12)
        )

        destino_frame = tk.Frame(
            frame,
            bg=COLORS["panel"]
        )
        destino_frame.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=(12, 0)
        )

        self._criar_secao_topico(
            origem_frame,
            "source",
            "ORIGEM",
            dados.get("source_id", ""),
            dados.get("topic_id")
        )

        self._criar_secao_topico(
            destino_frame,
            "target",
            "DESTINO",
            dados.get("target_id", ""),
            dados.get("target_topic_id")
        )

        self._label(
            frame,
            "Nome da rota"
        ).grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(20, 0)
        )

        self.nome = ttk.Entry(
            frame,
            width=94
        )
        self.nome.grid(
            row=2,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(5, 20)
        )
        self.nome.insert(
            0,
            str(dados.get("name", ""))
        )

        botoes = tk.Frame(
            frame,
            bg=COLORS["panel"]
        )
        botoes.grid(
            row=3,
            column=0,
            columnspan=2,
            sticky="e"
        )

        ttk.Button(
            botoes,
            text="Cancelar",
            command=self.destroy
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            botoes,
            text="Salvar",
            style="Start.TButton",
            command=self.salvar
        ).pack(side="left")

        self.bind(
            "<Escape>",
            lambda _event: self.destroy()
        )
        self.bind(
            "<Return>",
            lambda _event: self.salvar()
        )

        self.source_peer.focus_set()


    def _label(self, parent, texto):

        return tk.Label(
            parent,
            text=texto,
            bg=COLORS["panel"],
            fg=COLORS["text"],
            font=("Segoe UI", 10)
        )


    def _criar_secao_topico(
        self,
        parent,
        lado,
        titulo,
        peer_id,
        topic_id
    ):

        tk.Label(
            parent,
            text=titulo,
            bg=COLORS["panel"],
            fg=COLORS["success"],
            font=("Segoe UI Semibold", 10)
        ).grid(
            row=0,
            column=0,
            sticky="w",
            pady=(0, 12)
        )

        self._label(
            parent,
            "Canal ou grupo"
        ).grid(row=1, column=0, sticky="w")

        peer_line = tk.Frame(
            parent,
            bg=COLORS["panel"]
        )
        peer_line.grid(
            row=2,
            column=0,
            sticky="ew",
            pady=(5, 16)
        )

        peer_entry = ttk.Entry(
            peer_line,
            width=28
        )
        peer_entry.pack(
            side="left",
            fill="x",
            expand=True
        )
        peer_entry.insert(0, str(peer_id))

        topic_button = ttk.Button(
            peer_line,
            text="Buscar tópicos",
            command=lambda: self.listar_topicos(lado)
        )
        topic_button.pack(
            side="left",
            padx=(8, 0)
        )

        self._label(
            parent,
            "ID do tópico (opcional)"
        ).grid(row=3, column=0, sticky="w")

        topic_entry = ttk.Entry(
            parent,
            width=45
        )
        topic_entry.grid(
            row=4,
            column=0,
            sticky="ew",
            pady=(5, 3)
        )
        topic_entry.insert(
            0,
            str(topic_id or "")
        )

        ajuda = (
            "Vazio: lê o canal ou grupo inteiro."
            if lado == "source"
            else "Vazio: envia para o canal ou grupo principal."
        )

        tk.Label(
            parent,
            text=ajuda,
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9)
        ).grid(
            row=5,
            column=0,
            sticky="w",
            pady=(0, 12)
        )

        self._label(
            parent,
            "Tópicos encontrados"
        ).grid(row=6, column=0, sticky="w")

        topic_combo = ttk.Combobox(
            parent,
            width=42,
            state="disabled"
        )
        topic_combo.grid(
            row=7,
            column=0,
            sticky="ew",
            pady=(5, 3)
        )
        topic_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._selecionar_topico(lado)
        )

        status_var = tk.StringVar(
            value="Informe o grupo e clique em Buscar tópicos."
        )
        status_label = tk.Label(
            parent,
            textvariable=status_var,
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9)
        )
        status_label.grid(
            row=8,
            column=0,
            sticky="w"
        )

        parent.columnconfigure(0, weight=1)

        setattr(self, f"{lado}_peer", peer_entry)
        setattr(self, f"{lado}_topic", topic_entry)
        setattr(self, f"{lado}_topic_button", topic_button)
        setattr(self, f"{lado}_topic_combo", topic_combo)
        setattr(self, f"{lado}_topic_status_var", status_var)
        setattr(self, f"{lado}_topic_status", status_label)


    def _definir_busca_ativa(self, lado, ativa):

        self.topic_busy[lado] = ativa
        getattr(
            self,
            f"{lado}_topic_button"
        ).configure(
            state=(
                "disabled"
                if ativa
                else "normal"
            )
        )


    def listar_topicos(self, lado):

        if self.topic_busy[lado]:
            return

        peer_texto = getattr(
            self,
            f"{lado}_peer"
        ).get().strip()

        if not peer_texto:
            messagebox.showerror(
                "Buscar tópicos",
                "Informe primeiro o ID ou @username do grupo.",
                parent=self
            )
            return

        try:
            peer_id = normalizar_peer(
                peer_texto
            )
        except ValueError as erro:
            messagebox.showerror(
                "Buscar tópicos",
                str(erro),
                parent=self
            )
            return

        if self.settings_provider is None:
            messagebox.showerror(
                "Buscar tópicos",
                "As credenciais do Telegram não estão disponíveis.",
                parent=self
            )
            return

        settings = self.settings_provider()

        if not settings:
            messagebox.showerror(
                "Buscar tópicos",
                (
                    "Configure API ID, API Hash e sessão na aba "
                    "Telegram antes de fazer a consulta."
                ),
                parent=self
            )
            return

        api_id, api_hash, session = settings

        self._definir_busca_ativa(lado, True)
        self.topic_maps[lado] = {}
        topic_combo = getattr(
            self,
            f"{lado}_topic_combo"
        )
        status_var = getattr(
            self,
            f"{lado}_topic_status_var"
        )
        status_label = getattr(
            self,
            f"{lado}_topic_status"
        )
        topic_combo.set("")
        topic_combo.configure(
            values=(),
            state="disabled"
        )
        status_var.set(
            "Consultando o Telegram..."
        )
        status_label.configure(
            fg=COLORS["warning"]
        )

        def worker():

            try:
                result = auth_service.executar(
                    auth_service.listar_topicos(
                        api_id,
                        api_hash,
                        session,
                        peer_id
                    )
                )
            except Exception as erro:
                result = {
                    "ok": False,
                    "error": str(erro)
                }

            try:
                self.parent.after(
                    0,
                    self._resultado_listar_topicos,
                    lado,
                    result
                )
            except tk.TclError:
                pass

        threading.Thread(
            target=worker,
            daemon=True
        ).start()


    def _resultado_listar_topicos(self, lado, result):

        if not self.winfo_exists():
            return

        self._definir_busca_ativa(lado, False)
        topic_combo = getattr(
            self,
            f"{lado}_topic_combo"
        )
        status_var = getattr(
            self,
            f"{lado}_topic_status_var"
        )
        status_label = getattr(
            self,
            f"{lado}_topic_status"
        )

        if not result.get("ok"):
            status_var.set(
                "A consulta não foi concluída."
            )
            status_label.configure(
                fg=COLORS["muted"]
            )
            messagebox.showerror(
                "Buscar tópicos",
                result.get(
                    "error",
                    "Erro desconhecido."
                ),
                parent=self
            )
            return

        if not result.get("is_forum"):
            status_var.set(
                "O grupo informado não possui tópicos."
            )
            status_label.configure(
                fg=COLORS["muted"]
            )
            messagebox.showinfo(
                "Buscar tópicos",
                (
                    f'"{result.get("group_title", "Grupo")}" '
                    "não é um grupo com tópicos ativados."
                ),
                parent=self
            )
            return

        topicos = result.get("topics", [])

        if not topicos:
            status_var.set(
                "Nenhum tópico visível foi encontrado."
            )
            status_label.configure(
                fg=COLORS["muted"]
            )
            return

        opcoes = []

        for topico in topicos:
            topico_id = int(topico["id"])
            titulo = " ".join(
                str(topico["title"]).split()
            )
            opcao = f"{topico_id} — {titulo}"
            self.topic_maps[lado][opcao] = topico_id
            opcoes.append(opcao)

        topic_combo.configure(
            values=opcoes,
            state="readonly"
        )
        status_var.set(
            f"{len(opcoes)} tópico(s) encontrado(s). Selecione um acima."
        )
        status_label.configure(
            fg=COLORS["success"]
        )
        topic_combo.focus_set()


    def _selecionar_topico(self, lado):

        topic_combo = getattr(
            self,
            f"{lado}_topic_combo"
        )
        topic_entry = getattr(
            self,
            f"{lado}_topic"
        )
        selecionado = topic_combo.get()
        topico_id = self.topic_maps[lado].get(
            selecionado
        )

        if topico_id is None:
            return

        topic_entry.delete(0, tk.END)
        topic_entry.insert(0, str(topico_id))


    def salvar(self):

        origem_texto = self.source_peer.get().strip()
        topico_texto = self.source_topic.get().strip()
        destino_texto = self.target_peer.get().strip()
        topico_destino_texto = self.target_topic.get().strip()
        nome = self.nome.get().strip()

        if not origem_texto:
            messagebox.showerror(
                "Dados inválidos",
                "Informe o canal ou grupo de origem.",
                parent=self
            )
            return

        if not destino_texto:
            messagebox.showerror(
                "Dados inválidos",
                "Informe o canal ou grupo de destino.",
                parent=self
            )
            return

        if not nome:
            messagebox.showerror(
                "Dados inválidos",
                "Informe um nome para o par.",
                parent=self
            )
            return

        try:
            origem = normalizar_peer(
                origem_texto
            )
            topico_id = normalizar_topico(
                topico_texto
            )
            destino = normalizar_peer(
                destino_texto
            )
            topico_destino_id = normalizar_topico(
                topico_destino_texto
            )

        except ValueError as erro:
            messagebox.showerror(
                "Dados inválidos",
                str(erro),
                parent=self
            )
            return

        self.resultado = {
            "source_id": origem,
            "topic_id": topico_id,
            "target_id": destino,
            "target_topic_id": topico_destino_id,
            "name": nome
        }

        self.destroy()


# ============================================================
# GUI PRINCIPAL
# ============================================================

class MLDForwarderGUI(tk.Tk):

    def __init__(self):

        super().__init__()

        self.title(
            f"MLDForwarder {VERSION}"
        )
        self.geometry("1180x760")
        self.minsize(1020, 650)
        self.configure(bg=COLORS["bg"])

        self.channels = {}

        self.normal_process = None
        self.retro_process = None

        self.auth_busy = False
        self.auth_phone = ""
        self.auth_phone_code_hash = None

        self.nav_buttons = {}
        self.pages = {}

        self.retro_map = {}

        self._configurar_estilo()
        self._construir_shell()
        self._construir_paginas()

        self.recarregar_tudo()
        self.mostrar_pagina("dashboard")
        self.atualizar_estados()

        self.after(
            800,
            self.verificar_sessao
        )

        self.protocol(
            "WM_DELETE_WINDOW",
            self.fechar
        )


    # ========================================================
    # ESTILO
    # ========================================================

    def _configurar_estilo(self):

        style = ttk.Style(self)

        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            ".",
            background=COLORS["panel"],
            foreground=COLORS["text"],
            fieldbackground=COLORS["panel_2"],
            bordercolor=COLORS["line"],
            lightcolor=COLORS["line"],
            darkcolor=COLORS["line"],
            font=("Segoe UI", 10)
        )

        style.configure(
            "TEntry",
            fieldbackground=COLORS["panel_2"],
            foreground=COLORS["text"],
            insertcolor=COLORS["text"],
            padding=7
        )

        style.configure(
            "TCombobox",
            fieldbackground=COLORS["panel_2"],
            foreground=COLORS["text"],
            arrowcolor=COLORS["text"],
            padding=5
        )

        style.map(
            "TCombobox",
            fieldbackground=[("readonly", COLORS["panel_2"])],
            foreground=[("readonly", COLORS["text"])]
        )

        style.configure(
            "TButton",
            background=COLORS["panel_2"],
            foreground=COLORS["text"],
            borderwidth=0,
            padding=(12, 8)
        )

        style.map(
            "TButton",
            background=[
                ("active", COLORS["line"])
            ]
        )

        style.configure(
            "Accent.TButton",
            background=COLORS["accent"],
            foreground=COLORS["text"],
            borderwidth=0,
            padding=(14, 9),
            font=("Segoe UI", 10, "bold")
        )

        style.map(
            "Accent.TButton",
            background=[
                ("active", COLORS["accent_hover"]),
                ("disabled", COLORS["line"])
            ],
            foreground=[
                ("active", COLORS["text"]),
                ("disabled", COLORS["muted"])
            ]
        )

        # Botões de execução usam o verde-lima da paleta.
        style.configure(
            "Start.TButton",
            background=COLORS["success"],
            foreground=COLORS["bg"],
            borderwidth=0,
            padding=(14, 9),
            font=("Segoe UI", 10, "bold")
        )

        style.map(
            "Start.TButton",
            background=[
                ("active", COLORS["success_hover"]),
                ("disabled", COLORS["line"])
            ],
            foreground=[
                ("active", COLORS["bg"]),
                ("disabled", COLORS["muted"])
            ]
        )

        style.configure(
            "Danger.TButton",
            background=COLORS["danger_bg"],
            foreground=COLORS["danger"],
            borderwidth=0,
            padding=(12, 8)
        )

        style.map(
            "Danger.TButton",
            background=[
                ("active", COLORS["danger_hover"])
            ],
            foreground=[
                ("active", COLORS["text"])
            ]
        )

        style.configure(
            "Treeview",
            background=COLORS["panel"],
            fieldbackground=COLORS["panel"],
            foreground=COLORS["text"],
            rowheight=31,
            borderwidth=0
        )

        style.map(
            "Treeview",
            background=[
                ("selected", COLORS["accent"])
            ],
            foreground=[
                ("selected", COLORS["text"])
            ]
        )

        style.configure(
            "Treeview.Heading",
            background=COLORS["panel_2"],
            foreground=COLORS["muted"],
            borderwidth=0,
            padding=8,
            font=("Segoe UI", 9, "bold")
        )

        style.map(
            "Treeview.Heading",
            background=[
                ("active", COLORS["panel_2"])
            ]
        )

        style.configure(
            "Horizontal.TProgressbar",
            troughcolor=COLORS["panel_2"],
            background=COLORS["success"],
            bordercolor=COLORS["panel_2"],
            lightcolor=COLORS["success"],
            darkcolor=COLORS["success"]
        )


    # ========================================================
    # SHELL
    # ========================================================

    def _construir_shell(self):

        self.sidebar = tk.Frame(
            self,
            bg=COLORS["sidebar"],
            width=220
        )
        self.sidebar.pack(
            side="left",
            fill="y"
        )
        self.sidebar.pack_propagate(False)

        brand = tk.Frame(
            self.sidebar,
            bg=COLORS["sidebar"],
            padx=20,
            pady=22
        )
        brand.pack(fill="x")

        tk.Label(
            brand,
            text="MLDFORWARDER",
            bg=COLORS["sidebar"],
            fg=COLORS["text"],
            font=("Segoe UI", 15, "bold")
        ).pack(anchor="w")

        tk.Label(
            brand,
            text=f"CONTROL PANEL  /  v{VERSION}",
            bg=COLORS["sidebar"],
            fg=COLORS["accent"],
            font=("Segoe UI", 8, "bold")
        ).pack(anchor="w", pady=(3, 0))

        nav = tk.Frame(
            self.sidebar,
            bg=COLORS["sidebar"],
            padx=10
        )
        nav.pack(fill="x", pady=(6, 0))

        itens = [
            ("dashboard", "Dashboard"),
            ("canais", "Rotas"),
            ("retro", "Retroativo"),
            ("telegram", "Telegram"),
            ("config", "Configurações"),
            ("log", "Log"),
        ]

        for chave, texto in itens:
            botao = tk.Button(
                nav,
                text=texto,
                anchor="w",
                relief="flat",
                bd=0,
                padx=14,
                pady=10,
                cursor="hand2",
                font=("Segoe UI", 10),
                command=lambda c=chave: self.mostrar_pagina(c)
            )
            botao.pack(fill="x", pady=2)

            self.nav_buttons[
                chave
            ] = botao

        status_box = tk.Frame(
            self.sidebar,
            bg=COLORS["sidebar"],
            padx=20,
            pady=18
        )
        status_box.pack(
            side="bottom",
            fill="x"
        )

        self.sidebar_telegram_var = tk.StringVar(
            value="● Telegram não verificado"
        )

        self.sidebar_engine_var = tk.StringVar(
            value="● Sincronizador parado"
        )

        self.sidebar_telegram_label = tk.Label(
            status_box,
            textvariable=self.sidebar_telegram_var,
            bg=COLORS["sidebar"],
            fg=COLORS["muted"],
            anchor="w",
            font=("Segoe UI", 9)
        )
        self.sidebar_telegram_label.pack(
            fill="x",
            pady=2
        )

        self.sidebar_engine_label = tk.Label(
            status_box,
            textvariable=self.sidebar_engine_var,
            bg=COLORS["sidebar"],
            fg=COLORS["muted"],
            anchor="w",
            font=("Segoe UI", 9)
        )
        self.sidebar_engine_label.pack(
            fill="x",
            pady=2
        )

        self.main = tk.Frame(
            self,
            bg=COLORS["bg"]
        )
        self.main.pack(
            side="left",
            fill="both",
            expand=True
        )

        top = tk.Frame(
            self.main,
            bg=COLORS["bg"],
            padx=28,
            pady=20
        )
        top.pack(fill="x")

        self.page_title_var = tk.StringVar(
            value="Dashboard"
        )

        tk.Label(
            top,
            textvariable=self.page_title_var,
            bg=COLORS["bg"],
            fg=COLORS["text"],
            font=("Segoe UI", 19, "bold")
        ).pack(
            side="left"
        )

        self.content = tk.Frame(
            self.main,
            bg=COLORS["bg"],
            padx=28,
            pady=4
        )
        self.content.pack(
            fill="both",
            expand=True
        )


    def _construir_paginas(self):

        for chave in [
            "dashboard",
            "canais",
            "retro",
            "telegram",
            "config",
            "log",
        ]:
            pagina = tk.Frame(
                self.content,
                bg=COLORS["bg"]
            )
            pagina.place(
                relx=0,
                rely=0,
                relwidth=1,
                relheight=1
            )
            self.pages[chave] = pagina

        self._pagina_dashboard()
        self._pagina_canais()
        self._pagina_retro()
        self._pagina_telegram()
        self._pagina_config()
        self._pagina_log()


    def mostrar_pagina(self, chave):

        titulos = {
            "dashboard": "Dashboard",
            "canais": "Gerenciar rotas",
            "retro": "Sincronização retroativa",
            "telegram": "Conta Telegram",
            "config": "Configurações",
            "log": "Log de atividade",
        }

        self.pages[chave].tkraise()

        self.page_title_var.set(
            titulos[chave]
        )

        for nome, botao in (
            self.nav_buttons.items()
        ):
            ativo = nome == chave

            botao.configure(
                bg=(
                    COLORS["accent"]
                    if ativo
                    else COLORS["sidebar"]
                ),
                fg=(
                    COLORS["text"]
                    if ativo
                    else COLORS["muted"]
                ),
                activebackground=(
                    COLORS["accent_hover"]
                    if ativo
                    else COLORS["panel_2"]
                ),
                activeforeground=(
                    COLORS["text"]
                    if ativo
                    else COLORS["text"]
                ),
                font=(
                    "Segoe UI",
                    10,
                    "bold"
                ) if ativo else (
                    "Segoe UI",
                    10
                )
            )


    # ========================================================
    # COMPONENTES
    # ========================================================

    def _panel(
        self,
        parent,
        padx=18,
        pady=16
    ):

        return tk.Frame(
            parent,
            bg=COLORS["panel"],
            highlightbackground=COLORS["line"],
            highlightthickness=1,
            padx=padx,
            pady=pady
        )


    def _section_title(
        self,
        parent,
        texto
    ):

        return tk.Label(
            parent,
            text=texto,
            bg=COLORS["panel"],
            fg=COLORS["text"],
            font=("Segoe UI", 11, "bold")
        )


    def _muted(
        self,
        parent,
        texto=None,
        textvariable=None,
        wraplength=800
    ):

        return tk.Label(
            parent,
            text=texto,
            textvariable=textvariable,
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            justify="left",
            anchor="w",
            wraplength=wraplength,
            font=("Segoe UI", 9)
        )


    def _card(
        self,
        parent,
        titulo,
        variavel,
        cor=None
    ):

        frame = self._panel(
            parent,
            padx=16,
            pady=14
        )

        tk.Label(
            frame,
            text=titulo.upper(),
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=("Segoe UI", 8, "bold")
        ).pack(anchor="w")

        label = tk.Label(
            frame,
            textvariable=variavel,
            bg=COLORS["panel"],
            fg=cor or COLORS["text"],
            font=("Segoe UI", 13, "bold")
        )
        label.pack(
            anchor="w",
            pady=(7, 0)
        )

        return frame, label


    # ========================================================
    # DASHBOARD
    # ========================================================

    def _pagina_dashboard(self):

        page = self.pages[
            "dashboard"
        ]

        self.qtd_canais_var = tk.StringVar(
            value="0"
        )
        self.telegram_status_var = tk.StringVar(
            value="Não verificado"
        )
        self.normal_status_var = tk.StringVar(
            value="Parado"
        )
        self.retro_status_var = tk.StringVar(
            value="Parado"
        )
        self.pendencias_var = tk.StringVar(
            value="0"
        )

        cards = tk.Frame(
            page,
            bg=COLORS["bg"]
        )
        cards.pack(fill="x")

        card1, _ = self._card(
            cards,
            "Telegram",
            self.telegram_status_var
        )
        card1.pack(
            side="left",
            fill="x",
            expand=True,
            padx=(0, 5)
        )

        card2, _ = self._card(
            cards,
            "Rotas",
            self.qtd_canais_var
        )
        card2.pack(
            side="left",
            fill="x",
            expand=True,
            padx=5
        )

        card3, _ = self._card(
            cards,
            "Normal",
            self.normal_status_var
        )
        card3.pack(
            side="left",
            fill="x",
            expand=True,
            padx=5
        )

        card4, _ = self._card(
            cards,
            "Retroativo",
            self.retro_status_var
        )
        card4.pack(
            side="left",
            fill="x",
            expand=True,
            padx=5
        )

        card5, _ = self._card(
            cards,
            "Pendências",
            self.pendencias_var
        )
        card5.pack(
            side="left",
            fill="x",
            expand=True,
            padx=(5, 0)
        )

        engine = self._panel(
            page,
            padx=20,
            pady=18
        )
        engine.pack(
            fill="x",
            pady=(16, 0)
        )

        self._section_title(
            engine,
            "Sincronizador normal"
        ).pack(anchor="w")

        self._muted(
            engine,
            (
                "Mantém todas as rotas configuradas sincronizadas "
                "continuamente. Rotas novas começam no ID mais recente."
            )
        ).pack(
            anchor="w",
            pady=(4, 14)
        )

        actions = tk.Frame(
            engine,
            bg=COLORS["panel"]
        )
        actions.pack(fill="x")

        self.start_normal_button = ttk.Button(
            actions,
            text="INICIAR SINCRONIZADOR",
            style="Start.TButton",
            command=self.iniciar_normal
        )
        self.start_normal_button.pack(
            side="left"
        )

        self.stop_normal_button = ttk.Button(
            actions,
            text="PARAR",
            style="Danger.TButton",
            command=self.parar_normal
        )
        self.stop_normal_button.pack(
            side="left",
            padx=(8, 0)
        )

        quick = self._panel(
            page,
            padx=20,
            pady=18
        )
        quick.pack(
            fill="x",
            pady=(16, 0)
        )

        self._section_title(
            quick,
            "Acesso rápido"
        ).pack(anchor="w")

        row = tk.Frame(
            quick,
            bg=COLORS["panel"]
        )
        row.pack(
            fill="x",
            pady=(12, 0)
        )

        ttk.Button(
            row,
            text="Gerenciar rotas",
            command=lambda: self.mostrar_pagina(
                "canais"
            )
        ).pack(
            side="left",
            padx=(0, 8)
        )

        ttk.Button(
            row,
            text="Importar histórico",
            command=lambda: self.mostrar_pagina(
                "retro"
            )
        ).pack(
            side="left",
            padx=(0, 8)
        )

        ttk.Button(
            row,
            text="Conta Telegram",
            command=lambda: self.mostrar_pagina(
                "telegram"
            )
        ).pack(
            side="left"
        )


    # ========================================================
    # CANAIS
    # ========================================================

    def _pagina_canais(self):

        page = self.pages[
            "canais"
        ]

        toolbar = tk.Frame(
            page,
            bg=COLORS["bg"]
        )
        toolbar.pack(
            fill="x",
            pady=(0, 12)
        )

        ttk.Button(
            toolbar,
            text="+ Adicionar",
            style="Start.TButton",
            command=self.adicionar_canal
        ).pack(side="left")

        ttk.Button(
            toolbar,
            text="Editar",
            command=self.editar_canal
        ).pack(
            side="left",
            padx=7
        )

        ttk.Button(
            toolbar,
            text="Remover",
            style="Danger.TButton",
            command=self.remover_canal
        ).pack(side="left")

        ttk.Button(
            toolbar,
            text="Limpar progresso",
            command=self.limpar_progresso_canal
        ).pack(
            side="left",
            padx=(14, 0)
        )

        ttk.Button(
            toolbar,
            text="Atualizar",
            command=self.recarregar_canais
        ).pack(side="right")

        holder = self._panel(
            page,
            padx=0,
            pady=0
        )
        holder.pack(
            fill="both",
            expand=True
        )

        cols = (
            "nome",
            "origem",
            "topico_origem",
            "destino",
            "topico_destino",
            "normal",
            "retro",
            "falhas"
        )

        self.channel_tree = ttk.Treeview(
            holder,
            columns=cols,
            show="headings",
            selectmode="browse"
        )

        headers = {
            "nome": "Nome",
            "origem": "Origem",
            "topico_origem": "Tópico origem",
            "destino": "Destino",
            "topico_destino": "Tópico destino",
            "normal": "Último ID normal",
            "retro": "Último ID retro",
            "falhas": "Pendências",
        }

        widths = {
            "nome": 170,
            "origem": 170,
            "topico_origem": 95,
            "destino": 150,
            "topico_destino": 100,
            "normal": 115,
            "retro": 115,
            "falhas": 80,
        }

        for col in cols:
            self.channel_tree.heading(
                col,
                text=headers[col]
            )
            self.channel_tree.column(
                col,
                width=widths[col]
            )

        scrollbar = ttk.Scrollbar(
            holder,
            orient="vertical",
            command=self.channel_tree.yview
        )

        self.channel_tree.configure(
            yscrollcommand=scrollbar.set
        )

        self.channel_tree.pack(
            side="left",
            fill="both",
            expand=True
        )
        scrollbar.pack(
            side="right",
            fill="y"
        )

        self.channel_tree.bind(
            "<Double-1>",
            lambda _event: self.editar_canal()
        )


    # ========================================================
    # RETROATIVO
    # ========================================================

    def _pagina_retro(self):

        page = self.pages[
            "retro"
        ]

        panel = self._panel(
            page,
            padx=20,
            pady=18
        )
        panel.pack(fill="x")

        self._section_title(
            panel,
            "Importação de mensagens antigas"
        ).grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="w"
        )

        self._muted(
            panel,
            (
                "Escolha uma rota específica ou processe todas. "
                "O progresso é salvo e pode ser retomado de onde parou."
            )
        ).grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(4, 14)
        )

        self.retro_channel_var = tk.StringVar()

        self._form_label(
            panel,
            "Rota"
        ).grid(
            row=2,
            column=0,
            sticky="w",
            pady=6
        )

        self.retro_channel_combo = ttk.Combobox(
            panel,
            textvariable=self.retro_channel_var,
            state="readonly",
            width=54
        )
        self.retro_channel_combo.grid(
            row=2,
            column=1,
            sticky="ew",
            padx=(14, 0),
            pady=6
        )

        self._field_description(
            panel,
            (
                "Define qual origem será importada. “Todas as rotas” "
                "processa cada rota cadastrada em sequência."
            )
        ).grid(
            row=3,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(0, 8)
        )

        self.retro_limit_var = tk.StringVar()
        self.retro_start_var = tk.StringVar()
        self.retro_batch_var = tk.StringVar()
        self.retro_attempts_var = tk.StringVar()

        fields = [
            (
                "Limite (0 = todo o histórico)",
                self.retro_limit_var,
                (
                    "Quantidade máxima de mensagens antigas a importar por rota. "
                    "Use 0 para importar todo o histórico disponível. Padrão: 1000."
                )
            ),
            (
                "Começar pelo ID",
                self.retro_start_var,
                (
                    "Ignora mensagens com ID menor ou igual a este número. "
                    "Use 0 para começar desde a mensagem mais antiga. Padrão: 0."
                )
            ),
            (
                "Tamanho do lote",
                self.retro_batch_var,
                (
                    "Número de mensagens preparado por etapa. Um lote maior pode "
                    "acelerar a importação, mas aumenta o uso da API. Padrão: 100."
                )
            ),
            (
                "Tentativas em caso de erro",
                self.retro_attempts_var,
                (
                    "Limite de tentativas de envio para cada mensagem com erro. "
                    "Ao atingir esse número, ela permanece nas pendências. Padrão: 3."
                )
            ),
        ]

        for index, (
            label,
            var,
            description
        ) in enumerate(fields):
            row = 4 + (index * 2)

            self._form_label(
                panel,
                label
            ).grid(
                row=row,
                column=0,
                sticky="w",
                pady=6
            )

            self._field_description(
                panel,
                description
            ).grid(
                row=row + 1,
                column=0,
                columnspan=2,
                sticky="w",
                pady=(0, 7)
            )

            ttk.Entry(
                panel,
                textvariable=var,
                width=22
            ).grid(
                row=row,
                column=1,
                sticky="w",
                padx=(14, 0),
                pady=6
            )

        panel.columnconfigure(
            1,
            weight=1
        )

        status = self._panel(
            page,
            padx=20,
            pady=18
        )
        status.pack(
            fill="x",
            pady=(16, 0)
        )

        top = tk.Frame(
            status,
            bg=COLORS["panel"]
        )
        top.pack(fill="x")

        self.retro_progress_text_var = tk.StringVar(
            value="Pronto"
        )

        self._section_title(
            top,
            "Progresso"
        ).pack(side="left")

        tk.Label(
            top,
            textvariable=self.retro_progress_text_var,
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9)
        ).pack(side="right")

        self.retro_progress = ttk.Progressbar(
            status,
            mode="determinate",
            maximum=100,
            value=0
        )
        self.retro_progress.pack(
            fill="x",
            pady=(12, 14)
        )

        actions = tk.Frame(
            status,
            bg=COLORS["panel"]
        )
        actions.pack(fill="x")

        self.start_retro_button = ttk.Button(
            actions,
            text="INICIAR RETROATIVO",
            style="Start.TButton",
            command=self.iniciar_retro
        )
        self.start_retro_button.pack(
            side="left"
        )

        self.stop_retro_button = ttk.Button(
            actions,
            text="PARAR",
            style="Danger.TButton",
            command=self.parar_retro
        )
        self.stop_retro_button.pack(
            side="left",
            padx=(8, 0)
        )


    # ========================================================
    # TELEGRAM
    # ========================================================

    def abrir_portal_api(self):

        try:
            abriu = webbrowser.open_new_tab(
                API_PORTAL_URL
            )
        except Exception as erro:
            abriu = False
            detalhe = str(erro)
        else:
            detalhe = API_PORTAL_URL

        if not abriu:
            messagebox.showerror(
                "Portal da API",
                (
                    "Não foi possível abrir o navegador.\n\n"
                    f"Acesse manualmente: {API_PORTAL_URL}\n\n"
                    f"Detalhes: {detalhe}"
                ),
                parent=self
            )

    def _pagina_telegram(self):

        page = self.pages[
            "telegram"
        ]

        settings = self._panel(
            page,
            padx=20,
            pady=18
        )
        settings.pack(fill="x")

        self._section_title(
            settings,
            "Credenciais da API"
        ).grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="w"
        )

        self._muted(
            settings,
            (
                "As credenciais são armazenadas localmente no arquivo .env."
            )
        ).grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(4, 5)
        )

        api_link = tk.Label(
            settings,
            text=(
                "Obter API ID e API Hash em my.telegram.org  ↗"
            ),
            bg=COLORS["panel"],
            fg=COLORS["success"],
            activeforeground=COLORS["success_hover"],
            cursor="hand2",
            font=("Segoe UI", 9, "underline"),
            takefocus=True
        )
        api_link.grid(
            row=2,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(0, 12)
        )
        api_link.bind(
            "<Button-1>",
            lambda _event: self.abrir_portal_api()
        )
        api_link.bind(
            "<Return>",
            lambda _event: self.abrir_portal_api()
        )
        api_link.bind(
            "<space>",
            lambda _event: self.abrir_portal_api()
        )

        self.api_id_var = tk.StringVar()
        self.api_hash_var = tk.StringVar()
        self.session_var = tk.StringVar()

        credentials = [
            ("API ID", self.api_id_var, False),
            ("API Hash", self.api_hash_var, True),
            ("Nome da sessão", self.session_var, False),
        ]

        for row, (
            label,
            var,
            secret
        ) in enumerate(
            credentials,
            start=3
        ):

            self._form_label(
                settings,
                label
            ).grid(
                row=row,
                column=0,
                sticky="w",
                pady=6
            )

            ttk.Entry(
                settings,
                textvariable=var,
                width=55,
                show="*" if secret else ""
            ).grid(
                row=row,
                column=1,
                sticky="ew",
                padx=(14, 0),
                pady=6
            )

        settings.columnconfigure(
            1,
            weight=1
        )

        ttk.Button(
            settings,
            text="SALVAR CREDENCIAIS",
            style="Start.TButton",
            command=self.salvar_telegram
        ).grid(
            row=6,
            column=1,
            sticky="e",
            pady=(12, 0)
        )

        login = self._panel(
            page,
            padx=20,
            pady=18
        )
        login.pack(
            fill="x",
            pady=(16, 0)
        )

        row_status = tk.Frame(
            login,
            bg=COLORS["panel"]
        )
        row_status.pack(fill="x")

        self._section_title(
            row_status,
            "Sessão Telegram"
        ).pack(side="left")

        self.account_status_var = tk.StringVar(
            value="Não verificada"
        )

        self.account_status_label = tk.Label(
            row_status,
            textvariable=self.account_status_var,
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=("Segoe UI", 10, "bold")
        )
        self.account_status_label.pack(
            side="right"
        )

        self.account_detail_var = tk.StringVar(
            value=""
        )

        self._muted(
            login,
            textvariable=self.account_detail_var
        ).pack(
            fill="x",
            pady=(6, 14)
        )

        form = tk.Frame(
            login,
            bg=COLORS["panel"]
        )
        form.pack(fill="x")

        self.phone_var = tk.StringVar()
        self.code_var = tk.StringVar()
        self.password_var = tk.StringVar()

        self._form_label(
            form,
            "Telefone"
        ).grid(
            row=0,
            column=0,
            sticky="w",
            pady=6
        )

        ttk.Entry(
            form,
            textvariable=self.phone_var,
            width=30
        ).grid(
            row=0,
            column=1,
            sticky="w",
            padx=(14, 8),
            pady=6
        )

        ttk.Button(
            form,
            text="Enviar código",
            command=self.enviar_codigo
        ).grid(
            row=0,
            column=2,
            sticky="w",
            pady=6
        )

        self._form_label(
            form,
            "Código recebido"
        ).grid(
            row=1,
            column=0,
            sticky="w",
            pady=6
        )

        ttk.Entry(
            form,
            textvariable=self.code_var,
            width=30
        ).grid(
            row=1,
            column=1,
            sticky="w",
            padx=(14, 8),
            pady=6
        )

        ttk.Button(
            form,
            text="Confirmar código",
            command=self.confirmar_codigo
        ).grid(
            row=1,
            column=2,
            sticky="w",
            pady=6
        )

        self._form_label(
            form,
            "Senha 2FA"
        ).grid(
            row=2,
            column=0,
            sticky="w",
            pady=6
        )

        ttk.Entry(
            form,
            textvariable=self.password_var,
            width=30,
            show="*"
        ).grid(
            row=2,
            column=1,
            sticky="w",
            padx=(14, 8),
            pady=6
        )

        ttk.Button(
            form,
            text="Confirmar senha",
            command=self.confirmar_senha
        ).grid(
            row=2,
            column=2,
            sticky="w",
            pady=6
        )

        footer = tk.Frame(
            login,
            bg=COLORS["panel"]
        )
        footer.pack(
            fill="x",
            pady=(14, 0)
        )

        ttk.Button(
            footer,
            text="Verificar sessão",
            command=self.verificar_sessao
        ).pack(side="left")

        ttk.Button(
            footer,
            text="Sair da conta",
            style="Danger.TButton",
            command=self.sair_da_conta
        ).pack(
            side="right"
        )


    # ========================================================
    # CONFIGURAÇÕES
    # ========================================================

    def _pagina_config(self):

        page = self.pages[
            "config"
        ]

        normal = self._panel(
            page,
            padx=20,
            pady=18
        )
        normal.pack(fill="x")

        self._section_title(
            normal,
            "Sincronização normal"
        ).grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="w"
        )

        self._muted(
            normal,
            (
                "Estas opções controlam como o MLDForwarder procura e processa "
                "mensagens novas. Os valores padrão funcionam bem na maioria dos casos."
            )
        ).grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(4, 14)
        )

        self.normal_batch_var = tk.StringVar()
        self.normal_interval_var = tk.StringVar()

        fields = [
            (
                "Tamanho do lote",
                self.normal_batch_var,
                (
                    "Quantidade máxima de mensagens processadas em cada ciclo. "
                    "Valores maiores ajudam quando há muitas mensagens acumuladas, "
                    "mas aumentam o uso da API. Padrão: 100."
                )
            ),
            (
                "Intervalo entre verificações (s)",
                self.normal_interval_var,
                (
                    "Tempo de espera antes de procurar novas mensagens novamente. "
                    "Um valor menor sincroniza mais rápido; um valor maior faz menos "
                    "consultas ao Telegram. Padrão: 5 segundos."
                )
            )
        ]

        for index, (
            label,
            var,
            description
        ) in enumerate(fields):
            row = 2 + (index * 2)

            self._form_label(
                normal,
                label
            ).grid(
                row=row,
                column=0,
                sticky="w",
                pady=7
            )

            ttk.Entry(
                normal,
                textvariable=var,
                width=22
            ).grid(
                row=row,
                column=1,
                sticky="w",
                padx=(14, 0),
                pady=7
            )

            self._field_description(
                normal,
                description
            ).grid(
                row=row + 1,
                column=0,
                columnspan=2,
                sticky="w",
                pady=(0, 8)
            )

        ttk.Button(
            normal,
            text="SALVAR CONFIGURAÇÕES",
            style="Start.TButton",
            command=self.salvar_configuracoes
        ).grid(
            row=6,
            column=1,
            sticky="e",
            pady=(14, 0)
        )

        normal.columnconfigure(
            1,
            weight=1
        )


    def _form_label(
        self,
        parent,
        texto
    ):

        return tk.Label(
            parent,
            text=texto,
            bg=COLORS["panel"],
            fg=COLORS["text"],
            font=("Segoe UI", 9)
        )


    def _field_description(
        self,
        parent,
        texto
    ):

        return tk.Label(
            parent,
            text=texto,
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9),
            justify="left",
            anchor="w",
            wraplength=760
        )


    # ========================================================
    # LOG
    # ========================================================

    def _pagina_log(self):

        page = self.pages[
            "log"
        ]

        toolbar = tk.Frame(
            page,
            bg=COLORS["bg"]
        )
        toolbar.pack(
            fill="x",
            pady=(0, 10)
        )

        ttk.Button(
            toolbar,
            text="Limpar log",
            command=self.limpar_log
        ).pack(side="right")

        holder = self._panel(
            page,
            padx=0,
            pady=0
        )
        holder.pack(
            fill="both",
            expand=True
        )

        self.log_text = tk.Text(
            holder,
            bg="#111719",
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            selectbackground=COLORS["accent"],
            selectforeground="#111111",
            relief="flat",
            borderwidth=0,
            padx=14,
            pady=12,
            wrap="word",
            font=("Cascadia Mono", 9),
            state="disabled"
        )

        self.log_text.tag_configure(
            "success",
            foreground=COLORS["success"]
        )
        self.log_text.tag_configure(
            "error",
            foreground=COLORS["danger"]
        )
        self.log_text.tag_configure(
            "warning",
            foreground=COLORS["warning"]
        )
        self.log_text.tag_configure(
            "accent",
            foreground=COLORS["accent"]
        )

        scroll = ttk.Scrollbar(
            holder,
            orient="vertical",
            command=self.log_text.yview
        )

        self.log_text.configure(
            yscrollcommand=scroll.set
        )

        self.log_text.pack(
            side="left",
            fill="both",
            expand=True
        )
        scroll.pack(
            side="right",
            fill="y"
        )


    # ========================================================
    # DADOS / CONFIGURAÇÕES
    # ========================================================

    def recarregar_tudo(self):

        self.recarregar_canais()
        self.carregar_configuracoes()


    def recarregar_canais(self):

        try:
            self.channels = carregar_canais()

        except Exception as erro:
            messagebox.showerror(
                "Erro",
                str(erro)
            )
            self.channels = {}

        sync_progress = carregar_json(
            SYNC_PROGRESS_FILE,
            {}
        )
        retro_progress = carregar_json(
            HISTORICO_PROGRESS_FILE,
            {}
        )

        for item in (
            self.channel_tree.get_children()
        ):
            self.channel_tree.delete(
                item
            )

        total_falhas = 0

        for chave_rota, data in (
            self.channels.items()
        ):

            normal_id = self._normal_last_id(
                sync_progress.get(
                    str(chave_rota)
                )
            )

            retro_data = retro_progress.get(
                str(chave_rota),
                {}
            )

            retro_id = (
                retro_data.get("last_id", "—")
                if isinstance(retro_data, dict)
                else "—"
            )

            falhas = (
                len(
                    retro_data.get(
                        "failed_messages",
                        []
                    )
                )
                if isinstance(retro_data, dict)
                else 0
            )

            total_falhas += falhas

            self.channel_tree.insert(
                "",
                "end",
                iid=str(chave_rota),
                values=(
                    data.get("name", ""),
                    data.get("source_id", ""),
                    data.get("topic_id") or "—",
                    data.get("target_id", ""),
                    data.get("target_topic_id") or "—",
                    normal_id,
                    retro_id,
                    falhas
                )
            )

        self.qtd_canais_var.set(
            str(len(self.channels))
        )

        self.pendencias_var.set(
            str(total_falhas)
        )

        self._atualizar_retro_combo()


    def _normal_last_id(
        self,
        value
    ):

        if value is None:
            return "—"

        if isinstance(value, dict):
            return value.get(
                "last_synced_id",
                value.get(
                    "last_id",
                    "—"
                )
            )

        return value


    def _atualizar_retro_combo(self):

        values = [
            "Todas as rotas"
        ]

        self.retro_map = {
            "Todas as rotas": None
        }

        for chave_rota, data in (
            self.channels.items()
        ):
            nome = data.get(
                "name",
                chave_rota
            )

            origem = data.get(
                "source_id",
                chave_rota
            )
            topico_id = data.get(
                "topic_id"
            )
            destino = data.get(
                "target_id",
                ""
            )
            topico_destino_id = data.get(
                "target_topic_id"
            )

            if topico_id is None:
                label = f"{nome} — {origem}"
            else:
                label = (
                    f"{nome} — {origem} "
                    f"[tópico {topico_id}]"
                )

            label += f" > {destino}"

            if topico_destino_id is not None:
                label += f" [tópico {topico_destino_id}]"

            values.append(
                label
            )

            self.retro_map[
                label
            ] = str(chave_rota)

        self.retro_channel_combo[
            "values"
        ] = values

        if (
            self.retro_channel_var.get()
            not in values
        ):
            self.retro_channel_var.set(
                values[0]
            )


    def carregar_configuracoes(self):

        env = ler_env()
        app = carregar_config_app()
        normal = carregar_config_normal()
        retro = carregar_config_retro()

        self.api_id_var.set(
            env.get("API_ID", "")
        )
        self.api_hash_var.set(
            env.get("API_HASH", "")
        )
        self.session_var.set(
            app["session_file"]
        )

        self.normal_batch_var.set(
            str(
                normal["tamanho_lote"]
            )
        )
        self.normal_interval_var.set(
            str(
                normal["intervalo"]
            )
        )

        self.retro_limit_var.set(
            str(
                retro["limite"]
            )
        )
        self.retro_start_var.set(
            str(
                retro["a_partir_do_id"]
            )
        )
        self.retro_batch_var.set(
            str(
                retro["tamanho_lote"]
            )
        )
        self.retro_attempts_var.set(
            str(
                retro["tentativas_erro"]
            )
        )


    # ========================================================
    # CANAIS
    # ========================================================

    def adicionar_canal(self):

        dialog = ChannelDialog(
            self,
            "Adicionar rota",
            settings_provider=self._topic_settings
        )
        self.wait_window(dialog)

        if not dialog.resultado:
            return

        item = dialog.resultado
        key = montar_chave_rota(
            item["source_id"],
            item.get("topic_id")
        )

        if key in self.channels:
            messagebox.showerror(
                "Rota existente",
                "Essa combinação de origem e tópico já está configurada."
            )
            return

        self.channels[key] = {
            "source_id": item["source_id"],
            "target_id": item["target_id"],
            "topic_id": item.get("topic_id"),
            "target_topic_id": item.get("target_topic_id"),
            "name": item["name"]
        }

        salvar_json(
            CHANNELS_FILE,
            self.channels
        )

        self.recarregar_canais()

        self.log(
            f'[CONFIG] Rota adicionada: {item["name"]}',
            "success"
        )


    def _selected_channel(self):

        selection = (
            self.channel_tree.selection()
        )

        if not selection:
            messagebox.showinfo(
                "Rotas",
                "Selecione uma rota."
            )
            return None

        return selection[0]


    def editar_canal(self):

        old_source = (
            self._selected_channel()
        )

        if old_source is None:
            return

        old = self.channels[
            old_source
        ]

        dialog = ChannelDialog(
            self,
            "Editar rota",
            {
                "source_id": old.get(
                    "source_id",
                    old_source
                ),
                "topic_id": old.get(
                    "topic_id"
                ),
                "target_id": old.get(
                    "target_id",
                    ""
                ),
                "target_topic_id": old.get(
                    "target_topic_id"
                ),
                "name": old.get(
                    "name",
                    ""
                )
            },
            settings_provider=self._topic_settings
        )
        self.wait_window(dialog)

        if not dialog.resultado:
            return

        item = dialog.resultado
        new_source = montar_chave_rota(
            item["source_id"],
            item.get("topic_id")
        )

        if (
            new_source != old_source
            and new_source in self.channels
        ):
            messagebox.showerror(
                "Rota existente",
                "A nova combinação de origem e tópico já está configurada."
            )
            return

        del self.channels[
            old_source
        ]

        self.channels[
            new_source
        ] = {
            "source_id": item["source_id"],
            "target_id": item["target_id"],
            "topic_id": item.get("topic_id"),
            "target_topic_id": item.get("target_topic_id"),
            "name": item["name"]
        }

        salvar_json(
            CHANNELS_FILE,
            self.channels
        )

        if new_source != old_source:
            self._remove_progress(
                old_source
            )

        self.recarregar_canais()

        self.log(
            f'[CONFIG] Rota atualizada: {item["name"]}',
            "success"
        )


    def remover_canal(self):

        source = self._selected_channel()

        if source is None:
            return

        name = (
            self.channels[source]
            .get(
                "name",
                source
            )
        )

        if not messagebox.askyesno(
            "Remover rota",
            (
                f'Remover a rota "{name}" da configuração?\n\n'
                "Nenhuma mensagem será apagada no Telegram."
            )
        ):
            return

        del self.channels[
            source
        ]

        salvar_json(
            CHANNELS_FILE,
            self.channels
        )

        if messagebox.askyesno(
            "Remover progresso",
            (
                "Deseja remover também os registros "
                "de progresso dessa rota?"
            )
        ):
            self._remove_progress(
                source
            )

        self.recarregar_canais()

        self.log(
            f"[CONFIG] Rota removida: {name}",
            "warning"
        )


    def limpar_progresso_canal(self):

        source = self._selected_channel()

        if source is None:
            return

        name = (
            self.channels[source]
            .get(
                "name",
                source
            )
        )

        if not messagebox.askyesno(
            "Limpar progresso",
            (
                f'Limpar o progresso de "{name}"?\n\n'
                "Normal: será reinicializado no ID mais recente.\n"
                "Retroativo: voltará ao ID inicial configurado."
            )
        ):
            return

        self._remove_progress(
            source
        )
        self.recarregar_canais()

        self.log(
            f"[CONFIG] Progresso limpo: {name}",
            "warning"
        )


    def _remove_progress(
        self,
        source
    ):

        for path in [
            SYNC_PROGRESS_FILE,
            HISTORICO_PROGRESS_FILE
        ]:
            data = carregar_json(
                path,
                {}
            )

            if (
                isinstance(data, dict)
                and str(source) in data
            ):
                del data[
                    str(source)
                ]
                salvar_json(
                    path,
                    data
                )


    # ========================================================
    # SALVAR CONFIGURAÇÕES
    # ========================================================

    def salvar_telegram(
        self,
        silencioso=False
    ):

        api_id = self.api_id_var.get().strip()
        api_hash = self.api_hash_var.get().strip()
        session = self.session_var.get().strip()

        try:
            if not api_id:
                raise ValueError(
                    "Informe o API ID."
                )
            int(api_id)

            if not api_hash:
                raise ValueError(
                    "Informe o API Hash."
                )

            if not session:
                raise ValueError(
                    "Informe o nome da sessão."
                )

        except ValueError as erro:
            if not silencioso:
                messagebox.showerror(
                    "Configuração inválida",
                    str(erro)
                )
            return False

        atualizar_env(
            {
                "API_ID": api_id,
                "API_HASH": api_hash
            }
        )

        salvar_json(
            APP_CONFIG_FILE,
            {
                "session_file": session
            }
        )

        if not silencioso:
            self.log(
                "[CONFIG] Credenciais Telegram salvas.",
                "success"
            )
            messagebox.showinfo(
                "Telegram",
                "Credenciais salvas."
            )

        return True


    def salvar_configuracoes(
        self,
        silencioso=False
    ):

        try:
            normal_batch = int(
                self.normal_batch_var.get()
            )
            normal_interval = int(
                self.normal_interval_var.get()
            )

            retro_limit = int(
                self.retro_limit_var.get()
            )
            retro_start = int(
                self.retro_start_var.get()
            )
            retro_batch = int(
                self.retro_batch_var.get()
            )
            retro_attempts = int(
                self.retro_attempts_var.get()
            )

            if (
                normal_batch <= 0
                or normal_interval <= 0
                or retro_limit < 0
                or retro_start < 0
                or retro_batch <= 0
                or retro_attempts <= 0
            ):
                raise ValueError

        except ValueError:
            if not silencioso:
                messagebox.showerror(
                    "Configuração inválida",
                    (
                        "Lotes, intervalo e tentativas precisam "
                        "ser maiores que zero. Limite e ID inicial "
                        "podem ser zero."
                    )
                )
            return False

        salvar_json(
            NORMAL_CONFIG_FILE,
            {
                "tamanho_lote": normal_batch,
                "intervalo": normal_interval
            }
        )

        salvar_json(
            RETRO_CONFIG_FILE,
            {
                "limite": retro_limit,
                "a_partir_do_id": retro_start,
                "tamanho_lote": retro_batch,
                "tentativas_erro": retro_attempts
            }
        )

        if not silencioso:
            self.log(
                "[CONFIG] Configurações salvas.",
                "success"
            )
            messagebox.showinfo(
                "Configurações",
                "Configurações salvas."
            )

        return True


    # ========================================================
    # AUTENTICAÇÃO TELEGRAM
    # ========================================================

    def _topic_settings(self):

        if not self.salvar_telegram(
            silencioso=True
        ):
            return None

        return (
            int(self.api_id_var.get().strip()),
            self.api_hash_var.get().strip(),
            self.session_var.get().strip()
        )

    def _auth_settings(self):

        if not self.salvar_telegram(
            silencioso=True
        ):
            messagebox.showerror(
                "Telegram",
                (
                    "Preencha API ID, API Hash e nome "
                    "da sessão antes de autenticar."
                )
            )
            self.mostrar_pagina(
                "telegram"
            )
            return None

        return (
            int(self.api_id_var.get().strip()),
            self.api_hash_var.get().strip(),
            self.session_var.get().strip()
        )


    def _auth_thread(
        self,
        func,
        callback
    ):

        if self.auth_busy:
            messagebox.showinfo(
                "Telegram",
                "Já existe uma operação de autenticação em andamento."
            )
            return

        self.auth_busy = True
        self.account_status_var.set(
            "Verificando..."
        )
        self.account_status_label.configure(
            fg=COLORS["warning"]
        )

        def worker():

            try:
                result = func()

            except Exception as erro:
                result = {
                    "ok": False,
                    "error": str(erro)
                }

            self.after(
                0,
                callback,
                result
            )

        threading.Thread(
            target=worker,
            daemon=True
        ).start()


    def _auth_done(self):

        self.auth_busy = False


    def verificar_sessao(self):

        settings = self._auth_settings()

        if not settings:
            return

        api_id, api_hash, session = settings

        self._auth_thread(
            lambda: auth_service.executar(
                auth_service.verificar_sessao(
                    api_id,
                    api_hash,
                    session
                )
            ),
            self._resultado_status_sessao
        )


    def _resultado_status_sessao(
        self,
        result
    ):

        self._auth_done()

        if not result.get("ok"):
            self._set_telegram_status(
                False,
                "Erro ao verificar sessão"
            )
            self.account_detail_var.set(
                result.get(
                    "error",
                    "Erro desconhecido."
                )
            )
            return

        if result.get("authorized"):
            name = result.get(
                "name",
                ""
            )
            username = result.get(
                "username",
                ""
            )

            detail = " ".join(
                item
                for item in [
                    name,
                    username
                ]
                if item
            )

            self._set_telegram_status(
                True,
                "Conectado"
            )
            self.account_detail_var.set(
                detail or "Sessão autorizada."
            )

        else:
            self._set_telegram_status(
                False,
                "Não autenticado"
            )
            self.account_detail_var.set(
                "Use o telefone abaixo para iniciar a autenticação."
            )


    def enviar_codigo(self):

        if self._processo_em_execucao():
            messagebox.showwarning(
                "Telegram",
                (
                    "Pare as sincronizações antes de "
                    "alterar a autenticação."
                )
            )
            return

        settings = self._auth_settings()

        if not settings:
            return

        phone = self.phone_var.get().strip()

        if not phone:
            messagebox.showerror(
                "Telefone",
                (
                    "Informe o telefone com código do país, "
                    "por exemplo +55..."
                )
            )
            return

        api_id, api_hash, session = settings
        self.auth_phone = phone

        self._auth_thread(
            lambda: auth_service.executar(
                auth_service.enviar_codigo(
                    api_id,
                    api_hash,
                    session,
                    phone
                )
            ),
            self._resultado_enviar_codigo
        )


    def _resultado_enviar_codigo(
        self,
        result
    ):

        self._auth_done()

        if not result.get("ok"):
            self._set_telegram_status(
                False,
                "Falha no envio"
            )
            messagebox.showerror(
                "Telegram",
                result.get(
                    "error",
                    "Não foi possível enviar o código."
                )
            )
            return

        if result.get(
            "already_authorized"
        ):
            self.verificar_sessao()
            return

        self.auth_phone_code_hash = (
            result.get(
                "phone_code_hash"
            )
        )

        self.account_status_var.set(
            "Código enviado"
        )
        self.account_status_label.configure(
            fg=COLORS["warning"]
        )
        self.account_detail_var.set(
            "Digite o código recebido no campo abaixo."
        )
        self.log(
            "[TELEGRAM] Código de autenticação solicitado.",
            "accent"
        )


    def confirmar_codigo(self):

        settings = self._auth_settings()

        if not settings:
            return

        code = self.code_var.get().strip()

        if not self.auth_phone:
            messagebox.showerror(
                "Telegram",
                "Solicite um código primeiro."
            )
            return

        if not code:
            messagebox.showerror(
                "Telegram",
                "Informe o código recebido."
            )
            return

        if not self.auth_phone_code_hash:
            messagebox.showerror(
                "Telegram",
                (
                    "O código de autenticação não está mais "
                    "associado a esta sessão da GUI. "
                    "Solicite um novo código."
                )
            )
            return

        api_id, api_hash, session = settings

        self._auth_thread(
            lambda: auth_service.executar(
                auth_service.confirmar_codigo(
                    api_id,
                    api_hash,
                    session,
                    self.auth_phone,
                    code,
                    self.auth_phone_code_hash
                )
            ),
            self._resultado_confirmar_codigo
        )


    def _resultado_confirmar_codigo(
        self,
        result
    ):

        self._auth_done()

        if not result.get("ok"):
            messagebox.showerror(
                "Telegram",
                result.get(
                    "error",
                    "Não foi possível confirmar o código."
                )
            )
            return

        if result.get(
            "need_password"
        ):
            self.account_status_var.set(
                "Senha 2FA necessária"
            )
            self.account_status_label.configure(
                fg=COLORS["warning"]
            )
            self.account_detail_var.set(
                "A conta usa verificação em duas etapas. Informe a senha 2FA."
            )
            self.log(
                "[TELEGRAM] Senha 2FA solicitada.",
                "warning"
            )
            return

        self.auth_phone_code_hash = None
        self.code_var.set("")

        self.log(
            "[TELEGRAM] Código confirmado.",
            "success"
        )
        self.verificar_sessao()


    def confirmar_senha(self):

        settings = self._auth_settings()

        if not settings:
            return

        password = self.password_var.get()

        if not password:
            messagebox.showerror(
                "Telegram",
                "Informe a senha de verificação em duas etapas."
            )
            return

        api_id, api_hash, session = settings

        self._auth_thread(
            lambda: auth_service.executar(
                auth_service.confirmar_senha(
                    api_id,
                    api_hash,
                    session,
                    password
                )
            ),
            self._resultado_confirmar_senha
        )


    def _resultado_confirmar_senha(
        self,
        result
    ):

        self._auth_done()

        self.password_var.set("")

        if not result.get("ok"):
            messagebox.showerror(
                "Telegram",
                result.get(
                    "error",
                    "Não foi possível confirmar a senha."
                )
            )
            return

        self.auth_phone_code_hash = None
        self.log(
            "[TELEGRAM] Autenticação concluída.",
            "success"
        )
        self.verificar_sessao()


    def sair_da_conta(self):

        if self._processo_em_execucao():
            messagebox.showwarning(
                "Telegram",
                "Pare as sincronizações antes de sair da conta."
            )
            return

        if not messagebox.askyesno(
            "Sair da conta",
            (
                "Encerrar a sessão Telegram deste projeto?\n\n"
                "Será necessário autenticar novamente para sincronizar."
            )
        ):
            return

        settings = self._auth_settings()

        if not settings:
            return

        api_id, api_hash, session = settings

        self._auth_thread(
            lambda: auth_service.executar(
                auth_service.sair_da_conta(
                    api_id,
                    api_hash,
                    session
                )
            ),
            self._resultado_logout
        )


    def _resultado_logout(
        self,
        result
    ):

        self._auth_done()

        if not result.get("ok"):
            messagebox.showerror(
                "Telegram",
                result.get(
                    "error",
                    "Não foi possível sair da conta."
                )
            )
            return

        self.auth_phone_code_hash = None
        self._set_telegram_status(
            False,
            "Não autenticado"
        )
        self.account_detail_var.set(
            "Sessão encerrada."
        )
        self.log(
            "[TELEGRAM] Sessão encerrada.",
            "warning"
        )


    def _set_telegram_status(
        self,
        connected,
        text
    ):

        self.telegram_status_var.set(
            text
        )
        self.account_status_var.set(
            text
        )

        color = (
            COLORS["success"]
            if connected
            else COLORS["muted"]
        )

        self.account_status_label.configure(
            fg=color
        )

        self.sidebar_telegram_var.set(
            (
                "● Telegram conectado"
                if connected
                else "● Telegram desconectado"
            )
        )
        self.sidebar_telegram_label.configure(
            fg=color
        )


    # ========================================================
    # PROCESSOS
    # ========================================================

    def normal_active(self):

        return (
            self.normal_process is not None
            and self.normal_process.poll() is None
        )


    def retro_active(self):

        return (
            self.retro_process is not None
            and self.retro_process.poll() is None
        )


    def _processo_em_execucao(self):

        return (
            self.normal_active()
            or self.retro_active()
        )


    def _validar_execucao(self):

        env = ler_env()

        if (
            not env.get("API_ID")
            or not env.get("API_HASH")
        ):
            messagebox.showerror(
                "Telegram",
                "Configure API ID e API Hash primeiro."
            )
            self.mostrar_pagina(
                "telegram"
            )
            return False

        if not self.channels:
            messagebox.showerror(
                "Rotas",
                "Adicione pelo menos uma rota."
            )
            self.mostrar_pagina(
                "canais"
            )
            return False

        return True


    def _engine_command(
        self,
        kind
    ):
        """
        Em modo Python, executa os scripts .py.
        Em modo empacotado, executa os helpers .exe.
        """

        frozen = getattr(
            sys,
            "frozen",
            False
        )

        if kind == "normal":

            if frozen:
                engine = (
                    BASE_DIR
                    / "MLDForwarderSync.exe"
                )

                if not engine.exists():
                    raise RuntimeError(
                        "MLDForwarderSync.exe não foi encontrado "
                        "na pasta do MLDForwarder."
                    )

                return [
                    str(engine)
                ]

            return [
                sys.executable,
                "-u",
                str(
                    BASE_DIR
                    / "sincronizar.py"
                )
            ]

        if kind == "retro":

            if frozen:
                engine = (
                    BASE_DIR
                    / "MLDForwarderRetro.exe"
                )

                if not engine.exists():
                    raise RuntimeError(
                        "MLDForwarderRetro.exe não foi encontrado "
                        "na pasta do MLDForwarder."
                    )

                return [
                    str(engine)
                ]

            return [
                sys.executable,
                "-u",
                str(
                    BASE_DIR
                    / "sincronizar_antigas.py"
                )
            ]

        raise RuntimeError(
            f"Motor desconhecido: {kind}"
        )


    def _start_subprocess(
        self,
        command,
        kind
    ):

        env = os.environ.copy()

        # Força UTF-8 nos helpers. Isso evita que o Windows use
        # cp1252 ao enviar os logs pela pipe da GUI.
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        # Cada helper é um executável PyInstaller independente.
        # Isso evita reaproveitar o ambiente interno do executável
        # que iniciou o processo.
        if getattr(sys, "frozen", False):
            env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"

        creationflags = 0

        if os.name == "nt":
            creationflags = getattr(
                subprocess,
                "CREATE_NO_WINDOW",
                0
            )

        try:
            process = subprocess.Popen(
                command,
                cwd=str(BASE_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=None,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=env,
                creationflags=creationflags
            )

        except OSError as error:
            messagebox.showerror(
                "Erro",
                str(error)
            )
            return None

        self.mostrar_pagina(
            "log"
        )

        threading.Thread(
            target=self._read_output,
            args=(
                process,
                kind
            ),
            daemon=True
        ).start()

        return process


    def _read_output(
        self,
        process,
        kind
    ):

        try:
            if process.stdout:
                for line in process.stdout:
                    text = line.rstrip(
                        "\r\n"
                    )

                    self.after(
                        0,
                        self._handle_output,
                        kind,
                        text
                    )

            code = process.wait()

        except Exception as error:
            code = -1

            self.after(
                0,
                self.log,
                f"[GUI] {error}",
                "error"
            )

        self.after(
            0,
            self._process_finished,
            kind,
            code
        )


    def _handle_output(
        self,
        kind,
        text
    ):

        tag = None
        lower = text.lower()

        if (
            "erro" in lower
            or "✗" in text
        ):
            tag = "error"

        elif (
            "✓" in text
            or "conclu" in lower
            or "conectado" in lower
        ):
            tag = "success"

        elif (
            "aviso" in lower
            or "flood" in lower
            or "pendente" in lower
        ):
            tag = "warning"

        self.log(
            text,
            tag
        )

        if kind == "retro":
            self._parse_retro_progress(
                text
            )


    def _parse_retro_progress(
        self,
        text
    ):

        match = re.search(
            r"Progresso:\s*(\d+)/(\d+|\?)",
            text
        )

        if not match:
            return

        current = int(
            match.group(1)
        )
        total_raw = match.group(2)

        if total_raw == "?":
            if str(
                self.retro_progress["mode"]
            ) != "indeterminate":
                self.retro_progress.configure(
                    mode="indeterminate"
                )
                self.retro_progress.start(10)

            self.retro_progress_text_var.set(
                f"{current} mensagens processadas"
            )
            return

        total = int(
            total_raw
        )

        self.retro_progress.stop()
        self.retro_progress.configure(
            mode="determinate",
            maximum=max(total, 1),
            value=min(current, total)
        )

        percent = (
            int((current / total) * 100)
            if total > 0
            else 0
        )

        self.retro_progress_text_var.set(
            f"{current}/{total}  •  {percent}%"
        )


    def _process_finished(
        self,
        kind,
        code
    ):

        if kind == "normal":
            self.normal_process = None
        else:
            self.retro_process = None
            self.retro_progress.stop()

        self.log(
            (
                f"[GUI] Processo {kind} finalizado "
                f"(código {code})."
            ),
            "success" if code == 0 else "error"
        )

        self.recarregar_canais()
        self.atualizar_estados()


    # ========================================================
    # NORMAL
    # ========================================================

    def iniciar_normal(self):

        if self.normal_active():
            messagebox.showinfo(
                "Sincronizador",
                "O sincronizador normal já está ativo."
            )
            return

        if self.retro_active():
            messagebox.showwarning(
                "Processo em andamento",
                (
                    "Pare o modo retroativo antes de "
                    "iniciar o sincronizador normal."
                )
            )
            return

        self.recarregar_canais()

        if not self._validar_execucao():
            return

        if not self.salvar_configuracoes(
            silencioso=True
        ):
            messagebox.showerror(
                "Configurações",
                "Verifique as configurações."
            )
            return

        try:
            SYNC_STOP_FILE.unlink()
        except FileNotFoundError:
            pass

        self.log(
            "=" * 64,
            "accent"
        )
        self.log(
            "INICIANDO SINCRONIZADOR NORMAL",
            "accent"
        )
        self.log(
            "=" * 64,
            "accent"
        )

        try:
            command = self._engine_command(
                "normal"
            )

        except RuntimeError as error:
            messagebox.showerror(
                "MLDForwarder",
                str(error)
            )
            return

        process = self._start_subprocess(
            command,
            "normal"
        )

        if process:
            self.normal_process = process
            self.atualizar_estados()


    def parar_normal(self):

        if not self.normal_active():
            messagebox.showinfo(
                "Sincronizador",
                "O sincronizador normal não está ativo."
            )
            return

        SYNC_STOP_FILE.write_text(
            "stop\n",
            encoding="utf-8"
        )

        self.normal_status_var.set(
            "Parando..."
        )

        self.log(
            "[GUI] Parada do sincronizador solicitada.",
            "warning"
        )

        self.atualizar_estados()


    # ========================================================
    # RETRO
    # ========================================================

    def iniciar_retro(self):

        if self.retro_active():
            messagebox.showinfo(
                "Retroativo",
                "O modo retroativo já está ativo."
            )
            return

        if self.normal_active():
            messagebox.showwarning(
                "Processo em andamento",
                (
                    "Pare o sincronizador normal antes de "
                    "iniciar o modo retroativo."
                )
            )
            return

        if not self.salvar_configuracoes(
            silencioso=True
        ):
            messagebox.showerror(
                "Configurações",
                "Verifique as configurações retroativas."
            )
            return

        self.recarregar_canais()

        if not self._validar_execucao():
            return

        label = self.retro_channel_var.get()
        source = self.retro_map.get(
            label
        )

        try:
            RETRO_STOP_FILE.unlink()
        except FileNotFoundError:
            pass

        try:
            command = self._engine_command(
                "retro"
            )

        except RuntimeError as error:
            messagebox.showerror(
                "MLDForwarder",
                str(error)
            )
            return

        if source is not None:
            command.append(
                f"--canal={source}"
            )

        self.retro_progress.stop()

        try:
            limit = int(
                self.retro_limit_var.get()
            )
        except ValueError:
            limit = 0

        if limit == 0:
            self.retro_progress.configure(
                mode="indeterminate"
            )
            self.retro_progress.start(10)
            self.retro_progress_text_var.set(
                "Processando histórico completo..."
            )

        else:
            self.retro_progress.configure(
                mode="determinate",
                maximum=max(limit, 1),
                value=0
            )
            self.retro_progress_text_var.set(
                f"0/{limit}  •  0%"
            )

        self.log(
            "=" * 64,
            "accent"
        )
        self.log(
            "INICIANDO SINCRONIZAÇÃO RETROATIVA",
            "accent"
        )
        self.log(
            f"Seleção: {label}",
            "accent"
        )
        self.log(
            "=" * 64,
            "accent"
        )

        process = self._start_subprocess(
            command,
            "retro"
        )

        if process:
            self.retro_process = process
            self.atualizar_estados()


    def parar_retro(self):

        if not self.retro_active():
            messagebox.showinfo(
                "Retroativo",
                "O modo retroativo não está ativo."
            )
            return

        RETRO_STOP_FILE.write_text(
            "stop\n",
            encoding="utf-8"
        )

        self.retro_status_var.set(
            "Parando..."
        )

        self.log(
            "[GUI] Parada do retroativo solicitada.",
            "warning"
        )

        self.atualizar_estados()


    # ========================================================
    # ESTADOS
    # ========================================================

    def atualizar_estados(self):

        normal = self.normal_active()
        retro = self.retro_active()

        if normal:
            self.normal_status_var.set(
                "Ativo"
            )
            self.sidebar_engine_var.set(
                "● Sincronizador ativo"
            )
            self.sidebar_engine_label.configure(
                fg=COLORS["success"]
            )
        elif retro:
            self.normal_status_var.set(
                "Parado"
            )
            self.sidebar_engine_var.set(
                "● Retroativo ativo"
            )
            self.sidebar_engine_label.configure(
                fg=COLORS["warning"]
            )
        else:
            if self.normal_status_var.get() != "Parando...":
                self.normal_status_var.set(
                    "Parado"
                )

            self.sidebar_engine_var.set(
                "● Sincronizador parado"
            )
            self.sidebar_engine_label.configure(
                fg=COLORS["muted"]
            )

        if retro:
            self.retro_status_var.set(
                "Ativo"
            )
        elif self.retro_status_var.get() != "Parando...":
            self.retro_status_var.set(
                "Parado"
            )

        self.start_normal_button.configure(
            state=(
                "disabled"
                if normal or retro
                else "normal"
            )
        )
        self.stop_normal_button.configure(
            state=(
                "normal"
                if normal
                else "disabled"
            )
        )

        self.start_retro_button.configure(
            state=(
                "disabled"
                if normal or retro
                else "normal"
            )
        )
        self.stop_retro_button.configure(
            state=(
                "normal"
                if retro
                else "disabled"
            )
        )


    # ========================================================
    # LOG
    # ========================================================

    def log(
        self,
        text,
        tag=None
    ):

        self.log_text.configure(
            state="normal"
        )

        if tag:
            self.log_text.insert(
                "end",
                str(text) + "\n",
                tag
            )
        else:
            self.log_text.insert(
                "end",
                str(text) + "\n"
            )

        self.log_text.see(
            "end"
        )

        self.log_text.configure(
            state="disabled"
        )


    def limpar_log(self):

        self.log_text.configure(
            state="normal"
        )
        self.log_text.delete(
            "1.0",
            "end"
        )
        self.log_text.configure(
            state="disabled"
        )


    # ========================================================
    # ENCERRAMENTO
    # ========================================================

    def fechar(self):

        if self._processo_em_execucao():

            if not messagebox.askyesno(
                "Encerrar MLDForwarder",
                (
                    "Há uma sincronização em andamento.\n\n"
                    "Solicitar a parada e fechar a interface?"
                )
            ):
                return

            if self.normal_active():
                SYNC_STOP_FILE.write_text(
                    "stop\n",
                    encoding="utf-8"
                )

            if self.retro_active():
                RETRO_STOP_FILE.write_text(
                    "stop\n",
                    encoding="utf-8"
                )

        self.destroy()


if __name__ == "__main__":

    app = MLDForwarderGUI()
    app.mainloop()
