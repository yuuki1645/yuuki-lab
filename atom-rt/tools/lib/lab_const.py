"""
lab_debug の定数（ライブラリ。直接起動しない）。

色・軸数・WAV パス・校正範囲。GUI も USB セッションもここを読む。
パスは本ファイルが tools/lib/ にある前提（atom-rt は 2 つ上）。
"""

from __future__ import annotations

from pathlib import Path

from . import rt_usb_proto as proto

# ---------------------------------------------------------------------------
# 見た目
# ---------------------------------------------------------------------------
BG = "#0e1318"
CARD = "#17202a"
CARD_HI = "#1f2a36"
TEXT = "#e8eef4"
MUTED = "#8b9bb0"
GOOD = "#10ac84"
WARN = "#feca57"
BAD = "#ee5253"
CMD_COLOR = "#ff9f43"
AS_COLOR = "#54a0ff"
UNWRAP_COLOR = "#1dd1a1"
VOLT_COLOR = "#feca57"
AMP_COLOR = "#00d2d3"
WATT_COLOR = "#ff6b81"
PERIOD_COLOR = "#f5f6fa"
CORR_COLOR = "#ff4757"  # 補正角（マップ適用後）
FLASH = "#a29bfe"
# 頻繁に更新する数値用。比例フォントだと桁が変わるたびにラベル幅が揺れる
MONO = ("Consolas", 12, "bold")
MONO_MD = ("Consolas", 14, "bold")
MONO_LG = ("Consolas", 16, "bold")
# 固定文字幅。" 1234.56 °" が収まるサイズ（Tk Label の width は文字数）
METRIC_VALUE_CHARS = 11

BAUD = 115200
# 論理関節数（ファーム kSnapJoints / usb_proto と揃える）
JOINTS = 8
# Hub / Tk イベントログのリング。追記配信なので 5000 でも全文転送にはしない
EVENTS_MAX = 5000
# 同時に出す関節パネル数。各パネルで 0〜7 を選ぶ
JOINT_PANELS = 2
INA_CHS = proto.INA_CHS
INA_DEFAULT_ASSIGNED = proto.INA_DEFAULT_ASSIGNED
# 電源グラフの系列色（関節 0〜7）
INA_PLOT_COLORS = (
    "#feca57",
    "#e67e22",
    "#00d2d3",
    "#5f27cd",
    "#10ac84",
    "#ee5253",
    "#54a0ff",
    "#c8d6e5",
)
HISTORY_SEC = 20.0
PLOT_INTERVAL_S = 0.12
TARGET_MS = 50.0
# ランダム動作の既定（atoms3 robot / servo-cal に近い）
RAND_MIN_DEG = 40.0
RAND_MAX_DEG = 230.0
RAND_HOLD_MIN_S = 0.7
RAND_HOLD_MAX_S = 1.4
RAND_MIN_JUMP_DEG = 25.0
# サーボ校正（PC が PWM を出す）。COP ライブの 100〜170 クランプは掛けない
CAL_MIN_DEG = 40.0
CAL_MAX_DEG = 230.0
CAL_STEP_DEG = 1.0
CAL_SETTLE_S = 0.18
CAL_FIRST_MOVE_S = 0.80
CAL_FRAME_WAIT_S = 3.0
CAL_MIN_MAP_POINTS = 80
CAL_MIN_UNWRAP_SPAN = 40.0

# tools/lib/ → tools/ → atom-rt/
_LIB_DIR = Path(__file__).resolve().parent
_TOOLS_DIR = _LIB_DIR.parent
REPO_ROOT = _TOOLS_DIR.parent
# COM の表示名。tools/ 直下（gitignore）。lib/ には置かない。
NODES_PATH = _TOOLS_DIR / "lab_nodes.json"
# 右脚制御の起動アナウンス。将来は ATOMS3R AI Chatbot 側で再生する想定
BOOT_WAV = REPO_ROOT / "audio" / "right_leg_boot.wav"
# 起動後の健全チェック通過アナウンス
GREEN_WAV = REPO_ROOT / "audio" / "system_all_green.wav"
# 起動音のあとに緑音を重ねないための最短待ち（秒）
BOOT_SOUND_GAP_S = 2.8
# 緑判定に使う起動直後のテレメトリ枚数
GREEN_FRAME_NEED = 10

MAG_LABEL = {
    0: "OK",
    1: "磁石なし",
    2: "弱い",
    3: "強い",
    4: "I2C",
    255: "—",
}


def mag_color(code: int) -> str:
    """AS5600 磁石 STATUS を GUI 色にする。"""
    if code == 0:
        return GOOD
    if code in (1, 4):
        return BAD
    if code in (2, 3):
        return WARN
    return MUTED


def at(xs: list, i: int, default=None):
    """範囲外なら default。テレメトリが短いとき関節 2〜7 を選んでも壊れないようにする。"""
    if 0 <= i < len(xs):
        return xs[i]
    return default


def fmt(v: float | None, unit: str) -> str:
    """数値を固定桁で整形する。等幅フォントと組み合わせて表示位置を固定する。"""
    if v is None:
        return f"— {unit}"
    # 整数部最大4桁 + 小数2桁。unwrap が 360° を超えても幅が変わらない
    return f"{v:8.2f} {unit}"


def fmt_ms(us: int) -> str:
    """マイクロ秒を固定桁のミリ秒表示にする（符号付きジッタも幅が変わらない）。"""
    return f"{us / 1000.0:7.1f} ms"
