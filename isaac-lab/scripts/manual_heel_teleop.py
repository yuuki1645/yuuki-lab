# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""ゲームパッドで、腰基準の左右の踵を Isaac Sim 上で動かす。

強化学習の歩行環境とは別のスクリプト。方策は使わない。
接続されている XInput パッド（Logicool を Xbox 360 Controller として認識したもの）を読み、
スティックの速度を踵目標へ積算してから逆運動学で関節角にする。

起動例（isaac-lab ディレクトリ、env_isaaclab）::

    python scripts/manual_heel_teleop.py

操作:
    左スティック  左踵を腰の XY で動かす。奥が前、右がロボットの右。
    右スティック  右踵。同じ向き。
    L / R         肩のバンパー。押しているあいだ、その足を腰の天井側へ。
    ZL / ZR       肩のトリガー。引いているあいだ、その足を腰の床側へ。
    スティックやボタンを戻しても、そこまでの踵位置は保持する。
"""

from __future__ import annotations

import argparse
import traceback

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Manual heel teleop in the waist frame.")
parser.add_argument("--xy-speed", type=float, default=0.10, help="スティック倒し切りの踵の速さ [m/s]。")
parser.add_argument("--z-speed", type=float, default=0.08, help="肩ボタンを押し切ったときの高さの速さ [m/s]。")
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
from isaaclab.sim import SimulationContext
from isaaclab.utils.math import quat_apply, quat_apply_inverse

from yuuki_isaac_lab.assets.robots.yuuki_biped import YUUKI_BIPED_CFG
from yuuki_isaac_lab.manual_heel.gamepad_heel import HeelGamepad
from yuuki_isaac_lab.manual_heel.leg_ik import Y_HIP_LEFT, Y_HIP_RIGHT, stand_heel, step_heel_target

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
# 足裏リンクから踵点まで。URDF の heel_bottom_site と同じ。
_HEEL_IN_SOLE = (-0.025, 0.0, 0.0)
# 胴体のバランス軸は、この操作では中立のまま持つ。
_HOLD_JOINTS = ("basket_top_roll", "balance_pitch")


def main() -> None:
    """地面の上に両脚を出し、パッドの速度を腰基準の踵目標へ積算する。"""
    sim_cfg = sim_utils.SimulationCfg(device=args_cli.device, dt=1.0 / 120.0)
    sim = SimulationContext(sim_cfg)
    # 前方やや右から、足と腰が見える位置。
    sim.set_camera_view(eye=[1.35, -1.15, 0.72], target=[0.0, 0.0, 0.32])
    robot = _design_scene()
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

    joint_index = {name: int(robot.find_joints(name)[0][0]) for name in (*_LEFT_JOINTS, *_RIGHT_JOINTS, *_HOLD_JOINTS)}
    waist_id = int(robot.find_bodies("basket_thigh")[0][0])
    # 踵サイトは固定リンクのため、この USD の関節ボディには入らない。足裏姿勢からオフセットする。
    left_sole_id = int(robot.find_bodies("left_sole")[0][0])
    right_sole_id = int(robot.find_bodies("right_sole")[0][0])

    # 目標の初期値は運動学の立位。測定値で上書きしないので、接地の沈みを目標に取り込まない。
    left_target = stand_heel(Y_HIP_LEFT)
    right_target = stand_heel(Y_HIP_RIGHT)
    left_q = np.zeros(5)
    right_q = np.zeros(5)
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
        "      緑の球が左踵の目標、橙の球が右踵の目標です。届かない高さは自動でずらします。",
        flush=True,
    )

    sim_dt = sim.get_physics_dt()
    # 速度の単位は m/s。1 フレームが遅れても、目標が一気に飛ばないようにする。
    speed = np.array([args_cli.xy_speed, args_cli.xy_speed, args_cli.z_speed], dtype=float)
    step_index = 0
    status_interval = max(1, int(round(2.0 / sim_dt)))
    while simulation_app.is_running():
        left_weight, right_weight = pad.velocity_weights()
        frame_dt = min(float(sim_dt), 0.05)
        left_target, left_q, _ = step_heel_target(left_target, left_weight * speed * frame_dt, Y_HIP_LEFT, left_q)
        right_target, right_q, _ = step_heel_target(
            right_target, right_weight * speed * frame_dt, Y_HIP_RIGHT, right_q
        )
        _apply_joints(robot, joint_pos, joint_index, left_q, right_q)
        robot.write_data_to_sim()
        _draw_targets(left_marker, right_marker, robot, waist_id, left_target, right_target)
        sim.step()
        robot.update(sim_dt)
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
    pad.close()


def _design_scene() -> Articulation:
    """地面と両脚を置く。ベースは固定しない。倒れていても腰の軸で動かすため。"""
    ground = sim_utils.GroundPlaneCfg()
    ground.func("/World/ground", ground)
    light = sim_utils.DomeLightCfg(intensity=2500.0, color=(0.75, 0.75, 0.75))
    light.func("/World/Light", light)
    robot_cfg = YUUKI_BIPED_CFG.replace(prim_path="/World/Robot")
    return Articulation(cfg=robot_cfg)


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
    """逆運動学の角度を位置目標にする。胴体の 2 軸は中立を維持する。"""
    targets = joint_pos.clone()
    for name, angle in zip(_LEFT_JOINTS, left_q, strict=True):
        targets[0, joint_index[name]] = float(angle)
    for name, angle in zip(_RIGHT_JOINTS, right_q, strict=True):
        targets[0, joint_index[name]] = float(angle)
    for name in _HOLD_JOINTS:
        targets[0, joint_index[name]] = 0.0
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
    finally:
        simulation_app.close()
