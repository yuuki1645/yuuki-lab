"""PPO 学習ループ（ロールアウト・テレメトリ・チェックポイント）の共通実装。

各 exp_* は train.py から ``PpoTrainBindings`` を組み立てて ``run_ppo_train`` を呼ぶ。
実験間で共通の学習フローをここに集約し、環境・契約・チェックポイントだけ差し替える。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

import numpy as np

from contract.telemetry import build_reset_payload, build_step_payload
from contract.spec import TelemetryContract
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
  """実験フォルダ固有のモジュール・型を束ねる。"""

  config: Any
  checkpoint: Any
  wandb_logging: Any
  warmup: Any
  exp_name: str
  telemetry: TelemetryContract
  env_factory: Callable[[bool], _EnvProtocol]
  create_agent: Callable[[Any], tuple[Any, dict[str, Any] | None]]
  init_wandb: Callable[[Any, dict[str, Any] | None], None]
  train_run_config: Any
  # 学習 DR（env_factory が参照。banner 表示にも使用）
  training_dr_enabled: bool = True
  training_seed_resolved: int | None = None
  # checkpoint run dir 作成直後に config_effective.json 等を書く任意フック
  on_checkpoint_run_dir: Callable[[Path, dict[str, Any] | None, Any], None] | None = None


def _start_telemetry(
  env: _EnvProtocol,
  run: Any,
  *,
  hub_path_label: str = "/training-telemetry",
) -> HubTelemetrySocketIoServer | None:
  if not run.telemetry:
    print("[telemetry] disabled")
    return None
  tel = HubTelemetrySocketIoServer(
    host=run.telemetry_host,
    port=run.telemetry_port,
    set_step_wall_sleep_sec=env.set_step_wall_sleep_sec,
    get_step_wall_sleep_sec=env.get_step_wall_sleep_sec,
  )
  tel.start()
  print(
    f"[telemetry] Socket.IO http://{run.telemetry_host}:{run.telemetry_port} "
    f"(robotics-hub {hub_path_label})"
  )
  return tel


def _print_run_banner(
  bindings: PpoTrainBindings,
  run: Any,
  *,
  start_update: int,
  end_update: int,
  total_env_steps: int,
  episode_index: int,
  checkpoint_run_dir: Path | None,
) -> None:
  config = bindings.config
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
    print(f"[contract] telemetry schema={bindings.telemetry.schema_id}")

  if checkpoint_run_dir is not None:
    print(f"[checkpoint] run dir: {checkpoint_run_dir}")

  if bindings.training_dr_enabled:
    print(
      "[training-dr] enabled: pose + foot friction + actuator kp/kv "
      f"(seed={bindings.training_seed_resolved})"
    )
  else:
    print("[training-dr] disabled")

  wall_sleep = _effective_step_wall_sleep_sec(run, config)
  num_envs = int(getattr(config, "NUM_ENVS", 1))
  for msg in pacing_warnings(
    viewer=bool(run.viewer),
    telemetry=bool(run.telemetry),
    step_wall_sleep_sec=wall_sleep,
    num_envs=num_envs,
  ):
    print(msg)
  if num_envs > 1:
    print(
      f"[subproc-vec] enabled: {num_envs} env workers "
      f"(rollout_steps={config.ROLLOUT_STEPS} total per update)"
    )


def _run_warmup_step(
  obs,
  obs_vec: tuple[float, ...],
  *,
  env: _EnvProtocol,
  warmup_mod,
  config_mod,
  contract_mod: TelemetryContract,
  tel: HubTelemetrySocketIoServer | None,
  episode_metrics,
  exp_name_str: str,
  episode_step_val: int,
  total_env_steps_val: int,
  episode_index_val: int,
  visualize_steps_flag: bool,
) -> tuple[Any, tuple[float, ...], int, int, int]:
  elapsed_s = warmup_mod.episode_sim_elapsed_s(episode_step_val)
  action = warmup_mod.resolve_warmup_action(
    config_mod.WARMUP_ACTION_FN,
    warmup_mod.WarmupContext(
      obs=obs,
      elapsed_s=elapsed_s,
      total_env_steps=total_env_steps_val,
      episode_step=episode_step_val,
      episode_index=episode_index_val,
    ),
  )
  obs_before = obs_vec
  obs_next, reward, terminated, step_info = env.step(
    action,
    visualize=visualize_steps_flag,
    episode_step=episode_step_val,
  )
  obs_vec = tuple(obs_next)
  episode_step_val += 1
  total_env_steps_val += 1
  if tel is not None:
    tel.publish_step(
      build_step_payload(
        contract_mod,
        obs_before=np.asarray(obs_before, dtype=np.float64),
        action_norm=action,
        obs_after=np.asarray(obs_vec, dtype=np.float64),
        info=step_info,
        episode_step=episode_step_val,
        num_timesteps=total_env_steps_val,
        exp_name=exp_name_str,
      )
    )
  truncated = episode_step_val >= config_mod.MAX_STEPS_PER_EPISODE
  done = terminated or truncated
  obs = obs_next
  if done:
    episode_metrics.on_episode_end(
      episode_step=episode_step_val,
      terminated=terminated,
      truncated=truncated,
      step_info=step_info,
      env_step=total_env_steps_val,
    )
    episode_index_val += 1
    obs = env.reset(episode_index=episode_index_val)
    obs_vec = tuple(obs)
    if tel is not None:
      tel.publish_reset(
        build_reset_payload(
          contract_mod,
          obs_vector=obs_vec,
          num_timesteps=total_env_steps_val,
          exp_name=exp_name_str,
        )
      )
    episode_step_val = 0
  return obs, obs_vec, episode_step_val, total_env_steps_val, episode_index_val


def _effective_step_wall_sleep_sec(run: Any, config: Any) -> float:
  """制御ステップごとの壁時計待ち [s]（CLI > config）。"""
  if run.step_wall_sleep_sec is not None:
    return max(0.0, float(run.step_wall_sleep_sec))
  return max(0.0, float(config.STEP_WALL_SLEEP_SEC))


def _viewer_visualize_realtime(run: Any, config: Any, wall_sleep_sec: float) -> bool:
  """MuJoCo ビューアを実時間（CONTROL_TIMESTEP_S）で追従するか。

  ビューアは ``env.step`` 内で常に sync する。``visualize=True`` のときだけ
  追加で ``CONTROL_TIMESTEP_S`` 分 sleep する。wall_sleep_sec==0 なら最速表示。
  """
  if not run.viewer:
    return False
  return wall_sleep_sec > 0.0


def _collect_rollout_subproc(
  *,
  vec_env: SubprocVecEnvBiped,
  agent: Any,
  config: Any,
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
  """Subproc VecEnv で ``ROLLOUT_STEPS`` 分のロールアウトを収集する。"""
  num_envs = vec_env.num_envs
  policy_steps = 0
  last_obs: Any = obs_list[0]
  sum_ipc_s = 0.0
  sum_act_batch_s = 0.0

  while policy_steps < config.ROLLOUT_STEPS:
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

      truncated = episode_steps[env_id] >= config.MAX_STEPS_PER_EPISODE
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

      if policy_steps >= config.ROLLOUT_STEPS:
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
  """PPO 学習のメインループ。

  外側: update ループ（NUM_UPDATES 回）
  内側: ROLLOUT_STEPS 分の環境 Interaction → agent.update()
  各エピソード先頭 WARMUP_DURATION_S は方策データに含めない（warmup 専用 step）。
  """
  run = bindings.train_run_config
  config = bindings.config
  contract = bindings.telemetry
  warmup = bindings.warmup
  checkpoint = bindings.checkpoint
  wandb_logging = bindings.wandb_logging
  exp_name = bindings.exp_name

  agent, payload = bindings.create_agent(run)
  bindings.init_wandb(run, payload)

  episode_metrics = wandb_logging.episode_collector()
  num_envs = int(getattr(config, "NUM_ENVS", 1))
  use_subproc = num_envs > 1
  wall_sleep_sec = _effective_step_wall_sleep_sec(run, config)

  env = None
  vec_env: SubprocVecEnvBiped | None = None
  tel: HubTelemetrySocketIoServer | None = None
  visualize_steps = False

  if use_subproc:
    if config.WARMUP_ENABLED:
      print(
        "[subproc-vec] warmup disabled for num_envs>1 "
        f"(config.WARMUP_ENABLED={config.WARMUP_ENABLED})"
      )
    vec_env = SubprocVecEnvBiped(
      num_envs,
      training_dr_enabled=bool(bindings.training_dr_enabled),
      training_seed=bindings.training_seed_resolved,
      step_wall_sleep_sec=wall_sleep_sec,
    )
  else:
    env = bindings.env_factory(run.viewer)
    env.set_step_wall_sleep_sec(wall_sleep_sec)
    tel = _start_telemetry(env, run)
    visualize_steps = _viewer_visualize_realtime(run, config, wall_sleep_sec)

  if run.viewer and not use_subproc:
    if visualize_steps:
      print(
        f"[viewer] realtime pacing ({config.CONTROL_TIMESTEP_S:.3f}s/step); "
        "最速表示は --step-wall-sleep 0 または --viewer-fast"
      )
    else:
      print("[viewer] enabled (no wall-clock sleep; viewer sync only)")

  start_update = int(payload["update"]) if payload is not None else 0
  total_env_steps = int(payload.get("total_env_steps", 0)) if payload is not None else 0
  episode_index = int(payload.get("episodes_finished", 0)) if payload is not None else 0
  end_update = start_update + run.num_updates

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
          contract,
          obs_vector=obs_vec,
          num_timesteps=total_env_steps,
          exp_name=exp_name,
        )
      )
  last_update = start_update
  updates_done_this_run = 0
  throughput = ThroughputTracker(rollout_steps_per_update=int(config.ROLLOUT_STEPS))

  wandb_name = wandb_logging.active_run_name() if run.wandb else None
  checkpoint_run_dir = (
    checkpoint.make_run_dir(wandb_run_name=wandb_name)
    if config.SAVE_CHECKPOINTS
    else None
  )
  if checkpoint_run_dir is not None:
    wandb_logging.log_checkpoint_run_dir(checkpoint_run_dir)
    if bindings.on_checkpoint_run_dir is not None:
      bindings.on_checkpoint_run_dir(checkpoint_run_dir, payload, agent)
  _print_run_banner(
    bindings,
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
          config=config,
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

        # --- ロールアウト収集: ROLLOUT_STEPS 分 interact → バッファ ---
        while policy_steps < config.ROLLOUT_STEPS:
          if warmup.in_episode_warmup(episode_step):
            # ウォームアップ中は agent.store しない（方策学習データに混ぜない）
            obs, obs_vec, episode_step, total_env_steps, episode_index = (
              _run_warmup_step(
                obs,
                obs_vec,
                env=env,
                warmup_mod=warmup,
                config_mod=config,
                contract_mod=contract,
                tel=tel,
                episode_metrics=episode_metrics,
                exp_name_str=exp_name,
                episode_step_val=episode_step,
                total_env_steps_val=total_env_steps,
                episode_index_val=episode_index,
                visualize_steps_flag=visualize_steps,
              )
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
                contract,
                obs_before=np.asarray(obs_before, dtype=np.float64),
                action_norm=action,
                obs_after=np.asarray(obs_vec, dtype=np.float64),
                info=step_info,
                episode_step=episode_step,
                num_timesteps=total_env_steps,
                exp_name=exp_name,
              )
            )
          episode_metrics.on_step(reward, step_info)
          truncated = episode_step >= config.MAX_STEPS_PER_EPISODE
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
                  contract,
                  obs_vector=obs_vec,
                  num_timesteps=total_env_steps,
                  exp_name=exp_name,
                )
              )
            episode_step = 0

      t_rollout_s = time.perf_counter() - t_rollout_start

      # --- PPO 更新（同一ロールアウトを PPO_EPOCHS 回ミニバッチ学習）---
      t_ppo_start = time.perf_counter()
      stats = agent.update(obs)
      t_ppo_s = time.perf_counter() - t_ppo_start

      timing = UpdateTiming(
        rollout_s=t_rollout_s,
        ppo_update_s=t_ppo_s,
        rollout_steps=int(config.ROLLOUT_STEPS),
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
        rolling = episode_metrics.rolling_summary()
        interval_suffix = episode_metrics.take_interval_log_suffix()
        print(
          f"update {last_update: 5d}/{end_update} "
          f"(run +{updates_done_this_run: 5d}/{run.num_updates}) | "
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
      final_checkpoint_path = paths[0]
      print(f"[checkpoint] saved final -> {final_checkpoint_path}")
    # wandb.finish() は train.py が post-train eval 後に呼ぶ（eval 主指標を summary に載せるため）
    if tel is not None:
      tel.stop()
    if vec_env is not None:
      vec_env.close()

  return TrainRunResult(
    checkpoint_run_dir=checkpoint_run_dir,
    final_checkpoint_path=final_checkpoint_path,
    updates_done_this_run=updates_done_this_run,
  )
