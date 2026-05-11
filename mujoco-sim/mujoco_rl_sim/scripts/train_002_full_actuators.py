# type: ignore

"""連番 002: PPO で ``FullActuatorPositionEnv`` を学習。オプションでライブ Viewer 子プロセス。"""

from __future__ import annotations

import argparse
import subprocess
import sys

from mujoco_sim_assets.paths import resolved_model_xml
from mujoco_rl_sim import FullActuatorPositionEnv
from stable_baselines3 import PPO
from stable_baselines3.common.env_checker import check_env
from stable_baselines3.common.monitor import Monitor


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="FullActuatorPositionEnv（全 position アクチュエータ）を PPO で学習"
    )
    p.add_argument(
        "--xml-path",
        default=None,
        help="MJCF（省略時は mujoco_sim_assets の既定）",
    )
    p.add_argument("--max-steps", type=int, default=500, help="1 エピソード上限ステップ")
    p.add_argument(
        "--reset-joint-noise",
        type=float,
        default=0.05,
        help="リセット時の関節ノイズ（FullActuatorPositionEnv の引数）",
    )
    p.add_argument("--total-timesteps", type=int, default=100_000)
    p.add_argument("--learn-chunk", type=int, default=10_000)
    p.add_argument(
        "--live-ckpt",
        default="ppo_full_actuators_live",
        help="学習中に上書き保存するベース名（.zip は付けない）",
    )
    p.add_argument(
        "--final-ckpt",
        default="ppo_full_actuators",
        help="学習完了時に保存するベース名（.zip は付けない）",
    )
    p.add_argument(
        "--no-viewer",
        action="store_true",
        help="学習中のライブ Viewer 子プロセスを起動しない",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    xml_path = args.xml_path or str(resolved_model_xml())

    env = FullActuatorPositionEnv(
        xml_path=xml_path,
        max_steps=args.max_steps,
        reset_joint_noise=args.reset_joint_noise,
    )
    check_env(env, warn=True)
    env = Monitor(env)

    model = PPO(
        policy="MlpPolicy",
        env=env,
        n_steps=2048,
        batch_size=512,
        learning_rate=3e-4,
        gamma=0.99,
        verbose=1,
    )

    viewer_proc: subprocess.Popen | None = None
    if not args.no_viewer:
        viewer_proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "mujoco_rl_sim.scripts.watch_full_actuators",
                "--xml-path",
                xml_path,
                "--model-base",
                args.live_ckpt,
                "--max-steps",
                str(args.max_steps),
                "--reset-joint-noise",
                str(args.reset_joint_noise),
            ]
        )

    try:
        learned = 0
        while learned < args.total_timesteps:
            chunk = min(args.learn_chunk, args.total_timesteps - learned)
            model.learn(total_timesteps=chunk, reset_num_timesteps=False)
            learned += chunk
            model.save(args.live_ckpt)
            print(
                f"[train-full] learned {learned}/{args.total_timesteps} "
                f"(live checkpoint updated)"
            )

        model.save(args.final_ckpt)
        print(f"[train-full] saved final model: {args.final_ckpt}.zip")
    finally:
        env.close()
        if viewer_proc is not None:
            viewer_proc.terminate()


if __name__ == "__main__":
    main()
