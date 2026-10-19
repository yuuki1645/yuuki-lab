"""BipedWalk がリセットできて、観測を返して、1歩進むかだけ見る。学習はしない。

conda は切ってから、Isaac Lab 3 で起動する。

    cd /d Z:\\Projects\\IsaacLab-3
    isaaclab.bat -p Z:\\Projects\\yuuki-lab\\isaac-lab\\scripts\\smoke_biped_walk.py
"""

from __future__ import annotations

import argparse
import os
import traceback
from pathlib import Path

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="YuukiLab-BipedWalk-v0 を2体で数ステップ進める。")
parser.add_argument("--num_envs", type=int, default=2)
parser.add_argument("--steps", type=int, default=20)
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import torch

import yuuki_isaac_lab  # noqa: F401  Gym 登録
from isaaclab.envs import ManagerBasedRLEnv

from yuuki_isaac_lab.tasks.manager_based.biped_walk.biped_walk_env_cfg import BipedWalkEnvCfg


def _report(lines: list[str]) -> None:
    """コンソールが途中で切れても、結果がファイルに残るようにする。"""
    text = "\n".join(lines) + "\n"
    path = Path(os.environ.get("TEMP", ".")) / "smoke_biped_walk.txt"
    path.write_text(text, encoding="utf-8")
    print(text, flush=True)


def _nearest_link(prim) -> str | None:
    """いちばん近い胴体リンク。すねの子である足首は、すねに数えない。"""
    names = {"left_thigh", "left_shin", "right_thigh", "right_shin", "left_foot", "right_foot"}
    current = prim
    while current.IsValid():
        if current.GetName() in names:
            return current.GetName()
        current = current.GetParent()
    return None


def _check_self_collision(env) -> str:
    """関節の隣以外は当たる。足裏板から反対の板やすねを除外していないこと。"""
    from pxr import Usd, UsdPhysics

    robot = env.sim.stage.GetPrimAtPath("/World/envs/env_0/Robot")
    left = None
    right = None
    right_shin = None
    self_on = False
    foot_servo_off = 0
    # 環境はインスタンスなので、通常の走査ではカゴの中まで入らない。
    for prim in Usd.PrimRange(robot, Usd.TraverseInstanceProxies()):
        schemas = set(prim.GetAppliedSchemas())
        is_root = "PhysicsArticulationRootAPI" in schemas or "NewtonArticulationRootAPI" in schemas
        if is_root:
            # Isaac Sim 6 の URDF 取り込みは newton:selfCollisionEnabled を書く。
            # 古い PhysX 属性が残っている変換結果も、どちらかが真なら有効と見る。
            for name in ("newton:selfCollisionEnabled", "physxArticulation:enabledSelfCollisions"):
                attr = prim.GetAttribute(name)
                if attr and attr.HasValue() and bool(attr.Get()):
                    self_on = True
        if not prim.HasAPI(UsdPhysics.CollisionAPI):
            continue
        blob = f"{prim.GetName()} {prim.GetDisplayName() or ''}"
        if "foot_servo" in blob:
            # 属性が無いときは有効。明示的に False のときだけ、切れていると数える。
            enabled = UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr()
            if enabled and enabled.Get() is False:
                foot_servo_off += 1
        if "left" in blob and "foot_plate" in blob:
            left = prim
        elif "right" in blob and "foot_plate" in blob:
            right = prim
        elif right_shin is None and _nearest_link(prim) == "right_shin":
            right_shin = prim
    if left is None or right is None or right_shin is None:
        raise RuntimeError("足裏板、またはすねの衝突形状が見つかりません")
    # 変換済み USD は newton:selfCollisionEnabled が 0 のことがある。
    # ここで止めると距離の点の確認まで届かないので、真偽は戻り値に残す。
    if foot_servo_off:
        raise RuntimeError(f"足サーボの衝突が {foot_servo_off} 個切れています")
    blocked: set[str] = set()
    if left.HasAPI(UsdPhysics.FilteredPairsAPI):
        blocked = {str(path) for path in UsdPhysics.FilteredPairsAPI(left).GetFilteredPairsRel().GetTargets()}
    if str(right.GetPath()) in blocked or str(right_shin.GetPath()) in blocked:
        raise RuntimeError(f"反対の板やすねが、左の板から除外されています: {sorted(blocked)[:8]}")
    return f"self_collision {self_on} filtered {len(blocked)}"


def main() -> int:
    lines: list[str] = []
    cfg = BipedWalkEnvCfg()
    cfg.scene.num_envs = args_cli.num_envs
    env = ManagerBasedRLEnv(cfg=cfg)
    lines.append(_check_self_collision(env))
    obs, _ = env.reset()
    from isaaclab.managers import SceneEntityCfg

    from yuuki_isaac_lab.tasks.manager_based.biped_walk.mdp.rewards import (
        PLATE_WIDTH_Y_M,
        TARGET_FEET_GAP_M,
        feet_apart,
        feet_lateral_gap_m,
        track_forward_progress,
    )

    foot_cfg = SceneEntityCfg("robot", body_names=["left_foot", "right_foot"], preserve_order=True)
    foot_cfg.resolve(env.scene)
    gap_m = feet_lateral_gap_m(env, foot_cfg)
    apart = feet_apart(env, foot_cfg)
    lines.append(
        f"feet_gap_m {float(gap_m.mean()):.3f} target {TARGET_FEET_GAP_M:.3f} feet_apart {float(apart.mean()):.3f}"
    )
    # リセット直後は、板が重ならない開き。符号や足首の戻しが逆だと、ここで落ちる。
    if float(gap_m.mean()) <= PLATE_WIDTH_Y_M or float(apart.mean()) < 0.8:
        raise RuntimeError(f"初期姿勢の足間隔が目標から遠い: gap {float(gap_m.mean()):.3f} score {float(apart.mean()):.3f}")
    policy = obs["policy"]
    critic = obs["critic"]
    # 関節10、傾き3、角速度3、の次が左右8隅の kg。
    foot_kg = policy[:, 16:24]
    lines.append(f"policy {tuple(policy.shape)} critic {tuple(critic.shape)}")
    lines.append(f"reset foot_kg mean {float(foot_kg.mean()):.3f}")
    command_vx = env.command_manager.get_command("base_velocity")[:, 0]
    track = track_forward_progress(env, "base_velocity")
    lines.append(f"command_vx {float(command_vx.mean()):.3f} track_forward {float(track.mean()):.3f}")
    # 停止では前進点は 0。指令は 0.1 m/s。
    if abs(float(command_vx.mean()) - 0.1) > 0.01 or float(track.mean()) > 0.2:
        raise RuntimeError(
            f"前進の指令か停止時の点が違う: vx {float(command_vx.mean()):.3f} score {float(track.mean()):.3f}"
        )
    action = torch.zeros(env.action_space.shape, device=env.device)
    for step in range(args_cli.steps):
        obs, reward, terminated, truncated, _ = env.step(action)
        root_z = env.scene["robot"].data.root_pos_w.torch[:, 2]
        foot_kg = obs["policy"][:, 16:24]
        lines.append(
            f"step {step + 1}"
            f"  reward {float(reward.mean()):.3f}"
            f"  root_z {float(root_z.mean()):.3f}"
            f"  foot_kg {float(foot_kg.mean()):.3f}"
            f"  done {int(terminated.sum())}/{int(truncated.sum())}"
        )
    settled_gap = float(feet_lateral_gap_m(env, foot_cfg).mean())
    settled_z = float(env.scene["robot"].data.root_pos_w.torch[:, 2].mean())
    forward_m = float(env.command_manager.get_term("base_velocity")._forward_sum.mean())
    lines.append(f"settled feet_gap_m {settled_gap:.3f} root_z {settled_z:.3f} forward_m {forward_m:.3f}")
    # 足首の戻しが逆だと板が傾いて倒れ、間隔も板幅以下に寄る。
    # 関節 0 のまま数歩では、前へはほとんど進まない。
    from yuuki_isaac_lab.assets.robots.yuuki_legs.model_size import SOLE_BELOW_ORIGIN_M

    # 足サーボで立つと、カゴ底が足裏高さより板厚ぶん高くなる。板で立っていれば 0.640 m 付近。
    if (
        settled_gap <= PLATE_WIDTH_Y_M
        or abs(settled_z - SOLE_BELOW_ORIGIN_M) > 0.03
        or int(terminated.sum()) > 0
        or abs(forward_m) > 0.05
    ):
        raise RuntimeError(
            f"開いた初期姿勢を保てていない: gap {settled_gap:.3f}"
            f" root_z {settled_z:.3f} sole {SOLE_BELOW_ORIGIN_M:.3f} forward_m {forward_m:.3f}"
        )
    env.close()
    lines.append("ok")
    _report(lines)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        Path(os.environ.get("TEMP", "."), "smoke_biped_walk.txt").write_text(
            traceback.format_exc(), encoding="utf-8"
        )
        raise
    finally:
        simulation_app.close()
