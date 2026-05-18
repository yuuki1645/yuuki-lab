"""exp_001 チェックポイント保存・読み込み。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, TYPE_CHECKING

import torch

from mujoco_rl_sim.experiments.exp_001_2joint_a2c import config
from mujoco_rl_sim.lib.mujoco_paths import mujoco_sim_asset_path

if TYPE_CHECKING:
  from mujoco_rl_sim.experiments.exp_001_2joint_a2c.agent import AgentExp001A2C

CHECKPOINT_FORMAT = "exp_001_a2c_v1"


def make_run_dir() -> Path:
  """1 回の train 実行用ディレクトリを作成して返す（mujoco-sim 直下・CWD 非依存）。"""
  base = Path(mujoco_sim_asset_path(config.CHECKPOINT_DIR))
  run_dir = base / datetime.now().strftime("run_%Y%m%d_%H%M%S")
  run_dir.mkdir(parents=True, exist_ok=True)
  return run_dir


def build_payload(
  agent: AgentExp001A2C,
  *,
  update: int,
  total_env_steps: int,
  episodes_finished: int,
) -> dict[str, Any]:
  return {
    "format": CHECKPOINT_FORMAT,
    "update": update,
    "total_env_steps": total_env_steps,
    "episodes_finished": episodes_finished,
    "obs_dim": agent.obs_dim,
    "action_dim": agent.action_dim,
    "actor": agent.actor.state_dict(),
    "critic": agent.critic.state_dict(),
    "optimizer": agent.optimizer.state_dict(),
  }


def save_agent_checkpoint(
  agent: AgentExp001A2C,
  *,
  run_dir: Path,
  update: int,
  total_env_steps: int,
  episodes_finished: int,
  numbered: bool = True,
  latest: bool = False,
  final: bool = False,
) -> list[Path]:
  """agent の重み（と optimizer）を保存。書き込んだパスの一覧を返す。"""
  payload = build_payload(
    agent,
    update=update,
    total_env_steps=total_env_steps,
    episodes_finished=episodes_finished,
  )
  written: list[Path] = []
  if numbered:
    path = run_dir / f"update_{update:06d}.pt"
    torch.save(payload, path)
    written.append(path)
  if latest:
    path = run_dir / "latest.pt"
    torch.save(payload, path)
    written.append(path)
  if final:
    path = run_dir / "final.pt"
    torch.save(payload, path)
    written.append(path)
  return written


def load_checkpoint(path: str | Path, *, map_location: str | torch.device = "cpu") -> dict[str, Any]:
  return torch.load(path, map_location=map_location, weights_only=False)
