"""exp_029 用 Hydra Structured Config。

config.py の定数を段階的に置き換えるための型付き設定スキーマ。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from omegaconf import DictConfig, OmegaConf


@dataclass
class SimConfig:
  # ロボット・モデル
  robot_morphology: str = "biped_legs_only"
  robot_leg_count: int = 2
  robot_actuated_dof: int = 12
  xml_relative: str = "model/main.xml"

  # 周期・観測正規化
  physics_timestep_s: float = 0.002
  control_hz: int = 50
  obs_dim: int = 51
  action_dim: int = 12
  max_dx_per_step_base: float = 0.05
  max_foot_dx_per_step_base: float = 0.04
  max_gyro_rad_s: float = 10.0
  max_joint_vel_rad_s: float = 10.0
  max_imu_z: float = 1.2
  min_imu_z_norm: float = 0.0
  min_foot_z_norm: float = 0.0
  max_foot_z_norm: float = 0.35
  policy_hidden_sizes: tuple[int, ...] = (256, 256, 128)

  # Viewer 参考平面（z は termination.min_imu_z_stance を overlay 側で参照）
  viewer_height_plane_half_xy: tuple[float, float] = (3.0, 3.0)
  viewer_height_plane_thickness: float = 0.001

  @property
  def frame_skip(self) -> int:
    # 1 行動あたりの物理ステップ数（500Hz -> 50Hz なら 10）
    return int(round(1.0 / (self.physics_timestep_s * float(self.control_hz))))

  @property
  def control_timestep_s(self) -> float:
    return float(self.physics_timestep_s) * float(self.frame_skip)

  @property
  def max_dx_per_step(self) -> float:
    return float(self.max_dx_per_step_base) * float(self.frame_skip)

  @property
  def max_foot_dx_per_step(self) -> float:
    return float(self.max_foot_dx_per_step_base) * float(self.frame_skip)


@dataclass
class RewardConfig:
  # ENABLE 群
  enable_forward: bool = True
  enable_forward_foot: bool = False
  enable_progress: bool = False
  enable_walk_shaping: bool = False
  enable_upright_bonus: bool = False
  enable_posture_penalties: bool = False
  enable_double_support: bool = False
  enable_flight_duration: bool = False
  enable_effort: bool = True

  # 前進報酬
  forward_reward_scale: float = 50.0
  forward_min_upright: float = 0.50
  forward_require_foot_contact: bool = True
  forward_require_single_support: bool = False
  forward_imu_lean_gate: bool = False
  forward_imu_lean_gate_thresh: float = 0.10
  forward_imu_lean_gate_scale: float = 4.0
  forward_imu_lean_gate_min_mult: float = 0.15

  # すり足抑制
  double_support_penalty_scale: float = 8.0
  double_support_min_forward: float = 0.001

  # 交互歩行 shaping
  push_off_bonus_scale: float = 0.22
  push_off_min_foot_dx: float = 0.002
  push_off_min_imu_dz: float = 0.003
  push_off_min_knee_ext_vel: float = 0.12
  landing_bonus_scale: float = 0.35
  landing_max_toe_z: float = 0.07
  landing_max_heel_z: float = 0.07
  landing_max_forward_lean: float = 0.30
  alternating_landing_bonus_scale: float = 0.45
  swing_clearance_bonus_scale: float = 0.12
  swing_min_foot_z: float = 0.04

  # 姿勢・ペナルティ
  upright_bonus_scale: float = 0.8
  upright_bonus_thresh: float = 0.60
  upright_bonus_require_flight: bool = False
  upright_bonus_min_dx: float = 0.0
  lean_backward_penalty_scale: float = 3.0
  lean_backward_thresh: float = 0.12
  lean_forward_penalty_scale: float = 4.0
  lean_forward_thresh: float = 0.14
  lean_forward_min_aerial_steps: int = 2
  heading_align_min: float = 0.85
  heading_misalign_penalty_scale: float = 1.5
  lateral_tilt_thresh: float = 0.12
  lateral_tilt_penalty_scale: float = 2.5
  aerial_duration_penalty_scale: float = 0.18
  aerial_duration_penalty_after_steps: int = 4
  progress_reward_scale: float = 20.0
  progress_min_upright: float = 0.60
  progress_require_single_support: bool = True
  knee_hyperflex_max_rad: float = 0.95
  knee_hyperflex_penalty_scale: float = 2.5
  knee_hyperflex_aerial_only: bool = True
  imu_height_penalty_scale: float = 2.0
  target_imu_z: float = 0.55
  target_imu_z_single_stance: float = 0.50
  target_imu_z_double_stance: float = 0.52
  height_penalty_aerial_crash_z: float = 0.42
  knee_human_flex_bonus_scale: float = 0.0

  # effort
  effort_penalty_scale: float = 3.0


@dataclass
class TerminationConfig:
  min_imu_z: float = 0.3
  min_imu_z_stance: float = 0.3
  min_imu_upright: float = 0.52
  max_backward_lean_body: float = 0.38
  pose_termination_penalty: float = -30.0
  contact_shank_terminates: bool = False


@dataclass
class PpoConfig:
  # gamma は 1 physics step あたりの係数を保持し、実効値は frame_skip を掛ける。
  gamma_per_physics_step: float = 0.99
  gae_lambda: float = 0.95
  lr: float = 2.5e-4
  rollout_steps: int = 512
  value_coef: float = 0.5
  entropy_coef: float = 0.05
  max_grad_norm: float = 0.5
  minibatch_size: int = 256
  std_min: float = 0.08
  clip_eps: float = 0.2
  ppo_epochs: int = 8
  target_kl: float = 0.02
  reward_clip: float = 20.0
  adv_clip: float = 10.0
  adv_std_min: float = 0.1
  action_log_prob_eps: float = 1e-6
  log_prob_clip: float = 20.0
  _sim: SimConfig | None = field(default=None, init=False, repr=False, compare=False)

  @property
  def gamma(self) -> float:
    if self._sim is None:
      raise ValueError("PpoConfig.gamma の計算には _sim が必要です")
    return float(self.gamma_per_physics_step) ** int(self._sim.frame_skip)


@dataclass
class TrainingConfig:
  warmup_enabled: bool = False
  warmup_duration_s: float = 1.0
  num_updates: int = 5000
  max_steps_per_episode: int = 1500
  log_every: int = 5
  seed: int | None = None
  training_dr: bool = True
  post_train_eval: bool = True
  training_dr_pose_scale: float = 1.0
  training_dr_foot_friction_geoms: tuple[str, ...] = ("foot_plate", "right_foot_plate")
  training_dr_friction_slide_mult_range: tuple[float, float] = (0.85, 1.15)
  training_dr_actuator_kp_mult_range: tuple[float, float] = (0.90, 1.10)
  training_dr_actuator_kv_mult_range: tuple[float, float] = (0.90, 1.10)


@dataclass
class RuntimeConfig:
  viewer: bool = True
  telemetry: bool = True
  num_envs: int = 1
  step_wall_sleep_sec: float = 0.02
  telemetry_host: str = "0.0.0.0"
  telemetry_port: int = 8791


@dataclass
class WandbConfig:
  enabled: bool = True
  run_name: str = ""
  project: str = "exp_029_biped_ppo_walk"
  entity: str = ""
  tags: tuple[str, ...] = (
    "ppo",
    "biped",
    "biped_walk",
    "minimal_reward",
    "12dof",
    "forward",
    "effort_penalty",
    "policy_mlp_256_256_128",
  )
  termination_rolling_window: int = 100
  episode_rolling_window: int = 100


@dataclass
class ResumeConfig:
  checkpoint: str | None = None
  lr: float | None = None
  load_optimizer: bool = False


@dataclass
class CheckpointConfig:
  save_checkpoints: bool = True
  checkpoint_dir: str = ""
  checkpoint_every: int = 500
  save_latest: bool = True
  save_final: bool = True


@dataclass
class EvalConfig:
  spec_id: str = "biped_walk_eval_v0"
  eval_seeds: tuple[int, ...] = (101, 102, 103, 104, 105, 106, 107, 108, 109, 110)
  episodes_per_seed: int = 5
  primary_metric_name: str = "eval/displacement_x_mean"


@dataclass
class AppConfig:
  exp_name: str = "exp_029_biped_ppo_walk"
  xml_path: str = "model/main.xml"
  compare_baseline_exp: str = "exp_028_biped_ppo_walk"
  sim: SimConfig = field(default_factory=SimConfig)
  reward: RewardConfig = field(default_factory=RewardConfig)
  termination: TerminationConfig = field(default_factory=TerminationConfig)
  ppo: PpoConfig = field(default_factory=PpoConfig)
  training: TrainingConfig = field(default_factory=TrainingConfig)
  runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
  wandb: WandbConfig = field(default_factory=WandbConfig)
  resume: ResumeConfig = field(default_factory=ResumeConfig)
  checkpoint: CheckpointConfig = field(default_factory=CheckpointConfig)
  eval: EvalConfig = field(default_factory=EvalConfig)


def build_app_config(dc: DictConfig | AppConfig | dict[str, Any] | None = None) -> AppConfig:
  """DictConfig / dict を型付き AppConfig に変換する。"""
  base = OmegaConf.structured(AppConfig())
  if dc is None:
    merged = base
  elif isinstance(dc, AppConfig):
    merged = OmegaConf.merge(base, OmegaConf.structured(dc))
  else:
    merged = OmegaConf.merge(base, dc)

  app = OmegaConf.to_object(merged)
  if not isinstance(app, AppConfig):
    raise TypeError("AppConfig への変換に失敗しました")

  app.ppo._sim = app.sim

  # チェックポイント保存先（実験 runs ルート）を package_meta と同期する。
  from package_meta import CHECKPOINT_ROOT, EXP_NAME

  if not app.checkpoint.checkpoint_dir:
    app.checkpoint.checkpoint_dir = str(CHECKPOINT_ROOT)
  if not app.wandb.project:
    app.wandb.project = EXP_NAME
  app.exp_name = EXP_NAME

  # xml_path が相対指定なら実験ルート基準で展開し、絶対化して扱う。
  xml_candidate = Path(app.xml_path)
  if not xml_candidate.is_absolute():
    root = Path(__file__).resolve().parents[2]
    app.xml_path = str((root / xml_candidate).resolve())
  else:
    app.xml_path = str(xml_candidate)

  return app
