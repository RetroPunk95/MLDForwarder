from __future__ import annotations

from ui_theme import (
    RoundedPanel,
    capture_window_placement,
    responsive_column_count,
    restore_window_placement,
)


class GeometrySurface:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def pack(self, **kwargs):
        self.calls.append(("pack", kwargs))
        return "packed"

    def grid(self, **kwargs):
        self.calls.append(("grid", kwargs))
        return "gridded"

    def place(self, **kwargs):
        self.calls.append(("place", kwargs))
        return "placed"


def rounded_panel_with_surface() -> tuple[RoundedPanel, GeometrySurface]:
    panel = object.__new__(RoundedPanel)
    surface = GeometrySurface()
    panel._surface = surface
    return panel, surface


def test_geometry_methods_forward_only_keyword_arguments() -> None:
    panel, surface = rounded_panel_with_surface()

    assert panel.pack(fill="x") == "packed"
    assert panel.grid({"row": 1}, column=2, sticky="ew") == "gridded"
    assert panel.place({"x": 10}, y=20) == "placed"

    assert surface.calls == [
        ("pack", {"fill": "x"}),
        ("grid", {"row": 1, "column": 2, "sticky": "ew"}),
        ("place", {"x": 10, "y": 20}),
    ]


def test_responsive_column_count_uses_expected_breakpoint() -> None:
    breakpoints = ((840, 4), (520, 2), (0, 1))

    assert responsive_column_count(1200, breakpoints) == 4
    assert responsive_column_count(700, breakpoints) == 2
    assert responsive_column_count(400, breakpoints) == 1


class WindowStub:
    def __init__(self) -> None:
        self.current_geometry = "1x1+0+0"
        self.current_state = "normal"

    def _get_window_scaling(self) -> float:
        return 1.0

    def winfo_screenwidth(self) -> int:
        return 1920

    def winfo_screenheight(self) -> int:
        return 1080

    def geometry(self, value=None):
        if value is not None:
            self.current_geometry = value
        return self.current_geometry

    def state(self, value=None):
        if value is not None:
            self.current_state = value
        return self.current_state

    def after_idle(self, callback) -> None:
        callback()

    def attributes(self, *_args) -> None:
        return None


def test_window_placement_uses_large_centered_default() -> None:
    window = WindowStub()

    geometry = restore_window_placement(
        window,
        default_size=(1320, 940),
        minimum_size=(1160, 740),
    )

    assert geometry == "1320x940+300+70"
    assert window.current_geometry == geometry


def test_window_placement_restores_size_and_maximized_state() -> None:
    window = WindowStub()

    geometry = restore_window_placement(
        window,
        "1280x900+80+40",
        True,
        default_size=(1320, 940),
        minimum_size=(1160, 740),
    )
    captured = capture_window_placement(window, geometry)

    assert geometry == "1280x900+80+40"
    assert window.current_state == "zoomed"
    assert captured == (geometry, True)
