"""実験フォルダ名から自動導出されるメタデータ。"""

from pathlib import Path

EXP_DIR = Path(__file__).resolve().parent
EXP_NAME = EXP_DIR.name
CHECKPOINT_ROOT = EXP_DIR / "runs" / EXP_NAME
CHECKPOINT_REL_FROM_EXP = f"runs/{EXP_NAME}"
CHECKPOINT_REL_FROM_MUJOCO_SIM = CHECKPOINT_REL_FROM_EXP
PACKAGE = EXP_NAME
CHECKPOINT_FORMAT = "exp_001_a2c_v1"
