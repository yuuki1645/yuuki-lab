"""チェックポイント保存・読み込み（runs/<実験名>/ に保存）。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, TYPE_CHECKING

import torch

from lib.run_dir import (
  make_unique_run_dir,
  resolve_run_dir_label,
  wandb_active_run_name,
)

from lib.experiment_context import ExperimentContext
from package_meta import CHECKPOINT_FORMAT, CHECKPOINT_ROOT

if TYPE_CHECKING:
  from rl.agent import AgentPPO

EXPECTED_CHECKPOINT_FORMAT = CHECKPOINT_FORMAT
# exp_008 からの転移学習（観測 25 次元同一）
COMPATIBLE_CHECKPOINT_FORMATS = (
  CHECKPOINT_FORMAT,
  "exp_008_2joint_ppo_hop_shaping_ppo_v1",
  "exp_009_2joint_ppo_hop_lean_gate_ppo_v1",
  "exp_010_2joint_ppo_hop_progress_ppo_v1",
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


def make_run_dir(ctx: ExperimentContext, *, wandb_run_name: str | None = None) -> Path:
  """1 回の train 実行用ディレクトリを作成して返す（CWD 非依存）。

  wandb 有効時は Run の Name（例: lunar-pond-4）をフォルダ名に使う。
  省略時は初期化済み wandb.run.name を参照し、無ければ run_YYYYMMDD_HHMMSS。
  """
  if wandb_run_name is None:
    wandb_run_name = wandb_active_run_name()
  checkpoint_base = str(ctx.checkpoint_root).strip() or str(ctx.cfg.checkpoint.checkpoint_dir)
  base = Path(checkpoint_base)
  label = resolve_run_dir_label(wandb_run_name=wandb_run_name)
  return make_unique_run_dir(base, label)


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
    "policy_hidden_sizes": agent.hidden_sizes,
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
