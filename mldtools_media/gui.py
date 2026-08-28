from __future__ import annotations

import argparse
import os
import queue
import re
import shutil
import subprocess
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

import customtkinter as ctk

from ui_theme import (
    COLORS,
    FONT,
    FONT_MONO,
    FONT_SEMIBOLD,
    PillLabel,
    ResponsiveGrid,
    RoundedPanel,
    SaaSButton,
    ScrollablePage,
    bind_responsive_wrap,
    capture_window_placement,
    configure_ttk_theme,
    configure_window,
    enable_dpi_awareness,
    load_brand_icon,
    restore_window_placement,
)

ttk.Button = SaaSButton

from . import __version__
from .config_store import ConfigStore, PERFORMANCE_PROFILES
from .models import DownloadTask
from .paths import APP_ROOT, DATA_DIR, LOG_DIR, default_download_directory, ensure_runtime_directories
from .runner import DownloadRunner
from .task_store import TaskStore
from .tdl_client import EngineBusyError, TDLClient
from .tool_runner import ToolRunner


STATUS_LABELS = {
    "queued": "Na fila",
    "running": "Baixando",
    "paused": "Pausado",
    "completed": "Concluído",
    "failed": "Falhou",
    "cancelled": "Cancelado",
}


def task_status_label(task: DownloadTask) -> str:
    if task.status == "running" and task.operation_type == "upload":
        return "Enviando"
    return STATUS_LABELS.get(task.status, task.status)

SOURCE_LABELS = {
    "Links de mensagens": "links",
    "Arquivo JSON": "json",
    "Canal, grupo ou tópico": "chat",
}

SCOPE_LABELS = {
    "Todo o conteúdo com mídia": "all",
    "Últimos X arquivos": "last",
    "Intervalo de IDs": "id",
    "Intervalo de datas": "time",
}

EXPORT_TYPE_LABELS = {
    "Mensagens": "messages",
    "Membros e inscritos": "users",
}

EXPORT_SCOPE_LABELS = {
    "Todo o histórico": "all",
    "Últimas X mensagens": "last",
    "Intervalo de IDs": "id",
    "Intervalo de datas": "time",
}

ALBUM_MODE_LABELS = {
    "Seleção atual": "selection",
    "Cada pasta": "folder",
}

SAVED_MESSAGES_LABEL = "Mensagens Salvas — minha conta"

CHAT_TYPE_LABELS = {
    "channel": "Canal",
    "group": "Grupo",
    "private": "Conversa",
    "unknown": "Outro",
}


def human_size(value: int | float) -> str:
    size = float(value)
    units = ("B", "KB", "MB", "GB", "TB")
    for unit in units:
        if abs(size) < 1024.0 or unit == units[-1]:
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def short_time(value: str) -> str:
    if not value:
        return "—"
    try:
        moment = datetime.fromisoformat(value)
        return moment.astimezone().strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return value[:16].replace("T", " ")


def safe_filename(value: str, fallback: str = "exportacao") -> str:
    clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", str(value)).strip(" ._")
    clean = re.sub(r"\s+", "_", clean)
    clean = re.sub(r"_+", "_", clean)
    return clean[:90] or fallback


def open_directory(path: str | Path) -> None:
    target = Path(path).expanduser()
    target.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        os.startfile(target)  # type: ignore[attr-defined]
    elif os.uname().sysname == "Darwin":
        subprocess.Popen(["open", str(target)])
    else:
        subprocess.Popen(["xdg-open", str(target)])


class MLDToolsMediaGUI(ctk.CTk):
    def __init__(self, start_page: str = "dashboard") -> None:
        enable_dpi_awareness()
        ensure_runtime_directories()
        super().__init__()
        self.title(f"MLD Tools — Central de mídia {__version__}")
        self.minsize(980, 640)
        self.configure(fg_color=COLORS["bg"])
        configure_window(self, APP_ROOT)

        self.config_store = ConfigStore()
        self.config_store.ensure_saved()
        self._normal_window_geometry = restore_window_placement(
            self,
            self.config_store.get("window_geometry", ""),
            bool(self.config_store.get("window_maximized", False)),
            default_size=(1320, 940),
            minimum_size=(980, 640),
        )
        self.bind("<Configure>", self._remember_window_placement, add="+")
        self.task_store = TaskStore()
        self.tdl = TDLClient(self.config_store)
        self.events: queue.Queue[dict[str, Any]] = queue.Queue()
        self.runner = DownloadRunner(self.task_store, self.tdl, self.events.put)
        self.runner.start()
        self.tool_runner = ToolRunner(self.tdl, self.events.put)

        self.pages: dict[str, tk.Frame] = {}
        self.nav_buttons: dict[str, tk.Button] = {}
        self.nav_rows: dict[str, tk.Frame] = {}
        self.nav_indicators: dict[str, tk.Frame] = {}
        self.brand_icon: tk.PhotoImage | None = None
        self.chat_rows: list[dict[str, Any]] = []
        self.chat_by_label: dict[str, dict[str, Any]] = {}
        self.topic_by_label: dict[str, dict[str, Any]] = {}
        self.json_files: list[str] = []
        self.upload_paths: list[str] = []
        self._last_export_path = ""
        self._active_export_path = ""
        self.login_process: subprocess.Popen[Any] | None = None
        self.login_operation_token: object | None = None
        self._chat_refresh_busy = False
        self._last_tree_signature: tuple[Any, ...] = ()

        self._setup_style()
        self._build_shell()
        self._build_pages()
        self._load_config_variables()
        self.show_page(start_page if start_page in self.pages else "dashboard")
        self._append_log("Central de mídia do MLD Tools iniciada.", "info")
        if not self.tdl.engine_exists():
            self._append_log("Motor tdl não encontrado na pasta engine.", "error")

        self.after(150, self._process_events)
        self.after(500, self._periodic_refresh)
        self.protocol("WM_DELETE_WINDOW", self.close)

    # ------------------------------------------------------------------
    # Style and shell
    # ------------------------------------------------------------------

    def _remember_window_placement(self, _event: tk.Event[Any] | None = None) -> None:
        try:
            if str(self.state()) == "normal":
                self._normal_window_geometry = self.geometry()
        except tk.TclError:
            pass

    def _save_window_placement(self) -> None:
        geometry, maximized = capture_window_placement(
            self,
            self._normal_window_geometry,
        )
        try:
            self.config_store.update(
                {
                    "window_geometry": geometry,
                    "window_maximized": maximized,
                }
            )
        except OSError:
            pass

    def _setup_style(self) -> None:
        # Keep the Combobox popup native. Styling its internal Listbox through
        # Tk's global option database prevents the popup from opening on some
        # Windows/Tk combinations.
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
            font=("Segoe UI", 10),
        )
        style.configure(
            "TEntry",
            fieldbackground=COLORS["panel_2"],
            foreground=COLORS["text"],
            insertcolor=COLORS["text"],
            padding=7,
        )
        style.configure(
            "TCombobox",
            fieldbackground=COLORS["panel_2"],
            foreground=COLORS["text"],
            arrowcolor=COLORS["text"],
            padding=5,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", COLORS["panel_2"])],
            foreground=[("readonly", COLORS["text"])],
        )
        style.configure(
            "TSpinbox",
            fieldbackground=COLORS["panel_2"],
            foreground=COLORS["text"],
            arrowcolor=COLORS["text"],
            padding=5,
        )
        style.configure(
            "TButton",
            background=COLORS["panel_2"],
            foreground=COLORS["text"],
            borderwidth=0,
            padding=(12, 8),
        )
        style.map("TButton", background=[("active", COLORS["line"])])
        style.configure(
            "Accent.TButton",
            background=COLORS["accent"],
            foreground="#FFFFFF",
            borderwidth=0,
            padding=(14, 9),
            font=("Segoe UI", 10, "bold"),
        )
        style.map(
            "Accent.TButton",
            background=[("active", COLORS["accent_hover"]), ("disabled", COLORS["line"])],
            foreground=[("disabled", COLORS["muted"])],
        )
        style.configure(
            "Danger.TButton",
            background=COLORS["danger_bg"],
            foreground=COLORS["danger"],
            borderwidth=0,
            padding=(12, 8),
        )
        style.map("Danger.TButton", background=[("active", COLORS["danger_hover"])])
        style.configure(
            "Treeview",
            background=COLORS["panel"],
            fieldbackground=COLORS["panel"],
            foreground=COLORS["text"],
            rowheight=31,
            borderwidth=0,
        )
        style.map(
            "Treeview",
            background=[("selected", COLORS["accent"])],
            foreground=[("selected", "#FFFFFF")],
        )
        style.configure(
            "Treeview.Heading",
            background=COLORS["panel_2"],
            foreground=COLORS["muted"],
            borderwidth=0,
            padding=8,
            font=("Segoe UI", 10, "bold"),
        )
        style.map("Treeview.Heading", background=[("active", COLORS["panel_2"])])
        style.configure(
            "Horizontal.TProgressbar",
            troughcolor=COLORS["panel_2"],
            background=COLORS["accent"],
            bordercolor=COLORS["panel_2"],
            lightcolor=COLORS["accent"],
            darkcolor=COLORS["accent"],
        )
        style.configure(
            "TCheckbutton",
            background=COLORS["panel"],
            foreground=COLORS["text"],
        )
        style.map("TCheckbutton", background=[("active", COLORS["panel"])])
        style.configure(
            "Vertical.TScrollbar",
            background=COLORS["panel_2"],
            troughcolor=COLORS["panel"],
            arrowcolor=COLORS["text"],
            bordercolor=COLORS["line"],
        )
        configure_ttk_theme(self)

    def _build_shell(self) -> None:
        self.sidebar = tk.Frame(self, bg=COLORS["sidebar"], width=252)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        brand = tk.Frame(self.sidebar, bg=COLORS["sidebar"], padx=18, pady=20)
        brand.pack(fill="x")

        brand_row = tk.Frame(brand, bg=COLORS["sidebar"])
        brand_row.pack(fill="x")

        self.brand_icon = load_brand_icon(self, APP_ROOT)
        if self.brand_icon is not None:
            tk.Label(
                brand_row,
                image=self.brand_icon,
                bg=COLORS["sidebar"],
                bd=0,
            ).pack(side="left", padx=(0, 12))

        brand_copy = tk.Frame(brand_row, bg=COLORS["sidebar"])
        brand_copy.pack(side="left", fill="x", expand=True)
        tk.Label(
            brand_copy,
            text="MLD TOOLS",
            bg=COLORS["sidebar"],
            fg=COLORS["text"],
            font=(FONT_SEMIBOLD, 16),
        ).pack(anchor="w")
        tk.Label(
            brand_copy,
            text="MEDIA CENTER",
            bg=COLORS["sidebar"],
            fg=COLORS["purple"],
            font=(FONT_SEMIBOLD, 9),
        ).pack(anchor="w", pady=(3, 0))

        PillLabel(
            brand_copy,
            text=f"v{__version__}",
            bg=COLORS["purple_soft"],
            fg="#B9ABFF",
            font=(FONT_SEMIBOLD, 9),
            padx=7,
            pady=2,
        ).pack(anchor="w", pady=(7, 0))

        tk.Frame(
            self.sidebar,
            bg=COLORS["line_soft"],
            height=1,
        ).pack(fill="x", padx=18, pady=(0, 17))

        nav = tk.Frame(self.sidebar, bg=COLORS["sidebar"], padx=10)
        nav.pack(fill="x")

        tk.Label(
            nav,
            text="CENTRAL DE MÍDIA",
            bg=COLORS["sidebar"],
            fg=COLORS["subtle"],
            font=(FONT_SEMIBOLD, 9),
        ).pack(anchor="w", padx=10, pady=(0, 8))

        items = [
            ("dashboard", "◫", "Visão geral"),
            ("new", "↓", "Novo download"),
            ("export", "⇲", "Central de exportação"),
            ("upload", "↑", "Upload para Telegram"),
            ("queue", "≡", "Fila"),
            ("history", "↺", "Histórico"),
            ("telegram", "✦", "Telegram"),
            ("config", "⚙", "Configurações"),
            ("log", "⌁", "Log"),
        ]
        for key, icon, text in items:
            nav_row = tk.Frame(nav, bg=COLORS["sidebar"], height=40)
            nav_row.pack(fill="x", pady=1)
            nav_row.pack_propagate(False)

            indicator = tk.Frame(nav_row, bg=COLORS["sidebar"], width=3)
            indicator.pack(side="left", fill="y")

            button = SaaSButton(
                nav_row,
                text=f"  {icon}    {text}",
                anchor="w",
                relief="flat",
                bd=0,
                padx=10,
                pady=8,
                cursor="hand2",
                bg=COLORS["sidebar"],
                fg=COLORS["muted"],
                activebackground=COLORS["panel_hover"],
                activeforeground=COLORS["text"],
                font=(FONT, 11),
                command=lambda value=key: self.show_page(value),
            )
            button.pack(side="left", fill="both", expand=True)
            self.nav_buttons[key] = button
            self.nav_rows[key] = nav_row
            self.nav_indicators[key] = indicator

        status_area = tk.Frame(self.sidebar, bg=COLORS["sidebar"], padx=14, pady=16)
        status_area.pack(side="bottom", fill="x")
        status = RoundedPanel(
            status_area,
            padx=13,
            pady=12,
            fg_color=COLORS["panel"],
            border_color=COLORS["line_soft"],
            corner_radius=9,
        )
        status.pack(fill="x")
        tk.Label(
            status,
            text="STATUS DO SISTEMA",
            bg=COLORS["panel"],
            fg=COLORS["subtle"],
            font=(FONT_SEMIBOLD, 9),
        ).pack(anchor="w", pady=(0, 7))
        self.sidebar_telegram_var = tk.StringVar(value="● Telegram não verificado")
        self.sidebar_engine_var = tk.StringVar(value="● Motor verificando")
        self.sidebar_download_var = tk.StringVar(value="● Nenhuma operação ativa")
        self.sidebar_telegram_label = self._sidebar_status(status, self.sidebar_telegram_var)
        self.sidebar_engine_label = self._sidebar_status(status, self.sidebar_engine_var)
        self.sidebar_download_label = self._sidebar_status(status, self.sidebar_download_var)

        self.main_frame = tk.Frame(self, bg=COLORS["bg"])
        self.main_frame.pack(side="left", fill="both", expand=True)
        top = tk.Frame(self.main_frame, bg=COLORS["bg"], padx=32, pady=22)
        top.pack(fill="x")

        title_group = tk.Frame(top, bg=COLORS["bg"])
        title_group.pack(side="left", fill="x", expand=True)
        tk.Label(
            title_group,
            text="MLD WORKSPACE  /  MEDIA ENGINE",
            bg=COLORS["bg"],
            fg=COLORS["purple"],
            font=(FONT_SEMIBOLD, 9),
        ).pack(anchor="w")

        self.page_title_var = tk.StringVar(value="Visão geral")
        self.page_description_var = tk.StringVar(
            value="Acompanhe transferências, fila e armazenamento em um só lugar."
        )
        tk.Label(
            title_group,
            textvariable=self.page_title_var,
            bg=COLORS["bg"],
            fg=COLORS["text"],
            font=(FONT_SEMIBOLD, 25),
        ).pack(anchor="w", pady=(4, 0))
        tk.Label(
            title_group,
            textvariable=self.page_description_var,
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=(FONT, 10),
        ).pack(anchor="w", pady=(4, 0))

        PillLabel(
            top,
            text="●  TDL DEDICADO",
            bg=COLORS["purple_soft"],
            fg="#B9ABFF",
            font=(FONT_SEMIBOLD, 9),
            padx=11,
            pady=7,
        ).pack(side="right", anchor="n", pady=(7, 0))

        tk.Frame(
            self.main_frame,
            bg=COLORS["line_soft"],
            height=1,
        ).pack(fill="x")

        self.content = tk.Frame(self.main_frame, bg=COLORS["bg"], padx=32, pady=20)
        self.content.pack(fill="both", expand=True)

    def _sidebar_status(self, parent: tk.Widget, variable: tk.StringVar) -> tk.Label:
        label = tk.Label(
            parent,
            textvariable=variable,
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            anchor="w",
            font=(FONT, 10),
        )
        label.pack(fill="x", pady=2)
        return label

    def _build_pages(self) -> None:
        for key in (
            "dashboard",
            "new",
            "export",
            "upload",
            "queue",
            "history",
            "telegram",
            "config",
            "log",
        ):
            page = ScrollablePage(self.content, bg=COLORS["bg"])
            page.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.pages[key] = page
        self._page_dashboard()
        self._page_new_download()
        self._page_export()
        self._page_upload()
        self._page_queue()
        self._page_history()
        self._page_telegram()
        self._page_config()
        self._page_log()

    def show_page(self, key: str) -> None:
        titles = {
            "dashboard": "Visão geral",
            "new": "Novo download",
            "export": "Central de exportação",
            "upload": "Upload para Telegram",
            "queue": "Fila de transferências",
            "history": "Histórico",
            "telegram": "Conta Telegram",
            "config": "Configurações",
            "log": "Log de atividade",
        }
        descriptions = {
            "dashboard": "Acompanhe transferências, fila e armazenamento em um só lugar.",
            "new": "Crie uma tarefa a partir de links, JSON, canais, grupos ou tópicos.",
            "export": "Exporte mensagens, membros e inscritos para arquivos JSON.",
            "upload": "Envie arquivos, pastas e álbuns com destino e legenda controlados.",
            "queue": "Inicie, pause, retome ou cancele downloads e uploads.",
            "history": "Revise tarefas concluídas, canceladas e operações com erro.",
            "telegram": "Verifique o motor TDL e selecione canais e tópicos da sua conta.",
            "config": "Ajuste desempenho, paralelismo, pastas e comportamento da fila.",
            "log": "Acompanhe a saída técnica do motor e os eventos da interface.",
        }
        self.pages[key].tkraise()
        self.pages[key].scroll_to_top()
        self.page_title_var.set(titles[key])
        self.page_description_var.set(descriptions[key])
        for name, button in self.nav_buttons.items():
            active = name == key
            button.configure(
                bg=COLORS["accent_soft"] if active else COLORS["sidebar"],
                fg="#FFFFFF" if active else COLORS["muted"],
                activebackground=COLORS["panel_hover"],
                activeforeground="#FFFFFF",
                font=(FONT_SEMIBOLD, 11) if active else (FONT, 11),
            )
            self.nav_rows[name].configure(
                bg=COLORS["accent_soft"] if active else COLORS["sidebar"]
            )
            self.nav_indicators[name].configure(
                bg=COLORS["accent"] if active else COLORS["sidebar"]
            )
        if key in {"dashboard", "queue", "history"}:
            self._refresh_task_views(force=True)

    # ------------------------------------------------------------------
    # Components
    # ------------------------------------------------------------------

    def _panel(self, parent: tk.Widget, padx: int = 18, pady: int = 16) -> tk.Frame:
        return RoundedPanel(
            parent,
            padx=padx,
            pady=pady,
            fg_color=COLORS["panel"],
            border_color=COLORS["line_soft"],
            corner_radius=9,
        )

    def _section_title(self, parent: tk.Widget, text: str) -> tk.Label:
        return ctk.CTkLabel(
            parent,
            text=text,
            fg_color="transparent",
            text_color=COLORS["text"],
            font=(FONT_SEMIBOLD, 16),
            height=24,
            anchor="w",
        )

    def _muted(
        self,
        parent: tk.Widget,
        text: str | None = None,
        variable: tk.StringVar | None = None,
        wraplength: int = 780,
    ) -> tk.Label:
        label = tk.Label(
            parent,
            text=text,
            textvariable=variable,
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            justify="left",
            anchor="w",
            wraplength=wraplength,
            font=(FONT, 10),
        )
        bind_responsive_wrap(label, parent, wraplength)
        return label

    def _field_label(self, parent: tk.Widget, text: str) -> tk.Label:
        return tk.Label(
            parent,
            text=text,
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=(FONT_SEMIBOLD, 10),
            anchor="w",
        )

    def _card(
        self,
        parent: tk.Widget,
        title: str,
        variable: tk.StringVar,
        color: str | None = None,
    ) -> tk.Frame:
        frame = self._panel(parent, padx=0, pady=0)
        tk.Frame(
            frame,
            bg=color or COLORS["accent"],
            height=3,
        ).pack(fill="x")
        body = tk.Frame(frame, bg=COLORS["panel"], padx=16, pady=14)
        body.pack(fill="both", expand=True)
        tk.Label(
            body,
            text=title.upper(),
            bg=COLORS["panel"],
            fg=COLORS["subtle"],
            font=(FONT_SEMIBOLD, 9),
        ).pack(anchor="w")
        tk.Label(
            body,
            textvariable=variable,
            bg=COLORS["panel"],
            fg=COLORS["text"],
            font=(FONT_SEMIBOLD, 17),
        ).pack(anchor="w", pady=(7, 0))
        return frame

    def _configure_task_tags(self, tree: ttk.Treeview) -> None:
        tree.tag_configure("running", foreground=COLORS["accent_hover"])
        tree.tag_configure("completed", foreground=COLORS["success"])
        tree.tag_configure("failed", foreground=COLORS["danger"])
        tree.tag_configure("paused", foreground=COLORS["warning"])
        tree.tag_configure("cancelled", foreground=COLORS["muted"])

    def _chat_label(self, row: dict[str, Any]) -> str:
        username = str(row.get("username", "")).strip().lstrip("@")
        suffix = f"@{username}  •  {row['id']}" if username and username != "-" else f"ID {row['id']}"
        return f"{row['name']}  —  {suffix}"

    @staticmethod
    def _topic_label(topic: dict[str, Any]) -> str:
        return f"{topic['name']}  —  ID {topic['id']}"

    def _populate_topic_combo(
        self,
        chat_variable: tk.StringVar,
        topic_variable: tk.StringVar,
        combo: ttk.Combobox,
    ) -> None:
        chat = self.chat_by_label.get(chat_variable.get())
        topic_variable.set("")
        if not chat or not chat.get("topics"):
            combo.configure(values=(), state="disabled")
            return
        combo.configure(
            values=[self._topic_label(topic) for topic in chat["topics"]],
            state="readonly",
        )

    def _selected_topic(
        self,
        chat: dict[str, Any] | None,
        topic_label: str,
    ) -> dict[str, Any] | None:
        if not chat or not topic_label:
            return None
        return next(
            (topic for topic in chat.get("topics", []) if self._topic_label(topic) == topic_label),
            None,
        )

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    def _page_dashboard(self) -> None:
        page = self.pages["dashboard"]
        self.dashboard_telegram_var = tk.StringVar(value="Não verificado")
        self.dashboard_active_var = tk.StringVar(value="Nenhum")
        self.dashboard_queue_var = tk.StringVar(value="0")
        self.dashboard_disk_var = tk.StringVar(value="—")
        cards = tk.Frame(page, bg=COLORS["bg"])
        cards.pack(fill="x")
        dashboard_cards = (
            self._card(cards, "Telegram", self.dashboard_telegram_var, COLORS["accent"]),
            self._card(cards, "Em andamento", self.dashboard_active_var, COLORS["purple"]),
            self._card(cards, "Na fila", self.dashboard_queue_var, COLORS["warning"]),
            self._card(cards, "Espaço livre", self.dashboard_disk_var, COLORS["success"]),
        )
        ResponsiveGrid(
            cards,
            dashboard_cards,
            breakpoints=((840, 4), (520, 2), (0, 1)),
            gap=12,
            uniform="dashboard_cards",
        )

        active = self._panel(page)
        active.pack(fill="x", pady=(14, 0))
        header = tk.Frame(active, bg=COLORS["panel"])
        header.pack(fill="x")
        self._section_title(header, "Operação atual").pack(side="left")
        ttk.Button(header, text="Abrir fila", command=lambda: self.show_page("queue")).pack(side="right")
        self.active_task_var = tk.StringVar(value="Nenhuma operação em andamento.")
        self._muted(active, variable=self.active_task_var).pack(fill="x", pady=(10, 7))
        self.active_progress = ttk.Progressbar(active, mode="determinate", maximum=100)
        self.active_progress.pack(fill="x")

        recent = self._panel(page)
        recent.pack(fill="both", expand=True, pady=(14, 0))
        header = tk.Frame(recent, bg=COLORS["panel"])
        header.pack(fill="x", pady=(0, 10))
        self._section_title(header, "Atividade recente").pack(side="left")
        ttk.Button(header, text="+ Novo download", style="Accent.TButton", command=lambda: self.show_page("new")).pack(side="right")
        self.dashboard_tree = ttk.Treeview(
            recent,
            columns=("status", "progress", "destination", "date"),
            show="tree headings",
            height=9,
        )
        self.dashboard_tree.heading("#0", text="Tarefa")
        self.dashboard_tree.heading("status", text="Status")
        self.dashboard_tree.heading("progress", text="Progresso")
        self.dashboard_tree.heading("destination", text="Destino")
        self.dashboard_tree.heading("date", text="Criado")
        self.dashboard_tree.column("#0", width=250)
        self.dashboard_tree.column("status", width=105, anchor="center")
        self.dashboard_tree.column("progress", width=95, anchor="center")
        self.dashboard_tree.column("destination", width=280)
        self.dashboard_tree.column("date", width=130)
        self.dashboard_tree.pack(fill="both", expand=True)
        self._configure_task_tags(self.dashboard_tree)

    # ------------------------------------------------------------------
    # New download
    # ------------------------------------------------------------------

    def _page_new_download(self) -> None:
        page = self.pages["new"]
        origin = self._panel(page)
        origin.pack(fill="x")
        top = tk.Frame(origin, bg=COLORS["panel"])
        top.pack(fill="x")
        self._section_title(top, "1. Escolha a origem").pack(side="left")
        self.source_type_var = tk.StringVar(value="Links de mensagens")
        source_combo = ttk.Combobox(
            top,
            state="readonly",
            width=27,
            values=list(SOURCE_LABELS),
            textvariable=self.source_type_var,
        )
        source_combo.pack(side="right")
        source_combo.bind("<<ComboboxSelected>>", lambda _event: self._show_source_frame())
        self._muted(
            origin,
            text="Baixe mensagens específicas, use uma exportação JSON ou selecione um canal da sua conta.",
        ).pack(fill="x", pady=(7, 10))

        self.source_container = tk.Frame(origin, bg=COLORS["panel"], height=132)
        self.source_container.pack(fill="x")
        self.source_container.pack_propagate(False)
        self.source_frames: dict[str, tk.Frame] = {}

        links_frame = tk.Frame(self.source_container, bg=COLORS["panel"])
        self.source_frames["links"] = links_frame
        links_header = tk.Frame(links_frame, bg=COLORS["panel"])
        links_header.pack(fill="x")
        self._field_label(links_header, "Links do Telegram — um por linha").pack(side="left")
        ttk.Button(links_header, text="Colar", command=self._paste_links).pack(side="right")
        self.links_text = tk.Text(
            links_frame,
            height=4,
            bg=COLORS["panel_2"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            selectbackground=COLORS["accent"],
            relief="flat",
            padx=9,
            pady=7,
            font=("Consolas", 10),
        )
        self.links_text.pack(fill="both", expand=True, pady=(5, 0))

        json_frame = tk.Frame(self.source_container, bg=COLORS["panel"])
        self.source_frames["json"] = json_frame
        self._field_label(json_frame, "Arquivos JSON exportados pelo Telegram ou pelo tdl").pack(anchor="w")
        json_line = tk.Frame(json_frame, bg=COLORS["panel"])
        json_line.pack(fill="x", pady=(5, 4))
        self.json_path_var = tk.StringVar()
        ttk.Entry(json_line, textvariable=self.json_path_var).pack(side="left", fill="x", expand=True)
        ttk.Button(json_line, text="Selecionar…", command=self._choose_json_files).pack(side="left", padx=(8, 0))
        self._muted(json_frame, text="É possível selecionar vários arquivos de uma vez.").pack(fill="x")

        chat_frame = tk.Frame(self.source_container, bg=COLORS["panel"])
        self.source_frames["chat"] = chat_frame
        row_one = tk.Frame(chat_frame, bg=COLORS["panel"])
        row_one.pack(fill="x")
        left = tk.Frame(row_one, bg=COLORS["panel"])
        left.pack(side="left", fill="x", expand=True)
        self._field_label(left, "Canal ou grupo").pack(anchor="w")
        self.chat_var = tk.StringVar()
        self.chat_combo = ttk.Combobox(left, state="readonly", textvariable=self.chat_var)
        self.chat_combo.pack(fill="x", pady=(5, 0))
        self.chat_combo.bind("<<ComboboxSelected>>", self._on_chat_selected)
        ttk.Button(row_one, text="Atualizar lista", command=self.refresh_chats).pack(side="left", padx=(8, 0), pady=(22, 0))
        right = tk.Frame(row_one, bg=COLORS["panel"])
        right.pack(side="left", fill="x", expand=True, padx=(12, 0))
        self._field_label(right, "Tópico — opcional").pack(anchor="w")
        self.topic_var = tk.StringVar()
        self.topic_combo = ttk.Combobox(right, state="disabled", textvariable=self.topic_var)
        self.topic_combo.pack(fill="x", pady=(5, 0))

        scope_line = tk.Frame(chat_frame, bg=COLORS["panel"])
        scope_line.pack(fill="x", pady=(10, 0))
        self.scope_var = tk.StringVar(value="Últimos X arquivos")
        self.scope_combo = ttk.Combobox(
            scope_line,
            state="readonly",
            width=28,
            values=list(SCOPE_LABELS),
            textvariable=self.scope_var,
        )
        self.scope_combo.pack(side="left")
        self.scope_combo.bind("<<ComboboxSelected>>", self._on_scope_selected)
        self.scope_value_var = tk.StringVar(value="100")
        self.scope_value_entry = ttk.Entry(scope_line, textvariable=self.scope_value_var, width=30)
        self.scope_value_entry.pack(side="left", padx=(8, 0), fill="x", expand=True)
        self.scope_hint_var = tk.StringVar(value="Quantidade de arquivos com mídia")
        self._muted(scope_line, variable=self.scope_hint_var, wraplength=270).pack(side="left", padx=(8, 0))

        destination = self._panel(page)
        destination.pack(fill="x", pady=(12, 0))
        self._section_title(destination, "2. Destino").pack(anchor="w")
        destination_line = tk.Frame(destination, bg=COLORS["panel"])
        destination_line.pack(fill="x", pady=(8, 0))
        self.destination_var = tk.StringVar()
        ttk.Entry(destination_line, textvariable=self.destination_var).pack(side="left", fill="x", expand=True)
        ttk.Button(destination_line, text="Escolher pasta…", command=self._choose_destination).pack(side="left", padx=(8, 0))

        options = self._panel(page)
        options.pack(fill="x", pady=(12, 0))
        self._section_title(options, "3. Opções").pack(anchor="w")
        checks = tk.Frame(options, bg=COLORS["panel"])
        checks.pack(fill="x", pady=(8, 7))
        self.option_group_var = tk.BooleanVar(value=True)
        self.option_skip_var = tk.BooleanVar(value=True)
        self.option_original_name_var = tk.BooleanVar(value=False)
        self.option_takeout_var = tk.BooleanVar(value=False)
        self.option_desc_var = tk.BooleanVar(value=False)
        download_option_widgets = (
            ttk.Checkbutton(checks, text="Completar álbuns", variable=self.option_group_var),
            ttk.Checkbutton(
                checks,
                text="Manter nome original",
                variable=self.option_original_name_var,
            ),
            ttk.Checkbutton(
                checks,
                text="Ignorar arquivos iguais",
                variable=self.option_skip_var,
            ),
            ttk.Checkbutton(checks, text="Modo Takeout", variable=self.option_takeout_var),
            ttk.Checkbutton(
                checks,
                text="Mais recentes primeiro",
                variable=self.option_desc_var,
            ),
        )
        ResponsiveGrid(
            checks,
            download_option_widgets,
            breakpoints=((760, 5), (430, 2), (0, 1)),
            gap=6,
            uniform="download-options",
        )
        self._muted(
            options,
            text=(
                "Nome original remove os IDs do início. Se houver arquivos diferentes "
                "com o mesmo nome, desmarque esta opção para evitar colisões."
            ),
        ).pack(fill="x", pady=(0, 8))

        option_fields = tk.Frame(options, bg=COLORS["panel"])
        option_fields.pack(fill="x")
        self.task_title_var = tk.StringVar()
        self.include_ext_var = tk.StringVar()
        self.exclude_ext_var = tk.StringVar()
        for column in range(3):
            option_fields.grid_columnconfigure(column, weight=1, uniform="option-fields")
        self._field_label(option_fields, "Nome da tarefa — opcional").grid(row=0, column=0, sticky="w")
        self._field_label(option_fields, "Incluir extensões").grid(row=0, column=1, sticky="w", padx=(10, 0))
        self._field_label(option_fields, "Excluir extensões").grid(row=0, column=2, sticky="w", padx=(10, 0))
        ttk.Entry(option_fields, textvariable=self.task_title_var).grid(row=1, column=0, sticky="ew", pady=(4, 0))
        ttk.Entry(option_fields, textvariable=self.include_ext_var).grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=(4, 0))
        ttk.Entry(option_fields, textvariable=self.exclude_ext_var).grid(row=1, column=2, sticky="ew", padx=(10, 0), pady=(4, 0))

        footer = tk.Frame(page, bg=COLORS["bg"])
        footer.pack(fill="x", pady=(12, 0))
        self.new_download_status_var = tk.StringVar(value="A tarefa será adicionada à fila.")
        tk.Label(
            footer,
            textvariable=self.new_download_status_var,
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=("Segoe UI", 10),
        ).pack(side="left")
        ttk.Button(footer, text="Adicionar à fila", style="Accent.TButton", command=self._create_task).pack(side="right")
        self._show_source_frame()

    def _show_source_frame(self) -> None:
        source_type = SOURCE_LABELS.get(self.source_type_var.get(), "links")
        for frame in self.source_frames.values():
            frame.pack_forget()
        self.source_frames[source_type].pack(fill="both", expand=True)

    def _paste_links(self) -> None:
        try:
            text = self.clipboard_get()
        except tk.TclError:
            return
        if self.links_text.get("1.0", "end").strip():
            self.links_text.insert("end", "\n")
        self.links_text.insert("end", text)

    def _choose_json_files(self) -> None:
        filenames = filedialog.askopenfilenames(
            parent=self,
            title="Selecione as exportações JSON",
            filetypes=(("Arquivos JSON", "*.json"), ("Todos os arquivos", "*.*")),
        )
        if filenames:
            self.json_files = list(filenames)
            self.json_path_var.set("; ".join(filenames))

    def _choose_destination(self) -> None:
        selected = filedialog.askdirectory(
            parent=self,
            title="Escolha a pasta de destino",
            initialdir=self.destination_var.get() or str(default_download_directory()),
        )
        if selected:
            self.destination_var.set(selected)

    def _on_chat_selected(self, _event: tk.Event[Any] | None = None) -> None:
        chat = self.chat_by_label.get(self.chat_var.get())
        self.topic_by_label.clear()
        self._populate_topic_combo(self.chat_var, self.topic_var, self.topic_combo)
        if chat:
            self.topic_by_label.update(
                {self._topic_label(topic): topic for topic in chat.get("topics", [])}
            )

    def _on_scope_selected(self, _event: tk.Event[Any] | None = None) -> None:
        scope = SCOPE_LABELS.get(self.scope_var.get(), "all")
        hints = {
            "all": "Nenhum valor necessário",
            "last": "Quantidade de arquivos com mídia",
            "id": "Formato: 100,500",
            "time": "Formato: 2026-01-01,2026-01-31",
        }
        defaults = {"all": "", "last": "100", "id": "1,100", "time": "2026-01-01,2026-01-31"}
        self.scope_hint_var.set(hints[scope])
        self.scope_value_entry.configure(state="disabled" if scope == "all" else "normal")
        self.scope_value_var.set(defaults[scope])

    def _create_task(self) -> None:
        source_type = SOURCE_LABELS.get(self.source_type_var.get(), "links")
        destination = self.destination_var.get().strip()
        if not destination:
            messagebox.showwarning("Destino necessário", "Escolha a pasta onde os arquivos serão salvos.", parent=self)
            return
        source: dict[str, Any]
        default_title: str
        if source_type == "links":
            links = re.findall(r"https?://[^\s]+", self.links_text.get("1.0", "end"))
            links = list(dict.fromkeys(link.rstrip(",;)") for link in links))
            if not links:
                messagebox.showwarning("Links necessários", "Cole pelo menos um link de mensagem do Telegram.", parent=self)
                return
            source = {"links": links}
            default_title = f"Links do Telegram ({len(links)})"
        elif source_type == "json":
            files = self.json_files or [piece.strip() for piece in self.json_path_var.get().split(";") if piece.strip()]
            missing = [filename for filename in files if not Path(filename).is_file()]
            if not files or missing:
                messagebox.showwarning("JSON inválido", "Selecione um ou mais arquivos JSON existentes.", parent=self)
                return
            source = {"files": files}
            default_title = Path(files[0]).stem if len(files) == 1 else f"Exportações JSON ({len(files)})"
        else:
            chat = self.chat_by_label.get(self.chat_var.get())
            if not chat:
                messagebox.showwarning("Canal necessário", "Atualize a lista e selecione um canal ou grupo.", parent=self)
                return
            topic = self.topic_by_label.get(self.topic_var.get())
            scope = SCOPE_LABELS.get(self.scope_var.get(), "all")
            if scope == "all" and self.config_store.get("confirm_full_chat", True):
                confirmed = messagebox.askyesno(
                    "Baixar todo o canal?",
                    "Esta opção exportará todas as mensagens com mídia do canal ou tópico. O processo pode usar muito espaço em disco. Deseja continuar?",
                    parent=self,
                )
                if not confirmed:
                    return
            source = {
                "chat_id": chat["id"],
                "chat_name": chat["name"],
                "topic_id": topic["id"] if topic else "",
                "topic_name": topic["name"] if topic else "",
                "scope": scope,
                "scope_value": self.scope_value_var.get().strip(),
            }
            default_title = chat["name"] + (f" / {topic['name']}" if topic else "")

        include_extensions = self.include_ext_var.get().strip()
        exclude_extensions = self.exclude_ext_var.get().strip()
        if include_extensions and exclude_extensions:
            messagebox.showwarning(
                "Filtros incompatíveis",
                "Use somente “Incluir extensões” ou “Excluir extensões”, não os dois.",
                parent=self,
            )
            return
        cfg = self.config_store.get_all()
        options = {
            "threads_per_file": cfg["threads_per_file"],
            "parallel_downloads": cfg["parallel_downloads"],
            "group_albums": self.option_group_var.get(),
            "skip_same": self.option_skip_var.get(),
            "keep_original_filename": self.option_original_name_var.get(),
            "takeout": self.option_takeout_var.get(),
            "descending": self.option_desc_var.get(),
            "rewrite_extension": cfg["rewrite_extension"],
            "include_extensions": include_extensions,
            "exclude_extensions": exclude_extensions,
            "filename_template": cfg["filename_template"],
        }
        task = DownloadTask(
            title=self.task_title_var.get().strip() or default_title,
            source_type=source_type,
            source=source,
            destination=destination,
            options=options,
        )
        try:
            # Validate the command before persisting the task.
            if source_type == "chat":
                self.tdl.build_export_command(task, self.tdl.task_export_path(task))
            else:
                self.tdl.build_download_command(task)
            self.task_store.add(task)
        except Exception as exc:
            messagebox.showerror("Não foi possível criar a tarefa", str(exc), parent=self)
            return
        self._append_log(f"[{task.title}] Tarefa adicionada à fila.", "success")
        self.new_download_status_var.set(
            f"“{task.title}” foi adicionado. Use Iniciar fila quando estiver pronto."
        )
        self.task_title_var.set("")
        self._refresh_task_views(force=True)
        self.show_page("queue")

    # ------------------------------------------------------------------
    # Export center
    # ------------------------------------------------------------------

    def _page_export(self) -> None:
        page = self.pages["export"]

        source = self._panel(page)
        source.pack(fill="x")
        header = tk.Frame(source, bg=COLORS["panel"])
        header.pack(fill="x")
        self._section_title(header, "1. Conteúdo e origem").pack(side="left")
        self.export_type_var = tk.StringVar(value="Mensagens")
        export_type_combo = ttk.Combobox(
            header,
            state="readonly",
            width=24,
            values=list(EXPORT_TYPE_LABELS),
            textvariable=self.export_type_var,
        )
        export_type_combo.pack(side="right")
        export_type_combo.bind("<<ComboboxSelected>>", self._on_export_type_selected)
        self.export_description_var = tk.StringVar(
            value="Exporte mensagens, textos e metadados para um arquivo JSON independente."
        )
        self._muted(source, variable=self.export_description_var).pack(fill="x", pady=(7, 10))

        selectors = tk.Frame(source, bg=COLORS["panel"])
        selectors.pack(fill="x")
        left = tk.Frame(selectors, bg=COLORS["panel"])
        left.pack(side="left", fill="x", expand=True)
        self._field_label(left, "Canal ou grupo").pack(anchor="w")
        self.export_chat_var = tk.StringVar()
        self.export_chat_combo = ttk.Combobox(left, state="readonly", textvariable=self.export_chat_var)
        self.export_chat_combo.pack(fill="x", pady=(5, 0))
        self.export_chat_combo.bind("<<ComboboxSelected>>", self._on_export_chat_selected)
        ttk.Button(selectors, text="Atualizar lista", command=self.refresh_chats).pack(
            side="left", padx=(8, 0), pady=(22, 0)
        )
        right = tk.Frame(selectors, bg=COLORS["panel"])
        right.pack(side="left", fill="x", expand=True, padx=(12, 0))
        self._field_label(right, "Tópico — opcional").pack(anchor="w")
        self.export_topic_var = tk.StringVar()
        self.export_topic_combo = ttk.Combobox(
            right, state="disabled", textvariable=self.export_topic_var
        )
        self.export_topic_combo.pack(fill="x", pady=(5, 0))

        scope_line = tk.Frame(source, bg=COLORS["panel"])
        scope_line.pack(fill="x", pady=(11, 0))
        self._field_label(scope_line, "Período").pack(side="left", padx=(0, 8))
        self.export_scope_var = tk.StringVar(value="Todo o histórico")
        self.export_scope_combo = ttk.Combobox(
            scope_line,
            state="readonly",
            width=25,
            values=list(EXPORT_SCOPE_LABELS),
            textvariable=self.export_scope_var,
        )
        self.export_scope_combo.pack(side="left")
        self.export_scope_combo.bind("<<ComboboxSelected>>", self._on_export_scope_selected)
        self.export_scope_value_var = tk.StringVar()
        self.export_scope_value_entry = ttk.Entry(
            scope_line, textvariable=self.export_scope_value_var, state="disabled"
        )
        self.export_scope_value_entry.pack(side="left", fill="x", expand=True, padx=(8, 0))
        self.export_scope_hint_var = tk.StringVar(value="Todas as mensagens disponíveis")
        self._muted(scope_line, variable=self.export_scope_hint_var, wraplength=280).pack(
            side="left", padx=(8, 0)
        )

        options = self._panel(page)
        options.pack(fill="x", pady=(12, 0))
        self._section_title(options, "2. Conteúdo do JSON").pack(anchor="w")
        checks = tk.Frame(options, bg=COLORS["panel"])
        checks.pack(fill="x", pady=(8, 8))
        self.export_non_media_var = tk.BooleanVar(value=True)
        self.export_content_var = tk.BooleanVar(value=True)
        self.export_raw_var = tk.BooleanVar(value=False)
        self.export_non_media_check = ttk.Checkbutton(
            checks, text="Incluir mensagens sem mídia", variable=self.export_non_media_var
        )
        self.export_content_check = ttk.Checkbutton(
            checks, text="Incluir conteúdo dos textos", variable=self.export_content_var
        )
        export_raw_check = ttk.Checkbutton(
            checks, text="Estrutura técnica bruta", variable=self.export_raw_var
        )
        ResponsiveGrid(
            checks,
            (self.export_non_media_check, self.export_content_check, export_raw_check),
            breakpoints=((650, 3), (380, 2), (0, 1)),
            gap=6,
            uniform="export-options",
        )
        self.export_filter_var = tk.StringVar()
        self._field_label(options, "Filtro avançado do tdl — opcional").pack(anchor="w")
        self.export_filter_entry = ttk.Entry(options, textvariable=self.export_filter_var)
        self.export_filter_entry.pack(fill="x", pady=(4, 0))

        destination = self._panel(page)
        destination.pack(fill="x", pady=(12, 0))
        self._section_title(destination, "3. Arquivo de destino").pack(anchor="w")
        line = tk.Frame(destination, bg=COLORS["panel"])
        line.pack(fill="x", pady=(8, 0))
        self.export_path_var = tk.StringVar()
        ttk.Entry(line, textvariable=self.export_path_var).pack(side="left", fill="x", expand=True)
        ttk.Button(line, text="Escolher arquivo…", command=self._choose_export_path).pack(
            side="left", padx=(8, 0)
        )

        footer = tk.Frame(page, bg=COLORS["bg"])
        footer.pack(fill="x", pady=(12, 0))
        status = tk.Frame(footer, bg=COLORS["bg"])
        status.pack(side="left", fill="x", expand=True)
        self.export_status_var = tk.StringVar(value="Pronto para exportar.")
        tk.Label(
            status,
            textvariable=self.export_status_var,
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            anchor="w",
            font=("Segoe UI", 10),
        ).pack(fill="x")
        self.export_progress = ttk.Progressbar(status, mode="determinate", maximum=100)
        self.export_progress.pack(fill="x", pady=(5, 0))
        self.export_cancel_button = ttk.Button(
            footer, text="Cancelar", command=lambda: self._cancel_tool("export"), state="disabled"
        )
        self.export_cancel_button.pack(side="right")
        self.export_start_button = ttk.Button(
            footer, text="Exportar JSON", style="Accent.TButton", command=self._start_export
        )
        self.export_start_button.pack(side="right", padx=(0, 8))
        ttk.Button(footer, text="Abrir pasta", command=self._open_export_folder).pack(
            side="right", padx=(0, 8)
        )
        self._on_export_type_selected()

    def _on_export_chat_selected(self, _event: tk.Event[Any] | None = None) -> None:
        self._populate_topic_combo(
            self.export_chat_var, self.export_topic_var, self.export_topic_combo
        )
        self._suggest_export_path()

    def _on_export_type_selected(self, _event: tk.Event[Any] | None = None) -> None:
        is_messages = EXPORT_TYPE_LABELS.get(self.export_type_var.get()) == "messages"
        self._refresh_export_chat_values()
        state = "normal" if is_messages else "disabled"
        combo_state = "readonly" if is_messages else "disabled"
        self.export_scope_combo.configure(state=combo_state)
        self.export_non_media_check.configure(state=state)
        self.export_content_check.configure(state=state)
        self.export_filter_entry.configure(state=state)
        if is_messages:
            self.export_description_var.set(
                "Exporte mensagens, textos e metadados para um arquivo JSON independente."
            )
            self._on_export_chat_selected()
            self._on_export_scope_selected()
        else:
            self.export_description_var.set(
                "Exporte membros, administradores, bots e inscritos visíveis no canal ou grupo."
            )
            self.export_topic_var.set("")
            self.export_topic_combo.configure(state="disabled", values=())
            self.export_scope_value_entry.configure(state="disabled")
            self.export_scope_hint_var.set("A lista completa disponível será exportada")
        self._suggest_export_path()

    def _refresh_export_chat_values(self) -> None:
        members = EXPORT_TYPE_LABELS.get(self.export_type_var.get()) == "users"
        labels = [
            self._chat_label(row)
            for row in self.chat_rows
            if not members or row.get("type") in {"channel", "group"}
        ]
        self.export_chat_combo.configure(values=labels)
        if self.export_chat_var.get() not in labels:
            self.export_chat_var.set("")

    def _on_export_scope_selected(self, _event: tk.Event[Any] | None = None) -> None:
        scope = EXPORT_SCOPE_LABELS.get(self.export_scope_var.get(), "all")
        hints = {
            "all": "Todas as mensagens disponíveis",
            "last": "Quantidade de mensagens",
            "id": "Formato: 100,500",
            "time": "Formato: 2026-01-01,2026-01-31",
        }
        defaults = {"all": "", "last": "100", "id": "1,100", "time": "2026-01-01,2026-01-31"}
        self.export_scope_hint_var.set(hints[scope])
        self.export_scope_value_entry.configure(state="disabled" if scope == "all" else "normal")
        self.export_scope_value_var.set(defaults[scope])

    def _suggest_export_path(self) -> None:
        chat = self.chat_by_label.get(self.export_chat_var.get())
        if not chat:
            return
        kind = EXPORT_TYPE_LABELS.get(self.export_type_var.get(), "messages")
        suffix = "mensagens" if kind == "messages" else "membros"
        base = Path(self.config_store.get("default_download_dir", str(default_download_directory())))
        suggestion = str(base / "MLD Tools Exports" / f"{safe_filename(chat['name'])}_{suffix}.json")
        current = self.export_path_var.get().strip()
        if not current or current == self._last_export_path:
            self.export_path_var.set(suggestion)
            self._last_export_path = suggestion

    def _choose_export_path(self) -> None:
        current = Path(self.export_path_var.get()).expanduser() if self.export_path_var.get() else None
        selected = filedialog.asksaveasfilename(
            parent=self,
            title="Salvar exportação JSON",
            initialdir=str(current.parent if current else default_download_directory()),
            initialfile=current.name if current else "exportacao.json",
            defaultextension=".json",
            filetypes=(("Arquivo JSON", "*.json"),),
        )
        if selected:
            self.export_path_var.set(selected)
            self._last_export_path = selected

    def _open_export_folder(self) -> None:
        value = self.export_path_var.get().strip()
        if not value:
            return
        try:
            open_directory(Path(value).expanduser().parent)
        except OSError as exc:
            messagebox.showerror("Não foi possível abrir a pasta", str(exc), parent=self)

    def _start_export(self) -> None:
        chat = self.chat_by_label.get(self.export_chat_var.get())
        if not chat:
            messagebox.showwarning(
                "Origem necessária", "Atualize a lista e selecione um canal ou grupo.", parent=self
            )
            return
        output_value = self.export_path_var.get().strip()
        if not output_value:
            messagebox.showwarning("Destino necessário", "Escolha o arquivo JSON de destino.", parent=self)
            return
        output = Path(output_value).expanduser()
        if output.exists() and not messagebox.askyesno(
            "Substituir exportação?",
            f"O arquivo “{output.name}” já existe. Deseja substituí-lo?",
            parent=self,
        ):
            return
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
            kind = EXPORT_TYPE_LABELS.get(self.export_type_var.get(), "messages")
            if kind == "messages":
                scope = EXPORT_SCOPE_LABELS.get(self.export_scope_var.get(), "all")
                if scope == "all" and not messagebox.askyesno(
                    "Exportar todo o histórico?",
                    (
                        "A exportação completa pode levar bastante tempo e gerar um JSON grande, "
                        "principalmente com mensagens sem mídia e conteúdo textual. Deseja continuar?"
                    ),
                    parent=self,
                ):
                    return
                topic = self._selected_topic(chat, self.export_topic_var.get())
                command = self.tdl.build_message_export_command(
                    chat["id"],
                    output,
                    topic_id=topic["id"] if topic else "",
                    scope=scope,
                    scope_value=self.export_scope_value_var.get(),
                    include_non_media=self.export_non_media_var.get(),
                    with_content=self.export_content_var.get(),
                    raw=self.export_raw_var.get(),
                    filter_expression=self.export_filter_var.get(),
                )
                label = f'a exportação de mensagens de "{chat["name"]}"'
            else:
                command = self.tdl.build_user_export_command(
                    chat["id"], output, raw=self.export_raw_var.get()
                )
                label = f'a exportação de membros de "{chat["name"]}"'
        except Exception as exc:
            messagebox.showerror("Não foi possível exportar", str(exc), parent=self)
            return
        try:
            started = self.tool_runner.start("export", label, command)
        except EngineBusyError as exc:
            messagebox.showinfo("Motor em uso", str(exc), parent=self)
            return
        if not started:
            messagebox.showinfo(
                "Operação em andamento", "Aguarde a operação atual terminar.", parent=self
            )
            return
        self._last_export_path = str(output)
        self._active_export_path = str(output)
        self._set_tool_running("export", True, "Preparando exportação…")

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    def _page_upload(self) -> None:
        page = self.pages["upload"]

        source = self._panel(page)
        source.pack(fill="x")
        header = tk.Frame(source, bg=COLORS["panel"])
        header.pack(fill="x", pady=(0, 8))
        self._section_title(header, "1. Arquivos e pastas").pack(anchor="w")
        upload_actions = tk.Frame(header, bg=COLORS["panel"])
        upload_actions.pack(fill="x", pady=(8, 0))
        ResponsiveGrid(
            upload_actions,
            (
                ttk.Button(
                    upload_actions,
                    text="Adicionar arquivos…",
                    command=self._choose_upload_files,
                ),
                ttk.Button(
                    upload_actions,
                    text="Adicionar pasta…",
                    command=self._choose_upload_folder,
                ),
                ttk.Button(
                    upload_actions,
                    text="Remover seleção",
                    command=self._remove_selected_upload_paths,
                ),
                ttk.Button(upload_actions, text="Limpar", command=self._clear_upload_paths),
            ),
            breakpoints=((720, 4), (380, 2), (0, 1)),
            gap=7,
            uniform="upload-actions",
        )
        self.upload_tree = ttk.Treeview(
            source, columns=("type", "size", "path"), show="tree headings", height=4
        )
        self.upload_tree.heading("#0", text="Nome")
        self.upload_tree.heading("type", text="Tipo")
        self.upload_tree.heading("size", text="Tamanho")
        self.upload_tree.heading("path", text="Local")
        self.upload_tree.column("#0", width=250)
        self.upload_tree.column("type", width=80, anchor="center")
        self.upload_tree.column("size", width=100, anchor="e")
        self.upload_tree.column("path", width=470)
        self.upload_tree.pack(fill="x")

        destination = self._panel(page)
        destination.pack(fill="x", pady=(12, 0))
        self._section_title(destination, "2. Destino no Telegram").pack(anchor="w")
        selectors = tk.Frame(destination, bg=COLORS["panel"])
        selectors.pack(fill="x", pady=(9, 0))
        left = tk.Frame(selectors, bg=COLORS["panel"])
        left.pack(side="left", fill="x", expand=True)
        self._field_label(left, "Conversa, canal ou grupo").pack(anchor="w")
        self.upload_chat_var = tk.StringVar(value=SAVED_MESSAGES_LABEL)
        self.upload_chat_combo = ttk.Combobox(
            left,
            state="readonly",
            values=(SAVED_MESSAGES_LABEL,),
            textvariable=self.upload_chat_var,
        )
        self.upload_chat_combo.pack(fill="x", pady=(5, 0))
        self.upload_chat_combo.bind("<<ComboboxSelected>>", self._on_upload_chat_selected)
        ttk.Button(selectors, text="Atualizar lista", command=self.refresh_chats).pack(
            side="left", padx=(8, 0), pady=(22, 0)
        )
        right = tk.Frame(selectors, bg=COLORS["panel"])
        right.pack(side="left", fill="x", expand=True, padx=(12, 0))
        self._field_label(right, "Tópico — opcional").pack(anchor="w")
        self.upload_topic_var = tk.StringVar()
        self.upload_topic_combo = ttk.Combobox(
            right, state="disabled", textvariable=self.upload_topic_var
        )
        self.upload_topic_combo.pack(fill="x", pady=(5, 0))

        options = self._panel(page)
        options.pack(fill="x", pady=(12, 0))
        self._section_title(options, "3. Legenda e filtros").pack(anchor="w")
        caption_line = tk.Frame(options, bg=COLORS["panel"])
        caption_line.pack(fill="x", pady=(8, 0))
        caption_left = tk.Frame(caption_line, bg=COLORS["panel"])
        self.upload_caption_label = self._field_label(
            caption_left, "Legenda — opcional, aplicada a cada arquivo"
        )
        self.upload_caption_label.pack(anchor="w")
        self.upload_caption_text = tk.Text(
            caption_left,
            height=3,
            bg=COLORS["panel_2"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            selectbackground=COLORS["accent"],
            relief="flat",
            padx=9,
            pady=7,
            font=("Segoe UI", 10),
        )
        self.upload_caption_text.pack(fill="x", pady=(4, 0))
        filter_right = tk.Frame(caption_line, bg=COLORS["panel"])
        self.upload_photo_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            filter_right, text="Enviar imagens como fotos", variable=self.upload_photo_var
        ).pack(anchor="w")
        self.upload_album_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            filter_right,
            text="Enviar arquivos agrupados em álbuns",
            variable=self.upload_album_var,
            command=self._toggle_album_options,
        ).pack(anchor="w", pady=(5, 0))
        album_line = tk.Frame(filter_right, bg=COLORS["panel"])
        album_line.pack(fill="x", pady=(7, 0))
        self._field_label(album_line, "Agrupar por").pack(side="left")
        self.upload_album_mode_var = tk.StringVar(value="Seleção atual")
        self.upload_album_mode_combo = ttk.Combobox(
            album_line,
            state="disabled",
            width=18,
            values=tuple(ALBUM_MODE_LABELS),
            textvariable=self.upload_album_mode_var,
        )
        self.upload_album_mode_combo.pack(side="right", fill="x", expand=True, padx=(8, 0))
        fields = tk.Frame(filter_right, bg=COLORS["panel"])
        fields.pack(fill="x", pady=(8, 0))
        fields.grid_columnconfigure(0, weight=1)
        fields.grid_columnconfigure(1, weight=1)
        self.upload_include_var = tk.StringVar()
        self.upload_exclude_var = tk.StringVar()
        self._field_label(fields, "Incluir extensões").grid(row=0, column=0, sticky="w")
        self._field_label(fields, "Excluir extensões").grid(row=0, column=1, sticky="w", padx=(8, 0))
        ttk.Entry(fields, textvariable=self.upload_include_var).grid(row=1, column=0, sticky="ew", pady=(4, 0))
        ttk.Entry(fields, textvariable=self.upload_exclude_var).grid(
            row=1, column=1, sticky="ew", padx=(8, 0), pady=(4, 0)
        )
        ResponsiveGrid(
            caption_line,
            (caption_left, filter_right),
            breakpoints=((720, 2), (0, 1)),
            gap=14,
            uniform="upload-caption",
        )

        footer = tk.Frame(page, bg=COLORS["bg"])
        footer.pack(fill="x", pady=(12, 0))
        status = tk.Frame(footer, bg=COLORS["bg"])
        status.pack(side="left", fill="x", expand=True)
        self.upload_status_var = tk.StringVar(value="Nenhum arquivo selecionado.")
        tk.Label(
            status,
            textvariable=self.upload_status_var,
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            anchor="w",
            font=("Segoe UI", 10),
        ).pack(fill="x")
        self.upload_start_button = ttk.Button(
            footer,
            text="Adicionar à fila",
            style="Accent.TButton",
            command=self._queue_upload,
        )
        self.upload_start_button.pack(side="right")

    def _choose_upload_files(self) -> None:
        filenames = filedialog.askopenfilenames(parent=self, title="Selecione os arquivos")
        self._add_upload_paths(filenames)

    def _choose_upload_folder(self) -> None:
        selected = filedialog.askdirectory(parent=self, title="Selecione uma pasta")
        if selected:
            self._add_upload_paths([selected])

    def _add_upload_paths(self, paths: Any) -> None:
        for value in paths:
            path = str(Path(value).expanduser())
            if path not in self.upload_paths:
                self.upload_paths.append(path)
        self._refresh_upload_tree()

    def _clear_upload_paths(self) -> None:
        self.upload_paths.clear()
        self._refresh_upload_tree()

    def _remove_selected_upload_paths(self) -> None:
        indices = sorted((int(item) for item in self.upload_tree.selection()), reverse=True)
        for index in indices:
            if 0 <= index < len(self.upload_paths):
                self.upload_paths.pop(index)
        self._refresh_upload_tree()

    def _refresh_upload_tree(self) -> None:
        for item in self.upload_tree.get_children():
            self.upload_tree.delete(item)
        for index, value in enumerate(self.upload_paths):
            path = Path(value)
            is_dir = path.is_dir()
            size = "—" if is_dir else human_size(path.stat().st_size) if path.exists() else "Ausente"
            self.upload_tree.insert(
                "",
                "end",
                iid=str(index),
                text=path.name or str(path),
                values=("Pasta" if is_dir else "Arquivo", size, str(path.parent)),
            )
        self.upload_status_var.set(
            f"{len(self.upload_paths)} item(ns) selecionado(s)."
            if self.upload_paths
            else "Nenhum arquivo selecionado."
        )

    def _on_upload_chat_selected(self, _event: tk.Event[Any] | None = None) -> None:
        if self.upload_chat_var.get() == SAVED_MESSAGES_LABEL:
            self.upload_topic_var.set("")
            self.upload_topic_combo.configure(values=(), state="disabled")
            return
        self._populate_topic_combo(
            self.upload_chat_var, self.upload_topic_var, self.upload_topic_combo
        )

    def _toggle_album_options(self) -> None:
        grouped = self.upload_album_var.get()
        self.upload_album_mode_combo.configure(state="readonly" if grouped else "disabled")
        self.upload_caption_label.configure(
            text=(
                "Legenda — opcional, aplicada ao primeiro arquivo de cada álbum"
                if grouped
                else "Legenda — opcional, aplicada a cada arquivo"
            )
        )

    def _queue_upload(self) -> None:
        if not self.upload_paths:
            messagebox.showwarning(
                "Arquivos necessários", "Adicione pelo menos um arquivo ou pasta.", parent=self
            )
            return
        selected_label = self.upload_chat_var.get()
        saved_messages = selected_label == SAVED_MESSAGES_LABEL
        chat = None if saved_messages else self.chat_by_label.get(selected_label)
        if not saved_messages and not chat:
            messagebox.showwarning(
                "Destino necessário", "Atualize a lista e selecione o destino.", parent=self
            )
            return
        topic = self._selected_topic(chat, self.upload_topic_var.get())
        destination = chat["name"] if chat else "Mensagens Salvas"
        activity_destination = destination + (f" / {topic['name']}" if topic else "")
        activity = DownloadTask(
            title=f"Upload — {activity_destination} ({len(self.upload_paths)} item(ns))",
            source_type="upload",
            source={
                "paths": list(self.upload_paths),
                "chat_id": chat["id"] if chat else "",
                "chat_type": chat.get("type", "") if chat else "private",
                "chat_username": chat.get("username", "") if chat else "",
                "topic_id": topic["id"] if topic else "",
                "topic_name": topic["name"] if topic else "",
            },
            destination=activity_destination,
            options={
                "group_albums": self.upload_album_var.get(),
                "album_mode": ALBUM_MODE_LABELS.get(
                    self.upload_album_mode_var.get(), "selection"
                ),
                "caption": self.upload_caption_text.get("1.0", "end-1c"),
                "as_photo": self.upload_photo_var.get(),
                "include_extensions": self.upload_include_var.get().strip(),
                "exclude_extensions": self.upload_exclude_var.get().strip(),
            },
            operation_type="upload",
            status="queued",
            phase="Aguardando",
        )
        try:
            self.tdl.validate_upload_task(activity)
            self.task_store.add(activity)
            self._refresh_task_views(force=True)
        except Exception as exc:
            messagebox.showerror(
                "Não foi possível adicionar o upload",
                str(exc),
                parent=self,
            )
            return
        self._append_log(f"[{activity.title}] Upload adicionado à fila.", "success")
        self.upload_status_var.set(
            f"“{activity.title}” foi adicionado. Use Iniciar fila quando estiver pronto."
        )
        self.show_page("queue")

    def _set_tool_running(self, kind: str, running: bool, message: str) -> None:
        if kind != "export":
            return
        status_var = self.export_status_var
        progress = self.export_progress
        start_button = self.export_start_button
        cancel_button = self.export_cancel_button
        status_var.set(message)
        start_button.configure(state="disabled" if running else "normal")
        cancel_button.configure(state="normal" if running else "disabled")
        if running:
            progress.configure(mode="indeterminate")
            progress.start(12)
        else:
            progress.stop()
            progress.configure(mode="determinate")

    def _cancel_tool(self, kind: str) -> None:
        if kind == "export" and self.tool_runner.active_kind == kind and self.tool_runner.cancel():
            self.export_cancel_button.configure(state="disabled")
            self.export_status_var.set("Cancelando operação…")

    # ------------------------------------------------------------------
    # Queue and history
    # ------------------------------------------------------------------

    def _page_queue(self) -> None:
        page = self.pages["queue"]
        panel = self._panel(page)
        panel.pack(fill="both", expand=True)
        header = tk.Frame(panel, bg=COLORS["panel"])
        header.pack(fill="x", pady=(0, 10))
        self._section_title(header, "Downloads e uploads aguardando ou em andamento").pack(side="left")
        ttk.Button(
            header,
            text="+ Novo upload",
            command=lambda: self.show_page("upload"),
        ).pack(side="right")
        ttk.Button(
            header,
            text="+ Novo download",
            style="Accent.TButton",
            command=lambda: self.show_page("new"),
        ).pack(side="right", padx=(0, 8))
        self.queue_tree = ttk.Treeview(
            panel,
            columns=("status", "progress", "speed", "destination", "date"),
            show="tree headings",
        )
        headings = {
            "#0": "Tarefa",
            "status": "Status",
            "progress": "Progresso",
            "speed": "Velocidade",
            "destination": "Destino",
            "date": "Criado",
        }
        for column, text in headings.items():
            self.queue_tree.heading(column, text=text)
        self.queue_tree.column("#0", width=260)
        self.queue_tree.column("status", width=105, anchor="center")
        self.queue_tree.column("progress", width=85, anchor="center")
        self.queue_tree.column("speed", width=105, anchor="center")
        self.queue_tree.column("destination", width=260)
        self.queue_tree.column("date", width=130)
        self.queue_tree.pack(fill="both", expand=True)
        self._configure_task_tags(self.queue_tree)
        self.queue_tree.bind("<Double-1>", lambda _event: self._show_selected_task_details(self.queue_tree))

        controls = tk.Frame(panel, bg=COLORS["panel"])
        controls.pack(fill="x", pady=(12, 0))
        ResponsiveGrid(
            controls,
            (
                ttk.Button(
                    controls,
                    text="Iniciar fila",
                    style="Accent.TButton",
                    command=self._start_transfer_queue,
                ),
                ttk.Button(
                    controls,
                    text="Pausar fila",
                    command=self._stop_transfer_queue,
                ),
                ttk.Button(controls, text="Pausar", command=self._pause_selected),
                ttk.Button(controls, text="Continuar", command=self._resume_selected),
                ttk.Button(
                    controls,
                    text="Tentar novamente",
                    command=self._retry_selected,
                ),
                ttk.Button(
                    controls,
                    text="Abrir pasta / destino",
                    command=lambda: self._open_selected_folder(self.queue_tree),
                ),
                ttk.Button(
                    controls,
                    text="Cancelar",
                    style="Danger.TButton",
                    command=self._cancel_selected,
                ),
            ),
            breakpoints=((900, 7), (620, 4), (350, 2), (0, 1)),
            gap=7,
            uniform="queue-controls",
        )

    def _page_history(self) -> None:
        page = self.pages["history"]
        panel = self._panel(page)
        panel.pack(fill="both", expand=True)
        header = tk.Frame(panel, bg=COLORS["panel"])
        header.pack(fill="x", pady=(0, 10))
        self._section_title(header, "Tarefas finalizadas").pack(side="left")
        ttk.Button(header, text="Limpar concluídos", command=self._clear_finished).pack(side="right")
        self.history_tree = ttk.Treeview(
            panel,
            columns=("status", "destination", "created", "finished"),
            show="tree headings",
        )
        self.history_tree.heading("#0", text="Tarefa")
        self.history_tree.heading("status", text="Status")
        self.history_tree.heading("destination", text="Destino")
        self.history_tree.heading("created", text="Criado")
        self.history_tree.heading("finished", text="Finalizado")
        self.history_tree.column("#0", width=270)
        self.history_tree.column("status", width=105, anchor="center")
        self.history_tree.column("destination", width=300)
        self.history_tree.column("created", width=135)
        self.history_tree.column("finished", width=135)
        self.history_tree.pack(fill="both", expand=True)
        self._configure_task_tags(self.history_tree)
        self.history_tree.bind("<Double-1>", lambda _event: self._show_selected_task_details(self.history_tree))
        controls = tk.Frame(panel, bg=COLORS["panel"])
        controls.pack(fill="x", pady=(12, 0))
        ttk.Button(
            controls,
            text="Abrir pasta / destino",
            command=lambda: self._open_selected_folder(self.history_tree),
        ).pack(side="left")
        ttk.Button(controls, text="Repetir tarefa", command=self._history_retry).pack(side="left", padx=(7, 0))

    def _selected_task_id(self, tree: ttk.Treeview) -> str | None:
        selected = tree.selection()
        return selected[0] if selected else None

    def _start_transfer_queue(self) -> None:
        if not self.runner.start_queue():
            messagebox.showinfo(
                "Fila vazia",
                "Não há downloads ou uploads aguardando início.",
                parent=self,
            )
            return
        self._append_log("Fila de transferências iniciada manualmente.", "info")

    def _stop_transfer_queue(self) -> None:
        if self.runner.stop_queue():
            self._append_log(
                "Fila pausada. A transferência atual termina; as próximas permanecerão aguardando.",
                "warning",
            )

    def _pause_selected(self) -> None:
        task_id = self._selected_task_id(self.queue_tree)
        task = self.task_store.get(task_id) if task_id else None
        if (
            task
            and task.operation_type == "upload"
            and task.status == "running"
            and not messagebox.askyesno(
                "Pausar upload?",
                "O Telegram não oferece retomada real de uploads. Ao continuar, "
                "a tarefa reiniciará do começo; arquivos ou álbuns já publicados "
                "permanecerão no destino e poderão ser duplicados. Deseja pausar?",
                parent=self,
            )
        ):
            return
        if task_id and not self.runner.pause(task_id):
            messagebox.showinfo("Pausa indisponível", "Selecione uma tarefa na fila ou em andamento.", parent=self)

    def _resume_selected(self) -> None:
        task_id = self._selected_task_id(self.queue_tree)
        if task_id and not self.runner.resume(task_id):
            messagebox.showinfo("Retomada indisponível", "A tarefa selecionada não está pausada.", parent=self)

    def _retry_selected(self) -> None:
        task_id = self._selected_task_id(self.queue_tree)
        if task_id and not self.runner.retry(task_id):
            messagebox.showinfo("Nova tentativa indisponível", "Selecione uma tarefa pausada ou com erro.", parent=self)

    def _cancel_selected(self) -> None:
        task_id = self._selected_task_id(self.queue_tree)
        if not task_id:
            return
        task = self.task_store.get(task_id)
        if not task:
            return
        detail = (
            "Arquivos já enviados permanecerão no Telegram."
            if task.operation_type == "upload"
            else "Os arquivos já baixados serão mantidos."
        )
        if messagebox.askyesno(
            "Cancelar transferência",
            f"Cancelar “{task.title}”? {detail}",
            parent=self,
        ):
            self.runner.cancel(task_id)

    def _history_retry(self) -> None:
        task_id = self._selected_task_id(self.history_tree)
        task = self.task_store.get(task_id) if task_id else None
        if task and task.operation_type == "upload" and "chat_id" not in task.source:
            available_paths = [
                str(path)
                for value in task.source.get("paths", [])
                if (path := Path(str(value)).expanduser()).exists()
            ]
            if available_paths:
                self.upload_paths = available_paths
                self._refresh_upload_tree()
            self.show_page("upload")
            messagebox.showinfo(
                "Upload de versão anterior",
                "Os arquivos foram recuperados. Selecione novamente o destino e "
                "adicione o upload à fila.",
                parent=self,
            )
        elif task_id:
            if self.runner.retry(
                task_id,
                restart=bool(task and task.operation_type == "upload"),
            ):
                self.show_page("queue")
            else:
                messagebox.showinfo(
                    "Não foi possível repetir",
                    "Confira se os arquivos de origem ainda existem e tente novamente.",
                    parent=self,
                )

    def _open_selected_folder(self, tree: ttk.Treeview) -> None:
        task_id = self._selected_task_id(tree)
        task = self.task_store.get(task_id) if task_id else None
        if task:
            if task.operation_type == "upload":
                messagebox.showinfo(
                    "Destino no Telegram",
                    f"Este upload foi enviado para:\n{task.destination}",
                    parent=self,
                )
                return
            try:
                open_directory(task.destination)
            except OSError as exc:
                messagebox.showerror("Não foi possível abrir a pasta", str(exc), parent=self)

    def _show_selected_task_details(self, tree: ttk.Treeview) -> None:
        task_id = self._selected_task_id(tree)
        task = self.task_store.get(task_id) if task_id else None
        if not task:
            return
        operation = "Upload" if task.operation_type == "upload" else "Download"
        message = (
            f"Operação: {operation}\n"
            f"Status: {task_status_label(task)}\n"
            f"Etapa: {task.phase}\n"
            f"Progresso: {task.progress:.1f}%\n"
            f"Destino: {task.destination}"
        )
        if task.error:
            message += f"\n\nErro:\n{task.error}"
        if task.estimated_bytes:
            message += f"\n\nTamanho estimado: {human_size(task.estimated_bytes)}"
        messagebox.showinfo(task.title, message, parent=self)

    def _clear_finished(self) -> None:
        if not messagebox.askyesno(
            "Limpar histórico",
            "Remover as tarefas concluídas e canceladas do histórico? "
            "Arquivos locais e publicações no Telegram não serão apagados.",
            parent=self,
        ):
            return
        removed = self.task_store.remove_finished()
        self._append_log(f"{removed} registro(s) removido(s) do histórico.", "info")
        self._refresh_task_views(force=True)

    # ------------------------------------------------------------------
    # Telegram
    # ------------------------------------------------------------------

    def _page_telegram(self) -> None:
        page = self.pages["telegram"]
        status_panel = self._panel(page)
        status_panel.pack(fill="x")
        self._section_title(status_panel, "Estado da conexão").pack(anchor="w")
        status_grid = tk.Frame(status_panel, bg=COLORS["panel"])
        status_grid.pack(fill="x", pady=(12, 0))
        status_grid.grid_columnconfigure(1, weight=1)
        self._field_label(status_grid, "Motor tdl").grid(row=0, column=0, sticky="w")
        self.telegram_engine_var = tk.StringVar(value="Verificando…")
        tk.Label(status_grid, textvariable=self.telegram_engine_var, bg=COLORS["panel"], fg=COLORS["text"], font=("Segoe UI", 10)).grid(row=0, column=1, sticky="w", padx=(15, 0))
        self._field_label(status_grid, "Sessão").grid(row=1, column=0, sticky="w", pady=(9, 0))
        self.telegram_session_var = tk.StringVar(value="Não verificada")
        tk.Label(status_grid, textvariable=self.telegram_session_var, bg=COLORS["panel"], fg=COLORS["text"], font=("Segoe UI", 10)).grid(row=1, column=1, sticky="w", padx=(15, 0), pady=(9, 0))
        ttk.Button(status_grid, text="Verificar conta", command=self.refresh_chats).grid(row=0, column=2, rowspan=2, sticky="e", padx=(12, 0))

        login = self._panel(page)
        login.pack(fill="x", pady=(14, 0))
        self._section_title(login, "Entrar no Telegram").pack(anchor="w")
        self._muted(
            login,
            text=(
                "A autenticação é executada pelo tdl em uma janela própria. Nenhum código ou senha é salvo pelo MLD Tools. "
                "Depois de concluir, volte ao aplicativo e clique em Verificar conta."
            ),
        ).pack(fill="x", pady=(7, 12))
        buttons = tk.Frame(login, bg=COLORS["panel"])
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Importar Telegram Desktop", style="Accent.TButton", command=lambda: self._start_login("desktop")).pack(side="left")
        ttk.Button(buttons, text="Entrar por QR Code", command=lambda: self._start_login("qr")).pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Telefone + código", command=lambda: self._start_login("code")).pack(side="left", padx=(8, 0))

        chats = self._panel(page)
        chats.pack(fill="both", expand=True, pady=(14, 0))
        header = tk.Frame(chats, bg=COLORS["panel"])
        header.pack(fill="x", pady=(0, 10))
        self._section_title(header, "Canais disponíveis").pack(side="left")
        self.telegram_chat_count_var = tk.StringVar(value="Lista ainda não carregada")
        self._muted(header, variable=self.telegram_chat_count_var, wraplength=300).pack(side="right")
        self.telegram_chat_tree = ttk.Treeview(
            chats,
            columns=("type", "username", "topics", "id"),
            show="tree headings",
            height=9,
        )
        self.telegram_chat_tree.heading("#0", text="Nome")
        self.telegram_chat_tree.heading("type", text="Tipo")
        self.telegram_chat_tree.heading("username", text="Usuário")
        self.telegram_chat_tree.heading("topics", text="Tópicos")
        self.telegram_chat_tree.heading("id", text="ID")
        self.telegram_chat_tree.column("#0", width=310)
        self.telegram_chat_tree.column("type", width=100)
        self.telegram_chat_tree.column("username", width=180)
        self.telegram_chat_tree.column("topics", width=90, anchor="center")
        self.telegram_chat_tree.column("id", width=140)
        self.telegram_chat_tree.pack(fill="both", expand=True)

    def _start_login(self, mode: str) -> None:
        if self.login_process and self.login_process.poll() is None:
            messagebox.showinfo("Login em andamento", "Conclua a autenticação na janela que já está aberta.", parent=self)
            return
        try:
            self.login_process, self.login_operation_token = self.tdl.launch_login(mode)
        except EngineBusyError as exc:
            messagebox.showinfo("Motor em uso", str(exc), parent=self)
            return
        except Exception as exc:
            messagebox.showerror("Não foi possível abrir o login", str(exc), parent=self)
            return
        self.telegram_session_var.set("Autenticação em andamento…")
        self._append_log("Janela de autenticação do Telegram aberta.", "info")

        def wait_for_login() -> None:
            process = self.login_process
            token = self.login_operation_token
            assert process is not None
            try:
                code = process.wait()
            finally:
                if token is not None:
                    self.tdl.release_operation(token)
            self.events.put({"type": "login_finished", "code": code})

        threading.Thread(target=wait_for_login, name="mldtools-login", daemon=True).start()

    def refresh_chats(self) -> None:
        if self._chat_refresh_busy:
            return
        self._chat_refresh_busy = True
        self.telegram_session_var.set("Verificando…")
        self.telegram_chat_count_var.set("Carregando canais…")

        def load() -> None:
            try:
                rows = self.tdl.run_chat_list()
                self.events.put({"type": "chats_loaded", "rows": rows})
            except Exception as exc:
                self.events.put({"type": "chats_failed", "message": str(exc)})

        threading.Thread(target=load, name="mldtools-chats", daemon=True).start()

    def _apply_chat_rows(self, rows: list[dict[str, Any]]) -> None:
        self.chat_rows = sorted(rows, key=lambda row: row["name"].casefold())
        self.chat_by_label.clear()
        labels = []
        for row in self.chat_rows:
            label = self._chat_label(row)
            labels.append(label)
            self.chat_by_label[label] = row
        self.chat_combo.configure(values=labels)
        if self.chat_var.get() not in labels:
            self.chat_var.set("")
        self._refresh_export_chat_values()
        upload_labels = [SAVED_MESSAGES_LABEL, *labels]
        self.upload_chat_combo.configure(values=upload_labels)
        if self.upload_chat_var.get() not in upload_labels:
            self.upload_chat_var.set(SAVED_MESSAGES_LABEL)
        self._on_chat_selected()
        self._on_export_chat_selected()
        self._on_upload_chat_selected()
        for item in self.telegram_chat_tree.get_children():
            self.telegram_chat_tree.delete(item)
        for row in self.chat_rows:
            username = str(row.get("username", "")).strip().lstrip("@")
            self.telegram_chat_tree.insert(
                "",
                "end",
                text=row["name"],
                values=(
                    CHAT_TYPE_LABELS.get(row["type"], row["type"]),
                    f"@{username}" if username and username != "-" else "—",
                    len(row["topics"]),
                    row["id"],
                ),
            )
        self.telegram_session_var.set("Conectado e verificado")
        self.telegram_chat_count_var.set(f"{len(rows)} canal(is), grupo(s) e conversa(s)")
        self.dashboard_telegram_var.set("Conectado")
        self.sidebar_telegram_var.set("● Telegram conectado")
        self.sidebar_telegram_label.configure(fg=COLORS["success"])
        self._append_log(f"Conta verificada: {len(rows)} conversas encontradas.", "success")

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def _page_config(self) -> None:
        page = self.pages["config"]
        folders = self._panel(page)
        folders.pack(fill="x")
        self._section_title(folders, "Pastas").pack(anchor="w")
        self.config_download_dir_var = tk.StringVar()
        self.config_workspace_dir_var = tk.StringVar()
        self._config_path_row(folders, "Destino padrão", self.config_download_dir_var, self._choose_config_download_dir)
        self._config_path_row(folders, "Arquivos temporários", self.config_workspace_dir_var, self._choose_workspace_dir)
        self._muted(
            folders,
            text="Os arquivos finais vão diretamente para o destino. A pasta temporária guarda somente exportações e dados de retomada.",
        ).pack(fill="x", pady=(8, 0))

        performance = self._panel(page)
        performance.pack(fill="x", pady=(14, 0))
        self._section_title(performance, "Desempenho e rede").pack(anchor="w")
        grid = tk.Frame(performance, bg=COLORS["panel"])
        grid.pack(fill="x", pady=(10, 0))
        self.config_threads_var = tk.IntVar(value=8)
        self.config_parallel_var = tk.IntVar(value=4)
        self.config_pool_var = tk.IntVar(value=8)
        self.config_delay_var = tk.IntVar(value=0)
        fields = (
            ("Conexões por arquivo", self.config_threads_var, 1, 32),
            ("Transferências simultâneas", self.config_parallel_var, 1, 16),
            ("Pool de conexões", self.config_pool_var, 1, 32),
            ("Atraso entre tarefas (s)", self.config_delay_var, 0, 3600),
        )
        field_widgets = []
        for label, variable, minimum, maximum in fields:
            field = tk.Frame(grid, bg=COLORS["panel"])
            self._field_label(field, label).pack(anchor="w")
            ttk.Spinbox(
                field,
                textvariable=variable,
                from_=minimum,
                to=maximum,
            ).pack(fill="x", pady=(4, 0))
            field_widgets.append(field)
        ResponsiveGrid(
            grid,
            field_widgets,
            breakpoints=((820, 4), (460, 2), (0, 1)),
            gap=10,
            uniform="performance_fields",
        )

        self.config_proxy_var = tk.StringVar()
        self.config_timeout_var = tk.StringVar()
        network = tk.Frame(performance, bg=COLORS["panel"])
        network.pack(fill="x", pady=(12, 0))
        network_widgets = []
        for label, variable in (
            ("Proxy — opcional", self.config_proxy_var),
            ("Tempo de reconexão", self.config_timeout_var),
        ):
            field = tk.Frame(network, bg=COLORS["panel"])
            self._field_label(field, label).pack(anchor="w")
            ttk.Entry(field, textvariable=variable).pack(fill="x", pady=(4, 0))
            network_widgets.append(field)
        ResponsiveGrid(
            network,
            network_widgets,
            breakpoints=((520, 2), (0, 1)),
            gap=10,
            uniform="network_fields",
        )

        presets = tk.Frame(performance, bg=COLORS["panel"])
        presets.pack(fill="x", pady=(12, 0))
        self._field_label(presets, "Perfis de desempenho").pack(anchor="w")
        preset_buttons = tk.Frame(presets, bg=COLORS["panel"])
        preset_buttons.pack(fill="x", pady=(6, 0))
        balanced_button = ttk.Button(
            preset_buttons,
            text="Equilibrado  8 / 4 / 8",
            command=lambda: self._apply_performance_profile(
                *PERFORMANCE_PROFILES["balanced"]
            ),
        )
        fast_button = ttk.Button(
            preset_buttons,
            text="Rápido  16 / 6 / 12",
            command=lambda: self._apply_performance_profile(
                *PERFORMANCE_PROFILES["fast"]
            ),
        )
        aggressive_button = ttk.Button(
            preset_buttons,
            text="Agressivo  24 / 8 / 16",
            command=lambda: self._apply_performance_profile(
                *PERFORMANCE_PROFILES["aggressive"]
            ),
        )
        ResponsiveGrid(
            preset_buttons,
            (balanced_button, fast_button, aggressive_button),
            breakpoints=((700, 3), (420, 2), (0, 1)),
            gap=8,
            uniform="performance_presets",
        )
        self._muted(
            performance,
            text=(
                "Equilibrado prioriza estabilidade; Rápido é recomendado para uso geral; "
                "Agressivo exige rede rápida, SSD e pode antecipar limites temporários do "
                "Telegram. Depois de escolher, salve antes de adicionar ou iniciar as "
                "próximas tarefas."
            ),
        ).pack(fill="x", pady=(8, 0))

        behaviour = self._panel(page)
        behaviour.pack(fill="x", pady=(14, 0))
        self._section_title(behaviour, "Comportamento padrão").pack(anchor="w")
        checks = tk.Frame(behaviour, bg=COLORS["panel"])
        checks.pack(fill="x", pady=(9, 0))
        self.config_skip_var = tk.BooleanVar()
        self.config_group_var = tk.BooleanVar()
        self.config_original_name_var = tk.BooleanVar()
        self.config_takeout_var = tk.BooleanVar()
        self.config_desc_var = tk.BooleanVar()
        self.config_confirm_full_var = tk.BooleanVar()
        check_widgets = (
            ttk.Checkbutton(checks, text="Ignorar arquivos iguais", variable=self.config_skip_var),
            ttk.Checkbutton(checks, text="Completar álbuns", variable=self.config_group_var),
            ttk.Checkbutton(
                checks,
                text="Manter nome original",
                variable=self.config_original_name_var,
            ),
            ttk.Checkbutton(checks, text="Takeout", variable=self.config_takeout_var),
            ttk.Checkbutton(checks, text="Mais recentes primeiro", variable=self.config_desc_var),
            ttk.Checkbutton(checks, text="Confirmar canal inteiro", variable=self.config_confirm_full_var),
        )
        ResponsiveGrid(
            checks,
            check_widgets,
            breakpoints=((780, 3), (430, 2), (0, 1)),
            gap=6,
            uniform="behaviour_checks",
        )

        footer = tk.Frame(page, bg=COLORS["bg"])
        footer.pack(fill="x", pady=(14, 0))
        ttk.Button(footer, text="Abrir pasta de dados", command=lambda: open_directory(DATA_DIR)).pack(side="left")
        ttk.Button(footer, text="Salvar configurações", style="Accent.TButton", command=self._save_config).pack(side="right")

    def _config_path_row(self, parent: tk.Widget, label: str, variable: tk.StringVar, command: Any) -> None:
        row = tk.Frame(parent, bg=COLORS["panel"])
        row.pack(fill="x", pady=(10, 0))
        self._field_label(row, label).pack(anchor="w")
        line = tk.Frame(row, bg=COLORS["panel"])
        line.pack(fill="x", pady=(4, 0))
        ttk.Entry(line, textvariable=variable).pack(side="left", fill="x", expand=True)
        ttk.Button(line, text="Escolher…", command=command).pack(side="left", padx=(8, 0))

    def _apply_performance_profile(
        self, threads_per_file: int, parallel_transfers: int, dc_pool: int
    ) -> None:
        self.config_threads_var.set(threads_per_file)
        self.config_parallel_var.set(parallel_transfers)
        self.config_pool_var.set(dc_pool)

    def _choose_config_download_dir(self) -> None:
        selected = filedialog.askdirectory(parent=self, initialdir=self.config_download_dir_var.get() or str(default_download_directory()))
        if selected:
            self.config_download_dir_var.set(selected)

    def _choose_workspace_dir(self) -> None:
        selected = filedialog.askdirectory(parent=self, initialdir=self.config_workspace_dir_var.get() or str(DATA_DIR))
        if selected:
            self.config_workspace_dir_var.set(selected)

    def _load_config_variables(self) -> None:
        cfg = self.config_store.get_all()
        self.destination_var.set(cfg["default_download_dir"])
        self.config_download_dir_var.set(cfg["default_download_dir"])
        self.config_workspace_dir_var.set(cfg["workspace_dir"])
        self.config_threads_var.set(cfg["threads_per_file"])
        self.config_parallel_var.set(cfg["parallel_downloads"])
        self.config_pool_var.set(cfg["dc_pool"])
        self.config_delay_var.set(cfg["delay_seconds"])
        self.config_proxy_var.set(cfg["proxy"])
        self.config_timeout_var.set(cfg["reconnect_timeout"])
        self.config_skip_var.set(cfg["skip_same"])
        self.config_group_var.set(cfg["group_albums"])
        self.config_original_name_var.set(cfg["keep_original_filename"])
        self.config_takeout_var.set(cfg["takeout"])
        self.config_desc_var.set(cfg["descending"])
        self.config_confirm_full_var.set(cfg["confirm_full_chat"])
        self.option_skip_var.set(cfg["skip_same"])
        self.option_group_var.set(cfg["group_albums"])
        self.option_original_name_var.set(cfg["keep_original_filename"])
        self.option_takeout_var.set(cfg["takeout"])
        self.option_desc_var.set(cfg["descending"])
        self.include_ext_var.set(cfg["include_extensions"])
        self.exclude_ext_var.set(cfg["exclude_extensions"])
        self.upload_include_var.set(cfg["include_extensions"])
        self.upload_exclude_var.set(cfg["exclude_extensions"])

    def _save_config(self) -> None:
        download_dir = self.config_download_dir_var.get().strip()
        workspace_dir = self.config_workspace_dir_var.get().strip()
        if not download_dir or not workspace_dir:
            messagebox.showwarning("Pastas necessárias", "Informe as pastas padrão e temporária.", parent=self)
            return
        try:
            Path(download_dir).expanduser().mkdir(parents=True, exist_ok=True)
            Path(workspace_dir).expanduser().mkdir(parents=True, exist_ok=True)
            self.config_store.update(
                {
                    "default_download_dir": download_dir,
                    "workspace_dir": workspace_dir,
                    "threads_per_file": self.config_threads_var.get(),
                    "parallel_downloads": self.config_parallel_var.get(),
                    "dc_pool": self.config_pool_var.get(),
                    "delay_seconds": self.config_delay_var.get(),
                    "proxy": self.config_proxy_var.get().strip(),
                    "reconnect_timeout": self.config_timeout_var.get().strip() or "2m",
                    "skip_same": self.config_skip_var.get(),
                    "group_albums": self.config_group_var.get(),
                    "keep_original_filename": self.config_original_name_var.get(),
                    "takeout": self.config_takeout_var.get(),
                    "descending": self.config_desc_var.get(),
                    "confirm_full_chat": self.config_confirm_full_var.get(),
                }
            )
        except Exception as exc:
            messagebox.showerror("Não foi possível salvar", str(exc), parent=self)
            return
        self.destination_var.set(download_dir)
        self._append_log("Configurações salvas.", "success")
        messagebox.showinfo("Configurações", "Configurações salvas.", parent=self)

    # ------------------------------------------------------------------
    # Log and events
    # ------------------------------------------------------------------

    def _page_log(self) -> None:
        page = self.pages["log"]
        panel = self._panel(page)
        panel.pack(fill="both", expand=True)
        header = tk.Frame(panel, bg=COLORS["panel"])
        header.pack(fill="x", pady=(0, 10))
        self._section_title(header, "Atividade do aplicativo e do motor tdl").pack(side="left")
        ttk.Button(header, text="Abrir pasta de logs", command=lambda: open_directory(LOG_DIR)).pack(side="right")
        self.log_text = tk.Text(
            panel,
            bg=COLORS["sidebar"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            selectbackground=COLORS["accent"],
            relief="flat",
            padx=12,
            pady=10,
            font=("Consolas", 10),
            state="disabled",
            wrap="word",
        )
        self.log_text.pack(fill="both", expand=True)
        self.log_text.tag_configure("success", foreground=COLORS["success"])
        self.log_text.tag_configure("error", foreground=COLORS["danger"])
        self.log_text.tag_configure("warning", foreground=COLORS["warning"])
        self.log_text.tag_configure("engine", foreground=COLORS["muted"])
        self.log_text.tag_configure("info", foreground=COLORS["text"])

    def _append_log(self, message: str, level: str = "info") -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {message.strip()}\n"
        if hasattr(self, "log_text"):
            self.log_text.configure(state="normal")
            self.log_text.insert("end", line, level if level in {"success", "error", "warning", "engine", "info"} else "info")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            with (LOG_DIR / "mldtools_media.log").open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(line)
        except OSError:
            pass

    def _process_events(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                event_type = event.get("type")
                if event_type == "log":
                    self._append_log(str(event.get("message", "")), str(event.get("level", "info")))
                elif event_type in {"tasks_changed", "progress"}:
                    self._refresh_task_views(force=True)
                elif event_type == "estimate":
                    estimated = int(event.get("estimated_bytes", 0))
                    free = int(event.get("free_bytes", 0))
                    self._append_log(
                        f"Tamanho estimado: {human_size(estimated)}; espaço livre: {human_size(free)}.",
                        "info",
                    )
                elif event_type == "chats_loaded":
                    self._chat_refresh_busy = False
                    self._apply_chat_rows(event.get("rows", []))
                elif event_type == "chats_failed":
                    self._chat_refresh_busy = False
                    message = str(event.get("message", "Não foi possível verificar a conta."))
                    self.telegram_session_var.set("Não conectada ou sessão inválida")
                    self.telegram_chat_count_var.set("Falha ao carregar a lista")
                    self.sidebar_telegram_var.set("● Telegram não conectado")
                    self.sidebar_telegram_label.configure(fg=COLORS["warning"])
                    self._append_log(message, "error")
                    messagebox.showerror("Falha ao verificar o Telegram", message[-1000:], parent=self)
                elif event_type == "login_finished":
                    code = int(event.get("code", 1))
                    self.login_process = None
                    self.login_operation_token = None
                    self._append_log(
                        "Autenticação finalizada." if code == 0 else f"Autenticação encerrada com código {code}.",
                        "success" if code == 0 else "warning",
                    )
                    self.telegram_session_var.set("Sessão encontrada; clique em Verificar conta" if self.tdl.session_exists() else "Não conectada")
                    if code != 0:
                        messagebox.showwarning(
                            "Autenticação não concluída",
                            (
                                "A janela de autenticação terminou com erro.\n\n"
                                "Se ela mostrou ‘Current database is used by another process’, "
                                "feche o MLD Tools, encerre qualquer tdl.exe no Gerenciador de "
                                "Tarefas e tente novamente. Se ainda persistir, reinicie o Windows uma vez.\n\n"
                                "Depois, abra apenas um método de login e aguarde-o terminar antes de verificar a conta."
                            ),
                            parent=self,
                        )
                elif event_type == "tool_log":
                    self._append_log(str(event.get("message", "")), "engine")
                elif event_type in {
                    "tool_started",
                    "tool_progress",
                    "tool_finished",
                    "tool_failed",
                    "tool_cancelled",
                }:
                    self._handle_tool_event(event)
        except queue.Empty:
            pass
        self.after(150, self._process_events)

    def _handle_tool_event(self, event: dict[str, Any]) -> None:
        event_type = str(event.get("type", ""))
        kind = str(event.get("kind", ""))
        if kind != "export":
            return
        status_var = self.export_status_var
        progress = self.export_progress
        action = "Exportação"

        if event_type == "tool_started":
            self._append_log(f"{action} iniciado(a).", "info")
            return
        if event_type == "tool_progress":
            value = event.get("progress")
            speed = str(event.get("speed", ""))
            if value is not None:
                progress.stop()
                progress.configure(mode="determinate")
                progress["value"] = float(value)
                status_var.set(
                    f"{action} em andamento — {float(value):.1f}%"
                    + (f" — {speed}" if speed else "")
                )
            elif speed:
                status_var.set(f"{action} em andamento — {speed}")
            return
        if event_type == "tool_finished":
            message = "Exportação concluída."
            self._set_tool_running(kind, False, message)
            progress["value"] = 100
            self._append_log(message, "success")
            messagebox.showinfo(
                "Exportação concluída",
                f"O arquivo JSON foi salvo em:\n{self._active_export_path}",
                parent=self,
            )
            return
        if event_type == "tool_cancelled":
            message = "Exportação cancelada. O arquivo parcial foi mantido."
            self._set_tool_running(kind, False, message)
            progress["value"] = 0
            self._append_log(message, "warning")
            return
        if event_type == "tool_failed":
            error = str(event.get("message", f"{action} falhou."))
            self._set_tool_running(kind, False, f"{action} falhou.")
            progress["value"] = 0
            self._append_log(f"{action}: {error}", "error")
            messagebox.showerror(f"Falha no {action.lower()}", error[-1200:], parent=self)

    def _periodic_refresh(self) -> None:
        self._refresh_status()
        self._refresh_task_views()
        self.after(1000, self._periodic_refresh)

    def _refresh_status(self) -> None:
        engine_ok = self.tdl.engine_exists()
        self.telegram_engine_var.set("Disponível — tdl v0.20.4" if engine_ok else "Não encontrado")
        self.sidebar_engine_var.set("● Motor tdl disponível" if engine_ok else "● Motor tdl ausente")
        self.sidebar_engine_label.configure(fg=COLORS["success"] if engine_ok else COLORS["danger"])
        if self.tdl.session_exists() and not self.chat_rows and not self._chat_refresh_busy:
            self.telegram_session_var.set("Sessão encontrada; falta verificar")
            self.dashboard_telegram_var.set("Sessão encontrada")
            self.sidebar_telegram_var.set("● Sessão não verificada")
            self.sidebar_telegram_label.configure(fg=COLORS["warning"])
        elif not self.tdl.session_exists() and not self.chat_rows:
            self.telegram_session_var.set("Não conectada")
            self.dashboard_telegram_var.set("Não conectada")
            self.sidebar_telegram_var.set("● Telegram não conectado")
            self.sidebar_telegram_label.configure(fg=COLORS["muted"])

        active_id = self.runner.active_task_id
        active = self.task_store.get(active_id) if active_id else None
        tool_kind = self.tool_runner.active_kind
        if active:
            self.dashboard_active_var.set(active.title)
            self.active_task_var.set(f"{active.phase}  •  {active.progress:.1f}%" + (f"  •  {active.speed}" if active.speed else ""))
            self.active_progress["value"] = active.progress
            self.sidebar_download_var.set(f"● {active.progress:.0f}% — {active.title[:20]}")
            self.sidebar_download_label.configure(fg=COLORS["accent_hover"])
        elif tool_kind:
            action = "Exportação"
            tool_progress = self.export_progress
            value = float(tool_progress["value"]) if str(tool_progress["mode"]) == "determinate" else 0.0
            self.dashboard_active_var.set(action)
            self.active_task_var.set(f"{action} em andamento")
            self.active_progress["value"] = value
            self.sidebar_download_var.set(f"● {action} em andamento")
            self.sidebar_download_label.configure(fg=COLORS["accent_hover"])
        else:
            self.dashboard_active_var.set("Nenhum")
            self.active_task_var.set("Nenhuma operação em andamento.")
            self.active_progress["value"] = 0
            self.sidebar_download_var.set("● Nenhuma operação ativa")
            self.sidebar_download_label.configure(fg=COLORS["muted"])
        tasks = self.task_store.list()
        self.dashboard_queue_var.set(
            str(
                sum(task.status == "queued" for task in tasks)
            )
        )
        path = Path(self.config_store.get("default_download_dir", str(default_download_directory()))).expanduser()
        try:
            path.mkdir(parents=True, exist_ok=True)
            free = shutil.disk_usage(path).free
            self.dashboard_disk_var.set(human_size(free))
        except OSError:
            self.dashboard_disk_var.set("Indisponível")

    def _refresh_task_views(self, force: bool = False) -> None:
        tasks = self.task_store.list()
        signature = tuple(
            (
                task.id,
                task.operation_type,
                task.status,
                round(task.progress, 1),
                task.speed,
                task.updated_at,
            )
            for task in tasks
        )
        if not force and signature == self._last_tree_signature:
            return
        self._last_tree_signature = signature
        self._fill_task_tree(self.dashboard_tree, list(reversed(tasks[-10:])), "dashboard")
        queue_tasks = [
            task
            for task in tasks
            if task.status not in {"completed", "cancelled"}
        ]
        self._fill_task_tree(self.queue_tree, queue_tasks, "queue")
        history_tasks = [task for task in reversed(tasks) if task.status in {"completed", "cancelled", "failed"}]
        self._fill_task_tree(self.history_tree, history_tasks, "history")

    def _fill_task_tree(self, tree: ttk.Treeview, tasks: list[DownloadTask], mode: str) -> None:
        selection = tree.selection()
        selected_id = selection[0] if selection else None
        for item in tree.get_children():
            tree.delete(item)
        for task in tasks:
            if mode == "dashboard":
                values = (
                    task_status_label(task),
                    f"{task.progress:.0f}%",
                    task.destination,
                    short_time(task.created_at),
                )
            elif mode == "queue":
                values = (
                    task_status_label(task),
                    f"{task.progress:.1f}%",
                    task.speed or "—",
                    task.destination,
                    short_time(task.created_at),
                )
            else:
                values = (
                    task_status_label(task),
                    task.destination,
                    short_time(task.created_at),
                    short_time(task.finished_at),
                )
            tree.insert("", "end", iid=task.id, text=task.title, values=values, tags=(task.status,))
        if selected_id and tree.exists(selected_id):
            tree.selection_set(selected_id)

    def close(self) -> None:
        tool_kind = self.tool_runner.active_kind
        if tool_kind:
            action = "exportação"
            should_close = messagebox.askyesno(
                f"{action.capitalize()} em andamento",
                f"A {action} será cancelada antes de sair. Deseja continuar?",
                parent=self,
            )
            if not should_close:
                return
        login_active = self.login_process is not None and self.login_process.poll() is None
        if login_active:
            should_close = messagebox.askyesno(
                "Autenticação em andamento",
                "A janela de autenticação será encerrada antes de sair. Deseja continuar?",
                parent=self,
            )
            if not should_close:
                return
        active = self.runner.active_task_id
        if active:
            active_task = self.task_store.get(active)
            is_upload = bool(active_task and active_task.operation_type == "upload")
            should_close = messagebox.askyesno(
                "Transferência em andamento",
                (
                    "Ao fechar, o upload atual será pausado e reiniciará do começo "
                    "na próxima tentativa. Itens já publicados permanecerão no "
                    "Telegram e poderão ser duplicados. Deseja sair?"
                    if is_upload
                    else "Ao fechar, o download atual será pausado e poderá ser "
                    "retomado na próxima abertura. Deseja sair?"
                ),
                parent=self,
            )
            if not should_close:
                return
        if login_active and self.login_process is not None:
            self.login_process.terminate()
            try:
                self.login_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.login_process.kill()
                self.login_process.wait(timeout=3)
        self.tool_runner.shutdown()
        self.runner.shutdown()
        self._save_window_placement()
        self.destroy()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--page",
        choices=("dashboard", "new", "export", "upload", "queue", "history", "telegram", "config", "log"),
        default="dashboard",
    )
    args, _unknown = parser.parse_known_args(argv)
    app = MLDToolsMediaGUI(start_page=args.page)
    app.mainloop()
