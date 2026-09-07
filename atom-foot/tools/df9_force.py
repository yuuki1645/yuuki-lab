"""
DF9-40@2kg の抵抗→力換算。

データシート（Velleman / DF9-40 series）:
  https://cdn.velleman.eu/downloads/25/infosheets/fsr_datasheet.pdf
  - 量程: 0–2kg
  - 無負荷抵抗: >10MΩ
  - 応答点: ≤20g（Rs が 1MΩ を下回った荷重）
  - 試験電圧: 典型 DC 3.3V
  - 参考回路: 固定抵抗 R1（通常 1kΩ〜100kΩ）。本機は 10kΩ。

回路（センサー上側。3V3 は ATOMS3 Lite 表面のピンソケット）:
  3V3 -- Rs --+-- ADC
              |
            R1=10k
              |
             GND
    Vout = 3.3 * R1 / (Rs + R1)
    Rs   = R1 * (3.3 / Vout - 1)

曲線はデータシート Data reference sheet（2kg 列）準拠。参考値のため、
絶対精度が必要なら既測おもりで FORCE_R_TABLE を校正すること。
"""

from __future__ import annotations

import math

VREF = 3.3
R1_OHM = 10000.0
FORCE_MAX_KG = 2.0

# データシートの応答点定義: Rs が 1MΩ を下回ると「応答」開始。
RS_UNLOADED_OHM = 1_000_000.0

# DF9-40@2kg 圧力-抵抗テーブル（force_kg, Rs_ohm）。
FORCE_R_TABLE = [
    (0.20, 11200.0),
    (0.40, 6070.0),
    (0.60, 4310.0),
    (0.80, 3430.0),
    (1.00, 2970.0),
    (1.20, 2670.0),
    (1.40, 2480.0),
    (1.60, 2300.0),
    (1.80, 2190.0),
    (2.00, 2080.0),
]


def clamp(x: float, lo: float, hi: float) -> float:
    """値を [lo, hi] に収める。"""
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def voltage_to_rs(voltage: float) -> float:
    """分圧電圧からセンサー抵抗 Rs[Ω] を求める（回路: センサー上側）。"""
    if voltage < 0.02:
        return 10_000_000.0
    rs = R1_OHM * (VREF / voltage - 1.0)
    if rs < 1.0:
        return 1.0
    return rs


def rs_to_force_kg(rs: float) -> float:
    """センサー抵抗 Rs[Ω] から力[kg]（log-log 区間補間）。"""
    if rs >= RS_UNLOADED_OHM:
        return 0.0

    table = FORCE_R_TABLE

    if rs >= table[0][1]:
        r0 = RS_UNLOADED_OHM
        f1, r1 = table[0]
        if rs >= r0:
            return 0.0
        f0 = 0.005
        t = (math.log(rs) - math.log(r0)) / (math.log(r1) - math.log(r0))
        force = f0 * math.exp(t * (math.log(f1) - math.log(f0)))
        return clamp(force, 0.0, FORCE_MAX_KG)

    if rs <= table[-1][1]:
        return FORCE_MAX_KG

    for i in range(len(table) - 1):
        f1, r1 = table[i]
        f2, r2 = table[i + 1]
        if r1 >= rs >= r2:
            if r1 == r2:
                return f1
            t = (math.log(rs) - math.log(r1)) / (math.log(r2) - math.log(r1))
            log_f = math.log(f1) + t * (math.log(f2) - math.log(f1))
            return clamp(math.exp(log_f), 0.0, FORCE_MAX_KG)

    return 0.0


def voltage_to_force_kg(voltage: float) -> tuple[float, float]:
    """電圧 → Rs → 力[kg] の一括変換。戻り値は (rs_ohm, force_kg)。"""
    rs = voltage_to_rs(voltage)
    return rs, rs_to_force_kg(rs)
