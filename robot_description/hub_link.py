"""Hub のサーボ度と URDF のラジアンを往復させる共通定義。

Isaac 同梱 Python からも、Hub 用の橋からも import する。
flask や Isaac のモジュールは import しない。
"""

from __future__ import annotations

import math

# Hub の指令バー。135° が直立（URDF の 0 rad）。
NEUTRAL_DEG = 135.0

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


def joint_names() -> list[str]:
    """URDF の revolute 関節名。チャンネル番号と同じ順。"""
    return [name for name, _label in JOINTS]


def deg_to_rad(deg: float) -> float:
    """サーボ度 → 関節ラジアン。135° が 0。正は URDF の正方向（開脚・後ろ曲げ）。"""
    return (float(deg) - NEUTRAL_DEG) * math.pi / 180.0


def rad_to_deg(rad: float) -> float:
    """関節ラジアン → サーボ度。画面の補正角に載せる。"""
    return NEUTRAL_DEG + float(rad) * 180.0 / math.pi


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


if __name__ == "__main__":
    _check()
    print("hub_link ok", JOINT_COUNT, "joints, neutral", NEUTRAL_DEG)
