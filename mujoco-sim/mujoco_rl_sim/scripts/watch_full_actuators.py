# type: ignore

"""学習中チェックポイントを読み直しながら ``Env002FullActuators`` を Viewer で表示。"""

from __future__ import annotations

import argparse
import json
import os
import time
from urllib.error import URLError
from urllib.request import urlopen

import mujoco.viewer
import numpy as np
from mujoco_sim_assets.paths import resolved_model_xml
from mujoco_rl_sim.envs.env_002_full_actuators import Env002FullActuators
from stable_baselines3 import PPO


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="全アクチュエータ学習のライブ Viewer")
    p.add_argument(
        "--xml-path",
        type=str,
        default=None,
        help="MJCF（省略時は mujoco_sim_assets の既定）",
    )
    p.add_argument(
        "--model-base",
        type=str,
        default="ppo_full_actuators_live",
        help="PPO.load に渡すベース名（.zip 省略可）",
    )
    p.add_argument("--max-steps", type=int, default=500)
    p.add_argument(
        "--reset-joint-noise",
        type=float,
        default=0.05,
        help="環境リセットの関節ノイズ（学習スクリプトと揃える）",
    )
    p.add_argument(
        "--step-wall-sleep",
        type=float,
        default=0.0,
        help="各 step 後の壁時計待ち秒（学習の --step-wall-sleep と揃える）",
    )
    p.add_argument(
        "--telemetry-config-url",
        type=str,
        default="",
        help="学習側 telemetry の config API URL（指定時は step-wall-sleep を定期同期）",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    xml_path = args.xml_path or str(resolved_model_xml())
    model_zip = (
        args.model_base if args.model_base.endswith(".zip") else f"{args.model_base}.zip"
    )

    env = Env002FullActuators(
        xml_path=xml_path,
        max_steps=args.max_steps,
        reset_joint_noise=args.reset_joint_noise,
        step_wall_sleep_sec=args.step_wall_sleep,
    )
    obs, _ = env.reset()
    model = None
    last_mtime = -1.0
    cfg_url = str(args.telemetry_config_url).strip()
    last_cfg_poll_t = 0.0
    cfg_poll_interval_sec = 0.5
    last_synced_sleep: float | None = None

    with mujoco.viewer.launch_passive(env.model, env.data) as viewer:
        while viewer.is_running():
            now = time.time()
            if cfg_url and now - last_cfg_poll_t >= cfg_poll_interval_sec:
                last_cfg_poll_t = now
                try:
                    with urlopen(cfg_url, timeout=0.3) as resp:
                        raw = resp.read()
                    payload = json.loads(raw.decode("utf-8"))
                    v = payload.get("step_wall_sleep_sec")
                    if isinstance(v, (int, float)):
                        v_num = max(0.0, float(v))
                        if last_synced_sleep is None or abs(v_num - last_synced_sleep) > 1e-9:
                            env.set_step_wall_sleep_sec(v_num)
                            last_synced_sleep = v_num
                except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
                    pass

            if os.path.exists(model_zip):
                mtime = os.path.getmtime(model_zip)
                if mtime > last_mtime:
                    try:
                        model = PPO.load(args.model_base)
                        last_mtime = mtime
                        print("[viewer-full] loaded latest checkpoint")
                    except Exception as e:
                        print(f"[viewer-full] checkpoint load failed: {e}")

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
