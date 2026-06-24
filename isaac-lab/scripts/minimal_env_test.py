# Minimal env test with explicit error reporting
import argparse
import traceback

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser()
parser.add_argument("--num_envs", type=int, default=1)
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
app = AppLauncher(args).app

import gymnasium as gym
import torch

import yuuki_isaac_lab.tasks  # noqa: F401
from isaaclab_tasks.utils import parse_env_cfg


def main() -> None:
    try:
        cfg = parse_env_cfg("YuukiLab-BipedPpoWalk-Direct-v0", device=args.device, num_envs=args.num_envs)
        print("[TEST] creating env...", flush=True)
        env = gym.make("YuukiLab-BipedPpoWalk-Direct-v0", cfg=cfg)
        print("[TEST] env created", flush=True)
        env.reset()
        print("[TEST] reset ok", flush=True)
        unwrapped = env.unwrapped
        for step in range(10):
            env.step(torch.zeros(env.action_space.shape, device=unwrapped.device))
            if unwrapped._last_physics:
                p = unwrapped._last_physics
                print(
                    f"[TEST step {step}] imu_z={p['imu_z'].mean():.3f} "
                    f"Lcontact={p['left_on_floor'].float().mean():.0f} "
                    f"Rcontact={p['right_on_floor'].float().mean():.0f} "
                    f"ss={unwrapped._last_biped_ctx.single_support.float().mean():.0f}",
                    flush=True,
                )
        print("[TEST] PASS", flush=True)
        env.close()
    except Exception:
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
    app.close()
