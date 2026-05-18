import time

import mujoco
import mujoco.viewer
from mujoco_sim_common.viewer_visual_presets import apply_model_visual_preset, apply_passive_viewer_options

from mujoco_rl_sim.experiments.exp_001_2joint_a2c import config
from mujoco_rl_sim.experiments.exp_001_2joint_a2c.episode_state import EpisodeState
from mujoco_rl_sim.experiments.exp_001_2joint_a2c.observation import Observation
from mujoco_rl_sim.experiments.exp_001_2joint_a2c.reward import Reward
from mujoco_rl_sim.experiments.exp_001_2joint_a2c.termination import Termination
from mujoco_rl_sim.lib.ctrl import action_to_ctrl


class EnvExp0012JointA2C:
  """exp_001 用 A2C 環境（model/main.xml）。"""

  def __init__(self, *, enable_viewer: bool = True):
    self.model = mujoco.MjModel.from_xml_path(config.XML_PATH)
    apply_model_visual_preset(self.model)
    self.data = mujoco.MjData(self.model)

    self.viewer = None
    if enable_viewer:
      self.viewer = mujoco.viewer.launch_passive(self.model, self.data)
      apply_passive_viewer_options(self.viewer)

    self._knee_ctrl_range = self.model.actuator_ctrlrange[self.model.actuator("knee_servo").id].copy()
    self._ankle_ctrl_range = self.model.actuator_ctrlrange[self.model.actuator("ankle_servo").id].copy()

    self._episode = EpisodeState()
    self._observation = Observation(self.model)
    self._reward = Reward()
    self._termination = Termination()

  def reset(self):
    mujoco.mj_resetData(self.model, self.data)
    mujoco.mj_forward(self.model, self.data)
    if self.viewer is not None:
      self.viewer.sync()

    imu_x = float(self.data.site("imu_site").xpos[0])
    self._episode.reset_imu_tracking(imu_x)
    self._episode.prev_action = (0.0, 0.0)

    obs, _raw = self._observation.build(self.model, self.data, self._episode, dx=0.0)
    return obs.to_vector()

  def step(self, action, visualize: bool = False, episode_step: int = 0):
    knee_a = max(-1.0, min(1.0, float(action[0])))
    ankle_a = max(-1.0, min(1.0, float(action[1])))

    self.data.ctrl[self.model.actuator("knee_servo").id] = action_to_ctrl(knee_a, self._knee_ctrl_range)
    self.data.ctrl[self.model.actuator("ankle_servo").id] = action_to_ctrl(ankle_a, self._ankle_ctrl_range)

    mujoco.mj_step(self.model, self.data)
    if self.viewer is not None:
      self.viewer.sync()

    if visualize:
      time.sleep(self.model.opt.timestep)

    imu_x = float(self.data.site("imu_site").xpos[0])
    dx = self._episode.advance_imu_x(imu_x)

    obs, raw = self._observation.build(self.model, self.data, self._episode, dx=dx)

    reward_breakdown = self._reward.compute(
      dx=dx,
      upright=raw.upright,
      knee_angle=raw.knee_angle,
      foot_on_floor=raw.foot_on_floor,
      imu_z=raw.imu_z,
      imu_zaxis_x=raw.imu_zaxis_x,
    )

    termination_reason = self._termination.done_reason(
      imu_z=raw.imu_z,
      upright=raw.upright,
      imu_zaxis_x=raw.imu_zaxis_x,
    )
    terminated = termination_reason is not None

    reward = reward_breakdown.total
    if terminated:
      reward += config.FALL_PENALTY

    # self._observation.maybe_print_debug(
    #   episode_step=episode_step,
    #   reward=reward,
    #   knee_human_flex_bonus=reward_breakdown.knee_flex_bonus,
    #   raw=raw,
    #   episode=self._episode,
    # )

    self._episode.prev_action = (knee_a, ankle_a)

    step_info = {
      "upright": raw.upright,
      "foot_on_floor": float(raw.foot_on_floor),
      "reward_forward": reward_breakdown.forward,
      "reward_upright": reward_breakdown.upright,
      "reward_backward_lean_penalty": reward_breakdown.backward_lean_penalty,
      "reward_height_penalty": reward_breakdown.height_penalty,
      "termination_reason": termination_reason,
    }

    return obs.to_vector(), reward, terminated, step_info


Env010A2C = EnvExp0012JointA2C
