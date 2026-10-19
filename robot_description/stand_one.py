#!/usr/bin/env python3
"""新しい URDF を浮動ベースの USD にし、1体だけ床に置いて直立を保つか見る。

Hub 再生の `.usd_cache` はカゴを地面に固定している。歩行の学習には使えないので、
変換結果は `.usd_float` に分ける。関節目標はすべて 0（脚をまっすぐ下へ伸ばした直立）。
位置ゲインは再生スクリプトと同じ仮の値で、トルクは URDF の 14.7 N·m で頭打ちにする。

conda の env_isaaclab は使わない。Isaac Lab 3 のランチャから起動する。

窓を出して見る（見た目の確認はこちら）::

    cd /d Z:\\Projects\\IsaacLab-3
    isaaclab.bat -p Z:\\Projects\\yuuki-lab\\robot_description\\stand_one.py --viz kit

高さ・傾き・足裏の高さだけを測って終える::

    isaaclab.bat -p Z:\\Projects\\yuuki-lab\\robot_description\\stand_one.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

from isaaclab.app import AppLauncher

from model_size import SOLE_BELOW_ORIGIN_M

# 直立時、カゴ底（URDF 原点）から足裏まで。1 cm 上から落として、板が床に乗るかを見る。
# 数値は yaml の ankle_to_sole_m から model_size が計算する。
SPAWN_CLEARANCE_M = 0.01
# 再生スクリプトと同じ仮の位置ゲイン。実機の PD ではない。
JOINT_STIFFNESS = 80.0
JOINT_DAMPING = 2.0
# サーボのトルク上限。無限トルクで直立を偽らない。
EFFORT_LIMIT_NM = 14.7

_HERE = Path(__file__).resolve().parent
URDF_PATH = _HERE / "yuuki_biped.urdf"
# カゴ固定の .usd_cache とは別。中身は変換結果なので手で編集しない。
USD_DIR = _HERE / ".usd_float"

parser = argparse.ArgumentParser(description="浮動ベースの1体を直立の角度で床に置き、数秒立っていられるか見る。")
parser.add_argument("--seconds", type=float, default=4.0, help="姿勢を保つか測る秒数。")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

"""キット起動のあとでないと、シミュレータ側のモジュールは読めない。"""

import torch

import isaaclab.sim as sim_utils
from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.assets import Articulation, ArticulationCfg
from isaaclab.sim import SimulationContext
from isaaclab.sim.converters import UrdfConverterCfg
from isaaclab.sim.spawners.from_files import UrdfFileCfg


def _wants_window() -> bool:
    """`--viz kit` のときだけ、測定のあと窓を残す。引数なしはヘッドレス。"""
    visualizer = getattr(args_cli, "visualizer", None)
    if args_cli.headless or not visualizer:
        return False
    return "kit" in visualizer


def _robot_cfg() -> ArticulationCfg:
    """URDF をその場で USD へ変換し、カゴが地面に固定されていない1体として出す。"""
    if not URDF_PATH.is_file():
        raise SystemExit(f"URDF がありません: {URDF_PATH}")
    USD_DIR.mkdir(parents=True, exist_ok=True)
    return ArticulationCfg(
        prim_path="/World/yuuki_biped",
        spawn=UrdfFileCfg(
            asset_path=str(URDF_PATH),
            usd_dir=str(USD_DIR),
            # 歩行と同じ条件。カゴを世界へ固定する関節は作らない。
            fix_base=False,
            # 足裏の参照リンクと、板以外の衝突を名前で切れるように、固定関節はまとめない。
            merge_fixed_joints=False,
            # URDF に衝突形状がある。見た目から作ると、目印の球まで床に当たる。
            collision_from_visuals=False,
            # 関節の隣以外は当たる。足サーボは板の上なので、床との当たりも切らない。
            self_collision=True,
            joint_drive=UrdfConverterCfg.JointDriveCfg(
                drive_type="force",
                target_type="position",
                gains=UrdfConverterCfg.JointDriveCfg.PDGainsCfg(
                    stiffness=JOINT_STIFFNESS,
                    damping=JOINT_DAMPING,
                ),
            ),
        ),
        init_state=ArticulationCfg.InitialStateCfg(
            pos=(0.0, 0.0, SOLE_BELOW_ORIGIN_M + SPAWN_CLEARANCE_M),
            joint_pos={".*": 0.0},
        ),
        actuators={
            "legs": ImplicitActuatorCfg(
                joint_names_expr=[".*"],
                stiffness=JOINT_STIFFNESS,
                damping=JOINT_DAMPING,
                effort_limit_sim=EFFORT_LIMIT_NM,
            ),
        },
    )


def _spawn_ground() -> None:
    """上面が z=0 の静的な床。核のデータは使わない。"""
    cfg = sim_utils.CuboidCfg(
        size=(8.0, 8.0, 0.1),
        collision_props=sim_utils.CollisionPropertiesCfg(collision_enabled=True),
        visual_material=sim_utils.PreviewSurfaceCfg(diffuse_color=(0.32, 0.32, 0.32)),
    )
    cfg.func("/World/ground", cfg, translation=(0.0, 0.0, -0.05))


def _design_scene() -> Articulation:
    """床と1体。カメラはカゴの高さが見える斜め前。足サーボは板の上なので切らない。"""
    _spawn_ground()
    light = sim_utils.DomeLightCfg(intensity=3000.0, color=(0.8, 0.8, 0.8))
    light.func("/World/light", light)
    return Articulation(_robot_cfg())


def _write_upright(robot: Articulation) -> None:
    """初期姿勢を、脚を伸ばした直立としてシミュレータへ書く。"""
    robot.write_root_pose_to_sim_index(root_pose=robot.data.default_root_pose.torch.clone())
    robot.write_root_velocity_to_sim_index(root_velocity=robot.data.default_root_vel.torch.clone())
    robot.write_joint_position_to_sim_index(position=robot.data.default_joint_pos.torch.clone())
    robot.write_joint_velocity_to_sim_index(velocity=robot.data.default_joint_vel.torch.clone())
    robot.reset()


def _hold_upright(robot: Articulation) -> None:
    """全関節の目標を 0 rad にする。書き込みは呼び出し側の write_data_to_sim。"""
    zeros = torch.zeros_like(robot.data.joint_pos.torch)
    robot.set_joint_position_target_index(target=zeros)


def _up_axis_z(robot: Articulation) -> float:
    """カゴの上方向が、世界の上とどれだけ揃っているか。直立なら 1、横倒しなら 0 付近。"""
    quat = robot.data.root_link_quat_w.torch[0]
    x, y, _z, _w = (float(quat[0]), float(quat[1]), float(quat[2]), float(quat[3]))
    return 1.0 - 2.0 * (x * x + y * y)


def _sole_z(robot: Articulation) -> dict[str, float | None]:
    """左右の足裏下面中心の高さ。板が床に乗っていれば 0 付近。"""
    height: dict[str, float | None] = {"left_sole": None, "right_sole": None}
    try:
        indices, names = robot.find_bodies(["left_sole", "right_sole"], preserve_order=True)
    except Exception as exc:
        print(f"[stand_one] 足裏リンクを読めませんでした: {exc}")
        return height
    positions = robot.data.body_link_pos_w.torch[0]
    for index, name in zip(indices, names):
        height[name] = float(positions[index][2])
    return height


def _measure(robot: Articulation) -> dict[str, float | None]:
    root_z = float(robot.data.root_link_pos_w.torch[0][2])
    joint = robot.data.joint_pos.torch[0]
    soles = _sole_z(robot)
    return {
        "root_z": root_z,
        "up_z": _up_axis_z(robot),
        "joint_abs_max": float(torch.max(torch.abs(joint))),
        "left_sole_z": soles["left_sole"],
        "right_sole_z": soles["right_sole"],
    }


def _standing(sample: dict[str, float | None]) -> tuple[bool, list[str]]:
    """数秒後に、倒れておらず、足裏が床の高さにあるか。

    カゴ底は足裏から SOLE_BELOW_ORIGIN_M。着地後もその近くにあり、上方向が残っていれば立っている。
    足裏が 2 cm より高いときは、板ではなくはみ出した形状で支えている。
    """
    reasons: list[str] = []
    root_z = float(sample["root_z"])
    # 3 cm 以上ずれると、板ではなく別の箱で立っているか、弾かれている。
    if abs(root_z - SOLE_BELOW_ORIGIN_M) > 0.03:
        reasons.append(
            f"カゴ底の高さが {root_z:.3f} m（足が床に乗った直立なら約 {SOLE_BELOW_ORIGIN_M:.3f} m）"
        )
    if float(sample["up_z"]) < 0.9:
        reasons.append(f"カゴの上方向が {float(sample['up_z']):.2f}（1 が直立、0 付近は横倒し）")
    if float(sample["joint_abs_max"]) > 0.25:
        reasons.append(f"関節が目標 0 から {float(sample['joint_abs_max']):.2f} rad ずれて脚が折れている")
    for name in ("left_sole_z", "right_sole_z"):
        sole_z = sample[name]
        if sole_z is None:
            reasons.append(f"{name} がステージに無い")
        elif abs(sole_z) > 0.008:
            reasons.append(f"{name} が床から {sole_z:.3f} m（板が床に乗っていれば 0 付近）")
    return (not reasons), reasons


def _print_sample(label: str, sample: dict[str, float | None]) -> None:
    left = sample["left_sole_z"]
    right = sample["right_sole_z"]
    left_text = "なし" if left is None else f"{left:.3f} m"
    right_text = "なし" if right is None else f"{right:.3f} m"
    print(
        f"[stand_one] {label}  カゴ底 {float(sample['root_z']):.3f} m"
        f"  上方向 {float(sample['up_z']):.2f}"
        f"  関節ずれ {float(sample['joint_abs_max']):.3f} rad"
        f"  左足裏 {left_text}  右足裏 {right_text}"
    )


def _run(sim: SimulationContext, robot: Articulation) -> int:
    """目標 0 を保ったまま進め、最後の姿勢で成否を返す。窓があるときは閉じるまで残す。"""
    _write_upright(robot)
    print(f"[stand_one] 関節 {robot.joint_names}")
    dt = sim.get_physics_dt()
    steps = max(1, int(args_cli.seconds / dt))
    next_report = dt
    sample = _measure(robot)
    for step in range(steps):
        if not simulation_app.is_running():
            break
        _hold_upright(robot)
        robot.write_data_to_sim()
        sim.step()
        robot.update(dt)
        elapsed = (step + 1) * dt
        if elapsed + 1e-9 >= next_report:
            sample = _measure(robot)
            _print_sample(f"{elapsed:.0f} s", sample)
            next_report += 1.0
    ok, reasons = _standing(sample)
    if ok:
        print("[stand_one] 数値のうえでは立っています。足裏が床の高さにあり、カゴは倒れていません。")
    else:
        print("[stand_one] 数値のうえでは直立を保てていません。")
        for reason in reasons:
            print(f"[stand_one]   - {reason}")
    if _wants_window():
        print("[stand_one] 窓は開いたままです。閉じると終了します。見た目（板が床に乗っているか、実機の姿勢に近いか）は画面で見てください。")
        while simulation_app.is_running():
            _hold_upright(robot)
            robot.write_data_to_sim()
            sim.step()
            robot.update(dt)
    return 0 if ok else 1


def main() -> int:
    sim = SimulationContext(sim_utils.SimulationCfg(dt=1.0 / 120.0, device=args_cli.device))
    sim.set_camera_view(eye=[1.8, -1.6, 0.85], target=[0.0, 0.0, 0.35])
    robot = _design_scene()
    sim.reset()
    print(f"[stand_one] USD の出力先 {USD_DIR}")
    return _run(sim, robot)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        simulation_app.close()
