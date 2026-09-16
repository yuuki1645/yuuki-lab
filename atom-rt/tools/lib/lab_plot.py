"""
lab_debug 用の小さな折れ線キャンバス（ライブラリ。直接起動しない）。
"""

from __future__ import annotations

import time
import tkinter as tk
from collections import deque

from .lab_const import CARD, HISTORY_SEC, MUTED


class LinePlot(tk.Canvas):
    """左軸固定レンジ、右軸は表示中系列の自動スケール。"""

    def __init__(self, parent: tk.Widget, title: str, ymin: float, ymax: float, yunit: str) -> None:
        super().__init__(parent, bg=CARD, highlightthickness=0, height=110)
        self.title = title
        self.ymin = ymin
        self.ymax = ymax
        self.yunit = yunit
        self.series: dict[str, deque[tuple[float, float]]] = {}
        self.colors: dict[str, str] = {}
        self.visible: dict[str, bool] = {}
        # "left"=ymin/ymax、"right"=表示中データの自動スケール（電流など単位が違う系列用）
        self.axis: dict[str, str] = {}
        self.right_units: dict[str, str] = {}
        self.guides: list[tuple[float, str]] = []
        self.bind("<Configure>", lambda _e: self.redraw())

    def add_series(self, name: str, color: str, axis: str = "left", unit: str = "") -> None:
        self.series[name] = deque()
        self.colors[name] = color
        self.visible[name] = True
        self.axis[name] = axis
        self.right_units[name] = unit

    def set_visible(self, name: str, on: bool) -> None:
        if name in self.visible:
            self.visible[name] = on

    def set_title(self, title: str) -> None:
        self.title = title

    def add_guide(self, y: float, color: str) -> None:
        self.guides.append((y, color))

    def push(self, name: str, t: float, value: float | None) -> None:
        if value is None or name not in self.series:
            return
        hist = self.series[name]
        hist.append((t, value))
        cutoff = t - HISTORY_SEC
        while hist and hist[0][0] < cutoff:
            hist.popleft()

    def clear(self) -> None:
        for hist in self.series.values():
            hist.clear()

    def _right_visible(self) -> list[str]:
        """右軸で今見えている系列名。"""
        return [
            name
            for name in self.series
            if self.axis.get(name) == "right" and self.visible.get(name, True)
        ]

    def _right_range(self) -> tuple[float, float]:
        """右軸の表示範囲。見える系列の値から少し余白を取る。"""
        vals: list[float] = []
        for name in self._right_visible():
            vals.extend(v for _t, v in self.series[name])
        if not vals:
            return 0.0, 1.0
        lo, hi = min(vals), max(vals)
        if hi - lo < 1e-6:
            pad = max(abs(hi) * 0.25, 0.05)
            return lo - pad, hi + pad
        span = hi - lo
        return lo - 0.08 * span, hi + 0.08 * span

    def _right_unit_label(self) -> str:
        units = [self.right_units.get(n, "") for n in self._right_visible()]
        units = [u for u in units if u]
        uniq: list[str] = []
        for u in units:
            if u not in uniq:
                uniq.append(u)
        return "/".join(uniq)

    def redraw(self) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 40 or h < 40:
            return
        right_on = bool(self._right_visible())
        pad_l, pad_t, pad_b = 44, 22, 8
        pad_r = 52 if right_on else 8
        self.create_text(8, 10, text=self.title, fill=MUTED, anchor="w", font=("Segoe UI", 9))
        y0, y1 = pad_t, h - pad_b
        x0, x1 = pad_l, w - pad_r
        left_span = self.ymax - self.ymin
        if left_span <= 0:
            return
        rymin, rymax = self._right_range()
        right_span = rymax - rymin
        if right_span <= 0:
            right_span = 1.0
        for gy in (self.ymin, (self.ymin + self.ymax) / 2, self.ymax):
            yy = y1 - (gy - self.ymin) / left_span * (y1 - y0)
            self.create_text(
                pad_l - 4, yy, text=f"{gy:.0f}{self.yunit}",
                fill=MUTED, anchor="e", font=("Segoe UI", 8),
            )
        if right_on:
            runit = self._right_unit_label()
            self.create_text(
                w - 4, 10, text=runit, fill=MUTED, anchor="e", font=("Segoe UI", 9),
            )
            for i in range(3):
                gv = rymin + right_span * i / 2.0
                yy = y1 - (gv - rymin) / right_span * (y1 - y0)
                self.create_text(
                    x1 + 4, yy, text=f"{gv:.2f}",
                    fill=MUTED, anchor="w", font=("Segoe UI", 8),
                )
        for gy, col in self.guides:
            yy = y1 - (gy - self.ymin) / left_span * (y1 - y0)
            self.create_line(x0, yy, x1, yy, fill=col, dash=(3, 3))
        now = time.time()
        t0 = now - HISTORY_SEC
        for name, hist in self.series.items():
            if not self.visible.get(name, True):
                continue
            use_right = self.axis.get(name) == "right"
            pts: list[float] = []
            for t, v in hist:
                x = x0 + (t - t0) / HISTORY_SEC * (x1 - x0)
                if use_right:
                    yy = y1 - (v - rymin) / right_span * (y1 - y0)
                else:
                    yy = y1 - (v - self.ymin) / left_span * (y1 - y0)
                pts.extend((x, yy))
            if len(pts) >= 4:
                self.create_line(*pts, fill=self.colors[name], width=1.5)
