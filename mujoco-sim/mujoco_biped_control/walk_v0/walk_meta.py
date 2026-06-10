"""walk_v0 メタデータ。"""

from pathlib import Path

EXP_DIR = Path(__file__).resolve().parent
EXP_NAME = EXP_DIR.name
MUJOCO_BIPED_CONTROL_ROOT = EXP_DIR.parent
MUJOCO_SIM_ROOT = MUJOCO_BIPED_CONTROL_ROOT.parent
RUNS_ROOT = MUJOCO_SIM_ROOT / "runs" / "mujoco_biped_control" / EXP_NAME
EXP030_DIR = MUJOCO_SIM_ROOT / "mujoco_rl_sim" / "experiments" / "exp_030_biped_ppo_walk"
