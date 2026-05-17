"""exp_001: 007_leg_2joint ・ 2 関節 A2C のハイパーパラメータ。"""

# MuJoCo
XML_PATH = "mujoco_sim_assets/xmls/007_leg_2joint/main.xml"

# 前進は imu_site のワールド +x
FORWARD_REWARD_SCALE = 500.0
UPRIGHT_BONUS_SCALE = 0.05
FALL_PENALTY = -10.0
MIN_IMU_Z = 0.35
MIN_IMU_UPRIGHT = 0.35

# 膝ヒンジ +Y: qpos/ctrl > 0 が後方屈曲（良い）
KNEE_WRONG_THRESH_RAD = 0.05
KNEE_WRONG_PENALTY_SCALE = 5.0
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
ENTROPY_COEF = 0.01
MAX_GRAD_NORM = 0.5
MINIBATCH_SIZE = 256

# train.py
NUM_UPDATES = 500_000
MAX_STEPS_PER_EPISODE = 5000
LOG_EVERY = 50
ENABLE_VIEWER = True

# wandb（pip install wandb / WANDB_MODE=disabled でオフ）
USE_WANDB = True
WANDB_PROJECT = "exp_001_2joint_a2c"
WANDB_RUN_NAME = ""
WANDB_ENTITY = ""
WANDB_TAGS = ("exp_001", "a2c", "2joint")


def training_config_dict() -> dict:
  """wandb.init(config=...) 用のハイパーパラメータ辞書。"""
  return {
    "xml_path": XML_PATH,
    "forward_reward_scale": FORWARD_REWARD_SCALE,
    "upright_bonus_scale": UPRIGHT_BONUS_SCALE,
    "fall_penalty": FALL_PENALTY,
    "min_imu_z": MIN_IMU_Z,
    "min_imu_upright": MIN_IMU_UPRIGHT,
    "knee_wrong_thresh_rad": KNEE_WRONG_THRESH_RAD,
    "knee_wrong_penalty_scale": KNEE_WRONG_PENALTY_SCALE,
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
    "minibatch_size": MINIBATCH_SIZE,
    "num_updates": NUM_UPDATES,
    "max_steps_per_episode": MAX_STEPS_PER_EPISODE,
    "log_every": LOG_EVERY,
    "enable_viewer": ENABLE_VIEWER,
  }
