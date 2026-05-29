"""`train` の CLI 引数と 1 run 分の実行設定（TrainRunConfig）。

`python -m mujoco_rl_sim.experiments.exp_019_biped_ppo_hop_balance.train` の
--resume / --no-viewer 等はここで解析する。学習ハイパラ本体は config.py。
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from . import checkpoint
from . import config
from .package_meta import CHECKPOINT_REL_FROM_MUJOCO_SIM, PACKAGE

_TRAIN_CLI_DESCRIPTION = f"""両脚バイペッド前進 PPO 学習ループ（10 DOF 全サーボ・観測 42 次元）。

タスク: +X 前進。reset は keyframe `stand`。

実行例（mujoco-sim ディレクトリから）:

  python -m {PACKAGE}.train

チェックポイントから再開（新 run ディレクトリ・新 wandb run、学習率指定）:

  python -m {PACKAGE}.train \\
    --resume run_YYYYMMDD_HHMMSS/update_005000.pt \\
    --lr 1e-4 \\
    --num-updates 1500

wandb を無効にする例:

  set WANDB_MODE=disabled
  python -m {PACKAGE}.train

Hub テレメトリを無効にする例:

  python -m {PACKAGE}.train --no-telemetry
"""


@dataclass(frozen=True)
class TrainRunConfig:
  """この `train` プロセス 1 回分の実行オプションをまとめた設定オブジェクト。

  `python -m ...train --resume ... --no-viewer` など CLI で渡した値を、
  `train.main()` や各初期化ヘルパが参照しやすい形にしたものです。
  config.py の学習ハイパラ（LR・ROLLOUT_STEPS 等）とは別で、
  **「今回の run だけ上書きするか」** を表します。

  - frozen=True … 実行中に書き換えない（設定が途中で変わらない）
  - argparse.Namespace の代わり … フィールド名・型が IDE で分かる

  主なフィールド:
    resume_path … チェックポイントから再開する場合の .pt パス（新規なら None）
    num_updates … この run で行う PPO 更新回数
    viewer / telemetry / step_wall_sleep_sec … 可視化・Hub・実時間化の on/off
  """

  resume_path: Path | None
  lr: float | None
  num_updates: int
  load_optimizer: bool
  wandb_run_name: str | None
  viewer: bool
  telemetry: bool
  telemetry_host: str
  telemetry_port: int
  step_wall_sleep_sec: float | None


def parse_train_args(argv: list[str] | None = None) -> TrainRunConfig:
  """コマンドライン引数を解析し TrainRunConfig を返す。

  config.py の既定値と CLI フラグをマージする（例: --no-viewer で ENABLE_VIEWER を無効化）。
  train.main() の先頭で 1 回だけ呼ぶ。

  Args:
    argv: 省略時は sys.argv。テストで引数を渡すときに使用。
  """
  p = argparse.ArgumentParser(
    description=_TRAIN_CLI_DESCRIPTION.split("\n\n")[0],
  )

  # --- 学習再開・最適化 ---
  p.add_argument(
    "--resume",
    type=str,
    default=None,
    help=(
      f"再開する .pt（相対パスは {CHECKPOINT_REL_FROM_MUJOCO_SIM}/ 基準、"
      "例: run_YYYYMMDD_HHMMSS/update_005000.pt）"
    ),
  )
  p.add_argument(
    "--lr",
    type=float,
    default=None,
    help=f"学習率の上書き（省略時は config.LR={config.LR}、再開のみで optimizer 復元時は ckpt 内の LR）",
  )
  p.add_argument(
    "--num-updates",
    type=int,
    default=None,
    help=f"この run で行う方策更新回数（省略時は config.NUM_UPDATES={config.NUM_UPDATES}）",
  )
  p.add_argument(
    "--load-optimizer",
    action="store_true",
    help="--resume 時に optimizer state も読み込む（--lr 指定時は無効）",
  )
  p.add_argument(
    "--wandb-run-name",
    type=str,
    default=None,
    help="wandb run 名（省略時は config または再開時の自動名）",
  )

  # --- 可視化・実時間化 ---
  p.add_argument(
    "--viewer",
    action="store_true",
    help="学習中に MuJoCo パッシブビューアを表示（省略時は config.ENABLE_VIEWER）",
  )
  p.add_argument(
    "--no-viewer",
    action="store_true",
    help="ビューアを無効化（config.ENABLE_VIEWER を上書き）",
  )
  p.add_argument(
    "--step-wall-sleep",
    type=float,
    default=None,
    help=(
      "制御ステップごとの壁時計待ち [s]（省略時は config.STEP_WALL_SLEEP_SEC）。"
      "0 にするとビューア表示のまま最速（visualize の実時間 sleep もオフ）。"
    ),
  )
  p.add_argument(
    "--viewer-fast",
    action="store_true",
    help=(
      "ビューア ON かつ壁時計待ち 0（--step-wall-sleep 0 と同義）。"
      "MuJoCo は毎ステップ sync するが sleep しない。"
    ),
  )

  # --- robotics-hub 向け Socket.IO テレメトリ ---
  p.add_argument(
    "--telemetry",
    action="store_true",
    help="Hub 向け Socket.IO テレメトリを有効化（省略時は config.TELEMETRY_ENABLED）",
  )
  p.add_argument(
    "--no-telemetry",
    action="store_true",
    help="Hub 向け Socket.IO テレメトリを無効化（config.TELEMETRY_ENABLED を上書き）",
  )
  p.add_argument(
    "--telemetry-host",
    type=str,
    default=config.TELEMETRY_HOST,
    help=f"テレメトリ bind アドレス（既定: {config.TELEMETRY_HOST}）",
  )
  p.add_argument(
    "--telemetry-port",
    type=int,
    default=config.TELEMETRY_PORT,
    help=f"テレメトリポート（既定: {config.TELEMETRY_PORT}）",
  )
  args = p.parse_args(argv)

  resume_path = None
  if args.resume is not None:
    resume_path = checkpoint.resolve_checkpoint_path(args.resume)

  num_updates = config.NUM_UPDATES if args.num_updates is None else args.num_updates
  if num_updates < 1:
    raise SystemExit("--num-updates は 1 以上にしてください")

  # --lr を指定した再開は「重みだけ載せ替え・optimizer は新規」が意図
  load_optimizer = args.load_optimizer
  if args.lr is not None:
    load_optimizer = False

  viewer = config.ENABLE_VIEWER
  if args.viewer:
    viewer = True
  if args.no_viewer:
    viewer = False

  telemetry = config.TELEMETRY_ENABLED
  if args.telemetry:
    telemetry = True
  if args.no_telemetry:
    telemetry = False

  step_wall_sleep_sec = args.step_wall_sleep
  if args.viewer_fast and step_wall_sleep_sec is None:
    step_wall_sleep_sec = 0.0

  return TrainRunConfig(
    resume_path=resume_path,
    lr=args.lr,
    num_updates=num_updates,
    load_optimizer=load_optimizer,
    wandb_run_name=args.wandb_run_name,
    viewer=viewer,
    telemetry=telemetry,
    telemetry_host=str(args.telemetry_host),
    telemetry_port=int(args.telemetry_port),
    step_wall_sleep_sec=step_wall_sleep_sec,
  )
