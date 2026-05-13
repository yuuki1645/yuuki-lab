# type: ignore
"""
006 で ``--ckpt`` 保存した **PPO の .zip** を読み込み、**passive viewer** で方策を再生する。

観測・行動・MJCF は ``mujoco_test_006.ForwardXOneActuatorEnv`` と同一である必要があります。

例::

  cd mujoco-sim/programs
  python mujoco_test_007.py --model ppo_006.zip

依存: ``pip install -e ".[rl]"``（006 と同じ）
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

_SIM_ROOT = Path(__file__).resolve().parents[1]
if str(_SIM_ROOT) not in sys.path:
    sys.path.insert(0, str(_SIM_ROOT))

import mujoco.viewer  # noqa: E402
import numpy as np  # noqa: E402

try:
    from stable_baselines3 import PPO  # noqa: E402

    from mujoco_test_006 import ForwardXOneActuatorEnv  # noqa: E402
except ImportError as e:
    raise SystemExit(
        "stable-baselines3 / gymnasium / mujoco_test_006 が必要です。\n"
        "  cd mujoco-sim && pip install -e \".[rl]\""
    ) from e


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument(
        "--model",
        type=str,
        required=True,
        help="006 で保存したチェックポイント（例: ppo_006.zip）",
    )
    p.add_argument(
        "--xml",
        type=str,
        default=str(_SIM_ROOT / "mujoco_sim_assets/xmls/004_leg_1joint/main.xml"),
        help="学習時と同じ MJCF を指定",
    )
    p.add_argument(
        "--max-episode-steps",
        type=int,
        default=400,
        help="環境の 1 エピソード上限（006 の --max-episode-steps と揃える）",
    )
    p.add_argument("--seed", type=int, default=0, help="最初の reset の乱数シード")
    p.add_argument(
        "--stochastic",
        action="store_true",
        help="推論を非決定論的にする（既定は deterministic）",
    )
    p.add_argument(
        "--pause",
        type=float,
        default=None,
        metavar="SEC",
        help="各ステップ後の sleep（秒）。省略時は MJCF の opt.timestep",
    )
    p.add_argument(
        "--print-every",
        type=int,
        default=0,
        help="N ステップごとに vx と累積報酬を表示（0 で無効）",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    model_path = Path(args.model).expanduser().resolve()
    if not model_path.is_file():
        raise SystemExit(f"[007] ファイルが見つかりません: {model_path}")

    rng = np.random.default_rng(args.seed)
    env = ForwardXOneActuatorEnv(
        args.xml,
        max_episode_steps=args.max_episode_steps,
        rng=rng,
    )

    rl = PPO.load(str(model_path), device="cpu", print_system_info=False)

    pause_s = float(env.model.opt.timestep) if args.pause is None else max(0.0, args.pause)

    obs, _ = env.reset(seed=args.seed)
    ep_ret = 0.0
    step_i = 0
    root_dof_adr = int(env.model.jnt_dofadr[0])

    print(f"[007] loaded {model_path}")
    print("[007] ビュワーを閉じると終了します。")

    with mujoco.viewer.launch_passive(env.model, env.data) as viewer:
        while viewer.is_running():
            act, _ = rl.predict(obs, deterministic=not args.stochastic)
            obs, r, terminated, truncated, _ = env.step(act)
            ep_ret += float(r)
            step_i += 1

            if args.print_every > 0 and step_i % args.print_every == 0:
                vx = float(env.data.qvel[root_dof_adr + 3])
                print(f"[007] step={step_i} vx={vx:.4f} ep_return={ep_ret:.3f}")

            viewer.sync()
            if pause_s > 0.0:
                time.sleep(pause_s)

            if terminated or truncated:
                print(f"[007] episode end (ret={ep_ret:.3f}, steps={step_i})")
                obs, _ = env.reset(seed=None)
                ep_ret = 0.0
                step_i = 0


if __name__ == "__main__":
    main()
