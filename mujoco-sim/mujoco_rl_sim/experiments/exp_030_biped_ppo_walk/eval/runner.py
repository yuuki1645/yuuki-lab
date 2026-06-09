"""チェックポイント評価の rollout 実行。"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from eval.metrics import EpisodeEvalRecord
from eval.spec import (
  EPISODES_PER_SEED,
  EVAL_SEEDS,
  make_episode_rng,
  iter_eval_trials,
)
from lib.load_run_context import build_eval_context, ctx_from_checkpoint
from rl.agent import AgentPPO
from sim.env import EnvBipedPPO
from sim.termination import REASON_TRUNCATED


def _episode_stop_state(
  *,
  terminated: bool,
  step_info: dict,
  episode_step: int,
  max_steps_per_episode: int,
) -> tuple[bool, str, bool]:
  """エピソードを終了すべきか、理由、truncated かを返す。"""
  if terminated:
    reason = step_info.get("termination_reason") or "terminated"
    return True, str(reason), False
  if (episode_step + 1) >= int(max_steps_per_episode):
    return True, REASON_TRUNCATED, True
  return False, "", False


def run_eval_episode(
  env: EnvBipedPPO,
  act_eval: Callable,
  *,
  eval_seed: int,
  ep_index: int,
  trial_index: int,
  max_steps_per_episode: int,
) -> EpisodeEvalRecord:
  """1 試行分の eval rollout。"""
  rng = make_episode_rng(eval_seed, ep_index)
  obs, origin_imu_x, noise_applied = env.reset_eval(rng)

  ep_return = 0.0
  policy_steps = 0
  single_support_steps = 0
  double_support_steps = 0
  alternating_landings = 0
  landing_events = 0
  final_imu_x = origin_imu_x
  termination_reason = REASON_TRUNCATED
  truncated = False
  episode_length = 0

  for step in range(int(max_steps_per_episode)):
    action = act_eval(obs)
    obs, reward, terminated, step_info = env.step(action, episode_step=step)
    ep_return += float(reward)
    policy_steps += 1
    episode_length = step + 1
    final_imu_x = float(step_info.get("imu_x", final_imu_x))

    if float(step_info.get("single_support", 0.0)) > 0.5:
      single_support_steps += 1
    if float(step_info.get("both_feet_on_floor", 0.0)) > 0.5:
      double_support_steps += 1
    if float(step_info.get("landed", 0.0)) > 0.5:
      landing_events += 1
    if float(step_info.get("alternating_landing", 0.0)) > 0.5:
      alternating_landings += 1

    should_stop, stop_reason, stop_truncated = _episode_stop_state(
      terminated=bool(terminated),
      step_info=step_info,
      episode_step=step,
      max_steps_per_episode=max_steps_per_episode,
    )
    if should_stop:
      termination_reason = stop_reason
      truncated = stop_truncated
      break

  denom_policy = max(policy_steps, 1)
  denom_landings = max(landing_events, 1)

  return EpisodeEvalRecord(
    trial_index=int(trial_index),
    eval_seed=int(eval_seed),
    ep_index=int(ep_index),
    displacement_x=float(final_imu_x - origin_imu_x),
    origin_imu_x=float(origin_imu_x),
    final_imu_x=float(final_imu_x),
    episode_length=int(episode_length),
    truncated=bool(truncated),
    termination_reason=str(termination_reason),
    alternating_landing_rate=float(alternating_landings / denom_landings),
    single_support_ratio=float(single_support_steps / denom_policy),
    double_support_ratio=float(double_support_steps / denom_policy),
    episode_return=float(ep_return),
    noise_applied=noise_applied,
  )


def run_checkpoint_eval(
  checkpoint_path: Path,
  *,
  device: str = "cpu",
  eval_seeds: tuple[int, ...] = EVAL_SEEDS,
  episodes_per_seed: int = EPISODES_PER_SEED,
) -> list[EpisodeEvalRecord]:
  """全 eval 試行を実行して per-episode 記録を返す。"""
  # 重み・環境とも ckpt run の学習設定を引き継ぎ、eval 向け override のみ適用
  policy_ctx = ctx_from_checkpoint(checkpoint_path)
  eval_context = build_eval_context(policy_ctx.cfg)
  agent = AgentPPO.from_checkpoint(policy_ctx, checkpoint_path, map_location=device)
  act_eval = agent.act_eval

  env = EnvBipedPPO(
    eval_context,
    enable_viewer=False,
    training_dr_enabled=False,
  )
  env.set_step_wall_sleep_sec(0.0)
  max_steps = int(eval_context.cfg.training.max_steps_per_episode)

  records: list[EpisodeEvalRecord] = []
  for plan in iter_eval_trials(
    eval_seeds=eval_seeds,
    episodes_per_seed=episodes_per_seed,
  ):
    records.append(
      run_eval_episode(
        env,
        act_eval,
        eval_seed=plan.eval_seed,
        ep_index=plan.ep_index,
        trial_index=plan.trial_index,
        max_steps_per_episode=max_steps,
      )
    )
  return records
