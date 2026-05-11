# type: ignore

import argparse
import os
import time

import mujoco.viewer
import numpy as np
from mujoco_realtime_sim.paths import resolved_model_xml
from mujoco_rl_sim import KneeTrackEnv
from stable_baselines3 import PPO


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--xml-path",
        type=str,
        default=None,
        help="MJCF パス（省略時は mujoco_realtime_sim の既定）",
    )
    parser.add_argument("--model-base", type=str, default="ppo_knee_track_live")
    return parser.parse_args()


def main():
    args = parse_args()
    xml_path = args.xml_path or str(resolved_model_xml())
    model_zip = args.model_base if args.model_base.endswith(".zip") else f"{args.model_base}.zip"

    env = KneeTrackEnv(xml_path=xml_path, max_steps=500)
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
