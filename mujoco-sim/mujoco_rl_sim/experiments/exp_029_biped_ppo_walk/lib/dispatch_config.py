"""後方互換 re-export。新規コードは ``lib.config_overrides`` を参照。"""

from __future__ import annotations

from lib.config_overrides import (  # noqa: F401
  OVERRIDABLE_CONFIG_KEYS,
  SWEEPABLE_CONFIG_KEYS,
  apply_cli_set_overrides,
  apply_config_overrides,
  apply_dispatch_config_overrides,
  apply_dispatch_env_overrides,
  parse_set_argument,
)
