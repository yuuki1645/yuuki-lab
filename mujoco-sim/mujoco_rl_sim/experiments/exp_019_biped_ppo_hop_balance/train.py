"""exp_019 学習エントリポイント（PPO メインループ）。

このファイルの役割:
  - 環境 (EnvBipedPPO) と方策 (AgentPPO) を用意する
  - ロールアウト収集 → PPO 更新 を繰り返す
  - チェックポイント / wandb / Hub テレメトリを配線する

CLI 引数と TrainRunConfig は run_config.py。報酬・観測は env.py / reward.py / observation.py。
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np

from mujoco_rl_sim.telemetry.biped_ppo import build_reset_payload, build_step_payload
from mujoco_sim_common.telemetry import HubTelemetrySocketIoServer

from . import checkpoint
from . import config
from . import wandb_logging
from .agent import AgentPPO
from .env import EnvBipedPPO
from .package_meta import EXP_NAME
from .run_config import TrainRunConfig, parse_train_args
from .warmup import (
  WarmupContext,
  episode_sim_elapsed_s,
  in_episode_warmup,
  resolve_warmup_action,
)


# ---------------------------------------------------------------------------
# エージェント・ログ・テレメトリの初期化ヘルパ
# ---------------------------------------------------------------------------


def _load_resume_state(resume_path: Path) -> dict[str, Any]:
  """チェックポイント .pt からメタデータ（update 番号など）を CPU で読む。"""
  return checkpoint.load_checkpoint(resume_path, map_location="cpu")


def _create_agent(run: TrainRunConfig) -> tuple[AgentPPO, dict[str, Any] | None]:
  """方策ネットワークを新規作成するか、チェックポイントから復元する。

  戻り値:
    agent: PPO 方策
    payload: 再開時のみ。update / total_env_steps / episodes_finished 等
  """
  if run.resume_path is None:
    agent = AgentPPO(obs_dim=config.OBS_DIM)
    if run.lr is not None:
      agent.set_learning_rate(run.lr)
    return agent, None

  payload = _load_resume_state(run.resume_path)
  agent = AgentPPO.from_checkpoint(
    run.resume_path,
    lr=run.lr,
    load_optimizer=run.load_optimizer,
  )
  return agent, payload


def _wandb_init(run: TrainRunConfig, payload: dict[str, Any] | None) -> None:
  """wandb run を開始。再開時はベース update や LR 上書きを config に記録。"""
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
  """コンソールに run 概要を表示（再開か新規か、チェックポイント保存先など）。"""
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


def _start_telemetry(env: EnvBipedPPO, run: TrainRunConfig) -> HubTelemetrySocketIoServer | None:
  """robotics-hub 学習テレメトリ用 Socket.IO サーバを別スレッドで起動。

  Hub から POST される step_wall_sleep_sec は env.set_step_wall_sleep_sec に転送される。
  """
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
    f"(robotics-hub /training-telemetry)"
  )
  return tel


# ---------------------------------------------------------------------------
# メイン学習ループ
# ---------------------------------------------------------------------------


def main() -> None:
  # ===== 1. 実行設定・方策・ログ =====
  run = parse_train_args()
  agent, payload = _create_agent(run)
  _wandb_init(run, payload)

  episode_metrics = wandb_logging.episode_collector()
  env = EnvBipedPPO(enable_viewer=run.viewer)
  if run.step_wall_sleep_sec is not None:
    env.set_step_wall_sleep_sec(run.step_wall_sleep_sec)
  elif not run.viewer:
    # ビューア無しのときだけ config の壁時計待ち（実時間化）
    env.set_step_wall_sleep_sec(config.STEP_WALL_SLEEP_SEC)

  tel = _start_telemetry(env, run)
  visualize_steps = run.viewer  # True なら env.step 内で CONTROL_TIMESTEP_S 待ち

  # ===== 2. グローバルカウンタ（再開時は ckpt から復元） =====
  start_update = int(payload["update"]) if payload is not None else 0
  total_env_steps = int(payload.get("total_env_steps", 0)) if payload is not None else 0
  episode_index = int(payload.get("episodes_finished", 0)) if payload is not None else 0
  end_update = start_update + run.num_updates

  # 現在エピソードの観測（tuple: Hub テレメトリ用にコピーしやすい）
  obs = env.reset()
  obs_vec = tuple(obs)
  if tel is not None:
    tel.publish_reset(
      build_reset_payload(
        obs_vector=obs_vec,
        num_timesteps=total_env_steps,
        exp_name=EXP_NAME,
      )
    )

  episode_step = 0  # エピソード内の制御ステップ数（warmup 判定にも使用）
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
    # ===== 3. PPO 外ループ: 1 iteration = ロールアウト ROLLOUT_STEPS 分 + 方策更新 =====
    for u in range(start_update, end_update):
      t_update_start = time.perf_counter()
      policy_steps = 0  # この update でバッファに積んだステップ数

      # ----- 3a. ロールアウト収集（環境と相互作用） -----
      while policy_steps < config.ROLLOUT_STEPS:

        # --- エピソード先頭の warmup: 固定／スクリプト action のみ（PPO バッファに入れない） ---
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
                obs_before=np.asarray(obs_before, dtype=np.float64),
                action_norm=action,
                obs_after=np.asarray(obs_vec, dtype=np.float64),
                info=step_info,
                episode_step=episode_step,
                num_timesteps=total_env_steps,
                exp_name=EXP_NAME,
              )
            )
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
            obs_vec = tuple(obs)
            if tel is not None:
              tel.publish_reset(
                build_reset_payload(
                  obs_vector=obs_vec,
                  num_timesteps=total_env_steps,
                  exp_name=EXP_NAME,
                )
              )
            episode_step = 0
          # warmup 中は agent.store しない
          continue

        # --- 通常ステップ: 方策から action をサンプルし、ロールアウトバッファへ保存 ---
        action, value, log_prob = agent.act(obs)
        obs_before = obs_vec  # テレメトリ: エージェントが見た観測（step 前）
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
              obs_before=np.asarray(obs_before, dtype=np.float64),
              action_norm=action,
              obs_after=np.asarray(obs_vec, dtype=np.float64),
              info=step_info,
              episode_step=episode_step,
              num_timesteps=total_env_steps,
              exp_name=EXP_NAME,
            )
          )
        episode_metrics.on_step(reward, step_info)
        truncated = episode_step >= config.MAX_STEPS_PER_EPISODE
        done = terminated or truncated

        # PPO: (s, a, r, V, done, log π) を蓄積。done で GAE ブートストラップが切れる
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
          obs = env.reset()
          obs_vec = tuple(obs)
          if tel is not None:
            tel.publish_reset(
              build_reset_payload(
                obs_vector=obs_vec,
                num_timesteps=total_env_steps,
                exp_name=EXP_NAME,
              )
            )
          episode_step = 0

      # ----- 3b. PPO 更新（収集したロールアウトで複数 epoch 学習） -----
      stats = agent.update(obs)
      last_update = u + 1
      updates_done_this_run += 1
      update_time_sum_s += time.perf_counter() - t_update_start
      avg_update_s = update_time_sum_s / updates_done_this_run

      # ----- 3c. 定期チェックポイント -----
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

      # ----- 3d. コンソール / wandb ログ -----
      if updates_done_this_run == 1 or last_update % config.LOG_EVERY == 0:
        rolling = episode_metrics.rolling_summary()
        print(
          f"update {last_update: 5d}/{end_update} "
          f"(run +{updates_done_this_run}/{run.num_updates}) | "
          f"avg_update_s: {avg_update_s:8.3f} | "
          f"mean_target: {stats['mean_target']:10.5f} | "
          f"policy_loss: {stats['policy_loss']:10.5f} | "
          f"value_loss: {stats['value_loss']:10.5f} | "
          f"entropy: {stats['entropy']:10.5f} | "
          f"approx_kl: {stats['approx_kl']:10.5f} | "
          f"clip_frac: {stats['clip_fraction']:10.5f} | "
          f"episodes: {episode_index}"
          f"{episode_metrics.format_rolling_log_suffix()}"
        )
        wandb_logging.log_train_update(
          stats,
          update=last_update,
          episodes_finished=episode_index,
          step=total_env_steps,
          episode_rolling=rolling,
        )

  finally:
    # ===== 4. 終了処理（例外時も実行） =====
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
    if tel is not None:
      tel.stop()


if __name__ == "__main__":
  main()
