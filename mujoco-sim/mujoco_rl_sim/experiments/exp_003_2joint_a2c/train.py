from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import checkpoint
from . import config
from . import wandb_logging
from .agent import AgentA2C
from .env import Env2JointA2C
from .package_meta import CHECKPOINT_ROOT, EXP_NAME, PACKAGE
from .warmup import (
  WarmupContext,
  episode_sim_elapsed_s,
  in_episode_warmup,
  resolve_warmup_action,
)

__doc__ = f"""2 関節脚 A2C 学習ループ。

実行例（mujoco-sim ディレクトリから）:

  python -m {PACKAGE}.train

チェックポイントから再開（新 run ディレクトリ・新 wandb run、学習率指定）:

  python -m {PACKAGE}.train \\
    --resume runs/{EXP_NAME}/run_YYYYMMDD_HHMMSS/update_005000.pt \\
    --lr 1e-4 \\
    --num-updates 1500

wandb を無効にする例:

  set WANDB_MODE=disabled
  python -m {PACKAGE}.train
"""


@dataclass(frozen=True)
class TrainRunConfig:
  """1 回の train 実行の設定（CLI）。"""

  resume_path: Path | None
  lr: float | None
  num_updates: int
  load_optimizer: bool
  wandb_run_name: str | None


def _parse_args() -> TrainRunConfig:
  p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
  p.add_argument(
    "--resume",
    type=str,
    default=None,
    help=f"再開する .pt（相対パスは runs/{EXP_NAME}/ 基準）。新 checkpoint / wandb run を作成",
  )
  p.add_argument(
    "--lr",
    type=float,
    default=None,
    help=f"学習率の上書き（省略時は config.LR={config.LR}、再開のみで optimizer 復元時は ckpt 内の LR）",
  )
  p.add_argument(
    "--num-updates",
    type=int,
    default=None,
    help=f"この run で行う方策更新回数（省略時は config.NUM_UPDATES={config.NUM_UPDATES}）",
  )
  p.add_argument(
    "--load-optimizer",
    action="store_true",
    help="--resume 時に optimizer state も読み込む（--lr 指定時は無効）",
  )
  p.add_argument(
    "--wandb-run-name",
    type=str,
    default=None,
    help="wandb run 名（省略時は config または再開時の自動名）",
  )
  args = p.parse_args()

  resume_path = None
  if args.resume is not None:
    resume_path = checkpoint.resolve_checkpoint_path(args.resume)

  num_updates = config.NUM_UPDATES if args.num_updates is None else args.num_updates
  if num_updates < 1:
    raise SystemExit("--num-updates は 1 以上にしてください")

  load_optimizer = args.load_optimizer
  if args.lr is not None:
    load_optimizer = False

  return TrainRunConfig(
    resume_path=resume_path,
    lr=args.lr,
    num_updates=num_updates,
    load_optimizer=load_optimizer,
    wandb_run_name=args.wandb_run_name,
  )


def _load_resume_state(resume_path: Path) -> dict[str, Any]:
  return checkpoint.load_checkpoint(resume_path, map_location="cpu")


def _create_agent(run: TrainRunConfig) -> tuple[AgentA2C, dict[str, Any] | None]:
  if run.resume_path is None:
    agent = AgentA2C(obs_dim=config.OBS_DIM)
    if run.lr is not None:
      agent.set_learning_rate(run.lr)
    return agent, None

  payload = _load_resume_state(run.resume_path)
  agent = AgentA2C.from_checkpoint(
    run.resume_path,
    lr=run.lr,
    load_optimizer=run.load_optimizer,
  )
  return agent, payload


def _wandb_init(run: TrainRunConfig, payload: dict[str, Any] | None) -> None:
  extra_config: dict[str, Any] | None = None
  extra_tags: tuple[str, ...] | None = None
  run_name = run.wandb_run_name

  if payload is not None:
    base_update = int(payload.get("update", 0))
    base_env_steps = int(payload.get("total_env_steps", 0))
    base_episodes = int(payload.get("episodes_finished", 0))
    extra_config = {
      "resume_checkpoint": str(run.resume_path),
      "resume_base_update": base_update,
      "resume_base_env_steps": base_env_steps,
      "resume_base_episodes_finished": base_episodes,
      "num_updates_this_run": run.num_updates,
      "end_update_target": base_update + run.num_updates,
    }
    if run.lr is not None:
      extra_config["lr"] = run.lr
      extra_config["lr_overridden"] = True
    else:
      extra_config["lr_overridden"] = False
    extra_tags = ("finetune", "resume")
    if run_name is None:
      lr_tag = f"lr{run.lr:g}" if run.lr is not None else "lr_ckpt"
      run_name = f"resume_u{base_update:06d}_{lr_tag}"

  wandb_logging.init(
    extra_config=extra_config,
    extra_tags=extra_tags,
    run_name=run_name,
  )


def _print_run_banner(
  run: TrainRunConfig,
  *,
  start_update: int,
  end_update: int,
  total_env_steps: int,
  episode_index: int,
  checkpoint_run_dir: Path | None,
) -> None:
  if run.resume_path is not None:
    print(f"[resume] checkpoint: {run.resume_path}")
    print(
      f"[resume] continuing from update {start_update} -> {end_update} "
      f"(+{run.num_updates} updates this run)"
    )
    print(
      f"[resume] env_steps={total_env_steps} episodes_finished={episode_index}"
    )
    if run.lr is not None:
      print(f"[resume] lr={run.lr:g} (optimizer state not loaded)")
    elif run.load_optimizer:
      print("[resume] optimizer state loaded from checkpoint")
    else:
      print(f"[resume] lr={config.LR} (fresh optimizer, weights only)")
  else:
    lr = run.lr if run.lr is not None else config.LR
    print(f"[train] fresh run | lr={lr:g} | num_updates={run.num_updates}")

  if checkpoint_run_dir is not None:
    print(f"[checkpoint] run dir: {checkpoint_run_dir}")


def main() -> None:
  run = _parse_args()
  agent, payload = _create_agent(run)
  _wandb_init(run, payload)

  episode_metrics = wandb_logging.episode_collector()
  env = Env2JointA2C(enable_viewer=config.ENABLE_VIEWER)

  start_update = int(payload["update"]) if payload is not None else 0
  total_env_steps = int(payload.get("total_env_steps", 0)) if payload is not None else 0
  episode_index = int(payload.get("episodes_finished", 0)) if payload is not None else 0
  end_update = start_update + run.num_updates

  obs = env.reset()
  episode_step = 0
  update_time_sum_s = 0.0
  last_update = start_update
  updates_done_this_run = 0

  checkpoint_run_dir = checkpoint.make_run_dir() if config.SAVE_CHECKPOINTS else None
  _print_run_banner(
    run,
    start_update=start_update,
    end_update=end_update,
    total_env_steps=total_env_steps,
    episode_index=episode_index,
    checkpoint_run_dir=checkpoint_run_dir,
  )

  if config.WARMUP_ENABLED:
    warmup_steps = int(config.WARMUP_DURATION_S / config.CONTROL_TIMESTEP_S)
    print(
      f"[warmup] enabled (policy B: not stored): first {config.WARMUP_DURATION_S:.3f}s "
      f"sim-time per episode ({warmup_steps} control steps @ {config.CONTROL_HZ} Hz), "
      f"action_fn={config.WARMUP_ACTION_FN.__name__}"
    )

  try:
    for u in range(start_update, end_update):
      t_update_start = time.perf_counter()
      policy_steps = 0
      while policy_steps < config.ROLLOUT_STEPS:
        if in_episode_warmup(episode_step):
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
          obs_next, reward, terminated, step_info = env.step(
            action,
            visualize=False,
            episode_step=episode_step,
          )
          episode_step += 1
          total_env_steps += 1
          truncated = episode_step >= config.MAX_STEPS_PER_EPISODE
          done = terminated or truncated
          obs = obs_next
          if done:
            episode_metrics.on_episode_end(
              episode_step=episode_step,
              terminated=terminated,
              truncated=truncated,
              step_info=step_info,
              env_step=total_env_steps,
            )
            episode_index += 1
            obs = env.reset()
            episode_step = 0
          continue

        action, value = agent.act(obs)
        obs_next, reward, terminated, step_info = env.step(
          action,
          visualize=False,
          episode_step=episode_step,
        )

        episode_step += 1
        total_env_steps += 1
        episode_metrics.on_step(reward, step_info)
        truncated = episode_step >= config.MAX_STEPS_PER_EPISODE
        done = terminated or truncated

        agent.store(obs, action, reward, value, done)
        policy_steps += 1

        obs = obs_next
        if done:
          episode_metrics.on_episode_end(
            episode_step=episode_step,
            terminated=terminated,
            truncated=truncated,
            step_info=step_info,
            env_step=total_env_steps,
          )
          episode_index += 1
          obs = env.reset()
          episode_step = 0

      stats = agent.update(obs)
      last_update = u + 1
      updates_done_this_run += 1
      update_time_sum_s += time.perf_counter() - t_update_start
      avg_update_s = update_time_sum_s / updates_done_this_run

      if (
        checkpoint_run_dir is not None
        and config.CHECKPOINT_EVERY > 0
        and last_update % config.CHECKPOINT_EVERY == 0
      ):
        paths = checkpoint.save_agent_checkpoint(
          agent,
          run_dir=checkpoint_run_dir,
          update=last_update,
          total_env_steps=total_env_steps,
          episodes_finished=episode_index,
          numbered=True,
          latest=config.CHECKPOINT_SAVE_LATEST,
        )
        print(f"[checkpoint] saved update {last_update} -> {paths[0]}")

      if updates_done_this_run == 1 or last_update % config.LOG_EVERY == 0:
        print(
          f"update {last_update: 5d}/{end_update} "
          f"(run +{updates_done_this_run}/{run.num_updates}) | "
          f"avg_update_s: {avg_update_s:8.3f} | "
          f"mean_target: {stats['mean_target']:10.5f} | "
          f"policy_loss: {stats['policy_loss']:10.5f} | "
          f"value_loss: {stats['value_loss']:10.5f} | "
          f"entropy: {stats['entropy']:10.5f} | "
          f"episodes: {episode_index}"
        )
        wandb_logging.log_train_update(
          stats,
          update=last_update,
          episodes_finished=episode_index,
          step=total_env_steps,
        )
  finally:
    if (
      checkpoint_run_dir is not None
      and config.CHECKPOINT_SAVE_FINAL
      and updates_done_this_run > 0
    ):
      paths = checkpoint.save_agent_checkpoint(
        agent,
        run_dir=checkpoint_run_dir,
        update=last_update,
        total_env_steps=total_env_steps,
        episodes_finished=episode_index,
        numbered=False,
        latest=False,
        final=True,
      )
      print(f"[checkpoint] saved final -> {paths[0]}")
    wandb_logging.finish()


if __name__ == "__main__":
  main()
