# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""学習済みポリシーの headless 定量評価（移動距離・エピソード長・片脚率）。"""

import argparse
import os

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Evaluate biped walking policy (headless metrics).")
parser.add_argument("--task", type=str, default="YuukiLab-BipedPpoWalk-Direct-v0")
parser.add_argument("--num_envs", type=int, default=64)
parser.add_argument("--episodes", type=int, default=5, help="評価エピソード数（各 env 独立）。")
parser.add_argument("--load_run", type=str, default=None, help="logs/rsl_rl/biped_ppo_walk 以下の run 名。")
parser.add_argument("--checkpoint", type=str, default=None, help="チェックポイントファイル名（省略時は最新）。")
parser.add_argument("--seed", type=int, default=42)
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import gymnasium as gym
import torch
from rsl_rl.runners import OnPolicyRunner

from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper
from isaaclab_tasks.utils import get_checkpoint_path
from isaaclab_tasks.utils.hydra import hydra_task_config

import isaaclab_tasks  # noqa: F401
import yuuki_isaac_lab.tasks  # noqa: F401


@hydra_task_config(args_cli.task, "rsl_rl_cfg_entry_point")
def main(env_cfg, agent_cfg):
    """チェックポイントをロードし、複数エピソードの歩行指標を集計する。"""
    agent_cfg.seed = args_cli.seed
    env_cfg.seed = args_cli.seed
    env_cfg.scene.num_envs = args_cli.num_envs
    env_cfg.sim.device = args_cli.device if args_cli.device is not None else env_cfg.sim.device

    log_root = os.path.join("logs", "rsl_rl", agent_cfg.experiment_name)
    resume_path = get_checkpoint_path(log_root, args_cli.load_run, args_cli.checkpoint)
    print(f"[INFO] Loading checkpoint: {resume_path}")

    env = gym.make(args_cli.task, cfg=env_cfg)
    env = RslRlVecEnvWrapper(env)

    runner = OnPolicyRunner(env, agent_cfg.to_dict(), log_dir=None, device=agent_cfg.device)
    runner.load(resume_path)
    policy = runner.get_inference_policy(device=env.unwrapped.device)

    obs = env.get_observations()
    num_envs = env.unwrapped.num_envs
    max_steps = env.unwrapped.max_episode_length

    # 各 env のエピソード統計
    ep_lengths = torch.zeros(num_envs, device=env.unwrapped.device)
    ep_rewards = torch.zeros(num_envs, device=env.unwrapped.device)
    ep_displacements = torch.zeros(num_envs, device=env.unwrapped.device)
    ep_single_support = torch.zeros(num_envs, device=env.unwrapped.device)
    ep_steps = torch.zeros(num_envs, device=env.unwrapped.device)
    completed = 0
    start_imu_x = torch.zeros(num_envs, device=env.unwrapped.device)

    env.reset()
    start_imu_x[:] = env.unwrapped.extras.get("log", {}).get("Metrics/mean_imu_x", 0.0)
    # 直接 env から IMU X を取得
    if hasattr(env.unwrapped, "_last_physics") and env.unwrapped._last_physics:
        start_imu_x[:] = env.unwrapped._last_physics["imu_x"]

    total_control_steps = args_cli.episodes * max_steps
    for step_idx in range(total_control_steps):
        with torch.inference_mode():
            actions = policy(obs)
        obs, rewards, dones, _ = env.step(actions)

        unwrapped = env.unwrapped
        if unwrapped._last_physics:
            physics = unwrapped._last_physics
            biped = unwrapped._last_biped_ctx
            ep_rewards += rewards
            ep_lengths += 1.0
            ep_steps += 1.0
            if biped is not None:
                ep_single_support += biped.single_support.float()

        if dones.any():
            done_ids = dones.nonzero(as_tuple=False).squeeze(-1)
            if done_ids.ndim == 0:
                done_ids = done_ids.unsqueeze(0)
            for env_id in done_ids.tolist():
                if ep_steps[env_id] > 0 and completed < args_cli.episodes * num_envs:
                    if unwrapped._last_physics:
                        disp = unwrapped._last_physics["imu_x"][env_id] - start_imu_x[env_id]
                        ep_displacements[env_id] = disp
                    completed += 1
                ep_lengths[env_id] = 0.0
                ep_rewards[env_id] = 0.0
                ep_steps[env_id] = 0.0
                ep_single_support[env_id] = 0.0
                if unwrapped._last_physics:
                    start_imu_x[env_id] = unwrapped._last_physics["imu_x"][env_id]

        if (step_idx + 1) % 500 == 0:
            print(f"[eval step {step_idx + 1}] completed_episodes={completed}")

    # 集計（完了エピソードのみ）
    print("\n========== BIPED WALK EVALUATION ==========")
    print(f"Checkpoint: {resume_path}")
    print(f"Envs: {num_envs}, target episodes/env: {args_cli.episodes}")
    if unwrapped._last_physics and unwrapped._last_biped_ctx:
        ss_ratio = (
            ep_single_support / torch.clamp(ep_steps, min=1.0)
        ).mean()
        print(f"Mean single_support ratio: {ss_ratio.item():.3f}")
    print(f"Mean episode displacement +X: {ep_displacements.mean().item():.3f} m")
    print(f"Max episode displacement +X: {ep_displacements.max().item():.3f} m")
    success_15m = (ep_displacements >= 15.0).float().mean().item()
    success_5m = (ep_displacements >= 5.0).float().mean().item()
    print(f"Success rate >= 5 m: {success_5m * 100:.1f}%")
    print(f"Success rate >= 15 m: {success_15m * 100:.1f}%")
    print("==========================================\n")

    env.close()


if __name__ == "__main__":
    main()
    simulation_app.close()
