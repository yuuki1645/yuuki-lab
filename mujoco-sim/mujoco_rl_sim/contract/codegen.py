"""契約から README 用 Markdown 等を生成。"""

from __future__ import annotations

from mujoco_rl_sim.contract.spec import TelemetryContract


def observation_markdown_table(contract: TelemetryContract) -> str:
  """観測ベクトルの idx 表（README 用）。"""
  lines = [
    "| idx | テレメトリキー | 次元 | 説明 |",
    "|-----|----------------|------|------|",
  ]
  for s in contract.observation.slices:
    dim = s.end - s.start
    idx = f"{s.start}" if dim == 1 else f"{s.start}–{s.end - 1}"
    lines.append(f"| {idx} | `{s.telemetry_key}` | {dim} | {s.description} |")
  lines.append(f"| **合計** | | **{contract.observation.obs_dim}** | |")
  return "\n".join(lines)


def reward_log_markdown_list(contract: TelemetryContract) -> str:
  lines = [f"- `{t.key}` — {t.label}" for t in contract.reward_log.terms]
  return "\n".join(lines)
