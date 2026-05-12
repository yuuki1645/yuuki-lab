# type: ignore

"""連番 002: PPO で ``Env002FullActuators`` を学習。

オプション:
- ``--training-viewer``: 学習に使っている **同一** ``MjData`` を MuJoCo passive Viewer で表示し、
  各環境ステップで ``viewer.sync()``。Robotics Hub テレメトリと画面が一致する。
- （従来）子プロセス ``watch_full_actuators``: 別シミュレーションでチェックポイント再生（ ``--no-viewer`` で抑止）。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import mujoco.viewer
from mujoco_rl_sim.envs.env_002_full_actuators import Env002FullActuators
from mujoco_rl_sim.telemetry import RlTelemetryServer, RlTelemetryWrapper
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.env_checker import check_env
from stable_baselines3.common.monitor import Monitor
import mujoco_sim_assets


# 学習に使う MJCF（別モデルにしたいときはこの定数だけ書き換え）
_ASSETS_ROOT = Path(mujoco_sim_assets.__file__).resolve().parent
TRAIN_MJCF_XML: Path | str = _ASSETS_ROOT / "xmls" / "002_leg_freejoint" / "main.xml"


class _SyncTrainingViewerCallback(BaseCallback):
    """学習環境の ``mj_step`` のたびに passive Viewer を同期する。"""

    def __init__(self, viewer: mujoco.viewer.Handle, verbose: int = 0) -> None:
        super().__init__(verbose)
        self._viewer = viewer

    def _on_step(self) -> bool:
        self._viewer.sync()
        return True


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Env002FullActuators（全 position アクチュエータ）を PPO で学習"
    )
    p.add_argument("--max-steps", type=int, default=500, help="1 エピソード上限ステップ")
    p.add_argument(
        "--reset-joint-noise",
        type=float,
        default=0.05,
        help="リセット時の関節ノイズ（Env002FullActuators の引数）",
    )
    p.add_argument(
        "--step-wall-sleep",
        type=float,
        default=0.0,
        help=(
            "各環境ステップの MuJoCo 更新後に待つ秒数（壁時計）。テレメトリや挙動確認用。"
            "例: 0.05 でおおよそ 20 steps/s 以下。0 で従来どおり最大速。"
        ),
    )
    p.add_argument(
        "--max-logical-delta-fraction",
        type=float,
        default=0.1,
        help=(
            "1 ステップあたりの論理角差分の上限（各関節の論理レンジ幅に対する比率）。"
            "action=±1 で ±(この値)×レンジ幅まで動かす。"
        ),
    )
    p.add_argument("--total-timesteps", type=int, default=100_000)
    p.add_argument("--learn-chunk", type=int, default=10_000)
    p.add_argument(
        "--live-ckpt",
        default="ppo_full_actuators_live",
        help="学習中に上書き保存するベース名（.zip は付けない）",
    )
    p.add_argument(
        "--final-ckpt",
        default="ppo_full_actuators",
        help="学習完了時に保存するベース名（.zip は付けない）",
    )
    p.add_argument(
        "--training-viewer",
        action="store_true",
        help=(
            "学習環境と同一の MjData を MuJoCo Viewer で表示し、各ステップで同期する。"
            "テレメトリと画面が一致する。指定時は別プロセスの watch_full_actuators は起動しない。"
        ),
    )
    p.add_argument(
        "--no-viewer",
        action="store_true",
        help=(
            "別プロセスのライブ Viewer（watch_full_actuators）を起動しない。"
            "--training-viewer とは独立（組み合わせ可能で、その場合は内蔵 Viewer のみ）。"
        ),
    )
    p.add_argument(
        "--no-telemetry",
        action="store_true",
        help="Robotics Hub 向け Socket.IO テレメトリサーバを起動しない",
    )
    p.add_argument(
        "--telemetry-host",
        default="0.0.0.0",
        help=(
            "テレメトリ Socket.IO の bind アドレス。既定は全インターフェース（Hub が "
            "http://<LANのIP>:8791 のときに接続できるようにする）。ローカルのみにしたいときは "
            "127.0.0.1 を指定。"
        ),
    )
    p.add_argument(
        "--telemetry-port",
        type=int,
        default=8791,
        help="テレメトリ Socket.IO のポート（Hub の VITE_TELEMETRY_SOCKET_URL と合わせる）",
    )
    p.add_argument(
        "--telemetry-max-hz",
        type=float,
        default=60.0,
        help="ステップイベントの最大送信レート（0 で無制限）",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    xml_path = str(TRAIN_MJCF_XML)

    env = Env002FullActuators(
        xml_path=xml_path,
        max_steps=args.max_steps,
        reset_joint_noise=args.reset_joint_noise,
        step_wall_sleep_sec=args.step_wall_sleep,
        max_logical_delta_fraction=args.max_logical_delta_fraction,
    )
    if args.step_wall_sleep > 0.0:
        print(
            f"[train-full] step_wall_sleep={args.step_wall_sleep}s / env step "
            "(壁時計ベースで遅延。本番学習では 0 推奨)"
        )
    check_env(env, warn=True)

    telemetry_server: RlTelemetryServer | None = None
    telemetry_wr: RlTelemetryWrapper | None = None
    if not args.no_telemetry:
        telemetry_server = RlTelemetryServer(
            host=args.telemetry_host,
            port=args.telemetry_port,
            set_step_wall_sleep_sec=env.set_step_wall_sleep_sec,
            get_step_wall_sleep_sec=env.get_step_wall_sleep_sec,
        )
        telemetry_server.start()
        max_hz = args.telemetry_max_hz
        if max_hz <= 0:
            max_hz = None
        env = RlTelemetryWrapper(
            env,
            telemetry_server.publish_step,
            telemetry_server.publish_reset,
            max_hz=max_hz,
        )
        telemetry_wr = env
        if str(args.telemetry_host) in ("0.0.0.0", "::", "::0"):
            print(
                f"[train-full] RL telemetry Socket.IO: bind {args.telemetry_host}:"
                f"{args.telemetry_port}（Hub は http://<このPCのLAN-IP>:"
                f"{args.telemetry_port} などで接続）"
            )
        else:
            print(
                f"[train-full] RL telemetry Socket.IO: "
                f"http://{args.telemetry_host}:{args.telemetry_port}"
            )

    env = Monitor(env)

    model = PPO(
        policy="MlpPolicy",
        env=env,
        n_steps=2048,
        batch_size=512,
        learning_rate=3e-4,
        gamma=0.99,
        verbose=1,
    )

    if telemetry_wr is not None:
        telemetry_wr.set_num_timesteps_getter(lambda: int(model.num_timesteps))

    viewer_proc: subprocess.Popen | None = None
    # --training-viewer のときは学習本体と同一シミュなので子プロセス Viewer は使わない
    if not args.no_viewer and not args.training_viewer:
        viewer_cmd = [
            sys.executable,
            "-m",
            "mujoco_rl_sim.scripts.watch_full_actuators",
            "--xml-path",
            xml_path,
            "--model-base",
            args.live_ckpt,
            "--max-steps",
            str(args.max_steps),
            "--reset-joint-noise",
            str(args.reset_joint_noise),
            "--step-wall-sleep",
            str(args.step_wall_sleep),
            "--max-logical-delta-fraction",
            str(args.max_logical_delta_fraction),
        ]
        if not args.no_telemetry:
            viewer_cmd.extend(
                [
                    "--telemetry-config-url",
                    f"http://127.0.0.1:{args.telemetry_port}/api/rl_telemetry/config",
                ]
            )
        viewer_proc = subprocess.Popen(viewer_cmd)

    inner = env.unwrapped
    if not isinstance(inner, Env002FullActuators):
        raise RuntimeError(
            "内部環境が Env002FullActuators ではありません（ラッパー構成を確認してください）"
        )

    if args.training_viewer:
        print(
            "[train-full] training-viewer: 学習と同一 MjData を Viewer に表示します "
            "（テレメトリと一致）。子プロセス watch_full_actuators は起動していません。"
        )

    def run_training_chunks(callback: BaseCallback | None) -> None:
        learned = 0
        while learned < args.total_timesteps:
            chunk = min(args.learn_chunk, args.total_timesteps - learned)
            model.learn(
                total_timesteps=chunk,
                reset_num_timesteps=False,
                callback=callback,
            )
            learned += chunk
            model.save(args.live_ckpt)
            print(
                f"[train-full] learned {learned}/{args.total_timesteps} "
                f"(live checkpoint updated)"
            )

        model.save(args.final_ckpt)
        print(f"[train-full] saved final model: {args.final_ckpt}.zip")

    try:
        if args.training_viewer:
            with mujoco.viewer.launch_passive(inner.model, inner.data) as viewer:
                cb = _SyncTrainingViewerCallback(viewer)
                run_training_chunks(cb)
        else:
            run_training_chunks(None)
    finally:
        env.close()
        if viewer_proc is not None:
            viewer_proc.terminate()
        if telemetry_server is not None:
            telemetry_server.stop()


if __name__ == "__main__":
    main()
