# type: ignore

from stable_baselines3 import PPO
from stable_baselines3.common.env_checker import check_env
from stable_baselines3.common.monitor import Monitor

from mujoco_rl_env_simple import KneeTrackEnv


def main():
    env = KneeTrackEnv(xml_path="xmls/main.xml", max_steps=500)
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
    model.learn(total_timesteps=50_000)
    model.save("ppo_knee_track")
    env.close()


if __name__ == "__main__":
    main()
