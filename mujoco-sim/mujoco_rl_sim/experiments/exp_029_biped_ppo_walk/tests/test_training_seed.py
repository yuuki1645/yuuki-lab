"""学習 seed の解決・適用の単体テスト。"""

from __future__ import annotations

import numpy as np
import torch

from lib.training_seed import apply_training_seed, resolve_training_seed


def test_resolve_prefers_cli_over_dispatch(monkeypatch) -> None:
  monkeypatch.setenv("DISPATCH_SEED", "7")
  assert resolve_training_seed(cli_seed=3) == 3


def test_resolve_uses_dispatch_when_cli_missing(monkeypatch) -> None:
  monkeypatch.setenv("DISPATCH_SEED", "11")
  assert resolve_training_seed(cli_seed=None) == 11


def test_apply_training_seed_is_reproducible() -> None:
  apply_training_seed(12345)
  a = torch.randn(4)
  apply_training_seed(12345)
  b = torch.randn(4)
  assert torch.allclose(a, b)

  apply_training_seed(99)
  x = float(np.random.rand())
  apply_training_seed(99)
  y = float(np.random.rand())
  assert x == y
