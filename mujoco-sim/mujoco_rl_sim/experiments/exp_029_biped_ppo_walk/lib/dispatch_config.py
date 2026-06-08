"""dispatch 互換 re-export（``lib.dispatch_cfg_merge`` が正本）。"""

from __future__ import annotations

from lib.dispatch_cfg_merge import (  # noqa: F401
  DISPATCH_KEY_TO_CFG_PATH,
  merge_dispatch_overrides,
)

# sweep 文書との後方互換名
SWEEPABLE_CONFIG_KEYS = DISPATCH_KEY_TO_CFG_PATH
OVERRIDABLE_CONFIG_KEYS = DISPATCH_KEY_TO_CFG_PATH

apply_dispatch_config_overrides = merge_dispatch_overrides
apply_dispatch_env_overrides = merge_dispatch_overrides
