# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""両脚環境の物理診断: 立位安定性・接地判定・ゼロ行動時の挙動。"""

import argparse

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Diagnose biped physics and foot contact.")
parser.add_argument("--num_envs", type=int, default=1)
parser.add_argument("--steps", type=int, default=300)
parser.add_argument("--task", type=str, default="YuukiLab-BipedPpoWalk-Direct-v0")
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
    """ゼロ行動で立位を維持できるか、接地判定が妥当かを確認する。"""
    env_cfg = parse_env_cfg(args_cli.task, device=args_cli.device, num_envs=args_cli.num_envs)
    env = gym.make(args_cli.task, cfg=env_cfg)
    unwrapped = env.unwrapped
    env.reset()

    print("[INFO] Running zero-action standing test...")
    for step_idx in range(args_cli.steps):
        actions = torch.zeros(env.action_space.shape, device=unwrapped.device)
        _, rewards, terminated, truncated, _ = env.step(actions)

        if (step_idx + 1) % 50 == 0 and unwrapped._last_physics:
            p = unwrapped._last_physics
            b = unwrapped._last_biped_ctx
            print(
                f"[step {step_idx + 1:4d}] imu_z={p['imu_z'].mean():.3f} "
                f"upright={p['upright'].mean():.3f} "
                f"Lfoot_z={p['left_foot_z'].mean():.4f} Rfoot_z={p['right_foot_z'].mean():.4f} "
                f"Ltoe={p['left_toe_z'].mean():.4f} Rtoe={p['right_toe_z'].mean():.4f} "
                f"Lcontact={p['left_on_floor'].float().mean():.2f} "
                f"Rcontact={p['right_on_floor'].float().mean():.2f} "
                f"lean={p['lean_fwd_body'].mean():.3f} "
                f"reward={rewards.mean():.2f} "
                f"dones={(terminated | truncated).sum().item()}"
            )

    if unwrapped._last_physics:
        p = unwrapped._last_physics
        print(
            f"\n[SUMMARY] final imu_x={p['imu_x'].mean():.4f} "
            f"root_vel_x={p['root_vel_x'].mean():.4f} "
            f"imu_z={p['imu_z'].mean():.4f}"
        )
    env.close()


if __name__ == "__main__":
    main()
    simulation_app.close()
