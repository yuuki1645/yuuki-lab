"""exp_001: 007_leg_2joint ・ 2 関節 A2C のハイパーパラメータ。

報酬・終了・観測の実装は reward.py / termination.py / observation.py。
学習ループは train.py、方策は agent.py（連続 2 次元 → 膝・足首サーボ）。
"""

# --- MuJoCo -------------------------------------------------------------------
# mujoco_sim_asset_path から解決する相対パス（mujoco-sim 直下が基準）
XML_PATH = "mujoco_sim_assets/xmls/007_leg_2joint/main.xml"

# --- 報酬（reward.py）---------------------------------------------------------
# 前進方向: imu_site のワールド +X。前進報酬は条件を満たすときだけ dx を加点。

# 1 ステップ報酬 = max(0, dx_clipped) * SCALE。dx は IMU のワールド X 変位 [m/step]
FORWARD_REWARD_SCALE = 80.0
# 前進報酬を出す最低直立度（imu_zaxis_z）。低いと「倒れながらの前進」を抑止
FORWARD_MIN_UPRIGHT = 0.72
# True なら足裏−床接触時のみ前進報酬（接地していない滑り・跳ねを無報酬に）
FORWARD_REQUIRE_FOOT_CONTACT = False

# 直立ボーナス = max(0, upright - THRESH) * SCALE（前進ゲートより緩い姿勢報酬）
UPRIGHT_BONUS_SCALE = 2.0
UPRIGHT_BONUS_THRESH = 0.65

# 後傾ペナルティ = max(0, -imu_zaxis_x - THRESH) * SCALE
# imu_zaxis_x が負 = 体軸が −X（後ろ）へ傾いている
LEAN_BACKWARD_PENALTY_SCALE = 3.0
LEAN_BACKWARD_THRESH = 0.12

# 低姿勢ペナルティ = max(0, TARGET_IMU_Z - imu_z) * SCALE（しゃがみ・倒れ込みの予兆）
IMU_HEIGHT_PENALTY_SCALE = 2.0
TARGET_IMU_Z = 0.55  # この高さ [m] を下回るほど減点（imu_site のワールド Z）

# 早期終了ステップに env.py が一度だけ加算（termination と併用）
FALL_PENALTY = -30.0
# FALL_PENALTY = -70.0

# --- 早期終了（termination.py）-----------------------------------------------
# imu_site のワールド Z [m]。これ未満で終了（しゃがみ／転倒の床近傍）
MIN_IMU_Z = 0.42
# imu_zaxis_z（直立度）。これ未満で終了（大きく傾いた横倒し・後傾など）
MIN_IMU_UPRIGHT = 0.55
# imu_zaxis_x < -MAX で終了（後傾が強すぎる。MAX=0.40 → x < -0.40）
MAX_BACKWARD_LEAN = 0.40

# --- 膝ボーナス（reward.py）--------------------------------------------------
# +Y ヒンジ: qpos > 0 が後方屈曲。このレンジ内だけ小さな定数ボーナス
KNEE_HUMAN_FLEX_MIN_RAD = 0.02
KNEE_HUMAN_FLEX_MAX_RAD = 1.2
KNEE_HUMAN_FLEX_BONUS_SCALE = 0.15

# --- 観測正規化（observation.py）---------------------------------------------
# clip_scale / height_to_norm のスケール。超えた値は ±1 にクリップ（おおよそ [-1, 1]）
MAX_REL_IMU_X = 2.0  # エピソード開始からの IMU X 相対位置 [m]
MAX_DX_PER_STEP = 0.05  # 1 ステップの IMU X 変位 [m]（報酬の dx クリップ上限と同値）
MAX_GYRO_RAD_S = 10.0  # imu_gyro 各軸 [rad/s]
MAX_JOINT_VEL_RAD_S = 10.0  # 膝・足首 qvel [rad/s]
MAX_COM_X_OFFSET = 0.6  # COM X − 趾 X [m]（前後の体重偏り）
MAX_IMU_Z = 1.2  # imu_z / foot_z / com_z の正規化上限 [m]
MIN_IMU_Z_NORM = 0.0  # 上記高さ正規化の下限 [m]

# ポリシー入出力次元（ObsExp001 のフィールド数、膝+足首の連続行動）
OBS_DIM = 20
ACTION_DIM = 2

# --- A2C（agent.py）----------------------------------------------------------
GAMMA = 0.99  # TD ターゲットの割引率
LR = 3e-4  # Actor / Critic 共通 Adam 学習率
ROLLOUT_STEPS = 512  # 1 回の update 前に集める環境ステップ数
VALUE_COEF = 0.5  # 総損失における value_loss の係数
ENTROPY_COEF = 0.04  # 探索維持（大きいほどランダム寄り）
MAX_GRAD_NORM = 0.5  # 勾配ノルムクリップ（爆発抑制）
MINIBATCH_SIZE = 256  # ロールアウト内のミニバッチ（末尾は端数）
STD_MIN = 0.08  # 方策ガウス分布の下限標準偏差（探索の下限）

# 学習安定化（agent.update 内）
REWARD_CLIP = 20.0  # TD 用報酬のクリップ幅（スパイク抑制）
ADV_CLIP = 10.0  # 正規化後 advantage のクリップ
ADV_STD_MIN = 0.1  # advantage 標準化の分母下限（全ステップ同値時の除算回避）
ACTION_LOG_PROB_EPS = 1e-6  # tanh 行動を ±1 内側に寄せて log_prob を計算
LOG_PROB_CLIP = 20.0  # log_prob のクリップ（数値暴走抑制）

# --- 学習ループ（train.py）---------------------------------------------------
NUM_UPDATES = 100_000  # 方策更新回数（総環境ステップ ≒ NUM_UPDATES * ROLLOUT_STEPS）
MAX_STEPS_PER_EPISODE = 3000  # これで打ち切り（truncated、termination とは別）
LOG_EVERY = 20  # コンソール / wandb に train/* を出す更新間隔
ENABLE_VIEWER = True
# ENABLE_VIEWER = True  # MuJoCo パッシブビューア（学習を遅くする）

# --- wandb（wandb_logging.py）-----------------------------------------------
# pip install wandb / WANDB_MODE=disabled でオフ
USE_WANDB = False
WANDB_PROJECT = "exp_001_2joint_a2c"
WANDB_RUN_NAME = ""  # 空なら wandb が自動命名
WANDB_ENTITY = ""  # 空ならログインアカウントのデフォルト
WANDB_TAGS = ("exp_001", "a2c", "2joint")
# termination/rolling_rate_* の直近エピソード数
WANDB_TERMINATION_ROLLING_WINDOW = 100


def training_config_dict() -> dict:
  """wandb.init(config=...) 用のハイパーパラメータ辞書。"""
  return {
    "xml_path": XML_PATH,
    "forward_reward_scale": FORWARD_REWARD_SCALE,
    "forward_min_upright": FORWARD_MIN_UPRIGHT,
    "forward_require_foot_contact": FORWARD_REQUIRE_FOOT_CONTACT,
    "upright_bonus_scale": UPRIGHT_BONUS_SCALE,
    "upright_bonus_thresh": UPRIGHT_BONUS_THRESH,
    "lean_backward_penalty_scale": LEAN_BACKWARD_PENALTY_SCALE,
    "lean_backward_thresh": LEAN_BACKWARD_THRESH,
    "imu_height_penalty_scale": IMU_HEIGHT_PENALTY_SCALE,
    "target_imu_z": TARGET_IMU_Z,
    "fall_penalty": FALL_PENALTY,
    "min_imu_z": MIN_IMU_Z,
    "min_imu_upright": MIN_IMU_UPRIGHT,
    "max_backward_lean": MAX_BACKWARD_LEAN,
    "knee_human_flex_min_rad": KNEE_HUMAN_FLEX_MIN_RAD,
    "knee_human_flex_max_rad": KNEE_HUMAN_FLEX_MAX_RAD,
    "knee_human_flex_bonus_scale": KNEE_HUMAN_FLEX_BONUS_SCALE,
    "obs_dim": OBS_DIM,
    "action_dim": ACTION_DIM,
    "gamma": GAMMA,
    "lr": LR,
    "rollout_steps": ROLLOUT_STEPS,
    "value_coef": VALUE_COEF,
    "entropy_coef": ENTROPY_COEF,
    "max_grad_norm": MAX_GRAD_NORM,
    "std_min": STD_MIN,
    "reward_clip": REWARD_CLIP,
    "adv_clip": ADV_CLIP,
    "adv_std_min": ADV_STD_MIN,
    "log_prob_clip": LOG_PROB_CLIP,
    "minibatch_size": MINIBATCH_SIZE,
    "num_updates": NUM_UPDATES,
    "max_steps_per_episode": MAX_STEPS_PER_EPISODE,
    "log_every": LOG_EVERY,
    "enable_viewer": ENABLE_VIEWER,
  }
