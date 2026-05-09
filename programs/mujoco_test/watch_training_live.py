# type: ignore

import argparse
import os
import time

import mujoco.viewer
import numpy as np
from stable_baselines3 import PPO

from mujoco_rl_env_simple import KneeTrackEnv


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--xml-path", type=str, default="xmls/main.xml")
    parser.add_argument("--model-base", type=str, default="ppo_knee_track_live")
    return parser.parse_args()


def main():
    args = parse_args()
    model_zip = args.model_base if args.model_base.endswith(".zip") else f"{args.model_base}.zip"

    env = KneeTrackEnv(xml_path=args.xml_path, max_steps=500)
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
