"""exp_001: 007_leg_2joint ・ 2 関節 A2C のハイパーパラメータ。"""



# MuJoCo

XML_PATH = "mujoco_sim_assets/xmls/007_leg_2joint/main.xml"



# 前進は imu_site のワールド +x（直立・接地時のみ与える）

FORWARD_REWARD_SCALE = 80.0

FORWARD_MIN_UPRIGHT = 0.72

FORWARD_REQUIRE_FOOT_CONTACT = False

UPRIGHT_BONUS_SCALE = 2.0

UPRIGHT_BONUS_THRESH = 0.65

LEAN_FORWARD_PENALTY_SCALE = 3.0

LEAN_FORWARD_THRESH = 0.12

IMU_HEIGHT_PENALTY_SCALE = 2.0

TARGET_IMU_Z = 0.55

FALL_PENALTY = -30.0

MIN_IMU_Z = 0.42

MIN_IMU_UPRIGHT = 0.55

MAX_FORWARD_LEAN = 0.40



# 膝ヒンジ +Y: qpos/ctrl > 0 が後方屈曲（良い）

KNEE_HUMAN_FLEX_MIN_RAD = 0.02

KNEE_HUMAN_FLEX_MAX_RAD = 1.2

KNEE_HUMAN_FLEX_BONUS_SCALE = 0.15



# 観測正規化（おおよそ [-1, 1]）

MAX_REL_IMU_X = 2.0

MAX_DX_PER_STEP = 0.05

MAX_GYRO_RAD_S = 10.0

MAX_JOINT_VEL_RAD_S = 10.0

MAX_COM_X_OFFSET = 0.6

MAX_IMU_Z = 1.2

MIN_IMU_Z_NORM = 0.0



OBS_DIM = 20

ACTION_DIM = 2



# A2C

GAMMA = 0.99

LR = 3e-4

ROLLOUT_STEPS = 512

VALUE_COEF = 0.5

ENTROPY_COEF = 0.04

MAX_GRAD_NORM = 0.5

MINIBATCH_SIZE = 256

STD_MIN = 0.08

# 学習安定化（報酬スパイク・advantage 爆発対策）

REWARD_CLIP = 20.0

ADV_CLIP = 10.0

ADV_STD_MIN = 0.1

ACTION_LOG_PROB_EPS = 1e-6

LOG_PROB_CLIP = 20.0



# train.py

NUM_UPDATES = 10_000

MAX_STEPS_PER_EPISODE = 3000

LOG_EVERY = 20

# ENABLE_VIEWER = False
ENABLE_VIEWER = True



# wandb（pip install wandb / WANDB_MODE=disabled でオフ）

USE_WANDB = True

WANDB_PROJECT = "exp_001_2joint_a2c"

WANDB_RUN_NAME = ""

WANDB_ENTITY = ""

WANDB_TAGS = ("exp_001", "a2c", "2joint")

# 終了理由の直近比率（termination/rolling_rate_*）のウィンドウ幅（エピソード数）
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

    "lean_forward_penalty_scale": LEAN_FORWARD_PENALTY_SCALE,

    "lean_forward_thresh": LEAN_FORWARD_THRESH,

    "imu_height_penalty_scale": IMU_HEIGHT_PENALTY_SCALE,

    "target_imu_z": TARGET_IMU_Z,

    "fall_penalty": FALL_PENALTY,

    "min_imu_z": MIN_IMU_Z,

    "min_imu_upright": MIN_IMU_UPRIGHT,

    "max_forward_lean": MAX_FORWARD_LEAN,

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

