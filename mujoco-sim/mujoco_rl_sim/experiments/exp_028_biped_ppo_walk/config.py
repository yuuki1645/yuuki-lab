"""exp_028: exp_026 ベース・交互片脚歩行（ホップ/すり足を抑止）。

前進は片足支持時のみ。両足接地中の前進・飛翔中の IMU すり前進は無効化。
"""

from pathlib import Path

from package_meta import CHECKPOINT_ROOT, EXP_DIR, EXP_NAME

ROBOT_MORPHOLOGY = "biped_legs_only"
ROBOT_LEG_COUNT = 2
ROBOT_ACTUATED_DOF = 12

_EXP_DIR = EXP_DIR
XML_RELATIVE = "model/main.xml"
XML_PATH = str(_EXP_DIR / XML_RELATIVE)

# MuJoCo は 500 Hz（0.002 s）で物理積分。ポリシーは 50 Hz で 1 行動 = FRAME_SKIP 物理ステップ。
PHYSICS_TIMESTEP_S = 0.002
CONTROL_HZ = 50
FRAME_SKIP = int(round(1.0 / (PHYSICS_TIMESTEP_S * CONTROL_HZ)))  # 10
CONTROL_TIMESTEP_S = PHYSICS_TIMESTEP_S * FRAME_SKIP  # 0.02 s

# --- 前進（reward.py）-----------------------------------------------------------
# 歩行主線: 片足支持かつ直立時だけ IMU/支持脚の +X 移動に報酬（すり足・ホップ抑制）。
FORWARD_REWARD_SCALE = 50.0
FORWARD_MIN_UPRIGHT = 0.62
FORWARD_REQUIRE_FOOT_CONTACT = True
FORWARD_REQUIRE_SINGLE_SUPPORT = True  # 両足接地・完全飛翔中は forward=0
FORWARD_IMU_LEAN_GATE = True
FORWARD_IMU_LEAN_GATE_THRESH = 0.10
FORWARD_IMU_LEAN_GATE_SCALE = 4.0
FORWARD_IMU_LEAN_GATE_MIN_MULT = 0.15

# --- すり足抑制 ----------------------------------------------------------------
DOUBLE_SUPPORT_PENALTY_SCALE = 8.0
DOUBLE_SUPPORT_MIN_FORWARD = 0.001

# --- 交互歩行 shaping ----------------------------------------------------------
PUSH_OFF_BONUS_SCALE = 0.22
PUSH_OFF_MIN_FOOT_DX = 0.002
PUSH_OFF_MIN_IMU_DZ = 0.003
PUSH_OFF_MIN_KNEE_EXT_VEL = 0.12

LANDING_BONUS_SCALE = 0.35
LANDING_MAX_TOE_Z = 0.07
LANDING_MAX_HEEL_Z = 0.07
LANDING_MAX_FORWARD_LEAN = 0.30

ALTERNATING_LANDING_BONUS_SCALE = 0.45
SWING_CLEARANCE_BONUS_SCALE = 0.12
SWING_MIN_FOOT_Z = 0.04

# --- 直立・傾き（exp_024 系を維持）---------------------------------------------
UPRIGHT_BONUS_SCALE = 0.8
UPRIGHT_BONUS_THRESH = 0.60
UPRIGHT_BONUS_REQUIRE_FLIGHT = False
UPRIGHT_BONUS_MIN_DX = 0.0

LEAN_BACKWARD_PENALTY_SCALE = 3.0
LEAN_BACKWARD_THRESH = 0.12

LEAN_FORWARD_PENALTY_SCALE = 4.0
LEAN_FORWARD_THRESH = 0.14
LEAN_FORWARD_MIN_AERIAL_STEPS = 2

HEADING_ALIGN_MIN = 0.85
HEADING_MISALIGN_PENALTY_SCALE = 1.5

LATERAL_TILT_THRESH = 0.12
LATERAL_TILT_PENALTY_SCALE = 2.5

# 両足非接地（スイング遷移のみ短く許容）
AERIAL_DURATION_PENALTY_SCALE = 0.18
AERIAL_DURATION_PENALTY_AFTER_STEPS = 4

PROGRESS_REWARD_SCALE = 20.0
PROGRESS_MIN_UPRIGHT = 0.60
PROGRESS_REQUIRE_SINGLE_SUPPORT = True

KNEE_HYPERFLEX_MAX_RAD = 0.95
KNEE_HYPERFLEX_PENALTY_SCALE = 2.5
KNEE_HYPERFLEX_AERIAL_ONLY = True

IMU_HEIGHT_PENALTY_SCALE = 2.0
TARGET_IMU_Z = 0.55
TARGET_IMU_Z_SINGLE_STANCE = 0.50
TARGET_IMU_Z_DOUBLE_STANCE = 0.52
HEIGHT_PENALTY_AERIAL_CRASH_Z = 0.42

KNEE_HUMAN_FLEX_BONUS_SCALE = 0.0

EFFORT_PENALTY_SCALE = 3.0
APPLY_EFFORT_PENALTY = False

CONTACT_SHANK_TERMINATES = False
MAX_BACKWARD_LEAN_BODY = 0.38

# --- 観測: 51 次元（contract/biped_walk_v1.py のスライス定義と一致）---------
# 1 + 3 + 3 + 1 + 2 + 2 + 2 + 2 + 1 + 12 + 12 + 12 = 51
MAX_DX_PER_STEP = 0.05 * FRAME_SKIP
MAX_GYRO_RAD_S = 10.0
MAX_JOINT_VEL_RAD_S = 10.0
MAX_FOOT_DX_PER_STEP = 0.04 * FRAME_SKIP
MAX_IMU_Z = 1.2
MIN_IMU_Z_NORM = 0.0
MIN_FOOT_Z_NORM = 0.0
MAX_FOOT_Z_NORM = 0.35

ACTION_DIM = 12
OBS_DIM = 51

POLICY_HIDDEN_SIZES: tuple[int, ...] = (256, 256, 128)

# --- PPO ハイパラ（rl/agent.py）-----------------------------------------------
# GAMMA は 1 物理ステップではなく 1 制御ステップ（FRAME_SKIP 分）基準
GAMMA = 0.99**FRAME_SKIP
GAE_LAMBDA = 0.95
LR = 2.5e-4
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

from sim.warmup import default_warmup_action

WARMUP_ENABLED = True
WARMUP_DURATION_S = 1.0
WARMUP_ACTION_FN = default_warmup_action

NUM_UPDATES = 5_000
MAX_STEPS_PER_EPISODE = 15_000 // FRAME_SKIP
LOG_EVERY = 5
ENABLE_VIEWER = True

STEP_WALL_SLEEP_SEC = CONTROL_TIMESTEP_S

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
  "alternating_gait",
  "12dof",
  "forward",
  "progress_reward",
  "body_frame_lean",
  "heading_penalty",
  "single_support",
  "policy_mlp_256_256_128",
)
WANDB_TERMINATION_ROLLING_WINDOW = 100
EPISODE_ROLLING_WINDOW = 100

COMPARE_BASELINE_EXP = "exp_026_biped_ppo_hop_balance"


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
    "forward_reward_scale": FORWARD_REWARD_SCALE,
    "forward_require_single_support": FORWARD_REQUIRE_SINGLE_SUPPORT,
    "double_support_penalty_scale": DOUBLE_SUPPORT_PENALTY_SCALE,
    "alternating_landing_bonus_scale": ALTERNATING_LANDING_BONUS_SCALE,
    "progress_reward_scale": PROGRESS_REWARD_SCALE,
    "aerial_duration_penalty_after_steps": AERIAL_DURATION_PENALTY_AFTER_STEPS,
    "heading_align_min": HEADING_ALIGN_MIN,
    "obs_dim": OBS_DIM,
    "action_dim": ACTION_DIM,
    "policy_hidden_sizes": POLICY_HIDDEN_SIZES,
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
