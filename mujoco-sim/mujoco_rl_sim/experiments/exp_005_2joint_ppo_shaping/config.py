"""exp_005: 2 関節脚 PPO + exp_004 と同一の観測・報酬 shaping（50 Hz 制御）。

観測・報酬・終了は exp_004_2joint_a2c_shaping と同一（reward.py / termination.py / observation.py）。
アルゴリズムのみ PPO（GAE + clipped surrogate）に変更。exp_004 との比較用。
"""

from pathlib import Path

from .package_meta import CHECKPOINT_ROOT, EXP_DIR, EXP_NAME

# --- MuJoCo / 制御レート -------------------------------------------------------
_EXP_DIR = EXP_DIR
XML_RELATIVE = "model/main.xml"
XML_PATH = str(_EXP_DIR / XML_RELATIVE)

PHYSICS_TIMESTEP_S = 0.002
CONTROL_HZ = 50
FRAME_SKIP = int(round(1.0 / (PHYSICS_TIMESTEP_S * CONTROL_HZ)))  # 10
CONTROL_TIMESTEP_S = PHYSICS_TIMESTEP_S * FRAME_SKIP  # 0.02 s

# --- 本丸: 前進報酬（reward.py）— exp_004 と同一 --------------------------------
FORWARD_REWARD_SCALE = 80.0
FORWARD_MIN_UPRIGHT = 0.65
FORWARD_REQUIRE_FOOT_CONTACT = False

# --- shaping: 直立ボーナス — exp_004 と同一 ------------------------------------
UPRIGHT_BONUS_SCALE = 2.0
UPRIGHT_BONUS_THRESH = 0.55

# --- shaping: 後傾・低姿勢ペナルティ — exp_004 と同一 ----------------------------
LEAN_BACKWARD_PENALTY_SCALE = 3.0
LEAN_BACKWARD_THRESH = 0.12
IMU_HEIGHT_PENALTY_SCALE = 2.0
TARGET_IMU_Z = 0.55

# --- shaping: 膝屈曲ボーナス — exp_004 と同一 ------------------------------------
KNEE_HUMAN_FLEX_MIN_RAD = 0.02
KNEE_HUMAN_FLEX_MAX_RAD = 1.2
KNEE_HUMAN_FLEX_BONUS_SCALE = 0.15
KNEE_FLEX_MIN_UPRIGHT = 0.55

# --- 筋負荷 — exp_004 と同一 ---------------------------------------------------
EFFORT_PENALTY_SCALE = 5.0
APPLY_EFFORT_PENALTY = False

# --- 姿勢ベース早期終了 — exp_004 と同一 ---------------------------------------
MIN_IMU_Z = 0.42
MIN_IMU_UPRIGHT = 0.55
MAX_BACKWARD_LEAN = 0.40
POSE_TERMINATION_PENALTY = -30.0

# --- 接触ベース早期終了 — exp_004 と同一 ---------------------------------------
CONTACT_FLOOR_PENALTY_BASE = -20.0
CONTACT_FLOOR_PENALTY_PER_N = -0.016
CONTACT_FLOOR_MIN_FORCE_N = 0.0
CONTACT_FLOOR_FORCE_CAP_N = 10_000.0
CONTACT_FLOOR_PENALTY_MIN = -200.0
CONTACT_LINK_PENALTY_SCALE = 0.5

CONTACT_BASKET_PENALTY_BASE = CONTACT_FLOOR_PENALTY_BASE
CONTACT_BASKET_PENALTY_PER_N = CONTACT_FLOOR_PENALTY_PER_N
CONTACT_BASKET_MIN_FORCE_N = CONTACT_FLOOR_MIN_FORCE_N
CONTACT_BASKET_FORCE_CAP_N = CONTACT_FLOOR_FORCE_CAP_N
CONTACT_BASKET_PENALTY_MIN = CONTACT_FLOOR_PENALTY_MIN


def contact_floor_termination_penalty(
  normal_force_n: float,
  *,
  penalty_scale: float = 1.0,
) -> float:
  """geom−floor 接触の法線力 [N] から終了ペナルティを計算する。"""
  scale = float(penalty_scale)
  capped_span = max(0.0, CONTACT_FLOOR_FORCE_CAP_N - CONTACT_FLOOR_MIN_FORCE_N)
  excess_force_n = min(
    max(0.0, float(normal_force_n) - CONTACT_FLOOR_MIN_FORCE_N),
    capped_span,
  )
  penalty = scale * (
    CONTACT_FLOOR_PENALTY_BASE + CONTACT_FLOOR_PENALTY_PER_N * excess_force_n
  )
  return max(penalty, scale * CONTACT_FLOOR_PENALTY_MIN)


def contact_basket_termination_penalty(normal_force_n: float) -> float:
  return contact_floor_termination_penalty(normal_force_n, penalty_scale=1.0)


def contact_link_termination_penalty(normal_force_n: float) -> float:
  return contact_floor_termination_penalty(
    normal_force_n, penalty_scale=CONTACT_LINK_PENALTY_SCALE
  )

# --- 観測正規化 — exp_004 と同一 -----------------------------------------------
MAX_DX_PER_STEP = 0.05 * FRAME_SKIP  # 0.5 [m] @ 50 Hz
MAX_GYRO_RAD_S = 10.0
MAX_JOINT_VEL_RAD_S = 10.0
MAX_COM_X_OFFSET = 0.6
MAX_IMU_Z = 1.2
MIN_IMU_Z_NORM = 0.0

OBS_DIM = 19
ACTION_DIM = 2

# --- PPO（agent.py）— ネット構造・γ・探索は exp_004 A2C に合わせた出発点 ------
GAMMA = 0.99**FRAME_SKIP
# GAE: advantage の平滑化。1 に近いほど長い将来報酬を見る（0.95 がよく使われる）
GAE_LAMBDA = 0.95
LR = 3e-4
# 1 回の update 前に環境で集めるステップ数（このバッファを PPO で何度も学習）
ROLLOUT_STEPS = 512
VALUE_COEF = 0.5
ENTROPY_COEF = 0.04
MAX_GRAD_NORM = 0.5
MINIBATCH_SIZE = 256
STD_MIN = 0.08

# 方策比 r を [1-ε, 1+ε] に収める幅（0.2 が Schulman らの既定に近い）
CLIP_EPS = 0.2
# 同一ロールアウトを何周学習するか（多いほどデータ効率↑・方策変化↑）
PPO_EPOCHS = 8
# 1 epoch 平均の近似 KL がこれを超えたら残り epoch をスキップ（0 で無効）
TARGET_KL = 0.02

REWARD_CLIP = 20.0
ADV_CLIP = 10.0
ADV_STD_MIN = 0.1
ACTION_LOG_PROB_EPS = 1e-6
LOG_PROB_CLIP = 20.0

from .warmup import default_warmup_action

WARMUP_ENABLED = True
WARMUP_DURATION_S = 1.2
WARMUP_ACTION_FN = default_warmup_action

NUM_UPDATES = 10_100
MAX_STEPS_PER_EPISODE = 3000 // FRAME_SKIP
LOG_EVERY = 20
ENABLE_VIEWER = True

SAVE_CHECKPOINTS = True
CHECKPOINT_DIR = str(CHECKPOINT_ROOT)
CHECKPOINT_EVERY = 500
CHECKPOINT_SAVE_LATEST = True
CHECKPOINT_SAVE_FINAL = True

USE_WANDB = True
WANDB_PROJECT = EXP_NAME
WANDB_RUN_NAME = ""
WANDB_ENTITY = ""
WANDB_TAGS = ("ppo", "2joint", "shaping")
WANDB_TERMINATION_ROLLING_WINDOW = 100

# exp_004 A2C との比較用メタデータ
COMPARE_BASELINE_EXP = "exp_004_2joint_a2c_shaping"


def training_config_dict() -> dict:
  """wandb.init(config=...) 用のハイパーパラメータ辞書。"""
  return {
    "exp_name": EXP_NAME,
    "algorithm": "ppo",
    "compare_baseline_exp": COMPARE_BASELINE_EXP,
    "xml_path": XML_PATH,
    "physics_timestep_s": PHYSICS_TIMESTEP_S,
    "control_hz": CONTROL_HZ,
    "frame_skip": FRAME_SKIP,
    "control_timestep_s": CONTROL_TIMESTEP_S,
    "forward_reward_scale": FORWARD_REWARD_SCALE,
    "forward_min_upright": FORWARD_MIN_UPRIGHT,
    "forward_require_foot_contact": FORWARD_REQUIRE_FOOT_CONTACT,
    "upright_bonus_scale": UPRIGHT_BONUS_SCALE,
    "upright_bonus_thresh": UPRIGHT_BONUS_THRESH,
    "lean_backward_penalty_scale": LEAN_BACKWARD_PENALTY_SCALE,
    "lean_backward_thresh": LEAN_BACKWARD_THRESH,
    "imu_height_penalty_scale": IMU_HEIGHT_PENALTY_SCALE,
    "target_imu_z": TARGET_IMU_Z,
    "knee_human_flex_min_rad": KNEE_HUMAN_FLEX_MIN_RAD,
    "knee_human_flex_max_rad": KNEE_HUMAN_FLEX_MAX_RAD,
    "knee_human_flex_bonus_scale": KNEE_HUMAN_FLEX_BONUS_SCALE,
    "knee_flex_min_upright": KNEE_FLEX_MIN_UPRIGHT,
    "pose_termination_penalty": POSE_TERMINATION_PENALTY,
    "min_imu_z": MIN_IMU_Z,
    "min_imu_upright": MIN_IMU_UPRIGHT,
    "max_backward_lean": MAX_BACKWARD_LEAN,
    "effort_penalty_scale": EFFORT_PENALTY_SCALE,
    "apply_effort_penalty": APPLY_EFFORT_PENALTY,
    "contact_floor_penalty_base": CONTACT_FLOOR_PENALTY_BASE,
    "contact_floor_penalty_per_n": CONTACT_FLOOR_PENALTY_PER_N,
    "contact_floor_min_force_n": CONTACT_FLOOR_MIN_FORCE_N,
    "contact_floor_force_cap_n": CONTACT_FLOOR_FORCE_CAP_N,
    "contact_floor_penalty_min": CONTACT_FLOOR_PENALTY_MIN,
    "contact_link_penalty_scale": CONTACT_LINK_PENALTY_SCALE,
    "obs_dim": OBS_DIM,
    "action_dim": ACTION_DIM,
    "gamma": GAMMA,
    "gae_lambda": GAE_LAMBDA,
    "lr": LR,
    "rollout_steps": ROLLOUT_STEPS,
    "value_coef": VALUE_COEF,
    "entropy_coef": ENTROPY_COEF,
    "max_grad_norm": MAX_GRAD_NORM,
    "std_min": STD_MIN,
    "clip_eps": CLIP_EPS,
    "ppo_epochs": PPO_EPOCHS,
    "target_kl": TARGET_KL,
    "reward_clip": REWARD_CLIP,
    "adv_clip": ADV_CLIP,
    "adv_std_min": ADV_STD_MIN,
    "log_prob_clip": LOG_PROB_CLIP,
    "minibatch_size": MINIBATCH_SIZE,
    "num_updates": NUM_UPDATES,
    "max_steps_per_episode": MAX_STEPS_PER_EPISODE,
    "log_every": LOG_EVERY,
    "enable_viewer": ENABLE_VIEWER,
    "warmup_enabled": WARMUP_ENABLED,
    "warmup_duration_s": WARMUP_DURATION_S,
    "save_checkpoints": SAVE_CHECKPOINTS,
    "checkpoint_dir": CHECKPOINT_DIR,
    "checkpoint_every": CHECKPOINT_EVERY,
  }
