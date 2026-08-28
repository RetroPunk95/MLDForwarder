"""Sistema visual compartilhado pelas interfaces do MLD Tools.

CustomTkinter desenha as superfícies e ações modernas; Tk/ttk continua nos
controles densos, como tabelas, listas e campos, para preservar a lógica já
validada do aplicativo. As cores foram derivadas do ícone oficial da v3.
"""

from __future__ import annotations

import ctypes
import os
import re
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk

import customtkinter as ctk


COLORS = {
    # Estrutura
    "bg": "#080D18",
    "sidebar": "#0A1020",
    "panel": "#101827",
    "panel_hover": "#141F33",
    "panel_2": "#182338",
    "line": "#26324A",
    "line_soft": "#1B263A",

    # Tipografia
    "text": "#F6F8FC",
    "muted": "#91A0B8",
    "subtle": "#62718A",

    # Identidade
    "accent": "#168BFF",
    "accent_hover": "#0878E8",
    "accent_soft": "#102A48",
    "accent_glow": "#00C2FF",
    "purple": "#7C5CFF",
    "purple_hover": "#6D4DF1",
    "purple_soft": "#211B47",

    # Estados
    "success": "#4ADE80",
    "success_hover": "#6EE7A0",
    "success_soft": "#123522",
    "danger": "#FF657A",
    "danger_bg": "#351822",
    "danger_hover": "#49202C",
    "warning": "#F7C75C",
    "warning_soft": "#392E17",
}


FONT = "Segoe UI"
FONT_SEMIBOLD = "Segoe UI Semibold"
FONT_MONO = "Cascadia Mono"

WINDOW_GEOMETRY_PATTERN = re.compile(
    r"^(?P<width>\d+)x(?P<height>\d+)(?P<x>[+-]\d+)(?P<y>[+-]\d+)$"
)


# CustomTkinter é usado apenas na camada visual. Listas, tabelas e dropdowns
# continuam em ttk para preservar o comportamento já validado no Windows.
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


def enable_dpi_awareness() -> None:
    """Evita uma interface borrada em monitores Windows com escala alta."""

    if os.name != "nt":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def resource_path(relative: str, app_root: str | Path | None = None) -> Path:
    """Resolve recursos no código-fonte e em executáveis one-file."""

    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        candidate = Path(bundle_root) / relative
        if candidate.exists():
            return candidate
    if app_root is not None:
        candidate = Path(app_root) / relative
        if candidate.exists():
            return candidate
    return Path(__file__).resolve().parent / relative


def configure_window(window: tk.Tk | tk.Toplevel, app_root: str | Path | None = None) -> None:
    """Aplica ícone, opções globais e acabamento nativo da janela."""

    window.option_add("*tearOff", False)
    window.option_add("*Font", f"{{{FONT}}} 10")

    # Mantém textos legíveis em monitores 100% sem reduzir a escala já
    # escolhida pelo Windows em monitores HiDPI.
    try:
        current_scaling = float(window.tk.call("tk", "scaling"))
        if current_scaling < 1.45:
            window.tk.call("tk", "scaling", 1.45)
    except (tk.TclError, TypeError, ValueError):
        pass

    icon_path = resource_path("Icon.ico", app_root)
    if icon_path.exists():
        try:
            window.iconbitmap(default=str(icon_path))
        except tk.TclError:
            pass

    if os.name == "nt":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "MidiaLocalDownloads.MLDTools.v3"
            )
        except (AttributeError, OSError):
            pass
        window.after_idle(lambda: _set_dark_title_bar(window))


def restore_window_placement(
    window: tk.Misc,
    saved_geometry: str = "",
    maximized: bool = False,
    *,
    default_size: tuple[int, int],
    minimum_size: tuple[int, int],
) -> str:
    """Restaura uma geometria visível ou cria uma posição inicial centralizada."""

    try:
        scaling = float(window._get_window_scaling())  # type: ignore[attr-defined]
    except (AttributeError, TypeError, ValueError):
        scaling = 1.0
    scaling = max(0.5, scaling)

    screen_width = max(1, round(window.winfo_screenwidth() / scaling))
    screen_height = max(1, round(window.winfo_screenheight() / scaling))
    min_width, min_height = minimum_size
    max_width = max(min_width, screen_width - 40)
    max_height = max(min_height, screen_height - 80)

    match = WINDOW_GEOMETRY_PATTERN.fullmatch(str(saved_geometry).strip())
    if match:
        width = max(min_width, min(max_width, int(match.group("width"))))
        height = max(min_height, min(max_height, int(match.group("height"))))
        x = int(match.group("x"))
        y = int(match.group("y"))
        # Se a tela ou o monitor mudou, evita restaurar uma janela inacessível.
        if x < -width + 100 or x > screen_width - 100:
            x = max(0, (screen_width - width) // 2)
        if y < 0 or y > screen_height - 80:
            y = max(0, (screen_height - height) // 2)
    else:
        width = max(min_width, min(max_width, int(default_size[0])))
        height = max(min_height, min(max_height, int(default_size[1])))
        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)

    geometry = f"{width}x{height}+{x}+{y}"
    window.geometry(geometry)

    if maximized:
        def apply_maximized_state() -> None:
            try:
                window.state("zoomed")
            except tk.TclError:
                try:
                    window.attributes("-zoomed", True)
                except tk.TclError:
                    pass

        window.after_idle(apply_maximized_state)

    return geometry


def capture_window_placement(
    window: tk.Misc,
    last_normal_geometry: str,
) -> tuple[str, bool]:
    """Captura o tamanho normal e informa se a janela está maximizada."""

    try:
        maximized = str(window.state()) == "zoomed"
    except tk.TclError:
        maximized = False

    geometry = str(last_normal_geometry).strip()
    if not maximized:
        try:
            geometry = window.geometry()
        except tk.TclError:
            pass
    return geometry, maximized


def _set_dark_title_bar(window: tk.Misc) -> None:
    if os.name != "nt":
        return
    try:
        window.update_idletasks()
        value = ctypes.c_int(1)
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        # 20 é DWMWA_USE_IMMERSIVE_DARK_MODE nas versões atuais do Windows;
        # 19 cobre builds anteriores do Windows 10.
        for attribute in (20, 19):
            result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                attribute,
                ctypes.byref(value),
                ctypes.sizeof(value),
            )
            if result == 0:
                break
    except (AttributeError, OSError, tk.TclError):
        pass


def load_brand_icon(
    window: tk.Misc,
    app_root: str | Path | None = None,
) -> tk.PhotoImage | None:
    icon_path = resource_path("assets/app_icon_64.png", app_root)
    if not icon_path.exists():
        return None
    try:
        return tk.PhotoImage(master=window, file=str(icon_path))
    except tk.TclError:
        return None


class SaaSButton(ctk.CTkButton):
    """CTkButton compatível com a API usada pelos antigos ttk/tk.Button."""

    STYLE_COLORS = {
        "default": (COLORS["panel_2"], COLORS["line"], COLORS["text"]),
        "TButton": (COLORS["panel_2"], COLORS["line"], COLORS["text"]),
        "Secondary.TButton": (COLORS["panel_2"], COLORS["line"], COLORS["text"]),
        "Accent.TButton": (COLORS["accent"], COLORS["accent_hover"], "#FFFFFF"),
        "Purple.TButton": (COLORS["purple"], COLORS["purple_hover"], "#FFFFFF"),
        "Start.TButton": (COLORS["success"], COLORS["success_hover"], COLORS["bg"]),
        "Danger.TButton": (COLORS["danger_bg"], COLORS["danger_hover"], COLORS["danger"]),
        "Ghost.TButton": (COLORS["panel"], COLORS["panel_2"], COLORS["muted"]),
    }

    def __init__(self, master: tk.Misc, **kwargs) -> None:
        text = str(kwargs.get("text", ""))
        style_name = str(kwargs.pop("style", "default"))
        translated = self._translate_legacy_kwargs(kwargs)
        fg_color, hover_color, text_color = self.STYLE_COLORS.get(
            style_name,
            self.STYLE_COLORS["default"],
        )

        translated.setdefault("fg_color", fg_color)
        translated.setdefault("hover_color", hover_color)
        translated.setdefault("text_color", text_color)
        translated.setdefault("text_color_disabled", COLORS["subtle"])
        translated.setdefault("corner_radius", 8)
        translated.setdefault("border_width", 0)
        translated.setdefault("height", 38)
        translated.setdefault("border_spacing", 8)
        translated.setdefault("font", (FONT_SEMIBOLD, 12))
        translated.setdefault("width", max(88, len(text) * 8 + 32))

        self._mld_style = style_name
        super().__init__(master, **translated)

    @staticmethod
    def _translate_legacy_kwargs(kwargs: dict) -> dict:
        translated = dict(kwargs)

        aliases = {
            "bg": "fg_color",
            "background": "fg_color",
            "fg": "text_color",
            "foreground": "text_color",
            "activebackground": "hover_color",
        }
        for old_name, new_name in aliases.items():
            if old_name in translated:
                translated[new_name] = translated.pop(old_name)

        # Não há equivalente separado para a cor do texto durante hover.
        translated.pop("activeforeground", None)

        for unsupported in (
            "bd",
            "borderwidth",
            "relief",
            "padx",
            "pady",
            "takefocus",
            "default",
        ):
            translated.pop(unsupported, None)

        # ttk interpreta width como caracteres; CTk usa pixels.
        width = translated.get("width")
        if isinstance(width, int) and 0 < width < 60:
            translated["width"] = max(88, width * 8 + 28)

        if "font" in translated:
            translated["font"] = _legacy_font_to_ctk(translated["font"])

        return translated

    def configure(self, require_redraw: bool = False, **kwargs):
        style_name = kwargs.pop("style", None)
        if style_name is not None:
            self._mld_style = str(style_name)
            fg_color, hover_color, text_color = self.STYLE_COLORS.get(
                self._mld_style,
                self.STYLE_COLORS["default"],
            )
            kwargs.setdefault("fg_color", fg_color)
            kwargs.setdefault("hover_color", hover_color)
            kwargs.setdefault("text_color", text_color)

        translated = self._translate_legacy_kwargs(kwargs)
        return super().configure(require_redraw=require_redraw, **translated)

    def config(self, **kwargs):
        return self.configure(**kwargs)


class PillLabel(ctk.CTkLabel):
    """Rótulo compacto com fundo e cantos arredondados."""

    def __init__(self, master: tk.Misc, **kwargs) -> None:
        text = str(kwargs.get("text", ""))
        background = kwargs.pop("bg", kwargs.pop("background", COLORS["panel_2"]))
        foreground = kwargs.pop("fg", kwargs.pop("foreground", COLORS["text"]))
        horizontal_padding = int(kwargs.pop("padx", 9))
        vertical_padding = int(kwargs.pop("pady", 4))
        font = _legacy_font_to_ctk(kwargs.get("font", (FONT_SEMIBOLD, 9)))
        kwargs["font"] = font
        font_size = int(font[1]) if isinstance(font, tuple) and len(font) > 1 else 9

        kwargs.setdefault("fg_color", background)
        kwargs.setdefault("text_color", foreground)
        kwargs.setdefault("corner_radius", 7)
        kwargs.setdefault("height", max(24, font_size + vertical_padding * 2 + 4))
        kwargs.setdefault("width", max(42, len(text) * 7 + horizontal_padding * 2))
        super().__init__(master, **kwargs)


def _legacy_font_to_ctk(font):
    """Converte tamanhos Tk em pontos para pixels equivalentes no CTk."""

    if (
        isinstance(font, tuple)
        and len(font) >= 2
        and isinstance(font[1], (int, float))
        and font[1] > 0
    ):
        return (font[0], max(10, round(font[1] * 1.25)), *font[2:])
    return font


class RoundedPanel(tk.Frame):
    """Painel arredondado que preserva a API e o padding de tk.Frame.

    O frame interno continua sendo um master Tk normal para que Treeview,
    Listbox, Text e os demais controles legados funcionem sem adaptações.
    Os métodos de geometria encaminham o posicionamento para a superfície CTk.
    """

    def __init__(
        self,
        master: tk.Misc,
        *,
        padx: int = 18,
        pady: int = 16,
        fg_color: str = COLORS["panel"],
        border_color: str = COLORS["line_soft"],
        corner_radius: int = 10,
    ) -> None:
        self._surface = ctk.CTkFrame(
            master,
            width=1,
            height=1,
            fg_color=fg_color,
            bg_color="transparent",
            border_color=border_color,
            border_width=1,
            corner_radius=corner_radius,
        )

        inset = 4
        super().__init__(
            self._surface,
            bg=fg_color,
            bd=0,
            relief="flat",
            highlightthickness=0,
            padx=max(0, padx - inset),
            pady=max(0, pady - inset),
        )
        tk.Pack.pack_configure(
            self,
            fill="both",
            expand=True,
            padx=inset,
            pady=inset,
        )

    def pack(self, cnf=None, **kwargs):
        if cnf:
            options = dict(cnf)
            options.update(kwargs)
            kwargs = options
        return self._surface.pack(**kwargs)

    def grid(self, cnf=None, **kwargs):
        if cnf:
            options = dict(cnf)
            options.update(kwargs)
            kwargs = options
        return self._surface.grid(**kwargs)

    def place(self, cnf=None, **kwargs):
        if cnf:
            options = dict(cnf)
            options.update(kwargs)
            kwargs = options
        return self._surface.place(**kwargs)

    def pack_forget(self):
        return self._surface.pack_forget()

    def grid_forget(self):
        return self._surface.grid_forget()

    def grid_remove(self):
        return self._surface.grid_remove()

    def place_forget(self):
        return self._surface.place_forget()

    def destroy(self) -> None:
        """Remove também a superfície CTk externa do painel."""

        surface = self._surface
        try:
            tk.Frame.destroy(self)
        finally:
            try:
                if surface.winfo_exists():
                    surface.destroy()
            except tk.TclError:
                pass


class ScrollablePage(tk.Frame):
    """Página com largura fluida e rolagem vertical automática."""

    def __init__(self, master: tk.Misc, *, bg: str = COLORS["bg"]) -> None:
        self._viewport = tk.Frame(master, bg=bg, bd=0, highlightthickness=0)
        self._viewport.grid_rowconfigure(0, weight=1)
        self._viewport.grid_columnconfigure(0, weight=1)

        self._canvas = tk.Canvas(
            self._viewport,
            bg=bg,
            bd=0,
            highlightthickness=0,
            relief="flat",
        )
        self._canvas.grid(row=0, column=0, sticky="nsew")

        self._scrollbar = ttk.Scrollbar(
            self._viewport,
            orient="vertical",
            command=self._canvas.yview,
        )
        self._canvas.configure(yscrollcommand=self._scrollbar.set)

        super().__init__(self._canvas, bg=bg, bd=0, highlightthickness=0)
        self._canvas_window = self._canvas.create_window(
            (0, 0),
            window=self,
            anchor="nw",
        )
        self._active = False
        self._scrollbar_visible = False

        self.bind("<Configure>", self._update_scroll_region, add="+")
        self._canvas.bind("<Configure>", self._resize_content, add="+")
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel, add="+")
        self._canvas.bind_all("<Button-4>", self._on_linux_wheel, add="+")
        self._canvas.bind_all("<Button-5>", self._on_linux_wheel, add="+")

        registry = getattr(master, "_mld_scrollable_pages", None)
        if registry is None:
            registry = []
            setattr(master, "_mld_scrollable_pages", registry)
        registry.append(self)
        self._registry = registry

    def _update_scroll_region(self, _event=None) -> None:
        bbox = self._canvas.bbox("all")
        self._canvas.configure(scrollregion=bbox or (0, 0, 0, 0))
        self.after_idle(self._update_scrollbar_visibility)

    def _resize_content(self, event: tk.Event) -> None:
        self._canvas.itemconfigure(self._canvas_window, width=max(1, event.width))
        self.after_idle(self._update_scrollbar_visibility)

    def _update_scrollbar_visibility(self) -> None:
        try:
            needs_scrollbar = self.winfo_reqheight() > self._canvas.winfo_height() + 1
        except tk.TclError:
            return
        if needs_scrollbar and not self._scrollbar_visible:
            self._scrollbar.grid(row=0, column=1, sticky="ns")
            self._scrollbar_visible = True
        elif not needs_scrollbar and self._scrollbar_visible:
            self._scrollbar.grid_remove()
            self._scrollbar_visible = False
            self._canvas.yview_moveto(0)

    def _can_scroll(self) -> bool:
        return self._active and self._scrollbar_visible

    def _on_mousewheel(self, event: tk.Event):
        if not self._can_scroll():
            return None
        delta = int(-event.delta / 120) if event.delta else 0
        if delta == 0 and event.delta:
            delta = -1 if event.delta > 0 else 1
        if delta:
            self._canvas.yview_scroll(delta, "units")
            return "break"
        return None

    def _on_linux_wheel(self, event: tk.Event):
        if not self._can_scroll():
            return None
        self._canvas.yview_scroll(-1 if event.num == 4 else 1, "units")
        return "break"

    def activate(self) -> None:
        for page in self._registry:
            page._active = page is self
        self._viewport.tkraise()
        self.after_idle(self._update_scrollbar_visibility)

    def scroll_to_top(self) -> None:
        self._canvas.yview_moveto(0)

    def place(self, cnf=None, **kwargs):
        if cnf:
            options = dict(cnf)
            options.update(kwargs)
            kwargs = options
        return self._viewport.place(**kwargs)

    def place_forget(self):
        return self._viewport.place_forget()

    def tkraise(self, above_this=None):
        self.activate()

    def lift(self, above_this=None):
        self.activate()

    def destroy(self) -> None:
        viewport = self._viewport
        try:
            if self in self._registry:
                self._registry.remove(self)
            tk.Frame.destroy(self)
        finally:
            try:
                if viewport.winfo_exists():
                    viewport.destroy()
            except tk.TclError:
                pass


def responsive_column_count(
    width: int,
    breakpoints: tuple[tuple[int, int], ...],
) -> int:
    """Retorna a quantidade de colunas do primeiro breakpoint atendido."""

    for minimum_width, columns in sorted(breakpoints, reverse=True):
        if width >= minimum_width:
            return max(1, columns)
    return 1


class ResponsiveGrid:
    """Reposiciona widgets em grade somente quando um breakpoint muda."""

    def __init__(
        self,
        container: tk.Misc,
        widgets: list[tk.Misc] | tuple[tk.Misc, ...],
        *,
        breakpoints: tuple[tuple[int, int], ...],
        gap: int = 10,
        uniform: str = "responsive",
    ) -> None:
        self.container = container
        self.widgets = list(widgets)
        self.breakpoints = breakpoints
        self.gap = gap
        self.uniform = uniform
        self._columns = 0
        self._max_columns = max((columns for _, columns in breakpoints), default=1)
        container.bind("<Configure>", self._on_configure, add="+")
        controllers = getattr(container, "_mld_responsive_grids", [])
        controllers.append(self)
        setattr(container, "_mld_responsive_grids", controllers)
        container.after_idle(self.refresh)

    def _on_configure(self, event: tk.Event) -> None:
        self.refresh(event.width)

    def refresh(self, width: int | None = None) -> None:
        if width is None:
            width = self.container.winfo_width()
        columns = responsive_column_count(max(1, int(width)), self.breakpoints)
        if columns == self._columns:
            return
        self._columns = columns

        for column in range(self._max_columns):
            self.container.grid_columnconfigure(
                column,
                weight=1 if column < columns else 0,
                uniform=self.uniform if column < columns else "",
            )

        rows = max(1, (len(self.widgets) + columns - 1) // columns)
        half_gap = self.gap // 2
        for index, widget in enumerate(self.widgets):
            row, column = divmod(index, columns)
            widget.grid_forget()
            widget.grid(
                row=row,
                column=column,
                sticky="nsew",
                padx=(0 if column == 0 else half_gap, 0 if column == columns - 1 else half_gap),
                pady=(0, 0 if row == rows - 1 else self.gap),
            )


def bind_responsive_wrap(
    label: tk.Misc,
    parent: tk.Misc,
    maximum: int,
    *,
    horizontal_padding: int = 24,
) -> None:
    """Ajusta o wrap de um texto à largura disponível em tempo real."""

    def update(event: tk.Event | None = None) -> None:
        width = event.width if event is not None else parent.winfo_width()
        available = max(180, int(width) - horizontal_padding)
        try:
            label.configure(wraplength=min(maximum, available))
        except tk.TclError:
            pass

    parent.bind("<Configure>", update, add="+")
    parent.after_idle(update)


def configure_ttk_theme(root: tk.Misc) -> ttk.Style:
    """Configura todos os controles ttk usados nas duas aplicações."""

    style = ttk.Style(root)
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
        focuscolor=COLORS["accent"],
        font=(FONT, 10),
    )

    for style_name in ("TEntry", "TSpinbox"):
        style.configure(
            style_name,
            fieldbackground=COLORS["panel_2"],
            foreground=COLORS["text"],
            insertcolor=COLORS["text"],
            bordercolor=COLORS["line"],
            lightcolor=COLORS["line"],
            darkcolor=COLORS["line"],
            padding=(10, 8),
        )
        style.map(
            style_name,
            bordercolor=[("focus", COLORS["accent"]), ("!focus", COLORS["line"])],
        )

    style.configure(
        "TCombobox",
        fieldbackground=COLORS["panel_2"],
        background=COLORS["panel_2"],
        foreground=COLORS["text"],
        arrowcolor=COLORS["muted"],
        bordercolor=COLORS["line"],
        lightcolor=COLORS["line"],
        darkcolor=COLORS["line"],
        padding=(9, 7),
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", COLORS["panel_2"])],
        foreground=[("readonly", COLORS["text"]), ("disabled", COLORS["subtle"])],
        arrowcolor=[("active", COLORS["accent"]), ("disabled", COLORS["subtle"])],
        bordercolor=[("focus", COLORS["accent"]), ("!focus", COLORS["line"])],
    )

    _configure_button(
        style,
        "TButton",
        COLORS["panel_2"],
        COLORS["text"],
        COLORS["panel_hover"],
    )
    _configure_button(
        style,
        "Secondary.TButton",
        COLORS["panel_2"],
        COLORS["text"],
        COLORS["line"],
    )
    _configure_button(
        style,
        "Accent.TButton",
        COLORS["accent"],
        "#FFFFFF",
        COLORS["accent_hover"],
        bold=True,
    )
    _configure_button(
        style,
        "Purple.TButton",
        COLORS["purple"],
        "#FFFFFF",
        COLORS["purple_hover"],
        bold=True,
    )
    _configure_button(
        style,
        "Start.TButton",
        COLORS["success"],
        COLORS["bg"],
        COLORS["success_hover"],
        bold=True,
    )
    _configure_button(
        style,
        "Danger.TButton",
        COLORS["danger_bg"],
        COLORS["danger"],
        COLORS["danger_hover"],
    )
    _configure_button(
        style,
        "Ghost.TButton",
        COLORS["panel"],
        COLORS["muted"],
        COLORS["panel_2"],
    )

    style.configure(
        "Treeview",
        background=COLORS["panel"],
        fieldbackground=COLORS["panel"],
        foreground=COLORS["text"],
        bordercolor=COLORS["line_soft"],
        borderwidth=0,
        relief="flat",
        rowheight=38,
        font=(FONT, 10),
    )
    style.map(
        "Treeview",
        background=[("selected", COLORS["accent_soft"])],
        foreground=[("selected", COLORS["text"])],
    )
    style.configure(
        "Treeview.Heading",
        background=COLORS["panel_2"],
        foreground=COLORS["muted"],
        bordercolor=COLORS["line_soft"],
        borderwidth=0,
        relief="flat",
        padding=(10, 11),
        font=(FONT_SEMIBOLD, 10),
    )
    style.map(
        "Treeview.Heading",
        background=[("active", COLORS["panel_hover"])],
        foreground=[("active", COLORS["text"])],
    )

    style.configure(
        "Horizontal.TProgressbar",
        troughcolor=COLORS["panel_2"],
        background=COLORS["accent"],
        bordercolor=COLORS["panel_2"],
        lightcolor=COLORS["accent"],
        darkcolor=COLORS["accent"],
        thickness=8,
    )
    style.configure(
        "Success.Horizontal.TProgressbar",
        troughcolor=COLORS["panel_2"],
        background=COLORS["success"],
        bordercolor=COLORS["panel_2"],
        lightcolor=COLORS["success"],
        darkcolor=COLORS["success"],
        thickness=8,
    )

    for style_name in ("TCheckbutton", "TRadiobutton"):
        style.configure(
            style_name,
            background=COLORS["panel"],
            foreground=COLORS["text"],
            indicatorcolor=COLORS["panel_2"],
            bordercolor=COLORS["line"],
            padding=(0, 3),
        )
        style.map(
            style_name,
            background=[("active", COLORS["panel"])],
            foreground=[("disabled", COLORS["subtle"])],
            indicatorcolor=[("selected", COLORS["accent"])],
        )

    for orientation in ("Vertical", "Horizontal"):
        style.configure(
            f"{orientation}.TScrollbar",
            background=COLORS["panel_2"],
            troughcolor=COLORS["panel"],
            arrowcolor=COLORS["muted"],
            bordercolor=COLORS["panel"],
            lightcolor=COLORS["panel_2"],
            darkcolor=COLORS["panel_2"],
            relief="flat",
        )
        style.map(
            f"{orientation}.TScrollbar",
            background=[("active", COLORS["line"])],
            arrowcolor=[("active", COLORS["text"])],
        )

    style.configure("TSeparator", background=COLORS["line_soft"])
    return style


def _configure_button(
    style: ttk.Style,
    name: str,
    background: str,
    foreground: str,
    hover: str,
    *,
    bold: bool = False,
) -> None:
    style.configure(
        name,
        background=background,
        foreground=foreground,
        bordercolor=background,
        lightcolor=background,
        darkcolor=background,
        focuscolor=background,
        borderwidth=0,
        relief="flat",
        padding=(15, 9),
        font=(FONT_SEMIBOLD if bold else FONT, 10),
    )
    style.map(
        name,
        background=[("active", hover), ("disabled", COLORS["line_soft"])],
        foreground=[("active", foreground), ("disabled", COLORS["subtle"])],
        bordercolor=[("active", hover), ("disabled", COLORS["line_soft"])],
        lightcolor=[("active", hover), ("disabled", COLORS["line_soft"])],
        darkcolor=[("active", hover), ("disabled", COLORS["line_soft"])],
    )
