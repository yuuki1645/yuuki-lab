# type: ignore

import subprocess
import sys
from stable_baselines3 import PPO
from stable_baselines3.common.env_checker import check_env
from stable_baselines3.common.monitor import Monitor

from mujoco_rl_env_simple import KneeTrackEnv


def main():
    xml_path = "xmls/main.xml"
    total_timesteps = 50_000
    learn_chunk = 5_000
    live_ckpt_base = "ppo_knee_track_live"
    final_model_base = "ppo_knee_track"

    env = KneeTrackEnv(xml_path=xml_path, max_steps=500)
    check_env(env, warn=True)
    env = Monitor(env)

    model = PPO(
        policy="MlpPolicy",
        env=env,
        n_steps=1024,
        batch_size=256,
        learning_rate=3e-4,
        gamma=0.99,
        verbose=1,
    )

    viewer_proc = subprocess.Popen(
        [
            sys.executable,
            "watch_training_live.py",
            "--xml-path",
            xml_path,
            "--model-base",
            live_ckpt_base,
        ]
    )

    try:
        learned = 0
        while learned < total_timesteps:
            chunk = min(learn_chunk, total_timesteps - learned)
            model.learn(total_timesteps=chunk, reset_num_timesteps=False)
            learned += chunk
            model.save(live_ckpt_base)
            print(f"[train] learned {learned}/{total_timesteps} (live checkpoint updated)")

        model.save(final_model_base)
        print(f"[train] saved final model: {final_model_base}.zip")
    finally:
        env.close()
        viewer_proc.terminate()


if __name__ == "__main__":
    main()
