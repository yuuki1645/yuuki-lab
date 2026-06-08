"""PPO 学習ループ（ロールアウト・テレメトリ・チェックポイント）の共通実装。"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

import numpy as np
from omegaconf import DictConfig

from contract import TELEMETRY_CONTRACT
from contract.telemetry import build_reset_payload, build_step_payload
from lib.experiment_context import ExperimentContext
from lib.hydra_checkpoint import hydra_config_path
from lib.train_throughput import ThroughputTracker, UpdateTiming, pacing_warnings
from mujoco_sim_common.telemetry import HubTelemetrySocketIoServer
from sim.subproc_vec_env import SubprocVecEnvBiped


class _EnvProtocol(Protocol):
  def reset(self, *, episode_index: int = 0): ...
  def step(self, action, visualize: bool = False, episode_step: int = 0): ...
  def set_step_wall_sleep_sec(self, sec: float) -> None: ...
  def get_step_wall_sleep_sec(self) -> float: ...


@dataclass(frozen=True)
class TrainRunResult:
  """``run_ppo_train`` 完了時のチェックポイント情報（学習後 eval 用）。"""

  checkpoint_run_dir: Path | None
  final_checkpoint_path: Path | None
  updates_done_this_run: int


@dataclass(frozen=True)
class PpoTrainBindings:
  """実験フォルダ固有の依存モジュール・初期化関数を束ねる。"""

  ctx: ExperimentContext
  resolved_cfg: DictConfig | None
  checkpoint: Any
  wandb_logging: Any
  warmup: Any
  env_factory: Callable[[bool], _EnvProtocol]
  create_agent: Callable[[ExperimentContext], tuple[Any, dict[str, Any] | None]]
  init_wandb: Callable[[ExperimentContext, dict[str, Any] | None], None]
  on_checkpoint_run_dir: Callable[[Path], None] | None = None
  training_dr_enabled: bool = True
  training_seed_resolved: int | None = None


def _start_telemetry(
  env: _EnvProtocol,
  *,
  enabled: bool,
  host: str,
  port: int,
  hub_path_label: str = "/training-telemetry",
) -> HubTelemetrySocketIoServer | None:
  if not enabled:
    print("[telemetry] disabled")
    return None
  tel = HubTelemetrySocketIoServer(
    host=host,
    port=port,
    set_step_wall_sleep_sec=env.set_step_wall_sleep_sec,
    get_step_wall_sleep_sec=env.get_step_wall_sleep_sec,
  )
  tel.start()
  print(
    f"[telemetry] Socket.IO http://{host}:{port} "
    f"(robotics-hub {hub_path_label})"
  )
  return tel


def _effective_step_wall_sleep_sec(cfg: Any) -> float:
  """ビューア無効時は sleep を無効化し、最速で回す。"""
  if not bool(cfg.runtime.viewer):
    return 0.0
  return max(0.0, float(cfg.runtime.step_wall_sleep_sec))


def _viewer_visualize_realtime(cfg: Any, wall_sleep_sec: float) -> bool:
  if not bool(cfg.runtime.viewer):
    return False
  return wall_sleep_sec > 0.0


def _print_run_banner(
  bindings: PpoTrainBindings,
  *,
  start_update: int,
  end_update: int,
  total_env_steps: int,
  episode_index: int,
  checkpoint_run_dir: Path | None,
) -> None:
  cfg = bindings.ctx.cfg
  resume_cfg = cfg.resume
  if resume_cfg.checkpoint is not None and str(resume_cfg.checkpoint).strip():
    print(f"[resume] checkpoint: {resume_cfg.checkpoint}")
    print(
      f"[resume] continuing from update {start_update} -> {end_update} "
      f"(+{cfg.training.num_updates} updates this run)"
    )
    print(
      f"[resume] env_steps={total_env_steps} episodes_finished={episode_index}"
    )
    if resume_cfg.lr is not None:
      print(f"[resume] lr={float(resume_cfg.lr):g} (optimizer state not loaded)")
    elif bool(resume_cfg.load_optimizer):
      print("[resume] optimizer state loaded from checkpoint")
    else:
      print(f"[resume] lr={float(cfg.ppo.lr):g} (fresh optimizer, weights only)")
  else:
    print(f"[train] fresh run | lr={float(cfg.ppo.lr):g} | num_updates={cfg.training.num_updates}")
    print(f"[contract] telemetry schema={TELEMETRY_CONTRACT.schema_id}")

  if checkpoint_run_dir is not None:
    print(f"[checkpoint] run dir: {checkpoint_run_dir}")

  if bindings.training_dr_enabled:
    print(
      "[training-dr] enabled: pose + foot friction + actuator kp/kv "
      f"(seed={bindings.training_seed_resolved})"
    )
  else:
    print("[training-dr] disabled")

  wall_sleep = _effective_step_wall_sleep_sec(cfg)
  num_envs = int(cfg.runtime.num_envs)
  for msg in pacing_warnings(
    viewer=bool(cfg.runtime.viewer),
    telemetry=bool(cfg.runtime.telemetry),
    step_wall_sleep_sec=wall_sleep,
    num_envs=num_envs,
  ):
    print(msg)
  if num_envs > 1:
    print(
      f"[subproc-vec] enabled: {num_envs} env workers "
      f"(rollout_steps={cfg.ppo.rollout_steps} total per update)"
    )


def _run_warmup_step(
  obs,
  obs_vec: tuple[float, ...],
  *,
  bindings_ctx: ExperimentContext,
  env: _EnvProtocol,
  warmup_mod,
  cfg: Any,
  tel: HubTelemetrySocketIoServer | None,
  episode_metrics,
  exp_name: str,
  episode_step: int,
  total_env_steps: int,
  episode_index: int,
  visualize_steps: bool,
) -> tuple[Any, tuple[float, ...], int, int, int]:
  elapsed_s = warmup_mod.episode_sim_elapsed_s(episode_step, bindings_ctx)
  action = warmup_mod.resolve_warmup_action(
    warmup_mod.default_warmup_action,
    warmup_mod.WarmupContext(
      obs=obs,
      elapsed_s=elapsed_s,
      total_env_steps=total_env_steps,
      episode_step=episode_step,
      episode_index=episode_index,
    ),
  )
  obs_before = obs_vec
  obs_next, reward, terminated, step_info = env.step(
    action,
    visualize=visualize_steps,
    episode_step=episode_step,
  )
  obs_vec = tuple(obs_next)
  episode_step += 1
  total_env_steps += 1
  if tel is not None:
    tel.publish_step(
      build_step_payload(
        TELEMETRY_CONTRACT,
        obs_before=np.asarray(obs_before, dtype=np.float64),
        action_norm=action,
        obs_after=np.asarray(obs_vec, dtype=np.float64),
        info=step_info,
        episode_step=episode_step,
        num_timesteps=total_env_steps,
        exp_name=exp_name,
      )
    )
  truncated = episode_step >= int(cfg.training.max_steps_per_episode)
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
    obs = env.reset(episode_index=episode_index)
    obs_vec = tuple(obs)
    if tel is not None:
      tel.publish_reset(
        build_reset_payload(
          TELEMETRY_CONTRACT,
          obs_vector=obs_vec,
          num_timesteps=total_env_steps,
          exp_name=exp_name,
        )
      )
    episode_step = 0
  return obs, obs_vec, episode_step, total_env_steps, episode_index


def _collect_rollout_subproc(
  *,
  vec_env: SubprocVecEnvBiped,
  agent: Any,
  cfg: Any,
  obs_list: list[tuple[float, ...]],
  episode_steps: list[int],
  next_episode_index: int,
  episode_metrics: Any,
  total_env_steps: int,
  episodes_finished: int,
) -> tuple[
  list[tuple[float, ...]],
  list[int],
  int,
  int,
  int,
  Any,
  float,
  float,
]:
  """Subproc VecEnv で ``ppo.rollout_steps`` 分のロールアウトを収集する。"""
  num_envs = vec_env.num_envs
  policy_steps = 0
  last_obs: Any = obs_list[0]
  sum_ipc_s = 0.0
  sum_act_batch_s = 0.0
  rollout_steps = int(cfg.ppo.rollout_steps)
  max_steps_per_episode = int(cfg.training.max_steps_per_episode)

  while policy_steps < rollout_steps:
    obs_batch = np.asarray(obs_list, dtype=np.float64)

    t_act = time.perf_counter()
    actions, values, log_probs = agent.act_batch(obs_batch)
    sum_act_batch_s += time.perf_counter() - t_act

    t_ipc = time.perf_counter()
    batch = vec_env.step(actions)
    sum_ipc_s += time.perf_counter() - t_ipc

    for env_id in range(num_envs):
      obs_before = obs_list[env_id]
      action_row = actions[env_id]
      action_tuple = tuple(float(x) for x in action_row)
      reward = float(batch.rewards[env_id])
      terminated = bool(batch.terminated[env_id])
      step_info = batch.infos[env_id]

      episode_steps[env_id] += 1
      total_env_steps += 1
      episode_metrics.on_step(reward, step_info)

      truncated = episode_steps[env_id] >= max_steps_per_episode
      done = terminated or truncated

      agent.store(
        obs_before,
        action_tuple,
        reward,
        values[env_id],
        done,
        log_probs[env_id],
      )
      policy_steps += 1
      obs_list[env_id] = batch.observations[env_id]
      last_obs = obs_list[env_id]

      if policy_steps >= rollout_steps:
        break

      if done:
        episode_metrics.on_episode_end(
          episode_step=episode_steps[env_id],
          terminated=terminated,
          truncated=truncated,
          step_info=step_info,
          env_step=total_env_steps,
        )
        episodes_finished += 1
        obs_list[env_id] = vec_env.reset_env(
          env_id,
          episode_index=next_episode_index,
        )
        next_episode_index += 1
        episode_steps[env_id] = 0
        last_obs = obs_list[env_id]

  return (
    obs_list,
    episode_steps,
    next_episode_index,
    total_env_steps,
    episodes_finished,
    last_obs,
    sum_ipc_s,
    sum_act_batch_s,
  )


def run_ppo_train(bindings: PpoTrainBindings) -> TrainRunResult:
  """PPO 学習のメインループ。"""
  cfg = bindings.ctx.cfg
  checkpoint = bindings.checkpoint
  wandb_logging = bindings.wandb_logging
  warmup = bindings.warmup

  # 要件: wandb 初期化 -> run_dir 作成 -> Hydra 保存の順で行う。
  agent, payload = bindings.create_agent(bindings.ctx)
  bindings.init_wandb(bindings.ctx, payload)

  checkpoint_run_dir: Path | None = None
  if bool(cfg.checkpoint.save_checkpoints):
    wandb_name = wandb_logging.active_run_name() if bool(cfg.wandb.enabled) else None
    checkpoint_run_dir = checkpoint.make_run_dir(bindings.ctx, wandb_run_name=wandb_name)
    wandb_logging.log_checkpoint_run_dir(checkpoint_run_dir)
    if bindings.on_checkpoint_run_dir is not None:
      bindings.on_checkpoint_run_dir(checkpoint_run_dir)

  episode_metrics = wandb_logging.episode_collector()
  num_envs = int(cfg.runtime.num_envs)
  use_subproc = num_envs > 1
  wall_sleep_sec = _effective_step_wall_sleep_sec(cfg)

  env = None
  vec_env: SubprocVecEnvBiped | None = None
  tel: HubTelemetrySocketIoServer | None = None
  visualize_steps = False

  if use_subproc:
    if bool(cfg.training.warmup_enabled):
      print(
        "[subproc-vec] warmup disabled for num_envs>1 "
        f"(training.warmup_enabled={cfg.training.warmup_enabled})"
      )
    # subprocess 側が同一 Hydra 設定で env を復元できるよう、run_dir 配下の保存先を渡す。
    subproc_hydra_path = (
      str(hydra_config_path(checkpoint_run_dir))
      if checkpoint_run_dir is not None
      else None
    )
    vec_env = SubprocVecEnvBiped(
      num_envs,
      training_dr_enabled=bool(bindings.training_dr_enabled),
      training_seed=bindings.training_seed_resolved,
      step_wall_sleep_sec=wall_sleep_sec,
      hydra_config_path=subproc_hydra_path,
    )
  else:
    env = bindings.env_factory(bool(cfg.runtime.viewer))
    env.set_step_wall_sleep_sec(wall_sleep_sec)
    tel = _start_telemetry(
      env,
      enabled=bool(cfg.runtime.telemetry),
      host=str(cfg.runtime.telemetry_host),
      port=int(cfg.runtime.telemetry_port),
    )
    visualize_steps = _viewer_visualize_realtime(cfg, wall_sleep_sec)

  if bool(cfg.runtime.viewer) and not use_subproc:
    if visualize_steps:
      print(
        f"[viewer] realtime pacing ({cfg.sim.control_timestep_s:.3f}s/step); "
        "最速表示は runtime.step_wall_sleep_sec=0"
      )
    else:
      print("[viewer] enabled (no wall-clock sleep; viewer sync only)")

  start_update = int(payload["update"]) if payload is not None else 0
  total_env_steps = int(payload.get("total_env_steps", 0)) if payload is not None else 0
  episode_index = int(payload.get("episodes_finished", 0)) if payload is not None else 0
  end_update = start_update + int(cfg.training.num_updates)

  obs_list: list[tuple[float, ...]] = []
  episode_steps: list[int] = []
  next_episode_index = episode_index
  obs_vec: tuple[float, ...] = ()
  obs = None
  episode_step = 0

  if use_subproc:
    assert vec_env is not None
    obs_list = vec_env.reset_all(start_episode_index=episode_index)
    next_episode_index = episode_index + num_envs
    episode_steps = [0] * num_envs
    obs_vec = obs_list[0]
  else:
    assert env is not None
    obs = env.reset(episode_index=episode_index)
    obs_vec = tuple(obs)
    if tel is not None:
      tel.publish_reset(
        build_reset_payload(
          TELEMETRY_CONTRACT,
          obs_vector=obs_vec,
          num_timesteps=total_env_steps,
          exp_name=bindings.ctx.exp_name,
        )
      )

  _print_run_banner(
    bindings,
    start_update=start_update,
    end_update=end_update,
    total_env_steps=total_env_steps,
    episode_index=episode_index,
    checkpoint_run_dir=checkpoint_run_dir,
  )

  if bool(cfg.training.warmup_enabled):
    warmup_steps = int(float(cfg.training.warmup_duration_s) / float(cfg.sim.control_timestep_s))
    print(
      f"[warmup] enabled (policy B: not stored): first {float(cfg.training.warmup_duration_s):.3f}s "
      f"sim-time per episode ({warmup_steps} control steps @ {cfg.sim.control_hz} Hz), "
      f"action_fn={warmup.default_warmup_action.__name__}"
    )

  last_update = start_update
  updates_done_this_run = 0
  throughput = ThroughputTracker(rollout_steps_per_update=int(cfg.ppo.rollout_steps))
  final_checkpoint_path: Path | None = None
  try:
    for u in range(start_update, end_update):
      t_rollout_start = time.perf_counter()
      ipc_s = 0.0
      act_batch_s = 0.0

      if use_subproc:
        assert vec_env is not None
        (
          obs_list,
          episode_steps,
          next_episode_index,
          total_env_steps,
          episode_index,
          last_obs,
          ipc_s,
          act_batch_s,
        ) = _collect_rollout_subproc(
          vec_env=vec_env,
          agent=agent,
          cfg=cfg,
          obs_list=obs_list,
          episode_steps=episode_steps,
          next_episode_index=next_episode_index,
          episode_metrics=episode_metrics,
          total_env_steps=total_env_steps,
          episodes_finished=episode_index,
        )
        obs = last_obs
      else:
        policy_steps = 0
        rollout_steps = int(cfg.ppo.rollout_steps)
        while policy_steps < rollout_steps:
          if warmup.in_episode_warmup(episode_step, bindings.ctx):
            obs, obs_vec, episode_step, total_env_steps, episode_index = _run_warmup_step(
              obs,
              obs_vec,
              bindings_ctx=bindings.ctx,
              env=env,
              warmup_mod=warmup,
              cfg=cfg,
              tel=tel,
              episode_metrics=episode_metrics,
              exp_name=bindings.ctx.exp_name,
              episode_step=episode_step,
              total_env_steps=total_env_steps,
              episode_index=episode_index,
              visualize_steps=visualize_steps,
            )
            continue

          action, value, log_prob = agent.act(obs)
          obs_before = obs_vec
          obs_next, reward, terminated, step_info = env.step(
            action,
            visualize=visualize_steps,
            episode_step=episode_step,
          )
          obs_vec = tuple(obs_next)
          episode_step += 1
          total_env_steps += 1
          if tel is not None:
            tel.publish_step(
              build_step_payload(
                TELEMETRY_CONTRACT,
                obs_before=np.asarray(obs_before, dtype=np.float64),
                action_norm=action,
                obs_after=np.asarray(obs_vec, dtype=np.float64),
                info=step_info,
                episode_step=episode_step,
                num_timesteps=total_env_steps,
                exp_name=bindings.ctx.exp_name,
              )
            )

          episode_metrics.on_step(reward, step_info)
          truncated = episode_step >= int(cfg.training.max_steps_per_episode)
          done = terminated or truncated

          agent.store(obs, action, reward, value, done, log_prob)
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
            obs = env.reset(episode_index=episode_index)
            obs_vec = tuple(obs)
            if tel is not None:
              tel.publish_reset(
                build_reset_payload(
                  TELEMETRY_CONTRACT,
                  obs_vector=obs_vec,
                  num_timesteps=total_env_steps,
                  exp_name=bindings.ctx.exp_name,
                )
              )
            episode_step = 0

      t_rollout_s = time.perf_counter() - t_rollout_start
      t_ppo_start = time.perf_counter()
      stats = agent.update(obs)
      t_ppo_s = time.perf_counter() - t_ppo_start

      timing = UpdateTiming(
        rollout_s=t_rollout_s,
        ppo_update_s=t_ppo_s,
        rollout_steps=int(cfg.ppo.rollout_steps),
        ipc_s=ipc_s,
        act_batch_s=act_batch_s,
        num_envs=num_envs,
      )
      throughput.record(timing)

      last_update = u + 1
      updates_done_this_run += 1
      avg_update_s = throughput.avg_update_s

      if (
        checkpoint_run_dir is not None
        and int(cfg.checkpoint.checkpoint_every) > 0
        and last_update % int(cfg.checkpoint.checkpoint_every) == 0
      ):
        paths = checkpoint.save_agent_checkpoint(
          agent,
          run_dir=checkpoint_run_dir,
          update=last_update,
          total_env_steps=total_env_steps,
          episodes_finished=episode_index,
          numbered=True,
          latest=bool(cfg.checkpoint.save_latest),
        )
        print(f"[checkpoint] saved update {last_update} -> {paths[0]}")

      if updates_done_this_run == 1 or last_update % int(cfg.training.log_every) == 0:
        rolling = episode_metrics.rolling_summary()
        interval_suffix = episode_metrics.take_interval_log_suffix()
        print(
          f"update {last_update: 5d}/{end_update} "
          f"(run +{updates_done_this_run: 5d}/{cfg.training.num_updates}) | "
          f"avg_update_s: {avg_update_s:8.3f}"
          f"{throughput.format_interval_suffix(timing)}"
          f"{interval_suffix}"
        )
        wandb_logging.log_train_update(
          stats,
          update=last_update,
          episodes_finished=episode_index,
          step=total_env_steps,
          episode_rolling=rolling,
          total_updates=end_update,
          timing_metrics=throughput.wandb_metrics(timing),
        )
  finally:
    if updates_done_this_run > 0:
      print(throughput.format_run_summary())
    if (
      checkpoint_run_dir is not None
      and bool(cfg.checkpoint.save_final)
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
      final_checkpoint_path = paths[0]
      print(f"[checkpoint] saved final -> {final_checkpoint_path}")
    if tel is not None:
      tel.stop()
    if vec_env is not None:
      vec_env.close()

  return TrainRunResult(
    checkpoint_run_dir=checkpoint_run_dir,
    final_checkpoint_path=final_checkpoint_path,
    updates_done_this_run=updates_done_this_run,
  )
