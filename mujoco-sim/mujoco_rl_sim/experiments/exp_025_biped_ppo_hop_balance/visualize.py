from __future__ import annotations

from _paths import install

install()

import argparse
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import mujoco
from mujoco_sim_common.viewer_visual_presets import (
  apply_model_visual_preset,
  apply_passive_viewer_options,
)

import checkpoint
import config
from agent import AgentPPO
from env import EnvBipedPPO
from package_meta import CHECKPOINT_REL_FROM_EXP
from warmup import (
  WarmupContext,
  episode_sim_elapsed_s,
  in_episode_warmup,
  resolve_warmup_action,
)

__doc__ = f"""MuJoCo モデルまたはチェックポイントをビューアで実時間再生する。

実行例（本フォルダで）:

  python visualize.py
  python visualize.py --checkpoint run_YYYYMMDD_HHMMSS/final.pt
  # チェックポイント相対パス基準: {CHECKPOINT_REL_FROM_EXP}/run_.../final.pt
"""

_EXP_DIR = Path(__file__).resolve().parent
ActionFn = Callable[[Any], tuple[float, ...]]


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
    print("[visualize] mode: xml only (biped model, keyframe stand, ctrl from keyframe)")
    print(f"[visualize] xml: {config.XML_PATH}")
    return None

  ckpt_path = _resolve_checkpoint(args.checkpoint)
  agent = AgentPPO.from_checkpoint(ckpt_path, map_location=args.device)
  payload = getattr(agent, "checkpoint_payload", None) or {}
  _print_checkpoint_info(ckpt_path, payload)
  if args.stochastic:
    print("[visualize] policy: stochastic (act)")
    return lambda obs: agent.act(obs)[0]
  print("[visualize] policy: deterministic (act_eval)")
  return agent.act_eval


def _reset_biped_stand(model: mujoco.MjModel, data: mujoco.MjData) -> None:
  """keyframe stand があれば適用。無ければ mj_resetData。"""
  key_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "stand")
  if key_id >= 0:
    mujoco.mj_resetDataKeyframe(model, data, key_id)
  else:
    mujoco.mj_resetData(model, data)
  mujoco.mj_forward(model, data)


def _launch_biped_viewer() -> tuple[mujoco.MjModel, mujoco.MjData, mujoco.viewer.Handle]:
  model = mujoco.MjModel.from_xml_path(config.XML_PATH)
  apply_model_visual_preset(model)
  physics_dt = float(model.opt.timestep)
  if abs(physics_dt - config.PHYSICS_TIMESTEP_S) > 1e-9:
    raise ValueError(
      f"model.opt.timestep={physics_dt} != config.PHYSICS_TIMESTEP_S="
      f"{config.PHYSICS_TIMESTEP_S}"
    )
  data = mujoco.MjData(model)
  viewer = mujoco.viewer.launch_passive(model, data)
  apply_passive_viewer_options(viewer)
  return model, data, viewer


def _step_physics_only(
  model: mujoco.MjModel,
  data: mujoco.MjData,
  viewer: mujoco.viewer.Handle,
) -> None:
  for _ in range(config.FRAME_SKIP):
    mujoco.mj_step(model, data)
    viewer.sync()
  time.sleep(config.CONTROL_TIMESTEP_S)


def _run_biped_xml_only(*, print_every: int) -> None:
  model, data, viewer = _launch_biped_viewer()
  _reset_biped_stand(model, data)
  viewer.sync()
  print(
    f"[visualize] actuators: {model.nu} | "
    f"feet z: L={data.site('foot_site').xpos[2]:.3f} "
    f"R={data.site('right_foot_site').xpos[2]:.3f}"
  )
  step = 0
  try:
    while viewer.is_running():
      _step_physics_only(model, data, viewer)
      step += 1
      if print_every > 0 and step % print_every == 0:
        imu_z = float(data.site("imu_site").xpos[2])
        print(
          f"[visualize] step={step} imu_z={imu_z:.3f} "
          f"ctrl={data.ctrl.copy()}"
        )
  finally:
    viewer.close()


def _step_physics_only_env(env: EnvBipedPPO) -> None:
  """ctrl を書き換えず、物理ステップのみ進める（reset 後の ctrl=0 を維持）。"""
  for _ in range(config.FRAME_SKIP):
    mujoco.mj_step(env.model, env.data)
    if env.viewer is not None:
      env.viewer.sync()
  time.sleep(config.CONTROL_TIMESTEP_S)


def _run_physics_only(
  env: EnvBipedPPO,
  *,
  print_every: int,
) -> None:
  env.reset()
  step = 0

  while env.viewer.is_running():
    _step_physics_only_env(env)
    step += 1

    if print_every > 0 and step % print_every == 0:
      imu_z = float(env.data.site("imu_site").xpos[2])
      print(
        f"[visualize] step={step} imu_z={imu_z:.3f} "
        f"ctrl={env.data.ctrl.copy()}"
      )


def _run_episodes(
  env: EnvBipedPPO,
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
          f"elapsed_s={elapsed_s:.3f} action_dim={len(action)} "
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

  print("[visualize] ビューアを閉じると終了します。")
  print(
    f"[visualize] 制御レート: {config.CONTROL_HZ} Hz "
    f"({config.CONTROL_TIMESTEP_S:.3f} s/step)"
  )

  if action_fn is None:
    _run_biped_xml_only(print_every=args.print_every)
    print("[visualize] finished")
    return

  env = EnvBipedPPO(enable_viewer=True)
  if env.viewer is None:
    raise SystemExit("[visualize] MuJoCo ビューアを起動できませんでした。")

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
