"""exp_011: exp_010 + 直立・前傾ゲート強化・進捗報酬増（exp_010 final から転移）。

exp_010 final: ~3.1 m（最良）。長時間 run は ~1.5 m で打ち切り。
仮説: 前傾ダイブでの step dx 偏重 → 直立維持と進捗の両立を強化。

【重要】ロボット形態
  - 片脚（モノポッド）1 本 + freejoint。両脚歩行（バイペッド）ではない。
  - 「2joint」= 膝・足首の 2 自由度。脚が 2 本ある意味ではない。
  - タスク = 立脚 → 押し出し → 飛翔（IMU 前進）→ 足底着地 のホッピング。

報酬・終了の詳細は README.md / AGENTS.md を参照。
"""

from pathlib import Path

from package_meta import CHECKPOINT_ROOT, EXP_DIR, EXP_NAME

# ロボット形態（wandb・ドキュメント用の明示フラグ）
ROBOT_MORPHOLOGY = "monoped_single_leg_hopper"  # NOT biped
ROBOT_LEG_COUNT = 1
ROBOT_ACTUATED_DOF = 2  # knee + ankle

# --- MuJoCo / 制御レート -------------------------------------------------------
_EXP_DIR = EXP_DIR
XML_RELATIVE = "model/main.xml"
XML_PATH = str(_EXP_DIR / XML_RELATIVE)

PHYSICS_TIMESTEP_S = 0.002
CONTROL_HZ = 50
FRAME_SKIP = int(round(1.0 / (PHYSICS_TIMESTEP_S * CONTROL_HZ)))  # 10
CONTROL_TIMESTEP_S = PHYSICS_TIMESTEP_S * FRAME_SKIP  # 0.02 s

# --- 前進報酬（reward.py）-----------------------------------------------------
FORWARD_REWARD_SCALE = 70.0
FORWARD_MIN_UPRIGHT = 0.68
# 飛翔中、前傾がこれを超えると IMU 前進報酬ゼロ（減衰だけでは不足だった）
FORWARD_IMU_MAX_LEAN_FOR_REWARD = 0.12
FORWARD_REQUIRE_FOOT_CONTACT = False  # 飛翔中の IMU dx は主報酬のまま
FORWARD_FOOT_ONLY_WHEN_CONTACT = True  # foot_dx は足底接地時のみ

# --- shaping: 飛翔時の直立ボーナス（常時直立ボーナスは廃止）----------------------
UPRIGHT_BONUS_SCALE = 1.0
UPRIGHT_BONUS_THRESH = 0.60
UPRIGHT_BONUS_REQUIRE_FLIGHT = True
UPRIGHT_BONUS_MIN_DX = 0.0

# --- shaping: 後傾・前傾・低姿勢 -----------------------------------------------
LEAN_BACKWARD_PENALTY_SCALE = 3.0
LEAN_BACKWARD_THRESH = 0.12

LEAN_FORWARD_PENALTY_SCALE = 8.0
LEAN_FORWARD_THRESH = 0.14
LEAN_FORWARD_MIN_FLIGHT_STEPS = 2  # 連続非接地がこれ以上で前傾ペナルティ

# 飛翔中の前進 IMU 報酬を前傾で減衰（ダイブハック抑制、dx は殺さない）
FORWARD_IMU_LEAN_GATE = True
FORWARD_IMU_LEAN_GATE_THRESH = 0.10  # imu_zaxis_x がこれを超えると減衰開始
FORWARD_IMU_LEAN_GATE_SCALE = 4.0  # excess * scale を 1 から引く
FORWARD_IMU_LEAN_GATE_MIN_MULT = 0.15

# 長い非接地（着地しない飛翔）のステップペナルティ
FLIGHT_DURATION_PENALTY_SCALE = 0.08
FLIGHT_DURATION_PENALTY_AFTER_STEPS = 18  # 50 Hz で約 360 ms

# --- shaping: エピソード内の前進マイルストーン（exp_010）-----------------------
PROGRESS_REWARD_SCALE = 30.0
PROGRESS_MIN_UPRIGHT = 0.68

# 飛翔中の低 upright ペナルティ（exp_011）
FLIGHT_LOW_UPRIGHT_PENALTY_SCALE = 3.0
FLIGHT_LOW_UPRIGHT_THRESH = 0.72

# --- shaping: 飛翔中の膝過屈曲（ダイブ・縮み姿勢抑制）--------------------------
KNEE_HYPERFLEX_MAX_RAD = 0.95  # 約 54°、分析で 80°+ が墜落と相関
KNEE_HYPERFLEX_PENALTY_SCALE = 2.5
KNEE_HYPERFLEX_FLIGHT_ONLY = True

IMU_HEIGHT_PENALTY_SCALE = 2.0
TARGET_IMU_Z = 0.55
TARGET_IMU_Z_STANCE = 0.48  # 立脚中はこの高さまで許容（押し込み）
HEIGHT_PENALTY_SKIP_WHEN_STANCE = True
HEIGHT_PENALTY_FLIGHT_CRASH_Z = 0.45  # 非接地でこれ未満は強くペナルティ

# --- shaping: 膝屈曲ボーナス — 廃止（歩行向け）---------------------------------
KNEE_HUMAN_FLEX_BONUS_SCALE = 0.0

# --- shaping: 立脚押し出し・着地 -----------------------------------------------
PUSH_OFF_BONUS_SCALE = 0.25
PUSH_OFF_MIN_FOOT_DX = 0.002
PUSH_OFF_MIN_IMU_DZ = 0.004
PUSH_OFF_MIN_KNEE_EXT_VEL = 0.15  # 膝 qvel<0 = 伸展（+Y ヒンジ・屈曲が +）

LANDING_BONUS_SCALE = 0.75
LANDING_MIN_UPRIGHT = 0.72
LANDING_MAX_TOE_Z = 0.06
LANDING_MAX_HEEL_Z = 0.06
LANDING_MAX_FORWARD_LEAN = 0.18

# --- 筋負荷 --------------------------------------------------------------------
EFFORT_PENALTY_SCALE = 5.0
APPLY_EFFORT_PENALTY = False

# --- 姿勢ベース早期終了 --------------------------------------------------------
MIN_IMU_Z = 0.42
MIN_IMU_Z_STANCE = 0.36  # 立脚中のみ緩和
MIN_IMU_UPRIGHT = 0.55
MAX_BACKWARD_LEAN = 0.40
POSE_TERMINATION_PENALTY = -30.0

# --- 接触: basket/thigh は即終了、shank はステップペナルティのみ ---------------
CONTACT_SHANK_TERMINATES = False
CONTACT_SHANK_STEP_PENALTY_SCALE = 1.0  # contact_link_termination_penalty に掛ける

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


def contact_shank_step_penalty(normal_force_n: float) -> float:
  """下腿−床接触の制御ステップペナルティ（エピソードは継続）。"""
  return CONTACT_SHANK_STEP_PENALTY_SCALE * contact_link_termination_penalty(
    normal_force_n
  )

# --- 観測正規化（exp_006 と同一）----------------------------------------------
MAX_DX_PER_STEP = 0.05 * FRAME_SKIP
MAX_GYRO_RAD_S = 10.0
MAX_JOINT_VEL_RAD_S = 10.0
MAX_COM_X_OFFSET = 0.6
MAX_IMU_Z = 1.2
MIN_IMU_Z_NORM = 0.0
MAX_REL_HEEL_OFFSET = 1.0

OBS_DIM = 25
ACTION_DIM = 2

# --- PPO（exp_006 と同一）------------------------------------------------------
GAMMA = 0.99**FRAME_SKIP
GAE_LAMBDA = 0.95
LR = 3e-4
ROLLOUT_STEPS = 512
VALUE_COEF = 0.5
ENTROPY_COEF = 0.04
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

from warmup import default_warmup_action

WARMUP_ENABLED = True
WARMUP_DURATION_S = 1.2
WARMUP_ACTION_FN = default_warmup_action

NUM_UPDATES = 4_000
MAX_STEPS_PER_EPISODE = 15_000 // FRAME_SKIP  # 30 s @ 50 Hz（10 m 評価用）
LOG_EVERY = 20
ENABLE_VIEWER = False  # 学習速度優先（可視化は analyze_rollout / visualize）

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
  "2joint",
  "monoped",
  "hopper",
  "single_leg",
  "NOT_biped",
  "hop_shaping",
  "lean_gate",
  "long_episode",
  "progress_reward",
  "knee_hyperflex",
  "upright_vel",
)
WANDB_TERMINATION_ROLLING_WINDOW = 100

COMPARE_BASELINE_EXP = "exp_010_2joint_ppo_hop_progress"


def training_config_dict() -> dict:
  """wandb.init(config=...) 用のハイパーパラメータ辞書。"""
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
    "forward_min_upright": FORWARD_MIN_UPRIGHT,
    "forward_require_foot_contact": FORWARD_REQUIRE_FOOT_CONTACT,
    "forward_foot_only_when_contact": FORWARD_FOOT_ONLY_WHEN_CONTACT,
    "upright_bonus_scale": UPRIGHT_BONUS_SCALE,
    "upright_bonus_thresh": UPRIGHT_BONUS_THRESH,
    "upright_bonus_require_flight": UPRIGHT_BONUS_REQUIRE_FLIGHT,
    "lean_forward_penalty_scale": LEAN_FORWARD_PENALTY_SCALE,
    "lean_forward_thresh": LEAN_FORWARD_THRESH,
    "lean_forward_min_flight_steps": LEAN_FORWARD_MIN_FLIGHT_STEPS,
    "forward_imu_lean_gate": FORWARD_IMU_LEAN_GATE,
    "forward_imu_lean_gate_thresh": FORWARD_IMU_LEAN_GATE_THRESH,
    "flight_duration_penalty_scale": FLIGHT_DURATION_PENALTY_SCALE,
    "flight_duration_penalty_after_steps": FLIGHT_DURATION_PENALTY_AFTER_STEPS,
    "progress_reward_scale": PROGRESS_REWARD_SCALE,
    "knee_hyperflex_max_rad": KNEE_HYPERFLEX_MAX_RAD,
    "forward_imu_max_lean_for_reward": FORWARD_IMU_MAX_LEAN_FOR_REWARD,
    "flight_low_upright_penalty_scale": FLIGHT_LOW_UPRIGHT_PENALTY_SCALE,
    "landing_min_upright": LANDING_MIN_UPRIGHT,
    "lean_backward_penalty_scale": LEAN_BACKWARD_PENALTY_SCALE,
    "lean_backward_thresh": LEAN_BACKWARD_THRESH,
    "imu_height_penalty_scale": IMU_HEIGHT_PENALTY_SCALE,
    "target_imu_z": TARGET_IMU_Z,
    "target_imu_z_stance": TARGET_IMU_Z_STANCE,
    "height_penalty_skip_when_stance": HEIGHT_PENALTY_SKIP_WHEN_STANCE,
    "knee_human_flex_bonus_scale": KNEE_HUMAN_FLEX_BONUS_SCALE,
    "push_off_bonus_scale": PUSH_OFF_BONUS_SCALE,
    "landing_bonus_scale": LANDING_BONUS_SCALE,
    "contact_shank_terminates": CONTACT_SHANK_TERMINATES,
    "contact_shank_step_penalty_scale": CONTACT_SHANK_STEP_PENALTY_SCALE,
    "pose_termination_penalty": POSE_TERMINATION_PENALTY,
    "min_imu_z": MIN_IMU_Z,
    "min_imu_z_stance": MIN_IMU_Z_STANCE,
    "min_imu_upright": MIN_IMU_UPRIGHT,
    "max_backward_lean": MAX_BACKWARD_LEAN,
    "effort_penalty_scale": EFFORT_PENALTY_SCALE,
    "apply_effort_penalty": APPLY_EFFORT_PENALTY,
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
    "num_updates": NUM_UPDATES,
    "max_steps_per_episode": MAX_STEPS_PER_EPISODE,
    "warmup_enabled": WARMUP_ENABLED,
    "warmup_duration_s": WARMUP_DURATION_S,
    "save_checkpoints": SAVE_CHECKPOINTS,
    "checkpoint_dir": CHECKPOINT_DIR,
    "checkpoint_every": CHECKPOINT_EVERY,
  }
