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


def main() -> int:
    lines: list[str] = []
    cfg = BipedWalkEnvCfg()
    cfg.scene.num_envs = args_cli.num_envs
    env = ManagerBasedRLEnv(cfg=cfg)
    obs, _ = env.reset()
    policy = obs["policy"]
    critic = obs["critic"]
    # 関節10、傾き3、角速度3、の次が左右8隅の kg。
    foot_kg = policy[:, 16:24]
    lines.append(f"policy {tuple(policy.shape)} critic {tuple(critic.shape)}")
    lines.append(f"reset foot_kg mean {float(foot_kg.mean()):.3f}")
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
