import time

import mujoco
import mujoco.viewer
from mujoco_sim_common.viewer_visual_presets import apply_model_visual_preset, apply_passive_viewer_options

from mujoco_rl_sim.experiments.exp_002_2joint_a2c import config
from mujoco_rl_sim.experiments.exp_002_2joint_a2c.episode_state import EpisodeState
from mujoco_rl_sim.experiments.exp_002_2joint_a2c.observation import Observation
from mujoco_rl_sim.experiments.exp_002_2joint_a2c.reward import Reward
from mujoco_rl_sim.experiments.exp_002_2joint_a2c.termination import Termination
from mujoco_rl_sim.experiments.exp_002_2joint_a2c.lib.ctrl import action_to_ctrl


class EnvExp0022JointA2C:
  """exp_002 用 A2C 環境（model/main.xml）。

  物理は MuJoCo 既定 500 Hz、ポリシーは 50 Hz（1 行動あたり FRAME_SKIP 回 mj_step）。
  """

  def __init__(self, *, enable_viewer: bool = True):
    self.model = mujoco.MjModel.from_xml_path(config.XML_PATH)
    apply_model_visual_preset(self.model)
    self.data = mujoco.MjData(self.model)

    physics_dt = float(self.model.opt.timestep)
    if abs(physics_dt - config.PHYSICS_TIMESTEP_S) > 1e-9:
      raise ValueError(
        f"model.opt.timestep={physics_dt} != config.PHYSICS_TIMESTEP_S={config.PHYSICS_TIMESTEP_S}"
      )

    self.viewer = None
    if enable_viewer:
      self.viewer = mujoco.viewer.launch_passive(self.model, self.data)
      apply_passive_viewer_options(self.viewer)

    self._knee_ctrl_range = self.model.actuator_ctrlrange[self.model.actuator("knee_servo").id].copy()
    self._ankle_ctrl_range = self.model.actuator_ctrlrange[self.model.actuator("ankle_servo").id].copy()

    self._episode = EpisodeState()
    self._observation = Observation(self.model)
    self._reward = Reward()
    self._termination = Termination(self.model)

  def reset(self):
    mujoco.mj_resetData(self.model, self.data)
    mujoco.mj_forward(self.model, self.data)
    if self.viewer is not None:
      self.viewer.sync()

    imu_x = float(self.data.site("imu_site").xpos[0])
    self._episode.reset_imu_tracking(imu_x)
    self._episode.prev_action = (0.0, 0.0)

    policy_obs, _ = self._observation.build(self.model, self.data, self._episode, dx=0.0)
    return policy_obs.to_vector()

  def step(self, action, visualize: bool = False, episode_step: int = 0):
    knee_a = max(-1.0, min(1.0, float(action[0])))
    ankle_a = max(-1.0, min(1.0, float(action[1])))

    knee_ctrl = action_to_ctrl(knee_a, self._knee_ctrl_range)
    ankle_ctrl = action_to_ctrl(ankle_a, self._ankle_ctrl_range)
    knee_act_id = self.model.actuator("knee_servo").id
    ankle_act_id = self.model.actuator("ankle_servo").id
    self.data.ctrl[knee_act_id] = knee_ctrl
    self.data.ctrl[ankle_act_id] = ankle_ctrl

    termination_reason = None
    for _ in range(config.FRAME_SKIP):
      mujoco.mj_step(self.model, self.data)
      if self.viewer is not None:
        self.viewer.sync()

      termination_reason = self._termination.done_reason(self.data)
      if termination_reason is not None:
        break

    if visualize:
      time.sleep(config.CONTROL_TIMESTEP_S)

    imu_x = float(self.data.site("imu_site").xpos[0])
    dx = self._episode.advance_imu_x(imu_x)

    policy_obs, step_physics = self._observation.build(
      self.model, self.data, self._episode, dx=dx
    )

    reward_breakdown = self._reward.compute(step_physics)

    terminated = termination_reason is not None

    reward = reward_breakdown.total
    if terminated:
      reward += config.FALL_PENALTY

    # self._observation.maybe_print_debug(
    #   episode_step=episode_step,
    #   reward=reward,
    #   knee_human_flex_bonus=reward_breakdown.knee_flex_bonus,
    #   step_physics=step_physics,
    #   episode=self._episode,
    # )

    self._episode.prev_action = (knee_a, ankle_a)

    step_info = {
      "upright": step_physics.upright,
      "foot_on_floor": float(step_physics.foot_on_floor),
      "reward_forward": reward_breakdown.forward,
      "reward_upright": reward_breakdown.upright,
      "reward_backward_lean_penalty": reward_breakdown.backward_lean_penalty,
      "reward_height_penalty": reward_breakdown.height_penalty,
      "termination_reason": termination_reason,
    }

    return policy_obs.to_vector(), reward, terminated, step_info


Env010A2C = EnvExp0022JointA2C
