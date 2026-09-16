"""
PC 側のサーボ校正掃引（ライブラリ。直接起動しない）。

lab_debug が 40→230→40° を Joint 指令で掃引し、AS5600 unwrap と組んでマップを作る。
ボードの Cal コマンド（rt_usb_log の `cal 0`）とは別経路。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .lab_const import (
    CAL_MAX_DEG,
    CAL_MIN_DEG,
    CAL_MIN_MAP_POINTS,
    CAL_MIN_UNWRAP_SPAN,
    CAL_STEP_DEG,
)


@dataclass
class PcCalSweep:
    """1 軸の掃引状態。tick は LabApp がテレメトリを見て進める。"""

    port: str
    ch: int
    cmds: list[float]
    index: int = 0
    wait_until: float = 0.0
    seq_at_cmd: int | None = None
    samples: list[tuple[float, float]] = field(default_factory=list)
    prev_out: bool = False
    abort: bool = False


def cal_sweep_cmds(
    lo: float = CAL_MIN_DEG,
    hi: float = CAL_MAX_DEG,
    step: float = CAL_STEP_DEG,
) -> list[float]:
    """往路 lo→hi、復路 hi-step→lo の 1° 指令列。"""
    lo_i = int(round(lo))
    hi_i = int(round(hi))
    st = max(1, int(round(step)))
    up = [float(d) for d in range(lo_i, hi_i + 1, st)]
    down = [float(d) for d in range(hi_i - st, lo_i - 1, -st)]
    return up + down


def clamp_cal_deg(deg: float) -> float:
    """校正用 PWM。40〜230° に収める（ライブ実験の狭いクランプは掛けない）。"""
    if deg < CAL_MIN_DEG:
        return CAL_MIN_DEG
    if deg > CAL_MAX_DEG:
        return CAL_MAX_DEG
    return deg


def build_cal_map_points(samples: list[tuple[float, float]]) -> list[tuple[float, float]] | None:
    """(unwrap, servo_cmd) を整数°ごとに平均し、AS5600 昇順のマップにする。"""
    bins: dict[int, list[float]] = {}
    for unw, cmd in samples:
        idx = int(round(cmd))
        if idx < int(CAL_MIN_DEG) or idx > int(CAL_MAX_DEG):
            continue
        bins.setdefault(idx, []).append(unw)
    points: list[tuple[float, float]] = []
    for deg in range(int(CAL_MIN_DEG), int(CAL_MAX_DEG) + 1):
        xs = bins.get(deg)
        if not xs:
            continue
        points.append((sum(xs) / len(xs), float(deg)))
    points.sort(key=lambda p: p[0])
    if len(points) < CAL_MIN_MAP_POINTS:
        return None
    span = points[-1][0] - points[0][0]
    if span < CAL_MIN_UNWRAP_SPAN:
        return None
    return points
