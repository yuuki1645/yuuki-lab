"""実験フォルダ名から自動導出されるメタデータ。

実験ディレクトリをコピーしてリネームしたとき、このファイルは編集不要。
wandb プロジェクト名・チェックポイント保存先・モジュールパスは EXP_NAME から決まる。
"""

from pathlib import Path

EXP_DIR = Path(__file__).resolve().parent
EXP_NAME = EXP_DIR.name
MUJOCO_RL_SIM_ROOT = EXP_DIR.parent.parent
CHECKPOINT_ROOT = MUJOCO_RL_SIM_ROOT / "runs" / EXP_NAME
# mujoco-sim をカレントにしたときのパス表記（README / CLI 例用）
CHECKPOINT_REL_FROM_MUJOCO_SIM = f"mujoco_rl_sim/runs/{EXP_NAME}"
PACKAGE = f"mujoco_rl_sim.experiments.{EXP_NAME}"
CHECKPOINT_FORMAT = f"{EXP_NAME}_a2c_v1"
