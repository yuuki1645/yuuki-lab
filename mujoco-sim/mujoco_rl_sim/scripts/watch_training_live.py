# type: ignore

"""学習中に保存されるチェックポイントを読み直しながら ``KneeTrackEnv`` を Viewer で表示。"""

from __future__ import annotations

import argparse
import os
import time

import mujoco.viewer
import numpy as np
from mujoco_sim_assets.paths import resolved_model_xml
from mujoco_rl_sim import KneeTrackEnv
from stable_baselines3 import PPO


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="学習中チェックポイントのライブ Viewer")
    p.add_argument(
        "--xml-path",
        type=str,
        default=None,
        help="MJCF（省略時は mujoco_sim_assets の既定）",
    )
    p.add_argument(
        "--model-base",
        type=str,
        default="ppo_knee_track_live",
        help="PPO.load に渡すベース名（.zip 省略可）",
    )
    p.add_argument("--max-steps", type=int, default=500)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    xml_path = args.xml_path or str(resolved_model_xml())
    model_zip = (
        args.model_base if args.model_base.endswith(".zip") else f"{args.model_base}.zip"
    )

    env = KneeTrackEnv(xml_path=xml_path, max_steps=args.max_steps)
    obs, _ = env.reset()
    model = None
    last_mtime = -1.0

    with mujoco.viewer.launch_passive(env.model, env.data) as viewer:
        while viewer.is_running():
            if os.path.exists(model_zip):
                mtime = os.path.getmtime(model_zip)
                if mtime > last_mtime:
                    try:
                        model = PPO.load(args.model_base)
                        last_mtime = mtime
                        print("[viewer] loaded latest checkpoint")
                    except Exception as e:
                        print(f"[viewer] checkpoint load failed: {e}")

            if model is None:
                action = np.zeros(env.action_space.shape, dtype=np.float32)
            else:
                action, _ = model.predict(obs, deterministic=True)

            obs, _, terminated, truncated, _ = env.step(action)
            viewer.sync()
            time.sleep(env.model.opt.timestep)

            if terminated or truncated:
                obs, _ = env.reset()

    env.close()


if __name__ == "__main__":
    main()
