"""exp_023: 足裏板 25 cm×10 cm・踵 -2.5 cm はみ出し バイペッド PPO（exp_021 派生）。

``model/main.xml`` の足裏アルミ板 Y 幅 17 cm → 10 cm、中心 X を -2.5 cm（踵側はみ出し）。
学習ハイパラ・観測契約は exp_021 と同一（biped_ppo_v1）。
"""

from pathlib import Path

from .package_meta import CHECKPOINT_ROOT, EXP_DIR, EXP_NAME

ROBOT_MORPHOLOGY = "biped_legs_only"
ROBOT_LEG_COUNT = 2
ROBOT_ACTUATED_DOF = 10

_EXP_DIR = EXP_DIR
XML_RELATIVE = "model/main.xml"
XML_PATH = str(_EXP_DIR / XML_RELATIVE)

PHYSICS_TIMESTEP_S = 0.002
CONTROL_HZ = 50
FRAME_SKIP = int(round(1.0 / (PHYSICS_TIMESTEP_S * CONTROL_HZ)))
CONTROL_TIMESTEP_S = PHYSICS_TIMESTEP_S * FRAME_SKIP

# --- 報酬 shaping（前進スケール等は reward.py compute 内）---------------------------
UPRIGHT_BONUS_SCALE = 0.8
UPRIGHT_BONUS_THRESH = 0.60
UPRIGHT_BONUS_REQUIRE_FLIGHT = False
UPRIGHT_BONUS_MIN_DX = 0.0

LEAN_BACKWARD_PENALTY_SCALE = 3.0
LEAN_BACKWARD_THRESH = 0.12

LEAN_FORWARD_PENALTY_SCALE = 4.0
LEAN_FORWARD_THRESH = 0.14
LEAN_FORWARD_MIN_AERIAL_STEPS = 2

# 両脚とも非接地（遊脚期）
AERIAL_DURATION_PENALTY_SCALE = 0.12
AERIAL_DURATION_PENALTY_AFTER_STEPS = 8

PROGRESS_REWARD_SCALE = 20.0
PROGRESS_MIN_UPRIGHT = 0.60

KNEE_HYPERFLEX_MAX_RAD = 0.95
KNEE_HYPERFLEX_PENALTY_SCALE = 2.5
KNEE_HYPERFLEX_AERIAL_ONLY = True

IMU_HEIGHT_PENALTY_SCALE = 2.0
TARGET_IMU_Z = 0.55
TARGET_IMU_Z_STANCE = 0.46
HEIGHT_PENALTY_SKIP_WHEN_STANCE = True
HEIGHT_PENALTY_AERIAL_CRASH_Z = 0.42

# 片脚ホッパ向け（両脚では無効）
PUSH_OFF_BONUS_SCALE = 0.0
LANDING_BONUS_SCALE = 0.0
KNEE_HUMAN_FLEX_BONUS_SCALE = 0.0

EFFORT_PENALTY_SCALE = 3.0

CONTACT_SHANK_TERMINATES = False

# --- 観測: dx(1)+gyro(3)+zaxis(3)+imu_z(1)+feet(4)+joint_q(10)+joint_qvel(10)+prev_a(10) = 42
MAX_DX_PER_STEP = 0.05 * FRAME_SKIP
MAX_GYRO_RAD_S = 10.0
MAX_JOINT_VEL_RAD_S = 10.0
MAX_FOOT_DX_PER_STEP = 0.04 * FRAME_SKIP
MAX_IMU_Z = 1.2
MIN_IMU_Z_NORM = 0.0

ACTION_DIM = 10
OBS_DIM = 42

GAMMA = 0.99**FRAME_SKIP
GAE_LAMBDA = 0.95
LR = 3e-4
ROLLOUT_STEPS = 512
VALUE_COEF = 0.5
ENTROPY_COEF = 0.05
MAX_GRAD_NORM = 0.5
MINIBATCH_SIZE = 256
STD_MIN = 0.08
CLIP_EPS = 0.2
PPO_EPOCHS = 8
TARGET_KL = 0.02

REWARD_CLIP = 20.0
ADV_CLIP = 10.0
ADV_STD_MIN = 0.1
ACTION_LOG_PROB_EPS = 1e-6
LOG_PROB_CLIP = 20.0

from .warmup import default_warmup_action

WARMUP_ENABLED = True
WARMUP_DURATION_S = 1.0
WARMUP_ACTION_FN = default_warmup_action

NUM_UPDATES = 6_000
MAX_STEPS_PER_EPISODE = 15_000 // FRAME_SKIP
LOG_EVERY = 20
# 学習中ビューア（visualize=True 時は CONTROL_TIMESTEP_S で同期）
ENABLE_VIEWER = True

# 制御ステップごとの壁時計待ち（秒）。ビューア無効時の実時間化にも使用。
STEP_WALL_SLEEP_SEC = CONTROL_TIMESTEP_S

# Hub（robotics-hub テレメトリ）向け Socket.IO
TELEMETRY_ENABLED = True
TELEMETRY_HOST = "0.0.0.0"
TELEMETRY_PORT = 8791

SAVE_CHECKPOINTS = True
CHECKPOINT_DIR = str(CHECKPOINT_ROOT)
CHECKPOINT_EVERY = 500
CHECKPOINT_SAVE_LATEST = True
CHECKPOINT_SAVE_FINAL = True

USE_WANDB = True
WANDB_PROJECT = EXP_NAME
WANDB_RUN_NAME = ""
WANDB_ENTITY = ""
WANDB_TAGS = (
  "ppo",
  "biped",
  "biped_walk",
  "10dof",
  "forward",
  "progress_reward",
)
WANDB_TERMINATION_ROLLING_WINDOW = 100
# 学習ログ print / Issue 進捗用の直近エピソード数
EPISODE_ROLLING_WINDOW = 100

COMPARE_BASELINE_EXP = "exp_021_biped_ppo_hop_balance"


def training_config_dict() -> dict:
  return {
    "exp_name": EXP_NAME,
    "robot_morphology": ROBOT_MORPHOLOGY,
    "robot_leg_count": ROBOT_LEG_COUNT,
    "robot_actuated_dof": ROBOT_ACTUATED_DOF,
    "algorithm": "ppo",
    "compare_baseline_exp": COMPARE_BASELINE_EXP,
    "xml_path": XML_PATH,
    "physics_timestep_s": PHYSICS_TIMESTEP_S,
    "control_hz": CONTROL_HZ,
    "frame_skip": FRAME_SKIP,
    "control_timestep_s": CONTROL_TIMESTEP_S,
    "forward_reward_scale": 50.0,
    "forward_min_upright": 0.62,
    "progress_reward_scale": PROGRESS_REWARD_SCALE,
    "aerial_duration_penalty_scale": AERIAL_DURATION_PENALTY_SCALE,
    "obs_dim": OBS_DIM,
    "action_dim": ACTION_DIM,
    "gamma": GAMMA,
    "gae_lambda": GAE_LAMBDA,
    "lr": LR,
    "rollout_steps": ROLLOUT_STEPS,
    "entropy_coef": ENTROPY_COEF,
    "num_updates": NUM_UPDATES,
    "max_steps_per_episode": MAX_STEPS_PER_EPISODE,
    "warmup_enabled": WARMUP_ENABLED,
    "save_checkpoints": SAVE_CHECKPOINTS,
    "checkpoint_dir": CHECKPOINT_DIR,
    "checkpoint_every": CHECKPOINT_EVERY,
    "episode_rolling_window": EPISODE_ROLLING_WINDOW,
    "enable_viewer": ENABLE_VIEWER,
    "step_wall_sleep_sec": STEP_WALL_SLEEP_SEC,
    "telemetry_enabled": TELEMETRY_ENABLED,
    "telemetry_port": TELEMETRY_PORT,
  }
