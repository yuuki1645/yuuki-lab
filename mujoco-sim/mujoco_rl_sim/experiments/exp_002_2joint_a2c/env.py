import time

import mujoco
import mujoco.viewer
from mujoco_sim_common.viewer_visual_presets import apply_model_visual_preset, apply_passive_viewer_options

from mujoco_rl_sim.experiments.exp_002_2joint_a2c import config
from mujoco_rl_sim.experiments.exp_002_2joint_a2c.episode_state import EpisodeState
from mujoco_rl_sim.experiments.exp_002_2joint_a2c.observation import Observation
from mujoco_rl_sim.experiments.exp_002_2joint_a2c.reward import Reward
from mujoco_rl_sim.experiments.exp_002_2joint_a2c.termination import (
  NOT_TERMINATED,
  Termination,
  TerminationOutcome,
)
from mujoco_rl_sim.experiments.exp_002_2joint_a2c.lib.action import ActionBinding


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

    self._episode = EpisodeState()
    self._action = ActionBinding(self.model)
    self._observation = Observation(self.model)
    self._reward = Reward()
    self._termination = Termination(self.model)

  def reset(self):
    mujoco.mj_resetData(self.model, self.data)
    mujoco.mj_forward(self.model, self.data)
    if self.viewer is not None:
      self.viewer.sync()

    # エピソード内の前進量 dx は IMU の X 変位差分。原点をここで記録する
    imu_x = float(self.data.site("imu_site").xpos[0])
    self._episode.reset_imu_tracking(imu_x)
    self._episode.prev_action = (0.0, 0.0)

    # policy_obs: 正規化済み観測（ObsExp002）→ ポリシー入力。step_physics は reset では不要
    policy_obs, _ = self._observation.build(self.model, self.data, self._episode, dx=0.0)
    return policy_obs.to_vector()

  def step(self, action, visualize: bool = False, episode_step: int = 0):
    # 1 制御ステップ = FRAME_SKIP 回の物理ステップ（50 Hz ポリシー / 500 Hz 物理）
    prev_action = self._action.apply(self.data, action)

    termination = NOT_TERMINATED
    for _ in range(config.FRAME_SKIP):
      mujoco.mj_step(self.model, self.data)
      if self.viewer is not None:
        self.viewer.sync()

      # basket 接触は物理ステップごとに判定し、満たした時点で残りの mj_step を打ち切る
      termination = self._termination.done_reason(self.data)
      if termination.terminated:
        break

    if visualize:
      time.sleep(config.CONTROL_TIMESTEP_S)

    # 観測・報酬は制御レートで一度だけ（ループ後の最終姿勢を使う）
    imu_x = float(self.data.site("imu_site").xpos[0])
    dx = self._episode.advance_imu_x(imu_x)

    # observation.build は同じ MuJoCo 状態から二種類を返す:
    #   policy_obs   … ObsExp002。clip/正規化済み（おおよそ [-1, 1]）。train のニューラルネット入力
    #   step_physics … StepPhysics。生の物理量（m, rad, bool など）。報酬・wandb・デバッグ用
    policy_obs, step_physics = self._observation.build(
      self.model, self.data, self._episode, dx=dx
    )

    reward_breakdown = self._reward.compute(step_physics)

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

    # ログ用メトリクスは解釈しやすい生値（step_physics）を使う
    step_info = {
      "upright": step_physics.upright,
      "foot_on_floor": float(step_physics.foot_on_floor),
      "reward_forward": reward_breakdown.forward,
      "reward_termination_penalty": termination.penalty,
      "reward_contact_basket_penalty": termination.penalty,
      # 旧キー名（wandb 互換）
      "reward_fall_penalty": termination.penalty,
      "termination_reason": termination_reason,
      "basket_contact_normal_force_n": termination.contact_normal_force_n,
    }

    return policy_obs.to_vector(), reward, terminated, step_info  # 第1戻り値のみポリシー向け


Env010A2C = EnvExp0022JointA2C
