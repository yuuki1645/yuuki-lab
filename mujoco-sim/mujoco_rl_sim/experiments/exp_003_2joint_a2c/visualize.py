from __future__ import annotations

import argparse
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import mujoco

from . import checkpoint
from . import config
from .agent import AgentA2C
from .env import Env2JointA2C
from .package_meta import EXP_NAME, PACKAGE
from .warmup import (
  WarmupContext,
  episode_sim_elapsed_s,
  in_episode_warmup,
  resolve_warmup_action,
)

__doc__ = f"""MuJoCo モデルまたはチェックポイントをビューアで実時間再生する。

実行例（mujoco-sim ディレクトリから）:

  python -m {PACKAGE}.visualize
  python -m {PACKAGE}.visualize --checkpoint runs/{EXP_NAME}/run_YYYYMMDD_HHMMSS/final.pt
"""

_EXP_DIR = Path(__file__).resolve().parent
ActionFn = Callable[[Any], tuple[float, float]]


def _parse_args() -> argparse.Namespace:
  p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
  p.add_argument(
    "--checkpoint",
    type=str,
    default=None,
    help="再生する .pt。省略時は model/main.xml のみ（ctrl 無操作）",
  )
  p.add_argument(
    "--stochastic",
    action="store_true",
    help="評価時も確率的に行動（--checkpoint 指定時のみ。既定は act_eval）",
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
    help="torch.load の map_location（--checkpoint 指定時のみ）",
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


def _print_warmup_config() -> None:
  steps = int(config.WARMUP_DURATION_S / config.CONTROL_TIMESTEP_S)
  print(
    f"[visualize] warmup: {config.WARMUP_DURATION_S:.3f}s sim-time "
    f"({steps} steps @ {config.CONTROL_HZ} Hz), "
    f"action_fn={config.WARMUP_ACTION_FN.__name__}"
  )


def _make_action_fn(args: argparse.Namespace) -> ActionFn | None:
  if args.checkpoint is None:
    print("[visualize] mode: xml only (no policy, ctrl untouched)")
    print(f"[visualize] xml: {config.XML_PATH}")
    return None

  ckpt_path = _resolve_checkpoint(args.checkpoint)
  payload = checkpoint.load_checkpoint(ckpt_path, map_location=args.device)
  _print_checkpoint_info(ckpt_path, payload)

  agent = AgentA2C.from_checkpoint(ckpt_path, map_location=args.device)
  if args.stochastic:
    return lambda obs: agent.act(obs)[0]
  return agent.act_eval


def _step_physics_only(env: Env2JointA2C) -> None:
  """ctrl を書き換えず、物理ステップのみ進める（reset 後の ctrl=0 を維持）。"""
  for _ in range(config.FRAME_SKIP):
    mujoco.mj_step(env.model, env.data)
    if env.viewer is not None:
      env.viewer.sync()
  time.sleep(config.CONTROL_TIMESTEP_S)


def _run_physics_only(
  env: Env2JointA2C,
  *,
  print_every: int,
) -> None:
  env.reset()
  step = 0

  while env.viewer.is_running():
    _step_physics_only(env)
    step += 1

    if print_every > 0 and step % print_every == 0:
      imu_z = float(env.data.site("imu_site").xpos[2])
      print(
        f"[visualize] step={step} imu_z={imu_z:.3f} "
        f"ctrl={env.data.ctrl.copy()}"
      )


def _run_episodes(
  env: Env2JointA2C,
  action_fn: ActionFn,
  *,
  max_episodes: int,
  print_every: int,
) -> int:
  obs = env.reset()
  episode_step = 0
  episode_index = 0
  episode_return = 0.0
  total_env_steps = 0
  use_warmup = config.WARMUP_ENABLED
  warmup_announced = False

  while env.viewer.is_running():
    if use_warmup and in_episode_warmup(episode_step):
      elapsed_s = episode_sim_elapsed_s(episode_step)
      action = resolve_warmup_action(
        config.WARMUP_ACTION_FN,
        WarmupContext(
          obs=obs,
          elapsed_s=elapsed_s,
          total_env_steps=total_env_steps,
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
      total_env_steps += 1
      episode_return += float(reward)

      if print_every > 0 and episode_step % print_every == 0:
        print(
          f"[visualize] ep={episode_index + 1} step={episode_step} phase=warmup "
          f"elapsed_s={elapsed_s:.3f} action=({action[0]:+.3f}, {action[1]:+.3f}) "
          f"reward={reward:8.4f} return={episode_return:8.3f} "
          f"upright={step_info['upright']:.3f}"
        )

      truncated = episode_step >= config.MAX_STEPS_PER_EPISODE
      done = terminated or truncated
      if not done:
        continue

      print(
        f"[visualize] episode {episode_index + 1} end (during warmup) | "
        f"return={episode_return:.3f} | steps={episode_step} | "
        f"terminated={terminated} | truncated={truncated} | "
        f"reason={step_info['termination_reason']!r}"
      )
      episode_index += 1
      if max_episodes > 0 and episode_index >= max_episodes:
        break
      obs = env.reset()
      episode_step = 0
      episode_return = 0.0
      warmup_announced = False
      continue

    if use_warmup and not warmup_announced and episode_step > 0:
      print(
        f"[visualize] ep={episode_index + 1} warmup done at step={episode_step}, "
        "policy phase"
      )
      warmup_announced = True

    action = action_fn(obs)
    obs, reward, terminated, step_info = env.step(
      action,
      visualize=True,
      episode_step=episode_step,
    )

    episode_step += 1
    total_env_steps += 1
    episode_return += float(reward)

    if print_every > 0 and episode_step % print_every == 0:
      print(
        f"[visualize] ep={episode_index + 1} step={episode_step} phase=policy "
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
    if max_episodes > 0 and episode_index >= max_episodes:
      break

    obs = env.reset()
    episode_step = 0
    episode_return = 0.0
    warmup_announced = False

  return episode_index


def main() -> None:
  args = _parse_args()
  action_fn = _make_action_fn(args)
  env = Env2JointA2C(enable_viewer=True)
  if env.viewer is None:
    raise SystemExit("[visualize] MuJoCo ビューアを起動できませんでした。")

  print("[visualize] ビューアを閉じると終了します。")
  print(
    f"[visualize] 制御レート: {config.CONTROL_HZ} Hz "
    f"({config.CONTROL_TIMESTEP_S:.3f} s/step)"
  )

  if action_fn is None:
    _run_physics_only(env, print_every=args.print_every)
    print("[visualize] finished")
    return

  if config.WARMUP_ENABLED:
    _print_warmup_config()
  else:
    print("[visualize] warmup: disabled (config.WARMUP_ENABLED=False)")

  episode_index = _run_episodes(
    env,
    action_fn,
    max_episodes=args.episodes,
    print_every=args.print_every,
  )
  print(f"[visualize] finished ({episode_index} episode(s) played)")


if __name__ == "__main__":
  main()
