"""実験フォルダ名から自動導出されるメタデータ。

実験ディレクトリをコピーしてリネームしたとき、EXP_NAME はフォルダ名から決まる。
チェックポイントは ``mujoco_rl_sim/runs/<EXP_NAME>/`` に保存（CWD 非依存）。
"""

from pathlib import Path

EXP_DIR = Path(__file__).resolve().parent
EXP_NAME = EXP_DIR.name
MUJOCO_RL_SIM_ROOT = EXP_DIR.parent.parent
CHECKPOINT_ROOT = MUJOCO_RL_SIM_ROOT / "runs" / EXP_NAME
CHECKPOINT_REL_FROM_MUJOCO_SIM = f"mujoco_rl_sim/runs/{EXP_NAME}"
CHECKPOINT_REL_FROM_EXP = f"../../runs/{EXP_NAME}"
PACKAGE = EXP_NAME
CHECKPOINT_FORMAT = "exp_001_a2c_v1"
