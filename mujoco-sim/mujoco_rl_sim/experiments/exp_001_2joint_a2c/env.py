import time

import mujoco
from mujoco_sim_common.viewer_visual_presets import apply_model_visual_preset, apply_passive_viewer_options

from mujoco_rl_sim.experiments.exp_001_2joint_a2c import config
from mujoco_rl_sim.experiments.exp_001_2joint_a2c.episode_state import EpisodeState
from mujoco_rl_sim.experiments.exp_001_2joint_a2c.observation import Observation
from mujoco_rl_sim.experiments.exp_001_2joint_a2c.reward import Reward
from mujoco_rl_sim.experiments.exp_001_2joint_a2c.termination import Termination
from mujoco_rl_sim.lib.ctrl import action_to_ctrl
from mujoco_rl_sim.lib.mujoco_paths import mujoco_sim_asset_path


class EnvExp0012JointA2C:
  """007_leg_2joint 用 A2C 環境（exp_001）。"""

  def __init__(self, *, enable_viewer: bool = True):
    xml_path = mujoco_sim_asset_path(config.XML_PATH)
    self.model = mujoco.MjModel.from_xml_path(xml_path)
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
    )

    terminated = self._termination.is_done(imu_z=raw.imu_z, upright=raw.upright)

    reward = reward_breakdown.total
    if terminated:
      reward += config.FALL_PENALTY

    self._observation.maybe_print_debug(
      episode_step=episode_step,
      reward=reward,
      knee_human_flex_bonus=reward_breakdown.knee_flex_bonus,
      knee_wrong_penalty=reward_breakdown.knee_wrong_penalty,
      raw=raw,
      episode=self._episode,
    )

    self._episode.prev_action = (knee_a, ankle_a)

    return obs.to_vector(), reward, terminated


Env010A2C = EnvExp0012JointA2C
