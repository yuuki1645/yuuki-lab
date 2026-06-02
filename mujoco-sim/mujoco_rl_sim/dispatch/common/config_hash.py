"""ハイパラ組合せの config_hash（W&B group 用）。"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def _canonical_json(obj: Any) -> str:
  return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_config_hash(overrides: dict[str, Any]) -> str:
  """探索対象 overrides の正規化 JSON から短いハッシュを返す。"""
  payload = _canonical_json(overrides)
  digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
  return f"cfg_{digest[:12]}"
