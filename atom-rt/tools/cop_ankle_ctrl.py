#!/usr/bin/env python3
"""
右脚かかとピッチの COP 前後中心化（PC 閉ループ）。

ATOM ファームは触らない。lab_debug.py が 20 Hz テレメトリを見て
かかとピッチ（論理関節 3）だけを USB 指令する。

COP_y: Hub と同じ正規化。つま先 = -1、かかと = +1、板の前後中心 = 0。
P 制御: 目標角 = ニュートラル + sign * Kp * (0 - COP_y)、変化は最大 5°/s。
自動スイープ: 100〜170° を 2°/s で往復し、COP_y のゼロ交差からニュートラルを推定する。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# 実験用の絶対指令クランプ（ファームの 40〜230 より狭い。PC / Hub 側だけ）
CMD_MIN = 100.0
CMD_MAX = 170.0
# 右脚: 0 股ロール / 1 股ピッチ / 2 ひざ / 3 かかとピッチ / 4 かかとロール
HEEL_CH = 3
HOLD_CHS = (0, 1, 2, 4)
P_SLEW_DPS = 5.0
SWEEP_SLEW_DPS = 2.0
KP_DEFAULT = 10.0
KP_MIN = 1.0
KP_MAX = 40.0
# これ未満は COP が暴れるので P / スイープの角更新を止める
MIN_FORCE_KG = 0.3
CORNER_MIN_KG = 0.02
COP_MIN_W = 0.05
STEP_DEG = 0.5

# Hub RightFootSole と同じ正規化座標
CORNER_XY: dict[str, tuple[float, float]] = {
    "top_left": (-1.0, -1.0),
    "top_right": (1.0, -1.0),
    "bottom_left": (-1.0, 1.0),
    "bottom_right": (1.0, 1.0),
}


def clamp_cmd(deg: float) -> float:
    """ライブ PWM 指令を 100〜170° に収める。"""
    if deg < CMD_MIN:
        return CMD_MIN
    if deg > CMD_MAX:
        return CMD_MAX
    return deg


def clamp_kp(kp: float) -> float:
    """P ゲインの安全範囲。"""
    if kp < KP_MIN:
        return KP_MIN
    if kp > KP_MAX:
        return KP_MAX
    return kp


def cop_from_foot(foot: dict[str, Any] | None) -> tuple[float | None, float | None, float, bool]:
    """
    足圧サンプルから (cop_x, cop_y, total_kg, force_ok) を返す。
    force_ok は合計が MIN_FORCE_KG 以上かつ COP が計算できたときだけ True。
    """
    if not foot or not foot.get("ok"):
        return None, None, 0.0, False
    corners = foot.get("corners") or {}
    wx = 0.0
    wy = 0.0
    w = 0.0
    total = 0.0
    for key, pos in CORNER_XY.items():
        c = corners.get(key)
        if not isinstance(c, dict):
            continue
        try:
            kg = float(c.get("force_kg") or 0.0)
        except (TypeError, ValueError):
            continue
        if kg < 0.0:
            kg = 0.0
        total += kg
        if kg < CORNER_MIN_KG:
            continue
        wx += pos[0] * kg
        wy += pos[1] * kg
        w += kg
    if w < COP_MIN_W:
        return None, None, total, False
    ok = total >= MIN_FORCE_KG
    return wx / w, wy / w, total, ok


def zero_cross_cmd(c0: float, y0: float, c1: float, y1: float) -> float | None:
    """COP_y が 0 を跨いだ 2 点から、指令角を線形補間する。"""
    if y0 * y1 > 0:
        return None
    den = y1 - y0
    if abs(den) < 1e-6:
        return clamp_cmd(0.5 * (c0 + c1))
    t = (0.0 - y0) / den
    if t < -0.05 or t > 1.05:
        return None
    return clamp_cmd(c0 + t * (c1 - c0))


@dataclass
class CopCtrl:
    """セッション中だけの COP 制御状態（再起動で消える）。"""

    p_on: bool = False
    sweep_on: bool = False
    sweep_dir: float = 1.0
    sign: float = 1.0
    kp: float = KP_DEFAULT
    held: bool = False
    confirmed: float | None = None
    estimated: float | None = None
    last_cmd: float | None = None
    last_t: float | None = None
    status: str = "待機"
    force_kg: float = 0.0
    force_ok: bool = False
    cop_x: float | None = None
    cop_y: float | None = None
    _prev_sample: tuple[float, float] | None = None

    def display_neutral(self) -> float | None:
        """UI 常時表示。確定済みなら確定、未確定なら推定（計算中）。"""
        if self.confirmed is not None:
            return self.confirmed
        return self.estimated

    def active_neutral(self) -> float | None:
        """P 制御が使う目標。確定があればそれを使う。"""
        if self.confirmed is not None:
            return self.confirmed
        return self.estimated

    def to_dict(self) -> dict[str, Any]:
        """Hub の m5/control.cop と同じ形。"""
        return {
            "p_on": self.p_on,
            "sweep_on": self.sweep_on,
            "sign": int(self.sign),
            "kp": self.kp,
            "neutral_confirmed": self.confirmed,
            "neutral_estimated": self.estimated,
            "neutral_display": self.display_neutral(),
            "cop_y": self.cop_y,
            "cop_x": self.cop_x,
            "force_kg": self.force_kg,
            "force_ok": self.force_ok,
            "held": self.held,
            "status": self.status,
            "cmd_min": CMD_MIN,
            "cmd_max": CMD_MAX,
            "p_slew_dps": P_SLEW_DPS,
            "sweep_slew_dps": SWEEP_SLEW_DPS,
            "heel_ch": HEEL_CH,
        }

    def stop_motion(self, reason: str) -> None:
        """P とスイープを止める。PWM は触らない（呼び出し側が指令を残す）。"""
        self.p_on = False
        self.sweep_on = False
        if reason:
            self.status = reason

    def update_cop(self, foot: dict[str, Any] | None) -> None:
        """最新フレームの足圧で COP を更新する。"""
        cx, cy, total, ok = cop_from_foot(foot)
        self.cop_x = cx
        self.cop_y = cy
        self.force_kg = total
        self.force_ok = ok

    def note_sample(self, cmd: float) -> None:
        """有効な COP があればゼロ交差から推定ニュートラルを更新する。"""
        if self.cop_y is None or not self.force_ok:
            return
        cmd = clamp_cmd(cmd)
        if self._prev_sample is not None:
            est = zero_cross_cmd(
                self._prev_sample[0], self._prev_sample[1], cmd, self.cop_y
            )
            if est is not None:
                self.estimated = est
        self._prev_sample = (cmd, self.cop_y)

    def confirm_neutral(self, current_cmd: float) -> float:
        """いまの踵指令をニュートラルとして確定（何度でも上書き可）。推定は使わない。"""
        self.confirmed = clamp_cmd(current_cmd)
        self.status = f"ニュートラル確定  {self.confirmed:.1f}°"
        return self.confirmed

    def clear_confirmed(self) -> None:
        """確定だけ消す。推定は残す。"""
        self.confirmed = None
        self.status = "ニュートラル確定を解除"

    def tick(self, now: float, current_cmd: float) -> float | None:
        """
        新しいかかと指令。角を変えないときは None（最後の指令を保持）。
        足圧不足時は P / スイープとも None。
        """
        cmd = clamp_cmd(current_cmd)
        self.last_cmd = cmd
        if self.last_t is None:
            dt = 0.05
        else:
            dt = now - self.last_t
            if dt < 0.01:
                dt = 0.01
            elif dt > 0.25:
                dt = 0.25
        self.last_t = now

        if self.sweep_on:
            return self._tick_sweep(cmd, dt)
        if self.p_on:
            return self._tick_p(cmd, dt)
        return None

    def _tick_sweep(self, cmd: float, dt: float) -> float | None:
        if not self.force_ok:
            self.status = "スイープ中（足圧不足・待機）"
            return None
        nxt = cmd + self.sweep_dir * SWEEP_SLEW_DPS * dt
        if nxt >= CMD_MAX:
            nxt = CMD_MAX
            self.sweep_dir = -1.0
        elif nxt <= CMD_MIN:
            nxt = CMD_MIN
            self.sweep_dir = 1.0
        nxt = clamp_cmd(nxt)
        self.note_sample(nxt)
        if self.estimated is None:
            self.status = "自動スイープ中  推定 —（ゼロ交差待ち）"
        else:
            self.status = f"自動スイープ中  推定 {self.estimated:.1f}°"
        return nxt

    def _tick_p(self, cmd: float, dt: float) -> float | None:
        if not self.force_ok or self.cop_y is None:
            self.status = "P制御（足圧不足・保持）"
            return None
        neu = self.active_neutral()
        if neu is None:
            self.status = "P制御（ニュートラル未確定）"
            self.p_on = False
            return None
        err = 0.0 - self.cop_y
        target = clamp_cmd(neu + self.sign * self.kp * err)
        max_step = P_SLEW_DPS * dt
        delta = target - cmd
        if delta > max_step:
            delta = max_step
        elif delta < -max_step:
            delta = -max_step
        nxt = clamp_cmd(cmd + delta)
        self.status = f"P制御中  目標 {target:.1f}°"
        return nxt
