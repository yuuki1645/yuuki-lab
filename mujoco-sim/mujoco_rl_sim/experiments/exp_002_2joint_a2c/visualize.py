"""exp_002: チェックポイントを MuJoCo ビューアで実時間再生する。

実行例（mujoco-sim ディレクトリから）:

  python -m mujoco_rl_sim.experiments.exp_002_2joint_a2c.visualize \\
    --checkpoint mujoco_rl_sim/experiments/exp_002_2joint_a2c/checkpoints/run_20260520_160244/final.pt

ビューアを閉じると終了する。エピソード終了後は自動で reset して再生を続ける。
"""

from __future__ import annotations

import argparse
from pathlib import Path

from mujoco_rl_sim.experiments.exp_002_2joint_a2c import checkpoint
from mujoco_rl_sim.experiments.exp_002_2joint_a2c import config
from mujoco_rl_sim.experiments.exp_002_2joint_a2c.agent import AgentExp002A2C
from mujoco_rl_sim.experiments.exp_002_2joint_a2c.env import EnvExp0022JointA2C

_EXP_DIR = Path(__file__).resolve().parent


def _parse_args() -> argparse.Namespace:
  p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
  p.add_argument(
    "--checkpoint",
    type=str,
    required=True,
    help="再生する .pt（例: checkpoints/run_YYYYMMDD_HHMMSS/final.pt）",
  )
  p.add_argument(
    "--stochastic",
    action="store_true",
    help="評価時も確率的に行動（既定は act_eval = 平均行動）",
  )
  p.add_argument(
    "--episodes",
    type=int,
    default=0,
    help="再生するエピソード数（0 でビューアを閉じるまで）",
  )
  p.add_argument(
    "--print-every",
    type=int,
    default=0,
    help="N 制御ステップごとに報酬などを表示（0 で無効）",
  )
  p.add_argument(
    "--device",
    type=str,
    default="cpu",
    help="torch.load の map_location（例: cpu, cuda:0）",
  )
  return p.parse_args()


def _resolve_checkpoint(path_str: str) -> Path:
  path = Path(path_str).expanduser()
  if not path.is_absolute():
    path = (_EXP_DIR / path).resolve()
  else:
    path = path.resolve()
  if not path.is_file():
    raise SystemExit(f"[visualize] チェックポイントが見つかりません: {path}")
  return path


def _print_checkpoint_info(path: Path, payload: dict) -> None:
  print(f"[visualize] checkpoint: {path}")
  print(
    f"[visualize] update={payload.get('update', '?')} | "
    f"env_steps={payload.get('total_env_steps', '?')} | "
    f"episodes={payload.get('episodes_finished', '?')} | "
    f"format={payload.get('format', '?')}"
  )


def main() -> None:
  args = _parse_args()
  ckpt_path = _resolve_checkpoint(args.checkpoint)
  payload = checkpoint.load_checkpoint(ckpt_path, map_location=args.device)
  _print_checkpoint_info(ckpt_path, payload)

  agent = AgentExp002A2C.from_checkpoint(ckpt_path, map_location=args.device)
  env = EnvExp0022JointA2C(enable_viewer=True)
  if env.viewer is None:
    raise SystemExit("[visualize] MuJoCo ビューアを起動できませんでした。")

  print("[visualize] ビューアを閉じると終了します。")
  print(
    f"[visualize] 制御レート: {config.CONTROL_HZ} Hz "
    f"({config.CONTROL_TIMESTEP_S:.3f} s/step)"
  )

  obs = env.reset()
  episode_step = 0
  episode_index = 0
  episode_return = 0.0

  try:
    while env.viewer.is_running():
      if args.stochastic:
        action, _ = agent.act(obs)
      else:
        action = agent.act_eval(obs)

      obs, reward, terminated, step_info = env.step(
        action,
        visualize=True,
        episode_step=episode_step,
      )

      episode_step += 1
      episode_return += float(reward)

      if args.print_every > 0 and episode_step % args.print_every == 0:
        print(
          f"[visualize] ep={episode_index + 1} step={episode_step} "
          f"reward={reward:8.4f} return={episode_return:8.3f} "
          f"upright={step_info['upright']:.3f} "
          f"reason={step_info['termination_reason']!r}"
        )

      truncated = episode_step >= config.MAX_STEPS_PER_EPISODE
      done = terminated or truncated
      if not done:
        continue

      print(
        f"[visualize] episode {episode_index + 1} end | "
        f"return={episode_return:.3f} | steps={episode_step} | "
        f"terminated={terminated} | truncated={truncated} | "
        f"reason={step_info['termination_reason']!r}"
      )
      episode_index += 1
      if args.episodes > 0 and episode_index >= args.episodes:
        break

      obs = env.reset()
      episode_step = 0
      episode_return = 0.0
  finally:
    print(f"[visualize] finished ({episode_index} episode(s) played)")


if __name__ == "__main__":
  main()
