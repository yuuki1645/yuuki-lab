"""チェックポイント保存・読み込み（runs/<実験名>/ に保存）。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, TYPE_CHECKING

import torch

import config
from package_meta import CHECKPOINT_FORMAT, CHECKPOINT_ROOT

if TYPE_CHECKING:
  from .agent import AgentPPO

EXPECTED_CHECKPOINT_FORMAT = CHECKPOINT_FORMAT
# exp_008 からの転移学習（観測 25 次元同一）
COMPATIBLE_CHECKPOINT_FORMATS = (
  CHECKPOINT_FORMAT,
  "exp_008_2joint_ppo_hop_shaping_ppo_v1",
)


def resolve_checkpoint_path(path_str: str) -> Path:
  """チェックポイント .pt のパスを解決する。

  相対パスは config.CHECKPOINT_DIR（mujoco_rl_sim/runs/<実験名>/）基準。
  例: run_YYYYMMDD_HHMMSS/update_005000.pt
  """
  path = Path(path_str).expanduser()
  if not path.is_absolute():
    path = (CHECKPOINT_ROOT / path).resolve()
  else:
    path = path.resolve()
  if not path.is_file():
    raise FileNotFoundError(f"checkpoint not found: {path}")
  return path


def make_run_dir() -> Path:
  """1 回の train 実行用ディレクトリを作成して返す（CWD 非依存）。"""
  base = Path(config.CHECKPOINT_DIR)
  run_dir = base / datetime.now().strftime("run_%Y%m%d_%H%M%S")
  run_dir.mkdir(parents=True, exist_ok=True)
  return run_dir


def build_payload(
  agent: AgentPPO,
  *,
  update: int,
  total_env_steps: int,
  episodes_finished: int,
) -> dict[str, Any]:
  """torch.save 用の辞書。actor / critic / optimizer の state_dict を含む。"""
  return {
    "format": CHECKPOINT_FORMAT,
    "algorithm": "ppo",
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
  agent: AgentPPO,
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
  """.pt を読み込む。AgentPPO.from_checkpoint が利用。"""
  return torch.load(path, map_location=map_location, weights_only=False)
