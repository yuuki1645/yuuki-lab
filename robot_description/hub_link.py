"""Hub のサーボ度と URDF のラジアンを往復させる共通定義。

Isaac 同梱 Python からも、Hub 用の橋からも import する。
flask や Isaac のモジュールは import しない。

中立、プラスの向き、実機の窓の文章は docs/joint_angles.md。
ここが持つのは 135° と 0°、チャンネル順、度とラジアンの変換だけ。
"""

from __future__ import annotations

import math

# RDS51150 の指令バー。135° が直立（URDF の 0 rad）。
NEUTRAL_DEG = 135.0
# SM105BL（ひざ・かかとピッチ）。真下 0° が直立で、URDF の 0 rad と一致する。
SM105_NEUTRAL_DEG = 0.0

# Socket.IO（Hub）と、Isaac プロセスとの TCP。実機の :8794 とは分ける。
HUB_PORT = 8795
ISAAC_TCP_PORT = 8796
ISAAC_TCP_HOST = "127.0.0.1"

# 画面の行は上からこの順。ch 0〜4 が右脚（実機ファームの論理関節と同じ）。
# ch 5〜9 は左脚。実機ファームは 8 枠しか無く、左脚はまだ無いので画面では非アクティブ。
JOINTS: tuple[tuple[str, str], ...] = (
    ("right_hip_roll", "右 股ロール"),
    ("right_hip_pitch", "右 股ピッチ"),
    ("right_knee_pitch", "右 ひざ"),
    ("right_ankle_pitch", "右 かかとピッチ"),
    ("right_ankle_roll", "右 かかとロール"),
    ("left_hip_roll", "左 股ロール"),
    ("left_hip_pitch", "左 股ピッチ"),
    ("left_knee_pitch", "左 ひざ"),
    ("left_ankle_pitch", "左 かかとピッチ"),
    ("left_ankle_roll", "左 かかとロール"),
)

JOINT_COUNT = len(JOINTS)
RIGHT_COUNT = 5
# 右ひざ 2、右かかとピッチ 3、左ひざ 7、左かかとピッチ 8。画面の isSm105Channel と同じ。
SM105_CHANNELS = frozenset({2, 3, 7, 8})


def joint_names() -> list[str]:
    """URDF の revolute 関節名。チャンネル番号と同じ順。"""
    return [name for name, _label in JOINTS]


def is_sm105(ch: int) -> bool:
    """ひざピッチとかかとピッチ。PWM ではなく、真下 0° が基準。"""
    return ch in SM105_CHANNELS


def neutral_deg(ch: int) -> float:
    """直立の指令角。RDS は 135°、SM105BL は真下 0°。"""
    return SM105_NEUTRAL_DEG if is_sm105(ch) else NEUTRAL_DEG


def deg_to_rad(deg: float) -> float:
    """RDS のサーボ度 → 関節ラジアン。135° が 0。正は URDF の正方向。"""
    return (float(deg) - NEUTRAL_DEG) * math.pi / 180.0


def rad_to_deg(rad: float) -> float:
    """関節ラジアン → RDS のサーボ度。135° が直立。"""
    return NEUTRAL_DEG + float(rad) * 180.0 / math.pi


def joint_deg_to_rad(ch: int, deg: float) -> float:
    """画面の度を、その関節の URDF ラジアンへ。

    SM105BL は 0° がまっすぐ（URDF の 0）。RDS の 135° オフセットは掛けない。
    """
    if is_sm105(ch):
        return float(deg) * math.pi / 180.0
    return deg_to_rad(deg)


def joint_rad_to_deg(ch: int, rad: float) -> float:
    """URDF ラジアンを、その関節の画面の度へ。"""
    if is_sm105(ch):
        return float(rad) * 180.0 / math.pi
    return rad_to_deg(rad)


def _check() -> None:
    if abs(deg_to_rad(NEUTRAL_DEG)) > 1e-12:
        raise RuntimeError("135° が 0 rad になっていません")
    if abs(rad_to_deg(0.0) - NEUTRAL_DEG) > 1e-9:
        raise RuntimeError("0 rad が 135° になっていません")
    back = rad_to_deg(deg_to_rad(170.0))
    if abs(back - 170.0) > 1e-6:
        raise RuntimeError("度とラジアンの往復が閉じていません")
    if JOINT_COUNT != 10 or JOINTS[0][0] != "right_hip_roll":
        raise RuntimeError("チャンネル順が右脚 5 + 左脚 5 ではありません")
    if SM105_CHANNELS != frozenset({2, 3, 7, 8}):
        raise RuntimeError("SM105BL のチャンネルがひざ・かかとピッチではありません")
    for ch in range(JOINT_COUNT):
        neutral = neutral_deg(ch)
        if abs(joint_deg_to_rad(ch, neutral)) > 1e-12:
            raise RuntimeError(f"ch{ch} の直立が 0 rad になっていません")
        back_j = joint_rad_to_deg(ch, joint_deg_to_rad(ch, neutral + 20.0))
        if abs(back_j - (neutral + 20.0)) > 1e-6:
            raise RuntimeError(f"ch{ch} の度とラジアンの往復が閉じていません")
    # ひざを 0° のまま RDS の式に通すと -135° になり、URDF の端に張り付く。
    if abs(joint_deg_to_rad(2, 0.0)) > 1e-12:
        raise RuntimeError("ひざ 0° が URDF の 0 になっていません")
    if abs(deg_to_rad(0.0) - (-135.0 * math.pi / 180.0)) > 1e-9:
        raise RuntimeError("RDS の 0° が -135° オフセットになっていません")


if __name__ == "__main__":
    _check()
    print("hub_link ok", JOINT_COUNT, "joints, neutral", NEUTRAL_DEG)
