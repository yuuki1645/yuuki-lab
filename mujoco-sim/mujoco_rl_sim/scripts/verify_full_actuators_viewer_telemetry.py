# type: ignore

"""学習検証用: 単一の ``Env002FullActuators`` に MuJoCo ビュワーを直結し、
その同一シミュレーションから Robotics Hub 向けテレメトリを送る。

高速 PPO 学習（``train_002_full_actuators``）とは別プロセス・別用途。
既定で ``step_wall_sleep_sec`` を正にして壁時計ベースで遅く進める。
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import mujoco.viewer
from stable_baselines3 import PPO

import mujoco_sim_assets
from mujoco_rl_sim.envs.env_002_full_actuators import Env002FullActuators
from mujoco_rl_sim.telemetry import RlTelemetryServer, RlTelemetryWrapper


_ASSETS_ROOT = Path(mujoco_sim_assets.__file__).resolve().parent
DEFAULT_ENV_MODEL_XML = _ASSETS_ROOT / "xmls" / "002_leg_freejoint" / "main.xml"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Env002FullActuators を低速で回し、同一 MjData を MuJoCo Viewer と "
            "Socket.IO テレメトリの両方に使う（検証・デバッグ向け）。"
        )
    )
    p.add_argument(
        "--xml-path",
        type=str,
        default=None,
        help="MJCF（省略時は 002_leg_freejoint/main.xml）",
    )
    p.add_argument(
        "--model-base",
        default="ppo_full_actuators",
        help="PPO.load に渡すベース名（.zip は省略可）",
    )
    p.add_argument("--max-steps", type=int, default=500, help="1 エピソードあたりの上限ステップ")
    p.add_argument(
        "--reset-joint-noise",
        type=float,
        default=0.05,
        help="リセット時の関節ノイズ（学習スクリプトと揃えるなら同値）",
    )
    p.add_argument(
        "--max-logical-delta-fraction",
        type=float,
        default=0.1,
        help="論理角差分の上限比率（学習環境と合わせる）",
    )
    p.add_argument(
        "--step-wall-sleep",
        type=float,
        default=0.15,
        help=(
            "各環境ステップの mj_step 直後に待つ秒数（既定 0.15 で低速化）。"
            "0 でシミュレーション自体は最大速（ただし Viewer 描画は別）。"
        ),
    )
    p.add_argument(
        "--viewer-extra-sleep",
        type=float,
        default=0.0,
        help="viewer.sync() のあとに追加で待つ秒数（さらに体感を遅くしたいとき）",
    )
    p.add_argument(
        "--stochastic",
        action="store_true",
        help="指定時は model.predict を確率的にする（既定は決定的）",
    )
    p.add_argument(
        "--telemetry-host",
        default="0.0.0.0",
        help="テレメトリ Socket.IO のバインドアドレス",
    )
    p.add_argument(
        "--telemetry-port",
        type=int,
        default=8791,
        help="テレメトリポート（Hub の VITE_TELEMETRY_SOCKET_URL と合わせる）",
    )
    p.add_argument(
        "--telemetry-max-hz",
        type=float,
        default=60.0,
        help="テレメトリ送信の最大レート（0 で無制限）",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    xml_path = str(Path(args.xml_path) if args.xml_path else DEFAULT_ENV_MODEL_XML)

    model_zip = (
        args.model_base
        if str(args.model_base).endswith(".zip")
        else f"{args.model_base}.zip"
    )
    if not Path(model_zip).is_file():
        print(
            f"[verify-full] チェックポイントが見つかりません: {model_zip}",
            file=sys.stderr,
        )
        sys.exit(1)

    env_core = Env002FullActuators(
        xml_path=xml_path,
        max_steps=args.max_steps,
        reset_joint_noise=args.reset_joint_noise,
        step_wall_sleep_sec=args.step_wall_sleep,
        max_logical_delta_fraction=args.max_logical_delta_fraction,
    )

    telemetry_server = RlTelemetryServer(
        host=args.telemetry_host,
        port=args.telemetry_port,
        set_step_wall_sleep_sec=env_core.set_step_wall_sleep_sec,
        get_step_wall_sleep_sec=env_core.get_step_wall_sleep_sec,
    )
    telemetry_server.start()

    max_hz = args.telemetry_max_hz
    if max_hz <= 0:
        max_hz = None

    env = RlTelemetryWrapper(
        env_core,
        telemetry_server.publish_step,
        telemetry_server.publish_reset,
        max_hz=max_hz,
    )

    eval_step = 0

    def _num_ts() -> int:
        return eval_step

    env.set_num_timesteps_getter(_num_ts)

    model = PPO.load(args.model_base)
    deterministic = not bool(args.stochastic)

    inner = env.unwrapped
    assert isinstance(inner, Env002FullActuators)

    print(
        f"[verify-full] Viewer + telemetry は同一 env（MjData 共有）。\n"
        f"  MJCF: {xml_path}\n"
        f"  model: {args.model_base}\n"
        f"  step_wall_sleep_sec={args.step_wall_sleep}, "
        f"viewer_extra_sleep={args.viewer_extra_sleep}\n"
        f"  telemetry: http://{args.telemetry_host}:{args.telemetry_port} "
        f"(Hub のテレメトリ URL と合わせる)\n"
        f"  predict: {'stochastic' if not deterministic else 'deterministic'}"
    )

    obs, _ = env.reset()
    extra = max(0.0, float(args.viewer_extra_sleep))

    try:
        with mujoco.viewer.launch_passive(inner.model, inner.data) as viewer:
            while viewer.is_running():
                action, _ = model.predict(obs, deterministic=deterministic)
                obs, _reward, terminated, truncated, _info = env.step(action)
                eval_step += 1
                viewer.sync()
                if extra > 0.0:
                    time.sleep(extra)

                if terminated or truncated:
                    obs, _ = env.reset()
    finally:
        env.close()
        telemetry_server.stop()


if __name__ == "__main__":
    main()
