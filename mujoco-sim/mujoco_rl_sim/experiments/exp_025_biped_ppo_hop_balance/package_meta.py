"""実験フォルダ名から自動導出されるメタデータ。

実験ディレクトリをコピーしてリネームしたとき、このファイルは編集不要。
チェックポイントは実験フォルダ直下 ``runs/<EXP_NAME>/`` に保存する（CWD 非依存）。
"""

from pathlib import Path

EXP_DIR = Path(__file__).resolve().parent
EXP_NAME = EXP_DIR.name
CHECKPOINT_ROOT = EXP_DIR / "runs" / EXP_NAME
CHECKPOINT_REL_FROM_EXP = f"runs/{EXP_NAME}"
# 後方互換（README 内の旧表記）
CHECKPOINT_REL_FROM_MUJOCO_SIM = CHECKPOINT_REL_FROM_EXP
PACKAGE = EXP_NAME
CHECKPOINT_FORMAT = f"{EXP_NAME}_ppo_v1"
