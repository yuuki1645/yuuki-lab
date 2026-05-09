# type: ignore

import time
import mujoco.viewer
from stable_baselines3 import PPO

from mujoco_rl_env_simple import KneeTrackEnv


def main():
    env = KneeTrackEnv(xml_path="xmls/main.xml", max_steps=500)
    model = PPO.load("ppo_knee_track")

    # Reuse env's model/data so viewer shows exactly what policy sees.
    with mujoco.viewer.launch_passive(env.model, env.data) as viewer:
        obs, _ = env.reset()
        while viewer.is_running():
            action, _ = model.predict(obs, deterministic=True)
            obs, _, terminated, truncated, _ = env.step(action)
            viewer.sync()
            time.sleep(env.model.opt.timestep)

            if terminated or truncated:
                obs, _ = env.reset()

    env.close()


if __name__ == "__main__":
    main()
