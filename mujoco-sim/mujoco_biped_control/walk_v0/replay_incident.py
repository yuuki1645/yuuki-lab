"""記録済みインシデント瞬間を再現・可視化（seed 固定 run の state.npz 利用）。"""

from __future__ import annotations

from _paths import install

install()

import argparse
import json
import time
from pathlib import Path

import mujoco
import mujoco.viewer
from mujoco_sim_common.viewer_height_overlay import sync_viewer_with_height_overlay
from mujoco_sim_common.viewer_visual_presets import (
  apply_model_visual_preset,
  apply_passive_viewer_options,
)

from runtime.config import load_run_config
from runtime.exp030_env import create_env, install_exp030
from runtime.snapshot import apply_snapshot, load_physics_snapshot, render_frame_png
from walk_meta import EXP_DIR


def _load_incidents(run_dir: Path) -> list[dict]:
  path = run_dir / "incidents.json"
  if not path.is_file():
    raise FileNotFoundError(f"incidents.json not found: {path}")
  with path.open(encoding="utf-8") as f:
    return json.load(f)


def main() -> None:
  p = argparse.ArgumentParser(description="walk_v0: インシデント瞬間を viewer で再生")
  p.add_argument("--run-dir", type=str, required=True, help="run.py の出力ディレクトリ")
  p.add_argument(
    "--incident-index",
    type=int,
    default=0,
    help="incidents.json のインデックス",
  )
  p.add_argument(
    "--save-frame",
    type=str,
    default=None,
    help="追加 PNG 出力パス（省略時は保存しない）",
  )
  p.add_argument(
    "--hold-sec",
    type=float,
    default=5.0,
    help="viewer を開いたまま待機する秒数",
  )
  args = p.parse_args()

  run_dir = Path(args.run_dir).resolve()
  incidents = _load_incidents(run_dir)
  if not incidents:
    raise SystemExit("incidents.json is empty")
  if args.incident_index < 0 or args.incident_index >= len(incidents):
    raise SystemExit(f"incident-index out of range 0..{len(incidents) - 1}")

  inc = incidents[args.incident_index]
  snap_rel = inc.get("snapshot_dir")
  if not snap_rel:
    raise SystemExit("incident has no snapshot_dir (re-run with save_step_snapshots_on_incident)")

  snap_dir = run_dir / snap_rel
  snap = load_physics_snapshot(snap_dir)

  # effective_run.yaml があればそれを、なければ default
  eff = run_dir / "effective_run.yaml"
  cfg_path = eff if eff.is_file() else (EXP_DIR / "conf" / "default.yaml")
  run_cfg = load_run_config(cfg_path)

  install_exp030(run_cfg.exp030_dir)
  env = create_env(run_cfg, enable_viewer=False)
  apply_snapshot(env.model, env.data, snap)

  print(json.dumps(inc, ensure_ascii=False, indent=2))

  if args.save_frame:
    render_frame_png(env.model, env.data, Path(args.save_frame))

  with mujoco.viewer.launch_passive(env.model, env.data) as viewer:
    apply_passive_viewer_options(viewer)
    sync_viewer_with_height_overlay(viewer, env._ctx)
    t0 = time.time()
    while viewer.is_running() and (time.time() - t0) < args.hold_sec:
      sync_viewer_with_height_overlay(viewer, env._ctx)
      viewer.sync()
      time.sleep(0.02)


if __name__ == "__main__":
  main()
