# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""YouTube 向け: 16 並列 env で学習済み両脚 PPO ポリシーを長時間 MP4 録画する。

- 既定: 10 分・50 fps（step_dt=0.02）
- imageio でフレームを逐次ディスク書き込み（RecordVideo は全フレーム RAM 保持で OOM になる）
- GUI + --enable_cameras が安定（headless は Replicator attach 失敗の可能性）
"""

"""Launch Isaac Sim Simulator first."""

import argparse
import gc
import os
import sys
import time

from isaaclab.app import AppLauncher

import cli_args  # isort: skip
import env_cfg_cli  # isort: skip

parser = argparse.ArgumentParser(description="Record a long YouTube demo of biped PPO policy on parallel envs.")
parser.add_argument("--num_envs", type=int, default=16, help="Number of parallel environments (default: 16).")
parser.add_argument(
    "--duration_sec",
    type=float,
    default=600.0,
    help="Target video length in seconds (default: 600 = 10 minutes).",
)
parser.add_argument(
    "--output",
    type=str,
    default="videos/youtube/biped_ppo_walk_16env_10min.mp4",
    help="Output MP4 path.",
)
parser.add_argument(
    "--task",
    type=str,
    default="YuukiLab-BipedPpoWalk-Direct-Play-v0",
    help="Gym task id (Play env recommended for visualization).",
)
parser.add_argument("--seed", type=int, default=None, help="Environment / agent seed.")
parser.add_argument(
    "--agent",
    type=str,
    default="rsl_rl_cfg_entry_point",
    help="Hydra agent config entry point.",
)
parser.add_argument(
    "--disable_fabric",
    action="store_true",
    default=False,
    help="Set sim.use_fabric=False (USD I/O; GUI may look frozen). For mesh visibility use --visualize-robots.",
)
env_cfg_cli.add_robot_visualization_cli_args(parser)
parser.add_argument(
    "--use_pretrained_checkpoint",
    action="store_true",
    help="Use the pre-trained checkpoint from Nucleus.",
)
cli_args.add_rsl_rl_args(parser)
AppLauncher.add_app_launcher_args(parser)

args_cli, hydra_args = parser.parse_known_args()
args_cli.enable_cameras = True
if getattr(args_cli, "headless", False):
    print(
        "[WARN] --headless 録画は Isaac Sim 5.1 で Replicator が落ちることがあります。"
        " GUI モード（--headless なし）を推奨します。"
    )

sys.argv = [sys.argv[0]] + hydra_args

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

"""Rest everything follows."""

import gymnasium as gym
import imageio.v2 as imageio
import numpy as np
import torch
from rsl_rl.runners import DistillationRunner, OnPolicyRunner

from isaaclab.envs import DirectMARLEnv, DirectMARLEnvCfg, DirectRLEnvCfg, ManagerBasedRLEnvCfg, multi_agent_to_single_agent
from isaaclab.utils.assets import retrieve_file_path

from isaaclab_rl.rsl_rl import RslRlBaseRunnerCfg, RslRlVecEnvWrapper
from isaaclab_rl.utils.pretrained_checkpoint import get_published_pretrained_checkpoint

import isaaclab_tasks  # noqa: F401
from isaaclab_tasks.utils import get_checkpoint_path
from isaaclab_tasks.utils.hydra import hydra_task_config

import yuuki_isaac_lab.tasks  # noqa: F401


def _resolve_checkpoint(log_root_path: str, train_task_name: str, agent_cfg: RslRlBaseRunnerCfg) -> str:
    """CLI からチェックポイント .pt への絶対パスを解決する。"""
    if args_cli.use_pretrained_checkpoint:
        resume_path = get_published_pretrained_checkpoint("rsl_rl", train_task_name)
        if not resume_path:
            raise RuntimeError("Pre-trained checkpoint is unavailable for this task.")
        return resume_path
    if args_cli.checkpoint:
        ckpt = args_cli.checkpoint
        if os.path.basename(ckpt) == ckpt and not ckpt.startswith("http"):
            return get_checkpoint_path(log_root_path, agent_cfg.load_run, ckpt)
        return retrieve_file_path(ckpt)
    return get_checkpoint_path(log_root_path, agent_cfg.load_run, agent_cfg.load_checkpoint)


def _frame_to_rgb_uint8(frame: np.ndarray) -> np.ndarray:
    """Replicator 出力を imageio 向け RGB uint8 に変換する。"""
    arr = np.asarray(frame)
    if arr.ndim == 3 and arr.shape[-1] == 4:
        arr = arr[..., :3]
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    return arr


@hydra_task_config(args_cli.task, args_cli.agent)
def main(env_cfg: ManagerBasedRLEnvCfg | DirectRLEnvCfg | DirectMARLEnvCfg, agent_cfg: RslRlBaseRunnerCfg):
    """16 env 程度の並列歩行を 1 本の MP4 に録画する（逐次書き込みで OOM 回避）。"""
    task_name = args_cli.task.split(":")[-1]
    train_task_name = task_name.replace("-Play", "")

    agent_cfg = cli_args.update_rsl_rl_cfg(agent_cfg, args_cli)
    env_cfg.scene.num_envs = args_cli.num_envs
    env_cfg.seed = agent_cfg.seed
    env_cfg.sim.device = args_cli.device if args_cli.device is not None else env_cfg.sim.device
    env_cfg_cli.apply_robot_visualization_if_requested(env_cfg, args_cli)

    if hasattr(env_cfg, "viewer"):
        env_cfg.viewer.eye = (14.0, -18.0, 9.0)
        env_cfg.viewer.lookat = (0.0, 0.0, 0.55)
        env_cfg.viewer.resolution = (1280, 720)

    log_root_path = os.path.abspath(os.path.join("logs", "rsl_rl", agent_cfg.experiment_name))
    resume_path = _resolve_checkpoint(log_root_path, train_task_name, agent_cfg)
    env_cfg.log_dir = os.path.dirname(resume_path)

    output_path = os.path.abspath(args_cli.output)
    # 録画中は .part に書き、完了後にリネーム（moov 未書き込みの MP4 を誤って開くのを防ぐ）
    part_path = output_path + ".part"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    if os.path.isfile(part_path):
        os.remove(part_path)

    render_fps = int(round(1.0 / (env_cfg.sim.dt * env_cfg.decimation)))
    video_length = max(1, int(args_cli.duration_sec * render_fps))

    print("[INFO] YouTube recording settings:")
    print(f"       task={args_cli.task}, num_envs={args_cli.num_envs}")
    print(f"       checkpoint={resume_path}")
    print(f"       duration={args_cli.duration_sec}s, fps={render_fps}, steps={video_length}")
    print(f"       output={output_path}")
    print(f"       writing_to={part_path} (完了後にリネーム)")
    print("[INFO] 初回は 16 env の USD clone に 10 分以上かかることがあります。Isaac Sim ウィンドウを閉じないでください。")
    print("[INFO] .part ファイルは録画完了まで再生できません。完了ログ: Done. Wrote ...")
    sys.stdout.flush()

    env = gym.make(args_cli.task, cfg=env_cfg, render_mode="rgb_array")
    if isinstance(env.unwrapped, DirectMARLEnv):
        env = multi_agent_to_single_agent(env)

    # RecordVideo は使わない（長尺で RAM 枯渇）。RslRlVecEnvWrapper を直接使う。
    env = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)

    if agent_cfg.class_name == "OnPolicyRunner":
        runner = OnPolicyRunner(env, agent_cfg.to_dict(), log_dir=None, device=agent_cfg.device)
    elif agent_cfg.class_name == "DistillationRunner":
        runner = DistillationRunner(env, agent_cfg.to_dict(), log_dir=None, device=agent_cfg.device)
    else:
        raise ValueError(f"Unsupported runner class: {agent_cfg.class_name}")

    print(f"[INFO] Loading checkpoint: {resume_path}")
    runner.load(resume_path)
    policy = runner.get_inference_policy(device=env.unwrapped.device)

    try:
        policy_nn = runner.alg.policy
    except AttributeError:
        policy_nn = runner.alg.actor_critic

    obs = env.get_observations()
    frames_written = 0
    t0 = time.time()

    with imageio.get_writer(
        part_path,
        fps=render_fps,
        codec="libx264",
        quality=8,
        pixelformat="yuv420p",
        macro_block_size=1,
    ) as writer:
        while simulation_app.is_running() and frames_written < video_length:
            with torch.inference_mode():
                actions = policy(obs)
                obs, _, dones, _ = env.step(actions)
                policy_nn.reset(dones)

            # シミュレーション step 後に 1 フレーム取得して即ディスクへ（RAM に溜めない）
            frame = env.unwrapped.render()
            if frame is not None and np.asarray(frame).size > 0:
                writer.append_data(_frame_to_rgb_uint8(frame))
                frames_written += 1

            if frames_written % 500 == 0 and frames_written > 0:
                elapsed = time.time() - t0
                pct = 100.0 * frames_written / video_length
                eta = elapsed / frames_written * (video_length - frames_written)
                print(
                    f"[INFO] Recording progress: {frames_written}/{video_length} frames "
                    f"({pct:.1f}%), elapsed={elapsed:.0f}s, ETA={eta:.0f}s",
                    flush=True,
                )
                # 長時間録画でのメモリ断片化を軽減
                gc.collect()

    env.close()
    elapsed_total = time.time() - t0
    # moov atom を書き終えてから最終パスへ移動（この時点で初めて再生可能）
    if os.path.isfile(output_path):
        os.remove(output_path)
    os.replace(part_path, output_path)
    print(f"[INFO] Done. Wrote {frames_written} frames to {output_path} in {elapsed_total:.1f}s", flush=True)


if __name__ == "__main__":
    main()
    simulation_app.close()
