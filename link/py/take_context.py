"""
自動記録の take に置く context.json を作る。

別リポジトリがこのフォルダだけを読んで、関節の並び、単位、方策の出力の
意味を復元できるようにする。数値の正本は腰の walk_policy.cpp と
usb_frame.hpp で、ここは記録を開いた時点の写しである。定数を変えたら
両方を同じ変更で直す。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# このファイルは importlib で直接読まれることがある。兄弟モジュールを名前で読む。
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from policy_trace import DIMS
from rt_usb_proto import JOINT_FLAG_JUMP, JOINT_FLAG_MISSING, JOINT_FLAG_SHAKE, JOINT_FLAG_VALID
from rt_usb_proto import POLICY_REASON, POLICY_SAFETY

# ネットの生出力に掛ける係数。直立からの目標 [rad] = action * ACTION_SCALE。
# 包絡と速度制限の前の値。walk_policy.cpp の kActionScale。
ACTION_SCALE = 0.25

# 前進 0 の包絡。直立からの度。方策の関節順。
# walk_policy.cpp の kEnvelope* と同じ。画面の 135° は、ここでは 0。
# 股とかかとロールは ±20°。ひざは 0°〜+40°。かかとピッチは −20°〜+30°。
_ENVELOPE_MIN_DEG = (-20.0, -20.0, -20.0, -20.0, 0.0, 0.0, -20.0, -20.0, -20.0, -20.0)
_ENVELOPE_MAX_DEG = (20.0, 20.0, 20.0, 20.0, 40.0, 40.0, 30.0, 30.0, 20.0, 20.0)

# 画面の論理軸。sensors の配列はこの順。右が 0〜4、左が 5〜9。
# upright_deg は方策の 0 rad。RDS51150 は 135、SM105BL（ひざ、かかとピッチ）は 0。
_FIRMWARE_JOINTS: tuple[dict[str, Any], ...] = (
    {"index": 0, "name": "右股ロール", "side": "right", "joint": "hip_roll", "servo": "RDS51150", "upright_deg": 135.0, "plus": "外側"},
    {"index": 1, "name": "右股ピッチ", "side": "right", "joint": "hip_pitch", "servo": "RDS51150", "upright_deg": 135.0, "plus": "前"},
    {"index": 2, "name": "右ひざ", "side": "right", "joint": "knee", "servo": "SM105BL", "upright_deg": 0.0, "plus": "後ろ"},
    {"index": 3, "name": "右かかとピッチ", "side": "right", "joint": "ankle_pitch", "servo": "SM105BL", "upright_deg": 0.0, "plus": "つま先を上げる"},
    {"index": 4, "name": "右かかとロール", "side": "right", "joint": "ankle_roll", "servo": "RDS51150", "upright_deg": 135.0, "plus": "内側が下がる"},
    {"index": 5, "name": "左股ロール", "side": "left", "joint": "hip_roll", "servo": "RDS51150", "upright_deg": 135.0, "plus": "外側"},
    {"index": 6, "name": "左股ピッチ", "side": "left", "joint": "hip_pitch", "servo": "RDS51150", "upright_deg": 135.0, "plus": "前"},
    {"index": 7, "name": "左ひざ", "side": "left", "joint": "knee", "servo": "SM105BL", "upright_deg": 0.0, "plus": "後ろ"},
    {"index": 8, "name": "左かかとピッチ", "side": "left", "joint": "ankle_pitch", "servo": "SM105BL", "upright_deg": 0.0, "plus": "つま先を上げる"},
    {"index": 9, "name": "左かかとロール", "side": "left", "joint": "ankle_roll", "servo": "RDS51150", "upright_deg": 135.0, "plus": "内側が下がる"},
)

# 方策の関節 0..9 が指す画面の論理軸。obs、action、cmd_rad はこの順。
# walk_policy.cpp の kFwForPolicy。
_POLICY_FIRMWARE_INDEX = (5, 0, 6, 1, 7, 2, 8, 3, 9, 4)


def action_rad(action: object) -> list[float | None] | None:
    """生出力を、直立からのラジアンにする。欠測と非数は null。

    これは頭打ちの前の目標である。サーボへ出た角度は cmd_rad を見る。
    """
    if not isinstance(action, list):
        return None
    scaled: list[float | None] = []
    for item in action:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            scaled.append(None)
            continue
        number = float(item)
        if number != number or number in (float("inf"), float("-inf")):
            scaled.append(None)
            continue
        scaled.append(number * ACTION_SCALE)
    return scaled


def build_context() -> dict[str, Any]:
    """take を開いた瞬間に書く契約。あとからファームを変えても、このファイルは残る。"""
    firmware = [dict(joint) for joint in _FIRMWARE_JOINTS]
    policy_joints = []
    for policy_index, firmware_index in enumerate(_POLICY_FIRMWARE_INDEX):
        src = firmware[firmware_index]
        policy_joints.append(
            {
                "index": policy_index,
                "firmware_index": firmware_index,
                "name": src["name"],
                "side": src["side"],
                "joint": src["joint"],
                "servo": src["servo"],
                "upright_deg": src["upright_deg"],
                "plus": src["plus"],
            }
        )
    return {
        "format_id": "core_take_v2",
        "schema": "schema.md",
        "project": {
            "name": "yuuki-lab",
            "robot": "等身大の二足。脚と腰のカゴ。学習は YuukiLab-BipedWalk-v0。",
            "learn_run": "2026-11-27_14-01-29_stand_half",
            "checkpoint": "model_2200",
            "weights": "core-rt/src/policy_weights.hpp",
            "inference": "腰の CoreS3。入力 38、隠れ 128 と 64、ELU、出力 10。出すのは平均で、ガウス分布からは引かない。",
        },
        "time": {
            "clock": "sensors と policy の t は、サブ PC が受け取った UNIX 秒。ボードの時計ではない。",
            "align": "sensors の seq と policy の seq は別のカウンタ。突き合わせは t で行う。",
        },
        "body_frame": {
            "x": "前が正",
            "y": "左が正",
            "z": "上が正",
            "gravity": "方策が見る重力。直立なら z が約 -1 で、x と y は 0 に近い。",
        },
        "firmware_joints": firmware,
        "policy_joints": policy_joints,
        "policy": {
            "obs_count": 38,
            "action_scale": ACTION_SCALE,
            "action": "ネットの生出力。直立からの目標 [rad] は action_rad = action * action_scale。頭打ちと速度制限の前。ネットを回していない周期は null。",
            "action_rad": "action に action_scale を掛けた値。方策の関節順。直立が 0 rad。",
            "cmd_rad": "サーボへ実際に出した目標。直立が 0 rad。方策の関節順。前進 0 のときは policy.envelope の中に収め、サーボの最高速度以内に抑えたあと。",
            "envelope": {
                "unit": "直立からの度。cmd_rad と同じ関節順。前進 0 の頭打ち。",
                "min_deg": list(_ENVELOPE_MIN_DEG),
                "max_deg": list(_ENVELOPE_MAX_DEG),
            },
            "obs": [
                {
                    "index": index,
                    "key": dim["key"],
                    "label": dim["label"],
                    "group": dim["group"],
                }
                for index, dim in enumerate(DIMS)
            ],
        },
        "enums": {
            "reason": {str(number): text for number, text in sorted(POLICY_REASON.items())},
            "safety": {
                "0": "なし",
                "1": POLICY_SAFETY.get(1, "速度制限"),
                "2": POLICY_SAFETY.get(2, "直立へ戻している"),
                "3": POLICY_SAFETY.get(3, "目標を固定"),
            },
            "joint_flag": {
                str(JOINT_FLAG_VALID): "有効",
                str(JOINT_FLAG_MISSING): "欠測",
                str(JOINT_FLAG_JUMP): "飛び",
                str(JOINT_FLAG_SHAKE): "揺れ",
            },
        },
    }
