from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
  sys.path.insert(0, str(_ROOT))

from _paths import install

install()

import argparse

from lib.load_run_context import default_ctx
from sim.env import EnvBipedPPO
from sim.warmup import (
  WarmupContext,
  default_warmup_action,
  episode_sim_elapsed_s,
  in_episode_warmup,
  resolve_warmup_action,
)

__doc__ = """training.warmup 設定を MuJoCo ビューアで実時間プレビューする。

実行例（本フォルダで）:

  python scripts/preview_warmup.py
"""


def _parse_args() -> argparse.Namespace:
  p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
  p.add_argument(
    "--episodes",
    type=int,
    default=0,
    help="再生するエピソード数（0 でビューアを閉じるまでループ）",
  )
  p.add_argument(
    "--print-every",
    type=int,
    default=0,
    help="N 制御ステップごとに行動・報酬などを表示（0 で無効）",
  )
  return p.parse_args()


def _warmup_control_steps(ctx) -> int:
  sim = ctx.cfg.sim
  return int(ctx.cfg.training.warmup_duration_s / sim.control_timestep_s)


def _print_warmup_config(ctx) -> None:
  sim = ctx.cfg.sim
  training = ctx.cfg.training
  steps = _warmup_control_steps(ctx)
  print(
    f"[preview_warmup] action_fn={default_warmup_action.__name__} | "
    f"duration={training.warmup_duration_s:.3f}s sim-time "
    f"({steps} control steps @ {sim.control_hz} Hz)"
  )
  if not training.warmup_enabled:
    print(
      "[preview_warmup] note: training.warmup_enabled=false（学習では warmup 無効）。"
      " プレビューは default_warmup_action をそのまま再生します。"
    )


def _run_warmup_preview(
  env: EnvBipedPPO,
  *,
  ctx,
  max_episodes: int,
  print_every: int,
) -> int:
  obs = env.reset()
  episode_step = 0
  episode_index = 0
  episode_return = 0.0

  while env.viewer.is_running():
    if not in_episode_warmup(episode_step, ctx):
      print(
        f"[preview_warmup] episode {episode_index + 1} warmup end | "
        f"return={episode_return:.3f} | steps={episode_step}"
      )
      episode_index += 1
      if max_episodes > 0 and episode_index >= max_episodes:
        break
      obs = env.reset()
      episode_step = 0
      episode_return = 0.0
      continue

    elapsed_s = episode_sim_elapsed_s(episode_step, ctx)
    action = resolve_warmup_action(
      default_warmup_action,
      WarmupContext(
        obs=obs,
        elapsed_s=elapsed_s,
        total_env_steps=0,
        episode_step=episode_step,
        episode_index=episode_index,
      ),
    )
    obs, reward, terminated, step_info = env.step(
      action,
      visualize=True,
      episode_step=episode_step,
    )

    episode_step += 1
    episode_return += float(reward)

    if print_every > 0 and episode_step % print_every == 0:
      print(
        f"[preview_warmup] ep={episode_index + 1} step={episode_step} "
        f"elapsed_s={elapsed_s:.3f} action=({action[0]:+.3f}, {action[1]:+.3f}) "
        f"reward={reward:8.4f} return={episode_return:8.3f} "
        f"upright={step_info['upright']:.3f}"
      )

    if terminated:
      print(
        f"[preview_warmup] episode {episode_index + 1} terminated early | "
        f"step={episode_step} reason={step_info['termination_reason']!r}"
      )
      episode_index += 1
      if max_episodes > 0 and episode_index >= max_episodes:
        break
      obs = env.reset()
      episode_step = 0
      episode_return = 0.0

  return episode_index


def main() -> None:
  args = _parse_args()
  ctx = default_ctx()
  _print_warmup_config(ctx)

  env = EnvBipedPPO(ctx, enable_viewer=True, training_dr_enabled=False)
  if env.viewer is None:
    raise SystemExit("[preview_warmup] MuJoCo ビューアを起動できませんでした。")

  sim = ctx.cfg.sim
  print("[preview_warmup] ビューアを閉じると終了します。")
  print(
    f"[preview_warmup] 制御レート: {sim.control_hz} Hz "
    f"({sim.control_timestep_s:.3f} s/step, 実時間 sleep)"
  )

  episode_index = _run_warmup_preview(
    env,
    ctx=ctx,
    max_episodes=args.episodes,
    print_every=args.print_every,
  )
  print(f"[preview_warmup] finished ({episode_index} episode(s) played)")


if __name__ == "__main__":
  main()
