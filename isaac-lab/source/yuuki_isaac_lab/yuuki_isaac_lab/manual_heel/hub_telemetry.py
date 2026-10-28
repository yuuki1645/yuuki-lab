# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""手動の踵操作を、robotics-hub の実機テレメトリへ出す。

歩行再生と同じ橋（``robot_description/isaac_hub_bridge.py`` の 127.0.0.1:8796）へ、
JSON を 1 行ずつ書く。flask は入れない。橋が無いあいだは約 1 秒に 1 回だけつなぎ直し、
シミュレーションは止めない。

画面の関節順は右脚 5、左脚 5。ここでの並び（左が先）のまま送ると欄がずれる。
「指令」は逆運動学の目標角、「補正」はシミュレータが今保持している関節角。
電圧・電流は無いので送らない。スティックは歩行用の形で送らない。
``drive`` が ``heel`` のとき、画面は手動操作だと分かる表示にする。
"""

from __future__ import annotations

import importlib.util
import json
import socket
import time
from pathlib import Path

import torch

import isaaclab.utils.math as math_utils
from isaaclab.assets import Articulation
from isaaclab.sensors import ContactSensor

# 歩行タスクのパッケージ初期化（Gym 登録）は引かない。式だけを読む。
_SOLE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tasks"
    / "manager_based"
    / "biped_walk"
    / "mdp"
    / "sole_corners.py"
)
_sole_spec = importlib.util.spec_from_file_location("yuuki_sole_corners", _SOLE_PATH)
if _sole_spec is None or _sole_spec.loader is None:
    raise ImportError(f"四隅の分配式がありません: {_SOLE_PATH}")
_sole_module = importlib.util.module_from_spec(_sole_spec)
_sole_spec.loader.exec_module(_sole_module)
corner_newtons = _sole_module.corner_newtons

# hub_link.ISAAC_TCP と同じ。実機の Socket.IO :8794 でも、Hub 向け :8795 でもない。
_HOST = "127.0.0.1"
_PORT = 8796
# 脚タブは 20 Hz で足りる。物理は 120 Hz なので、毎ステップは送らない。
_SEND_PERIOD_S = 0.05
_RETRY_PERIOD_S = 1.0

# hub_link.JOINTS と同じ順。右が先。
_HUB_JOINTS = (
    "right_hip_roll",
    "right_hip_pitch",
    "right_knee_pitch",
    "right_ankle_pitch",
    "right_ankle_roll",
    "left_hip_roll",
    "left_hip_pitch",
    "left_knee_pitch",
    "left_ankle_pitch",
    "left_ankle_roll",
)

# sole_pressure.py / feet.py と同じ。各隅は 2 kg で頭打ち、0.02 kg 未満は 0。
_GRAVITY_MPS2 = 9.81
_DF9_MAX_KG = 2.0
_DEADZONE_KG = 0.02
# 足板 0.300 m × 0.170 m の半寸。
_PLATE_HALF_X_M = 0.150
_PLATE_HALF_Y_M = 0.085
# 画面の四隅。つま先が top、左が left。左右でミラーしない。
_CORNER_KEYS = ("top_left", "top_right", "bottom_left", "bottom_right")


class HubTelemetry:
    """1 体の手動操作を橋へ送る。橋が落ちていても操作は続ける。"""

    def __init__(self) -> None:
        self._sock: socket.socket | None = None
        self._next_try = 0.0
        self._next_send = 0.0
        self._seq = 0
        self._said_down = False
        self._said_up = False

    def publish(
        self,
        robot: Articulation,
        joint_index: dict[str, int],
        left_q: object,
        right_q: object,
        contact: ContactSensor | None,
        sim_time: float,
    ) -> None:
        """今の目標角・実測角・足裏を 1 行送る。失敗しても操作は続ける。"""
        try:
            now = time.time()
            self._ensure(now)
            if self._sock is None:
                return
            self._drain()
            if now < self._next_send:
                return
            self._next_send = now + _SEND_PERIOD_S
            self._seq += 1
            measured, commanded = _joint_radians(robot, joint_index, left_q, right_q)
            left_kg, right_kg = _foot_kg(contact, robot)
            payload = {
                "op": "joints",
                "rad": measured,
                "cmd_rad": commanded,
                "sim_time": float(sim_time),
                # 歩行の左スティックとは別。画面が「方策への前進」と読まないための印。
                "drive": "heel",
                "foot": _foot_sample(right_kg, self._seq),
                "foot_left": _foot_sample(left_kg, self._seq),
            }
            data = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
            self._sock.sendall(data)
        except Exception as exc:
            self._close()
            if not self._said_down:
                self._said_down = True
                print(f"hub telemetry send failed: {exc}", flush=True)

    def close(self) -> None:
        """操作終了時に、橋への接続を切る。"""
        self._close()

    def _ensure(self, now: float) -> None:
        """未接続なら、間隔を空けて 8796 へつなぐ。"""
        if self._sock is not None:
            return
        if now < self._next_try:
            return
        self._next_try = now + _RETRY_PERIOD_S
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.05)
        try:
            sock.connect((_HOST, _PORT))
        except OSError:
            sock.close()
            if not self._said_down:
                self._said_down = True
                print(
                    "hub telemetry: isaac_hub_bridge.py (127.0.0.1:8796) が無いので、画面には出しません。",
                    flush=True,
                )
            return
        sock.setblocking(False)
        self._sock = sock
        self._said_down = False
        if not self._said_up:
            self._said_up = True
            print("hub telemetry: connected 127.0.0.1:8796", flush=True)

    def _drain(self) -> None:
        """橋が返してくる目標角を捨てる。手動操作では関節に書かない。"""
        sock = self._sock
        if sock is None:
            return
        try:
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    self._close()
                    return
        except (BlockingIOError, TimeoutError):
            return
        except OSError:
            self._close()

    def _close(self) -> None:
        sock = self._sock
        self._sock = None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass


def _joint_radians(
    robot: Articulation,
    joint_index: dict[str, int],
    left_q: object,
    right_q: object,
) -> tuple[list[float], list[float]]:
    """実測角と目標角。どちらも画面の順（右 5、左 5）[rad]。"""
    positions = robot.data.joint_pos[0].detach().cpu().tolist()
    measured = [float(positions[joint_index[name]]) for name in _HUB_JOINTS]
    target = _targets_by_name(left_q, right_q)
    commanded = [float(target[name]) for name in _HUB_JOINTS]
    return measured, commanded


def _targets_by_name(left_q: object, right_q: object) -> dict[str, float]:
    """逆運動学の 5 角を、関節名へ戻す。"""
    left = [float(v) for v in left_q]  # type: ignore[union-attr]
    right = [float(v) for v in right_q]  # type: ignore[union-attr]
    names = (
        "left_hip_roll",
        "left_hip_pitch",
        "left_knee_pitch",
        "left_ankle_pitch",
        "left_ankle_roll",
        "right_hip_roll",
        "right_hip_pitch",
        "right_knee_pitch",
        "right_ankle_pitch",
        "right_ankle_roll",
    )
    angles = (*left, *right)
    return {name: angle for name, angle in zip(names, angles, strict=True)}


def _foot_kg(contact: ContactSensor | None, robot: Articulation) -> tuple[list[float] | None, list[float] | None]:
    """左右 4 隅の kg。センサがまだ無いステップは None。"""
    if contact is None:
        return None, None
    try:
        data = contact.data
        if data.force_matrix_w is None or data.contact_pos_w is None:
            return None, None
        names = list(contact.body_names)
        left_i = names.index("left_foot")
        right_i = names.index("right_foot")
        sole_names = list(robot.body_names)
        left_sole = sole_names.index("left_sole")
        right_sole = sole_names.index("right_sole")
        foot_ids = [left_i, right_i]
        sole_ids = [left_sole, right_sole]
        force_w = data.force_matrix_w[:, foot_ids, :, :]
        point_w = data.contact_pos_w[:, foot_ids, :, :]
        sole_pos = robot.data.body_pos_w[:, sole_ids, :]
        sole_quat = robot.data.body_quat_w[:, sole_ids, :]
        total, x_cop, y_cop = _sole_load(force_w, point_w, sole_pos, sole_quat)
        left = corner_newtons(total[:, 0], x_cop[:, 0], y_cop[:, 0], _PLATE_HALF_X_M, _PLATE_HALF_Y_M)
        right = corner_newtons(total[:, 1], x_cop[:, 1], y_cop[:, 1], _PLATE_HALF_X_M, _PLATE_HALF_Y_M)
        return _kg_list(_to_kg(left)), _kg_list(_to_kg(right))
    except (ValueError, RuntimeError, AttributeError, IndexError, TypeError):
        return None, None


def _kg_list(force_kg: torch.Tensor) -> list[float]:
    """環境 0 の 4 隅を、JSON に書ける float にする。"""
    return [float(v) for v in force_kg[0].detach().cpu().tolist()]


def _sole_load(
    force_w: torch.Tensor,
    point_w: torch.Tensor,
    sole_pos: torch.Tensor,
    sole_quat: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """ワールドの接触を足裏座標へ移し、上向き成分の合計と圧力中心を返す。

    歩行タスクの ``feet._sole_load`` と同じ式。ここは Manager 環境を持たないので写している。
    """
    count_env, count_foot, count_filter, _ = force_w.shape
    flat = count_env * count_foot
    quat = sole_quat.reshape(flat, 4).unsqueeze(1).expand(flat, count_filter, 4).reshape(-1, 4)
    origin = sole_pos.reshape(flat, 3).unsqueeze(1).expand(flat, count_filter, 3).reshape(-1, 3)
    force_local = math_utils.quat_apply_inverse(quat, force_w.reshape(-1, 3))
    point_local = math_utils.quat_apply_inverse(quat, point_w.reshape(-1, 3) - origin)
    # 足裏の +z が上。床が板を押す成分だけを圧縮とする。
    normal = force_local[:, 2].clamp(min=0.0).reshape(count_env, count_foot, count_filter)
    xy = point_local[:, 0:2].reshape(count_env, count_foot, count_filter, 2)
    total = normal.sum(dim=-1)
    weight = normal.unsqueeze(-1)
    cop = (xy * weight).sum(dim=2) / total.clamp(min=1.0e-6).unsqueeze(-1)
    return total, cop[..., 0], cop[..., 1]


def _to_kg(force_n: torch.Tensor) -> torch.Tensor:
    """ニュートンを kg 表示にし、応答点未満は 0、満量は 2 kg で止める。"""
    kg = force_n.clamp(min=0.0) / _GRAVITY_MPS2
    kg = torch.where(kg < _DEADZONE_KG, torch.zeros_like(kg), kg)
    return kg.clamp(max=_DF9_MAX_KG)


def _foot_sample(kg4: list[float] | None, seq: int) -> dict:
    """Hub の足裏 1 枚。四隅が取れないときは ok を false にする。"""
    ok = kg4 is not None and len(kg4) == 4
    values = kg4 if ok else [0.0, 0.0, 0.0, 0.0]
    corners: dict[str, dict] = {}
    total = 0.0
    for key, kg in zip(_CORNER_KEYS, values, strict=True):
        total += kg
        corners[key] = {
            "force_kg": kg,
            "force_pct": 100.0 * kg / _DF9_MAX_KG,
        }
    return {
        "ok": ok,
        "seq": int(seq),
        "mask": 0b1111 if ok else 0,
        "force_kg": total,
        "corners": corners,
    }
