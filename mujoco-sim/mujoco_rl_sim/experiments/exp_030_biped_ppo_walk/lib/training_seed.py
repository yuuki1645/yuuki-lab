"""学習 RNG の seed 解決と適用（再現性・multi-seed sweep 用）。

優先順位:
  1. CLI ``--seed``
  2. 環境変数 ``DISPATCH_SEED``（dispatch Worker が sweep の seed を渡す）
  3. 未指定 … 非決定的（``launch_parallel.ps1`` 等の並列 ad-hoc 実行向け）

eval seed（``eval/spec.py``）とは独立。学習の乱数源だけを固定する。
"""

from __future__ import annotations

import os
import random

import numpy as np
import torch


def resolve_training_seed(*, cli_seed: int | None) -> int | None:
  """この run で使う学習 seed を決める（未指定なら None）。"""
  if cli_seed is not None:
    return int(cli_seed)
  raw = os.environ.get("DISPATCH_SEED", "").strip()
  if not raw:
    return None
  return int(raw)


def apply_training_seed(seed: int) -> None:
  """Python / NumPy / PyTorch の RNG を学習 seed で初期化する。

  方策ネットワークの初期化と PPO 探索の再現性に効く。
  GPU 非決定性によりビット完全一致は保証しないが、実用上同じ学習曲線を目指す。
  """
  seed = int(seed)
  random.seed(seed)
  np.random.seed(seed)
  torch.manual_seed(seed)
  if torch.cuda.is_available():
    torch.cuda.manual_seed_all(seed)
