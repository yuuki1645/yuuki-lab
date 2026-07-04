# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""Observation normalization helpers."""

from __future__ import annotations

import torch


def clip_scale(values: torch.Tensor, scale: float) -> torch.Tensor:
    """Map values to [-1, 1] via division by scale."""
    if scale <= 0.0:
        return torch.zeros_like(values)
    return torch.clamp(values / scale, -1.0, 1.0)


def range_to_norm(values: torch.Tensor, lo: torch.Tensor, hi: torch.Tensor) -> torch.Tensor:
    """Linearly map [lo, hi] to [-1, 1]."""
    span = hi - lo
    safe_span = torch.where(span > 0.0, span, torch.ones_like(span))
    t = (values - lo.unsqueeze(0)) / safe_span.unsqueeze(0)
    return torch.clamp(2.0 * t - 1.0, -1.0, 1.0)


def height_to_norm(values: torch.Tensor, z_min: float, z_max: float) -> torch.Tensor:
    """Linearly map height [z_min, z_max] to [-1, 1]."""
    span = z_max - z_min
    if span <= 0.0:
        return torch.zeros_like(values)
    t = (values - z_min) / span
    return torch.clamp(2.0 * t - 1.0, -1.0, 1.0)
