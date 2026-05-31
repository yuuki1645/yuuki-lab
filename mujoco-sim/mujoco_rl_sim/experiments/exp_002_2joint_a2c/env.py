"""exp_002 の Gym 風環境ラッパー。

reset / step のインタフェースで MuJoCo を回し、観測・報酬・終了を各モジュールに委譲する。
1 step = FRAME_SKIP 回の mj_step（ポリシー 50 Hz / 物理 500 Hz）。
"""

import time

import mujoco
import mujoco.viewer
from mujoco_sim_common.viewer_visual_presets import apply_model_visual_preset, apply_passive_viewer_options

import config
from episode_state import EpisodeState
from observation import Observation
from effort import EffortTracker
from reward import Reward
from termination import (
  NOT_TERMINATED,
  REASON_CONTACT_BASKET,
  REASON_CONTACT_SHANK,
  REASON_CONTACT_THIGH,
  Termination,
  TerminationOutcome,
)
from lib.action import ActionBinding


class EnvExp0022JointA2C:
  """exp_002 用 A2C 環境（model/main.xml）。

  物理は MuJoCo 既定 500 Hz、ポリシーは 50 Hz（1 行動あたり FRAME_SKIP 回 mj_step）。
  """

  def __init__(self, *, enable_viewer: bool = True):
    self.model = mujoco.MjModel.from_xml_path(config.XML_PATH)
    apply_model_visual_preset(self.model)
    self.data = mujoco.MjData(self.model)

    # XML と config の物理ステップがずれると FRAME_SKIP の意味が変わるため起動時に確認
    physics_dt = float(self.model.opt.timestep)
    if abs(physics_dt - config.PHYSICS_TIMESTEP_S) > 1e-9:
      raise ValueError(
        f"model.opt.timestep={physics_dt} != config.PHYSICS_TIMESTEP_S={config.PHYSICS_TIMESTEP_S}"
      )

    self.viewer = None
    if enable_viewer:
      self.viewer = mujoco.viewer.launch_passive(self.model, self.data)
      apply_passive_viewer_options(self.viewer)

    # エピソード状態・行動・観測・報酬・負荷・終了は責務ごとに分割
    self._episode = EpisodeState()
    self._action = ActionBinding(self.model)
    self._observation = Observation(self.model)
    self._reward = Reward()
    self._effort = EffortTracker(self.model)  # 計測は常時。報酬への反映は config.APPLY_EFFORT_PENALTY
    self._termination = Termination(self.model)

  def reset(self):
    mujoco.mj_resetData(self.model, self.data)
    mujoco.mj_forward(self.model, self.data)
    if self.viewer is not None:
      self.viewer.sync()

    # 前進量 dx / foot_dx は各 site の X 変位差分。原点をここで記録する
    imu_x = float(self.data.site("imu_site").xpos[0])
    foot_x = float(self.data.site("foot_site").xpos[0])
    self._episode.reset_forward_tracking(imu_x=imu_x, foot_x=foot_x)
    self._episode.prev_action = (0.0, 0.0)

    # policy_obs: 正規化済み観測（ObsExp002）→ ポリシー入力。step_physics は reset では不要
    policy_obs, _ = self._observation.build(
      self.model, self.data, self._episode, dx=0.0, foot_dx=0.0
    )
    return policy_obs.to_vector()

  def step(self, action, visualize: bool = False, episode_step: int = 0):
    # 1 制御ステップ = FRAME_SKIP 回の物理ステップ（50 Hz ポリシー / 500 Hz 物理）
    prev_action = self._action.apply(self.data, action)

    termination = NOT_TERMINATED
    self._effort.reset_control_step()
    for _ in range(config.FRAME_SKIP):
      mujoco.mj_step(self.model, self.data)
      self._effort.record_physics_step(self.data)
      if self.viewer is not None:
        self.viewer.sync()

      # basket / thigh / shank の床接触は物理ステップごとに判定し、満たした時点で打ち切る
      termination = self._termination.done_reason(self.data)
      if termination.terminated:
        break

    effort = self._effort.control_step_breakdown()

    if visualize:
      time.sleep(config.CONTROL_TIMESTEP_S)

    # 観測・報酬は制御レートで一度だけ（ループ後の最終姿勢を使う）
    imu_x = float(self.data.site("imu_site").xpos[0])
    foot_x = float(self.data.site("foot_site").xpos[0])
    dx = self._episode.advance_imu_x(imu_x)
    foot_dx = self._episode.advance_foot_x(foot_x)

    # observation.build は同じ MuJoCo 状態から二種類を返す:
    #   policy_obs   … ObsExp002。clip/正規化済み（おおよそ [-1, 1]）。train のニューラルネット入力
    #   step_physics … StepPhysics。生の物理量（m, rad, bool など）。報酬・wandb・デバッグ用
    policy_obs, step_physics = self._observation.build(
      self.model, self.data, self._episode, dx=dx, foot_dx=foot_dx
    )

    reward_breakdown = self._reward.compute(step_physics, effort=effort)

    terminated = termination.terminated
    termination_reason = termination.reason

    reward = reward_breakdown.total + termination.penalty  # ペナルティは終了ステップのみ非ゼロ

    # self._observation.maybe_print_debug(
    #   episode_step=episode_step,
    #   reward=reward,
    #   step_physics=step_physics,
    #   episode=self._episode,
    # )

    # 次ステップの観測に載る「直前のポリシー出力」（クリップ済み [-1, 1]）
    self._episode.prev_action = prev_action

    contact_force_n = termination.contact_normal_force_n
    step_info = {
      "upright": step_physics.upright,
      "foot_on_floor": float(step_physics.foot_on_floor),
      "reward_forward": reward_breakdown.forward,
      "reward_forward_imu": reward_breakdown.forward_imu,
      "reward_forward_foot": reward_breakdown.forward_foot,
      "foot_dx": step_physics.foot_dx,
      "reward_effort_penalty": reward_breakdown.effort_penalty,
      "effort_power_cost": reward_breakdown.effort_power_cost,
      "reward_termination_penalty": termination.penalty,
      "reward_contact_basket_penalty": (
        termination.penalty if termination_reason == REASON_CONTACT_BASKET else 0.0
      ),
      "reward_contact_thigh_penalty": (
        termination.penalty if termination_reason == REASON_CONTACT_THIGH else 0.0
      ),
      "reward_contact_shank_penalty": (
        termination.penalty if termination_reason == REASON_CONTACT_SHANK else 0.0
      ),
      # 旧キー名（wandb 互換）
      "reward_fall_penalty": termination.penalty,
      "termination_reason": termination_reason,
      "contact_normal_force_n": contact_force_n,
      "basket_contact_normal_force_n": (
        contact_force_n if termination_reason == REASON_CONTACT_BASKET else None
      ),
      "thigh_contact_normal_force_n": (
        contact_force_n if termination_reason == REASON_CONTACT_THIGH else None
      ),
      "shank_contact_normal_force_n": (
        contact_force_n if termination_reason == REASON_CONTACT_SHANK else None
      ),
    }

    return policy_obs.to_vector(), reward, terminated, step_info  # 第1戻り値のみポリシー向け


# 旧実験名との互換エイリアス
Env010A2C = EnvExp0022JointA2C
