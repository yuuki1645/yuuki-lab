# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""両脚歩行環境の短時間スモークテスト（spawn・報酬・接地を確認）。"""

import argparse

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Smoke test for biped walking environment.")
parser.add_argument(
    "--disable_fabric", action="store_true", default=False, help="Disable fabric and use USD I/O operations."
)
parser.add_argument("--num_envs", type=int, default=4, help="Number of parallel environments.")
parser.add_argument("--steps", type=int, default=200, help="Number of control steps to run.")
parser.add_argument("--task", type=str, default="YuukiLab-BipedPpoWalk-Direct-v0", help="Gym task id.")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import gymnasium as gym
import torch

import isaaclab_tasks  # noqa: F401
from isaaclab_tasks.utils import parse_env_cfg

import yuuki_isaac_lab.tasks  # noqa: F401


def main() -> None:
    """環境を起動し、ランダム行動で指定ステップ実行して主要指標を表示する。"""
    env_cfg = parse_env_cfg(
        args_cli.task, device=args_cli.device, num_envs=args_cli.num_envs, use_fabric=not args_cli.disable_fabric
    )
    env = gym.make(args_cli.task, cfg=env_cfg)
    print(f"[INFO] obs space: {env.observation_space}, action space: {env.action_space}")

    env.reset()
    total_reward = torch.zeros(env.unwrapped.num_envs, device=env.unwrapped.device)
    done_count = 0

    for step_idx in range(args_cli.steps):
        actions = 2.0 * torch.rand(env.action_space.shape, device=env.unwrapped.device) - 1.0
        _, rewards, terminated, truncated, _ = env.step(actions)
        total_reward += rewards
        done_count += int((terminated | truncated).sum().item())
        if (step_idx + 1) % 50 == 0:
            print(
                f"[step {step_idx + 1}] mean_reward={rewards.mean().item():.3f} "
                f"total_mean={total_reward.mean().item():.1f} dones={done_count}"
            )

    print(f"[PASS] Completed {args_cli.steps} steps. mean episodic reward={total_reward.mean().item():.1f}")
    env.close()


if __name__ == "__main__":
    main()
    simulation_app.close()
