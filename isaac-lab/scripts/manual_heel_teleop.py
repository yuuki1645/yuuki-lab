# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""ゲームパッドで、腰基準の左右の踵を Isaac Sim 上で動かす。

強化学習の歩行環境とは別のスクリプト。方策は使わない。
機体は robot_description の両脚（バランス棒なし）。接続されている XInput パッド
（Logicool を Xbox 360 Controller として認識したもの）を読み、スティックの速度を
踵目標へ積算してから逆運動学で関節角にする。倒し量は二乗するので、少しの倒しは遅く、
倒し切りだけが最高速になる。

起動例（isaac-lab ディレクトリ、env_isaaclab）::

    python scripts/manual_heel_teleop.py

操作:
    左スティック  左踵を腰の XY で動かす。奥が前、右がロボットの右。
    右スティック  右踵。同じ向き。
    L / R         肩のバンパー。押しているあいだ、その足を腰の天井側へ。
    ZL / ZR       肩のトリガー。引いているあいだ、その足を腰の床側へ。
    スティックやボタンを戻しても、そこまでの踵位置は保持する。

``robot_description/isaac_hub_bridge.py`` が 127.0.0.1:8796 で待っていれば、
目標角・今の関節角・足裏を robotics-hub の実機テレメトリへ出す。橋が無くても操作は続く。
"""

from __future__ import annotations

import argparse
import traceback

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Manual heel teleop in the waist frame.")
parser.add_argument("--xy-speed", type=float, default=0.30, help="スティック倒し切りの踵の速さ [m/s]。")
parser.add_argument("--z-speed", type=float, default=0.20, help="肩ボタンを押し切ったときの高さの速さ [m/s]。")
parser.add_argument("--steps", type=int, default=0, help="0 ならウィンドウを閉じるまで。正ならその物理ステップで終了。")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import numpy as np
import torch

import isaaclab.sim as sim_utils
from isaaclab.assets import Articulation
from isaaclab.markers import VisualizationMarkers, VisualizationMarkersCfg
from isaaclab.sensors import ContactSensor, ContactSensorCfg
from isaaclab.sim import SimulationContext
from isaaclab.utils.math import quat_apply, quat_apply_inverse

from yuuki_isaac_lab.assets.robots.yuuki_legs import YUUKI_LEGS_CFG
from yuuki_isaac_lab.manual_heel.gamepad_heel import HeelGamepad
from yuuki_isaac_lab.manual_heel.hub_telemetry import HubTelemetry
from yuuki_isaac_lab.manual_heel.leg_ik import (
    ROLL_SIGN_LEFT,
    ROLL_SIGN_RIGHT,
    Y_HIP_LEFT,
    Y_HIP_RIGHT,
    fk_heel,
    step_heel_target,
)

# 片脚の関節名。逆運動学の並びと一致させる。
_LEFT_JOINTS = (
    "left_hip_roll",
    "left_hip_pitch",
    "left_knee_pitch",
    "left_ankle_pitch",
    "left_ankle_roll",
)
_RIGHT_JOINTS = (
    "right_hip_roll",
    "right_hip_pitch",
    "right_knee_pitch",
    "right_ankle_pitch",
    "right_ankle_roll",
)
# 足裏中心から踵まで。板の長さ 0.30 m の後ろ半分。下面の高さが足裏中心と同じ。
_HEEL_IN_SOLE = (-0.15, 0.0, 0.0)


def main() -> None:
    """地面の上に両脚を出し、パッドの速度を腰基準の踵目標へ積算する。"""
    sim_cfg = sim_utils.SimulationCfg(device=args_cli.device, dt=1.0 / 120.0)
    sim = SimulationContext(sim_cfg)
    # 前方やや右から、足と腰が見える位置。
    sim.set_camera_view(eye=[1.35, -1.15, 0.72], target=[0.0, 0.0, 0.32])
    robot, contact = _design_scene()
    left_marker, right_marker = _target_markers()
    sim.reset()

    # 立位を明示してからバッファを埋める。reset 直後は関節状態が空のことがある。
    root_state = robot.data.default_root_state.clone()
    robot.write_root_pose_to_sim(root_state[:, :7])
    robot.write_root_velocity_to_sim(root_state[:, 7:])
    joint_pos = robot.data.default_joint_pos.clone()
    joint_vel = torch.zeros_like(joint_pos)
    robot.write_joint_state_to_sim(joint_pos, joint_vel)
    robot.set_joint_position_target(joint_pos)
    robot.set_joint_velocity_target(joint_vel)
    robot.write_data_to_sim()
    sim.step()
    robot.update(sim.get_physics_dt())

    joint_index = {name: int(robot.find_joints(name)[0][0]) for name in (*_LEFT_JOINTS, *_RIGHT_JOINTS)}
    # カゴ底の中心が腰の原点。固定リンクの足裏は、USD でもリンクとして残してある。
    waist_id = int(robot.find_bodies("basket")[0][0])
    left_sole_id = int(robot.find_bodies("left_sole")[0][0])
    right_sole_id = int(robot.find_bodies("right_sole")[0][0])

    # 出現姿勢（少し開いた足裏平行）を、その順運動学の踵として保持する。
    # 測定した沈みは目標に取り込まない。
    left_q = _leg_angles(robot, joint_index, _LEFT_JOINTS)
    right_q = _leg_angles(robot, joint_index, _RIGHT_JOINTS)
    left_target, _ = fk_heel(left_q, Y_HIP_LEFT, ROLL_SIGN_LEFT)
    right_target, _ = fk_heel(right_q, Y_HIP_RIGHT, ROLL_SIGN_RIGHT)
    _report_model_error(robot, waist_id, left_sole_id, right_sole_id, left_target, right_target)

    if getattr(args_cli, "headless", False):
        # headless の Kit には入力インターフェースが無く、取得を試みるとアプリが落ちる。
        pad = _IdleGamepad()
        print("headless のためパッドは読まず、立位の保持だけ確認します。", flush=True)
    else:
        try:
            pad = HeelGamepad()
        except Exception:
            traceback.print_exc()
            pad = _IdleGamepad()
            print("gamepad: 読めないので、入力なしで立位だけ維持します。", flush=True)
    print(
        "操作: 左スティック=左踵、右スティック=右踵（腰のXY、奥が前、右がロボットの右）。\n"
        "      L/R バンパーで天井側、ZL/ZR トリガーで床側。離すとその位置を保持します。\n"
        "      緑の球が左踵の目標、橙の球が右踵の目標です。届かない高さは自動でずらします。\n"
        "      橋（isaac_hub_bridge.py）があれば、実機テレメトリの補正（シミュ）と足裏へ出します。",
        flush=True,
    )
    hub = HubTelemetry()

    sim_dt = sim.get_physics_dt()
    # 速度の単位は m/s。1 フレームが遅れても、目標が一気に飛ばないようにする。
    speed = np.array([args_cli.xy_speed, args_cli.xy_speed, args_cli.z_speed], dtype=float)
    step_index = 0
    status_interval = max(1, int(round(2.0 / sim_dt)))
    try:
        while simulation_app.is_running():
            left_weight, right_weight = pad.velocity_weights()
            frame_dt = min(float(sim_dt), 0.05)
            left_target, left_q, _ = step_heel_target(
                left_target,
                left_weight * speed * frame_dt,
                Y_HIP_LEFT,
                left_q,
                roll_sign=ROLL_SIGN_LEFT,
            )
            right_target, right_q, _ = step_heel_target(
                right_target,
                right_weight * speed * frame_dt,
                Y_HIP_RIGHT,
                right_q,
                roll_sign=ROLL_SIGN_RIGHT,
            )
            _apply_joints(robot, joint_pos, joint_index, left_q, right_q)
            robot.write_data_to_sim()
            _draw_targets(left_marker, right_marker, robot, waist_id, left_target, right_target)
            sim.step()
            robot.update(sim_dt)
            # 目標角は逆運動学、実測角はステップ後の関節。足裏は床との接触。
            hub.publish(robot, joint_index, left_q, right_q, contact, step_index * sim_dt)
            step_index += 1
            if step_index % status_interval == 0:
                print(
                    f"L target=({left_target[0]:+.3f},{left_target[1]:+.3f},{left_target[2]:+.3f}) "
                    f"R target=({right_target[0]:+.3f},{right_target[1]:+.3f},{right_target[2]:+.3f}) "
                    f"{pad.snapshot()}",
                    flush=True,
                )
            if args_cli.steps > 0 and step_index >= args_cli.steps:
                break
        print(
            f"done steps={step_index} "
            f"L=({left_target[0]:+.3f},{left_target[1]:+.3f},{left_target[2]:+.3f}) "
            f"R=({right_target[0]:+.3f},{right_target[1]:+.3f},{right_target[2]:+.3f})",
            flush=True,
        )
    finally:
        pad.close()
        hub.close()


def _design_scene() -> tuple[Articulation, ContactSensor]:
    """地面と両脚を置く。ベースは固定しない。倒れていても腰の軸で動かすため。

    足の接触は床の面で絞る。四隅の圧力は、このセンサの接触点から分ける。
    """
    ground = sim_utils.GroundPlaneCfg()
    ground.func("/World/ground", ground)
    light = sim_utils.DomeLightCfg(intensity=2500.0, color=(0.75, 0.75, 0.75))
    light.func("/World/Light", light)
    robot_cfg = YUUKI_LEGS_CFG.replace(prim_path="/World/Robot")
    robot = Articulation(cfg=robot_cfg)
    contact_cfg = ContactSensorCfg(
        prim_path="/World/Robot/.*",
        # 平らな床の衝突面。このプリムで絞らないと、圧力中心が取れない。
        filter_prim_paths_expr=[_ground_collision_path()],
        track_contact_points=True,
        max_contact_data_count_per_prim=8,
        history_length=0,
    )
    return robot, ContactSensor(contact_cfg)


def _ground_collision_path() -> str:
    """床 USD の衝突面。置き場所が版で違っても、名前で拾う。"""
    from isaaclab.sim.utils.stage import get_current_stage

    stage = get_current_stage()
    for prim in stage.Traverse():
        path = prim.GetPath().pathString
        if path.startswith("/World/ground") and prim.GetName() == "CollisionPlane":
            return path
    return "/World/ground/GroundPlane/CollisionPlane"


def _target_markers() -> tuple[VisualizationMarkers, VisualizationMarkers]:
    """左右の目標を別の球にする。一つの instancer に色違いを混ぜると Fabric が警告する。"""
    return (
        _sphere_marker("/World/Visuals/left_heel_target", (0.15, 0.85, 0.25)),
        _sphere_marker("/World/Visuals/right_heel_target", (0.95, 0.45, 0.1)),
    )


def _sphere_marker(path: str, color: tuple[float, float, float]) -> VisualizationMarkers:
    cfg = VisualizationMarkersCfg(
        prim_path=path,
        markers={
            "heel": sim_utils.SphereCfg(
                radius=0.018,
                visual_material=sim_utils.PreviewSurfaceCfg(diffuse_color=color),
            ),
        },
    )
    return VisualizationMarkers(cfg)


def _draw_targets(
    left_marker: VisualizationMarkers,
    right_marker: VisualizationMarkers,
    robot: Articulation,
    waist_id: int,
    left_target: np.ndarray,
    right_target: np.ndarray,
) -> None:
    """腰座標系の目標を、今の腰姿勢で世界座標へ置いて描く。"""
    waist_pos = robot.data.body_pos_w[0, waist_id]
    waist_quat = robot.data.body_quat_w[0, waist_id]
    local = torch.tensor(
        np.stack([left_target, right_target]),
        device=waist_pos.device,
        dtype=waist_pos.dtype,
    )
    quat = waist_quat.unsqueeze(0).expand(2, -1)
    world = waist_pos.unsqueeze(0) + quat_apply(quat, local)
    left_marker.visualize(translations=world[0:1])
    right_marker.visualize(translations=world[1:2])


class _IdleGamepad:
    """パッドが読めないとき、速度ゼロを返し続ける。"""

    available = False
    name = ""

    def velocity_weights(self) -> tuple[np.ndarray, np.ndarray]:
        zero = np.zeros(3)
        return zero, zero.copy()

    def snapshot(self) -> str:
        return "pad idle"

    def close(self) -> None:
        return None


def _apply_joints(
    robot: Articulation,
    joint_pos: torch.Tensor,
    joint_index: dict[str, int],
    left_q: np.ndarray,
    right_q: np.ndarray,
) -> None:
    """逆運動学の角度を位置目標にする。この機体に胴体関節は無い。"""
    targets = joint_pos.clone()
    for name, angle in zip(_LEFT_JOINTS, left_q, strict=True):
        targets[0, joint_index[name]] = float(angle)
    for name, angle in zip(_RIGHT_JOINTS, right_q, strict=True):
        targets[0, joint_index[name]] = float(angle)
    robot.set_joint_position_target(targets)
    robot.set_joint_velocity_target(torch.zeros_like(targets))


def _report_model_error(
    robot: Articulation,
    waist_id: int,
    left_sole_id: int,
    right_sole_id: int,
    left_target: np.ndarray,
    right_target: np.ndarray,
) -> None:
    """立位の順運動学と、シミュレータの踵位置がずれていたら知らせる。"""
    for label, sole_id, expected in (
        ("left", left_sole_id, left_target),
        ("right", right_sole_id, right_target),
    ):
        measured = _heel_in_waist(robot, waist_id, sole_id)
        error = float(np.linalg.norm(measured - expected))
        print(
            f"FK check {label}: model={np.array2string(expected, precision=3)} "
            f"sim={np.array2string(measured, precision=3)} err={error:.4f} m",
            flush=True,
        )
        if error > 0.02:
            print(
                f"警告: {label} 踵のモデルとシミュレータが 2cm 以上ずれています。関節はモデル側の目標を追います。",
                flush=True,
            )


def _leg_angles(robot: Articulation, joint_index: dict[str, int], names: tuple[str, ...]) -> np.ndarray:
    """名前の順で、今の関節角 [rad] を 5 個取り出す。"""
    positions = robot.data.joint_pos[0].detach().cpu().numpy()
    return np.array([float(positions[joint_index[name]]) for name in names], dtype=float)


def _heel_in_waist(robot: Articulation, waist_id: int, sole_id: int) -> np.ndarray:
    """足裏姿勢に踵オフセットを足し、今の腰座標で読む。"""
    waist_pos = robot.data.body_pos_w[0, waist_id]
    waist_quat = robot.data.body_quat_w[0, waist_id]
    sole_pos = robot.data.body_pos_w[0, sole_id]
    sole_quat = robot.data.body_quat_w[0, sole_id]
    offset = torch.tensor(_HEEL_IN_SOLE, device=sole_pos.device, dtype=sole_pos.dtype).unsqueeze(0)
    heel_pos = sole_pos + quat_apply(sole_quat.unsqueeze(0), offset)[0]
    local = quat_apply_inverse(waist_quat.unsqueeze(0), (heel_pos - waist_pos).unsqueeze(0))
    return local[0].detach().cpu().numpy()


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        # Kit は close の中でプロセスを終わらせることがあり、その後の表示が消える。
        traceback.print_exc()
        raise
    finally:
        simulation_app.close()
