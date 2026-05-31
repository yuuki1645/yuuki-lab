"""exp_002: config.WARMUP_ACTION_FN を MuJoCo ビューアで実時間プレビューする。

train.py と同じ warmup 行動・期間（WARMUP_DURATION_S）を使う。方策は使わない。
config.WARMUP_ENABLED の有無は学習のみの設定で、本スクリプトには影響しない。

実行例（mujoco-sim ディレクトリから）:

  python -m preview_warmup

  python -m preview_warmup --episodes 5 --print-every 10

ビューアを閉じると終了する。各エピソードはウォームアップ区間のみ再生し、終了後に reset する。
"""


from __future__ import annotations

from _paths import install

install()

import argparse

import config
from env import EnvExp0022JointA2C
from warmup import (
  WarmupContext,
  episode_sim_elapsed_s,
  in_episode_warmup,
  resolve_warmup_action,
)


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


def _warmup_control_steps() -> int:
  return int(config.WARMUP_DURATION_S / config.CONTROL_TIMESTEP_S)


def _print_warmup_config() -> None:
  steps = _warmup_control_steps()
  print(
    f"[preview_warmup] action_fn={config.WARMUP_ACTION_FN.__name__} | "
    f"duration={config.WARMUP_DURATION_S:.3f}s sim-time "
    f"({steps} control steps @ {config.CONTROL_HZ} Hz)"
  )
  if not config.WARMUP_ENABLED:
    print(
      "[preview_warmup] note: config.WARMUP_ENABLED=False（学習では warmup 無効）。"
      " プレビューは WARMUP_ACTION_FN をそのまま再生します。"
    )


def _run_warmup_preview(
  env: EnvExp0022JointA2C,
  *,
  max_episodes: int,
  print_every: int,
) -> int:
  obs = env.reset()
  episode_step = 0
  episode_index = 0
  episode_return = 0.0

  while env.viewer.is_running():
    if not in_episode_warmup(episode_step):
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

    elapsed_s = episode_sim_elapsed_s(episode_step)
    action = resolve_warmup_action(
      config.WARMUP_ACTION_FN,
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
  _print_warmup_config()

  env = EnvExp0022JointA2C(enable_viewer=True)
  if env.viewer is None:
    raise SystemExit("[preview_warmup] MuJoCo ビューアを起動できませんでした。")

  print("[preview_warmup] ビューアを閉じると終了します。")
  print(
    f"[preview_warmup] 制御レート: {config.CONTROL_HZ} Hz "
    f"({config.CONTROL_TIMESTEP_S:.3f} s/step, 実時間 sleep)"
  )

  episode_index = _run_warmup_preview(
    env,
    max_episodes=args.episodes,
    print_every=args.print_every,
  )
  print(f"[preview_warmup] finished ({episode_index} episode(s) played)")


if __name__ == "__main__":
  main()
