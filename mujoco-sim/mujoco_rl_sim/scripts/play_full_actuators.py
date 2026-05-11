# type: ignore

"""学習済み PPO を ``Env002FullActuators`` 上で MuJoCo Viewer 再生。"""

from __future__ import annotations

import argparse
import time

import mujoco.viewer
from mujoco_sim_assets.paths import resolved_model_xml
from mujoco_rl_sim.envs.env_002_full_actuators import Env002FullActuators
from stable_baselines3 import PPO


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="全アクチュエータ学習済みモデルを Viewer で再生"
    )
    p.add_argument(
        "--model-base",
        default="ppo_full_actuators",
        help="PPO.load に渡すベース名（.zip 省略可）",
    )
    p.add_argument(
        "--xml-path",
        default=None,
        help="MJCF（省略時は mujoco_sim_assets の既定）",
    )
    p.add_argument("--max-steps", type=int, default=500)
    p.add_argument("--reset-joint-noise", type=float, default=0.05)
    p.add_argument(
        "--step-wall-sleep",
        type=float,
        default=0.0,
        help="各 step 後の壁時計待ち秒（テスト再生を遅くする）",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    xml_path = args.xml_path or str(resolved_model_xml())
    env = Env002FullActuators(
        xml_path=xml_path,
        max_steps=args.max_steps,
        reset_joint_noise=args.reset_joint_noise,
        step_wall_sleep_sec=args.step_wall_sleep,
    )
    model = PPO.load(args.model_base)

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
