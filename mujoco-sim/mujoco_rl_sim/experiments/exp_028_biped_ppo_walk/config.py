"""exp_028: exp_026 ベース・交互片脚歩行 PPO。

報酬項の ON/OFF は REWARD_ENABLE_* で切り替える（sim/reward.py が参照）。
既定は報酬地獄回避のミニマル構成（前進 IMU + effort のみ）。
"""

from pathlib import Path

from package_meta import CHECKPOINT_ROOT, EXP_DIR, EXP_NAME

#region ロボット・モデル
ROBOT_MORPHOLOGY = "biped_legs_only"
ROBOT_LEG_COUNT = 2
ROBOT_ACTUATED_DOF = 12

_EXP_DIR = EXP_DIR
XML_RELATIVE = "model/main.xml"
XML_PATH = str(_EXP_DIR / XML_RELATIVE)
#endregion

#region シミュレーション周期
# MuJoCo は 500 Hz（0.002 s）で物理積分。ポリシーは 50 Hz で 1 行動 = FRAME_SKIP 物理ステップ。
PHYSICS_TIMESTEP_S = 0.002
CONTROL_HZ = 50
FRAME_SKIP = int(round(1.0 / (PHYSICS_TIMESTEP_S * CONTROL_HZ)))  # 10
CONTROL_TIMESTEP_S = PHYSICS_TIMESTEP_S * FRAME_SKIP  # 0.02 s
#endregion

#region 報酬 — ENABLE 群（sim/reward.py が各項の合成前に参照）
# False にすると対応する報酬項は 0 固定（scale は温存し ablation 用に残す）。
REWARD_ENABLE_FORWARD = True          # forward_imu（IMU +X 移動）
REWARD_ENABLE_FORWARD_FOOT = False    # forward_foot（支持脚 +X 移動）
REWARD_ENABLE_PROGRESS = False        # progress_bonus（エピソード内最高 IMU X 更新）
REWARD_ENABLE_WALK_SHAPING = False    # push_off / landing / alternating_landing / swing_clearance
REWARD_ENABLE_UPRIGHT_BONUS = False   # upright_bonus
REWARD_ENABLE_POSTURE_PENALTIES = False  # 傾き・向き・高さ・膝過屈曲ペナルティ群
REWARD_ENABLE_DOUBLE_SUPPORT = False  # double_support_penalty（すり足抑制）
REWARD_ENABLE_FLIGHT_DURATION = False # flight_duration_penalty（ホップ抑制）
REWARD_ENABLE_EFFORT = True           # effort_penalty（筋力コスト）
#endregion

#region 報酬 — 前進（sim/reward.py）
# ミニマル構成: 片足制約・飛翔前傾ゲートを外し、接地かつ直立時の IMU 前進のみ主報酬とする。
FORWARD_REWARD_SCALE = 50.0
FORWARD_MIN_UPRIGHT = 0.50
FORWARD_REQUIRE_FOOT_CONTACT = True
FORWARD_REQUIRE_SINGLE_SUPPORT = False  # True だと片足支持時のみ forward（歩行 shaping 向け）
FORWARD_IMU_LEAN_GATE = False
FORWARD_IMU_LEAN_GATE_THRESH = 0.10
FORWARD_IMU_LEAN_GATE_SCALE = 4.0
FORWARD_IMU_LEAN_GATE_MIN_MULT = 0.15
#endregion

#region 報酬 — すり足抑制
DOUBLE_SUPPORT_PENALTY_SCALE = 8.0
DOUBLE_SUPPORT_MIN_FORWARD = 0.001
#endregion

#region 報酬 — 交互歩行 shaping
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
#endregion

#region 報酬 — 直立・傾き・高さ（exp_024 系を維持）
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
#endregion

#region 報酬 — effort・終了関連
EFFORT_PENALTY_SCALE = 3.0
# 後方互換。実際の ON/OFF は REWARD_ENABLE_EFFORT を参照（sim/reward.py）。
APPLY_EFFORT_PENALTY = REWARD_ENABLE_EFFORT

CONTACT_SHANK_TERMINATES = False
MAX_BACKWARD_LEAN_BODY = 0.38
#endregion

#region 観測・行動（contract/biped_walk_v1.py と一致、51 次元）
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
#endregion

#region 方策ネット（rl/agent.py）
POLICY_HIDDEN_SIZES: tuple[int, ...] = (256, 256, 128)
#endregion

#region PPO ハイパラ（rl/agent.py）
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
#endregion

#region 学習ループ（contract/session.py）
from sim.warmup import default_warmup_action

WARMUP_ENABLED = True
WARMUP_DURATION_S = 1.0
WARMUP_ACTION_FN = default_warmup_action

NUM_UPDATES = 5_000
MAX_STEPS_PER_EPISODE = 15_000 // FRAME_SKIP
LOG_EVERY = 5
#endregion

#region ビューア・実時間 pacing
ENABLE_VIEWER = True
STEP_WALL_SLEEP_SEC = CONTROL_TIMESTEP_S

# passive viewer user_scn オーバーレイ: (z [m], rgba) — IMU 転倒下限の参考用薄赤平面
VIEWER_TARGET_HEIGHT_PLANES: tuple[tuple[float, tuple[float, float, float, float]], ...] = (
  (0.3, (1.0, 0.25, 0.25, 0.28)),
)
VIEWER_HEIGHT_PLANE_HALF_XY = (3.0, 3.0)  # 薄板 X/Y 半サイズ [m]
VIEWER_HEIGHT_PLANE_THICKNESS = 0.001  # 薄板厚 [m]
#endregion

#region テレメトリ（robotics-hub）
TELEMETRY_ENABLED = True
TELEMETRY_HOST = "0.0.0.0"
TELEMETRY_PORT = 8791
#endregion

#region チェックポイント
SAVE_CHECKPOINTS = True
CHECKPOINT_DIR = str(CHECKPOINT_ROOT)
CHECKPOINT_EVERY = 500
CHECKPOINT_SAVE_LATEST = True
CHECKPOINT_SAVE_FINAL = True
#endregion

#region W&B
USE_WANDB = True
WANDB_PROJECT = EXP_NAME
WANDB_RUN_NAME = ""
WANDB_ENTITY = ""
WANDB_TAGS = (
  "ppo",
  "biped",
  "biped_walk",
  "minimal_reward",
  "12dof",
  "forward",
  "effort_penalty",
  "policy_mlp_256_256_128",
)
WANDB_TERMINATION_ROLLING_WINDOW = 100
EPISODE_ROLLING_WINDOW = 100
#endregion

#region 比較・メタ
COMPARE_BASELINE_EXP = "exp_026_biped_ppo_hop_balance"
#endregion


#region training_config_dict（W&B / ログ用スナップショット）
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
    "reward_enable_forward": REWARD_ENABLE_FORWARD,
    "reward_enable_forward_foot": REWARD_ENABLE_FORWARD_FOOT,
    "reward_enable_progress": REWARD_ENABLE_PROGRESS,
    "reward_enable_walk_shaping": REWARD_ENABLE_WALK_SHAPING,
    "reward_enable_upright_bonus": REWARD_ENABLE_UPRIGHT_BONUS,
    "reward_enable_posture_penalties": REWARD_ENABLE_POSTURE_PENALTIES,
    "reward_enable_double_support": REWARD_ENABLE_DOUBLE_SUPPORT,
    "reward_enable_flight_duration": REWARD_ENABLE_FLIGHT_DURATION,
    "reward_enable_effort": REWARD_ENABLE_EFFORT,
    "forward_reward_scale": FORWARD_REWARD_SCALE,
    "forward_require_single_support": FORWARD_REQUIRE_SINGLE_SUPPORT,
    "forward_imu_lean_gate": FORWARD_IMU_LEAN_GATE,
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
#endregion
