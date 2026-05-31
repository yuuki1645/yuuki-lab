"""exp_002: 2 関節脚 A2C のハイパーパラメータ。

報酬・終了・観測の実装は reward.py / termination.py / observation.py。
学習ループは train.py、方策は agent.py（連続 2 次元 → 膝・足首サーボ）。

制御: 物理 500 Hz（MuJoCo 既定 timestep=0.002）、ポリシー 50 Hz（FRAME_SKIP=10）。
"""

from pathlib import Path

# --- MuJoCo / 制御レート -------------------------------------------------------
_EXP_DIR = Path(__file__).resolve().parent
XML_RELATIVE = "model/main.xml"
XML_PATH = str(_EXP_DIR / XML_RELATIVE)

# 物理は XML 既定のまま（opt.timestep=0.002 s → 500 Hz）
PHYSICS_TIMESTEP_S = 0.002
CONTROL_HZ = 50
FRAME_SKIP = int(round(1.0 / (PHYSICS_TIMESTEP_S * CONTROL_HZ)))  # 10
CONTROL_TIMESTEP_S = PHYSICS_TIMESTEP_S * FRAME_SKIP  # 0.02 s

# --- 報酬（reward.py）---------------------------------------------------------
# 前進方向: ワールド +X。前進報酬は条件を満たすときだけ加点。
#   imu_site … dx（観測・従来どおり）
#   foot_site … foot_dx（報酬のみ。同 SCALE・同条件）

# 1 制御ステップ報酬 = max(0, dx_clipped) * SCALE（imu + foot の合計）
FORWARD_REWARD_SCALE = 80.0
# 前進報酬を出す最低直立度（imu_zaxis_z）。低いと「倒れながらの前進」を抑止
FORWARD_MIN_UPRIGHT = 0.72
# True なら足裏−床接触時のみ前進報酬（接地していない滑り・跳ねを無報酬に）
FORWARD_REQUIRE_FOOT_CONTACT = False

# 筋負荷ペナルティ = EFFORT_PENALTY_SCALE * Σ_physics Σ_act |τ·q̇|·dt / τ_max
# τ_max は main.xml の forcerange から（膝 168、足首 98 N·m）
EFFORT_PENALTY_SCALE = 5.0
# False のとき報酬・学習に effort_penalty を反映しない（effort.py の計測は継続）
APPLY_EFFORT_PENALTY = False

# --- 早期終了（termination.py）-----------------------------------------------
# geom−floor 接触: 線形ペナルティ [N ベース]。env.py が終了ステップに一度だけ加算
# penalty = scale * (base + per_n * clamp(force_n - min_force_n, 0, cap_n - min_force_n))
# その後 max(penalty, scale * penalty_min) で下限（より負側）を cap
CONTACT_FLOOR_PENALTY_BASE = -20.0
CONTACT_FLOOR_PENALTY_PER_N = -0.016  # 5000 N 超過分で約 -80 → 合計約 -100
CONTACT_FLOOR_MIN_FORCE_N = 0.0  # この値までは base のみ
CONTACT_FLOOR_FORCE_CAP_N = 10_000.0  # ペナルティ計算に使う力の上限
CONTACT_FLOOR_PENALTY_MIN = -200.0  # これより大きな減点にはしない（例: -200）
# thigh_link / shank_link は basket と同式で CONTACT_LINK_PENALTY_SCALE 倍
CONTACT_LINK_PENALTY_SCALE = 0.5

# wandb 互換の別名（basket 用パラメータ名）
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
  """basket−floor 接触の終了ペナルティ（フルスケール）。"""
  return contact_floor_termination_penalty(normal_force_n, penalty_scale=1.0)


def contact_link_termination_penalty(normal_force_n: float) -> float:
  """thigh_link / shank_link−floor 接触の終了ペナルティ（basket の半分）。"""
  return contact_floor_termination_penalty(
    normal_force_n, penalty_scale=CONTACT_LINK_PENALTY_SCALE
  )

# --- 観測正規化（observation.py）---------------------------------------------
# clip_scale / height_to_norm のスケール。超えた値は ±1 にクリップ（おおよそ [-1, 1]）
# 500 Hz 時 0.05 m/step × FRAME_SKIP（制御ステップは 10 倍長い）
MAX_DX_PER_STEP = 0.05 * FRAME_SKIP  # 0.5 [m] @ 50 Hz
MAX_GYRO_RAD_S = 10.0  # imu_gyro 各軸 [rad/s]
MAX_JOINT_VEL_RAD_S = 10.0  # 膝・足首 qvel [rad/s]
MAX_COM_X_OFFSET = 0.6  # COM X − 趾 X [m]（前後の体重偏り）
MAX_IMU_Z = 1.2  # imu_z / foot_z / com_z の正規化上限 [m]
MIN_IMU_Z_NORM = 0.0  # 上記高さ正規化の下限 [m]

# ポリシー入出力次元（ObsExp002 のフィールド数、膝+足首の連続行動）
OBS_DIM = 19
ACTION_DIM = 2

# --- A2C（agent.py）----------------------------------------------------------
# 実時間の割引を exp_001（500 Hz, γ=0.99）に合わせる: 0.99^FRAME_SKIP
GAMMA = 0.99**FRAME_SKIP  # ≈ 0.904
LR = 3e-4  # Actor / Critic 共通 Adam 学習率
ROLLOUT_STEPS = 512  # 1 回の update 前に集める方策ステップ数（on-policy）
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

# --- 学習ウォームアップ（train.py / warmup.py）----------------------------------
# 各エピソード開始からシミュレーション時間 WARMUP_DURATION_S のあいだ、方策の代わりに WARMUP_ACTION_FN。
# 判定は 50 Hz 制御ステップ（CONTROL_TIMESTEP_S）基準。1.0 s ≒ 50 ステップ。
# 方針 B: warmup 中は env.step のみ（agent.store しない）。update ごとに ROLLOUT_STEPS 分の方策データを集める。
from warmup import default_warmup_action

WARMUP_ENABLED = True
WARMUP_DURATION_S = 1.2  # シミュレーション内の秒（壁時計ではない）
WARMUP_ACTION_FN = default_warmup_action  # (WarmupContext) -> (knee, ankle) in [-1, 1]

# --- 学習ループ（train.py）---------------------------------------------------
# NUM_UPDATES = 100_000  # 方策更新回数（総環境ステップ ≳ NUM_UPDATES * ROLLOUT_STEPS、warmup 分が上乗せ）
NUM_UPDATES = 10_100  # 方策更新回数（総環境ステップ ≳ NUM_UPDATES * ROLLOUT_STEPS、warmup 分が上乗せ）
# exp_001 の 3000 step @ 500 Hz と同じ実時間（約 6 s）
MAX_STEPS_PER_EPISODE = 3000 // FRAME_SKIP  # 300 @ 50 Hz
LOG_EVERY = 20  # コンソール / wandb に train/* を出す更新間隔
ENABLE_VIEWER = True
# ENABLE_VIEWER = False  # MuJoCo パッシブビューア（学習を遅くする）

# --- チェックポイント（checkpoint.py / train.py）-----------------------------
SAVE_CHECKPOINTS = True
CHECKPOINT_DIR = str(_EXP_DIR / "checkpoints")
CHECKPOINT_EVERY = 1000  # この update 間隔で update_XXXXXX.pt を保存
CHECKPOINT_SAVE_LATEST = True  # 保存のたびに latest.pt を上書き
CHECKPOINT_SAVE_FINAL = True  # 学習終了時に final.pt を保存

# --- wandb（wandb_logging.py）-----------------------------------------------
# pip install wandb / WANDB_MODE=disabled でオフ
USE_WANDB = True
WANDB_PROJECT = "exp_002_2joint_a2c"
WANDB_RUN_NAME = ""  # 空なら wandb が自動命名
WANDB_ENTITY = ""  # 空ならログインアカウントのデフォルト
WANDB_TAGS = ("exp_002", "a2c", "2joint")
# termination/rolling_rate_* の直近エピソード数
WANDB_TERMINATION_ROLLING_WINDOW = 100


def training_config_dict() -> dict:
  """wandb.init(config=...) 用のハイパーパラメータ辞書。

  キーはスネークケース。実験再現時はこの dict と config 定数を照合する。
  """
  return {
    "xml_path": XML_PATH,
    "physics_timestep_s": PHYSICS_TIMESTEP_S,
    "control_hz": CONTROL_HZ,
    "frame_skip": FRAME_SKIP,
    "control_timestep_s": CONTROL_TIMESTEP_S,
    "forward_reward_scale": FORWARD_REWARD_SCALE,
    "forward_min_upright": FORWARD_MIN_UPRIGHT,
    "forward_require_foot_contact": FORWARD_REQUIRE_FOOT_CONTACT,
    "effort_penalty_scale": EFFORT_PENALTY_SCALE,
    "apply_effort_penalty": APPLY_EFFORT_PENALTY,
    "contact_floor_penalty_base": CONTACT_FLOOR_PENALTY_BASE,
    "contact_floor_penalty_per_n": CONTACT_FLOOR_PENALTY_PER_N,
    "contact_floor_min_force_n": CONTACT_FLOOR_MIN_FORCE_N,
    "contact_floor_force_cap_n": CONTACT_FLOOR_FORCE_CAP_N,
    "contact_floor_penalty_min": CONTACT_FLOOR_PENALTY_MIN,
    "contact_link_penalty_scale": CONTACT_LINK_PENALTY_SCALE,
    "contact_basket_penalty_base": CONTACT_BASKET_PENALTY_BASE,
    "contact_basket_penalty_per_n": CONTACT_BASKET_PENALTY_PER_N,
    "contact_basket_min_force_n": CONTACT_BASKET_MIN_FORCE_N,
    "contact_basket_force_cap_n": CONTACT_BASKET_FORCE_CAP_N,
    "contact_basket_penalty_min": CONTACT_BASKET_PENALTY_MIN,
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
    "warmup_enabled": WARMUP_ENABLED,
    "warmup_duration_s": WARMUP_DURATION_S,
    "save_checkpoints": SAVE_CHECKPOINTS,
    "checkpoint_dir": CHECKPOINT_DIR,
    "checkpoint_every": CHECKPOINT_EVERY,
  }
