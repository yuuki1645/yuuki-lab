# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""MJCF インポート補助（headless 実行向け）。"""

from __future__ import annotations

_MJCF_EXTENSION = "isaacsim.asset.importer.mjcf"
_MJCF_EXTENSION_ENABLED = False


def ensure_mjcf_importer_enabled() -> None:
    """MJCF インポータ拡張を有効化する。

    GUI 用 ``isaaclab.python.kit`` には同梱されるが、
    ``isaaclab.python.headless.kit`` には含まれない。
    ``MjcfFileCfg`` でロボットを spawn する前に呼ぶこと。
    """
    global _MJCF_EXTENSION_ENABLED
    if _MJCF_EXTENSION_ENABLED:
        return

    from isaacsim.core.utils.extensions import enable_extension

    enable_extension(_MJCF_EXTENSION)
    _MJCF_EXTENSION_ENABLED = True
