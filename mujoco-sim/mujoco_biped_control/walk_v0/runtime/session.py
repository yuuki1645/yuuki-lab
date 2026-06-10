"""1 回の制御走行セッション。"""

from __future__ import annotations

import shutil
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from controller.walk import WalkController
from runtime.config import RunConfig, load_control_params
from runtime.exp030_env import create_env, reset_env
from runtime.incidents import IncidentDetector
from runtime.snapshot import render_frame_png, save_physics_snapshot
from runtime.trajectory import TrajectoryLogger, write_json, write_manifest
from walk_meta import EXP_DIR, RUNS_ROOT


def _make_run_dir() -> Path:
  ts = datetime.now().strftime("%Y%m%d_%H%M%S")
  run_dir = RUNS_ROOT / f"run_{ts}"
  run_dir.mkdir(parents=True, exist_ok=True)
  return run_dir


def run_session(
  run_cfg: RunConfig,
  *,
  enable_viewer: bool = False,
  visualize: bool = False,
  run_dir: Path | None = None,
) -> dict[str, Any]:
  """制御プログラムを MuJoCo 上で実行し、ログ・インシデントを保存する。"""
  run_dir = run_dir or _make_run_dir()
  run_dir.mkdir(parents=True, exist_ok=True)

  # 再現用に設定ファイルをコピー
  shutil.copy2(EXP_DIR / "conf" / "default.yaml", run_dir / "effective_run.yaml")
  shutil.copy2(run_cfg.controller_config, run_dir / "effective_controller.yaml")

  write_manifest(
    run_dir,
    seed=run_cfg.seed,
    run_cfg_path=str(run_dir / "effective_run.yaml"),
    controller_cfg_path=str(run_dir / "effective_controller.yaml"),
    exp030_dir=str(run_cfg.exp030_dir),
  )

  params = load_control_params(run_cfg.controller_config)
  controller = WalkController(params)
  controller.reset()

  env = create_env(run_cfg, enable_viewer=enable_viewer)
  control_dt = float(env._ctx.cfg.sim.control_timestep_s)

  obs, origin_imu_x = reset_env(env, seed=run_cfg.seed)
  detector = IncidentDetector(run_cfg.incident)
  logger = TrajectoryLogger(run_dir)

  terminated = False
  termination_reason: str | None = None
  last_step_info: dict[str, Any] = {}
  step = -1
  left_landings = 0
  right_landings = 0
  prev_left_on_floor = True
  prev_right_on_floor = True

  try:
    for step in range(run_cfg.max_steps):
      obs_arr = np.asarray(obs, dtype=np.float64)
      action, ctrl_debug = controller.compute_action(
        step=step,
        obs=obs_arr,
        env=env,
        control_dt=control_dt,
      )
      obs, _reward, terminated, step_info = env.step(
        action,
        visualize=visualize,
        episode_step=step,
      )
      last_step_info = step_info
      time_s = float(step + 1) * control_dt

      left_on = float(step_info.get("left_foot_on_floor", 0.0)) > 0.5
      right_on = float(step_info.get("right_foot_on_floor", 0.0)) > 0.5
      if left_on and not prev_left_on_floor:
        left_landings += 1
      if right_on and not prev_right_on_floor:
        right_landings += 1
      prev_left_on_floor = left_on
      prev_right_on_floor = right_on

      row = {
        "step": step,
        "time_s": time_s,
        "imu_x": float(step_info.get("imu_x", 0.0)),
        "imu_dx": float(step_info.get("imu_dx", 0.0)),
        "upright": float(step_info.get("upright", 0.0)),
        "left_foot_on_floor": float(step_info.get("left_foot_on_floor", 0.0)),
        "right_foot_on_floor": float(step_info.get("right_foot_on_floor", 0.0)),
        "single_support": float(step_info.get("single_support", 0.0)),
        "aerial_steps": float(step_info.get("aerial_steps", 0.0)),
        "reward_total": float(step_info.get("reward_total", 0.0)),
        "termination_reason": step_info.get("termination_reason") or "",
        **{f"action_{i}": action[i] for i in range(len(action))},
        "ctrl_phase": str(ctrl_debug.get("phase", "")),
        "ctrl_subphase": float(ctrl_debug.get("subphase", 0.0)),
        "ctrl_phase_step": float(ctrl_debug.get("phase_step", 0.0)),
        "ctrl_step_count": float(ctrl_debug.get("step_count", 0.0)),
        "ctrl_last_swing": str(ctrl_debug.get("last_swing", "")),
      }
      if step % run_cfg.log_every == 0:
        logger.log_step(row)

      term_reason = step_info.get("termination_reason")
      incident = detector.observe_step(
        step=step,
        time_s=time_s,
        step_info=step_info,
        controller_debug=ctrl_debug,
        terminated=bool(terminated),
        termination_reason=str(term_reason) if term_reason else None,
      )
      if incident and run_cfg.save_step_snapshots_on_incident:
        snap_dir = save_physics_snapshot(
          run_dir, step=step, model=env.model, data=env.data
        )
        incident.snapshot_dir = str(snap_dir.relative_to(run_dir))
        try:
          render_frame_png(
            env.model,
            env.data,
            snap_dir / "frame.png",
          )
        except Exception as exc:  # noqa: BLE001 — 画像は補助
          (snap_dir / "frame_error.txt").write_text(str(exc), encoding="utf-8")

      if terminated:
        termination_reason = str(term_reason) if term_reason else "unknown"
        break
  finally:
    logger.close()
    if run_cfg.save_trajectory_csv:
      logger.write_csv()
    if env.viewer is not None:
      env.viewer.close()

  final_imu_x = float(last_step_info.get("imu_x", 0.0))
  summary = {
    "seed": run_cfg.seed,
    "steps": step + 1,
    "time_s": float((step + 1) * control_dt),
    "origin_imu_x": origin_imu_x,
    "final_imu_x": final_imu_x,
    "displacement_x": final_imu_x - origin_imu_x,
    "terminated": terminated,
    "termination_reason": termination_reason,
    "incident_count": len(detector.records),
    "final_step_count": float(controller.state.step_count),
    "alternating_landings": min(left_landings, right_landings),
    "left_landings": left_landings,
    "right_landings": right_landings,
    "final_gait_phase": controller.state.phase.value,
    "controller_params": asdict(params),
  }
  write_json(run_dir / "summary.json", summary)
  write_json(
    run_dir / "incidents.json",
    [r.to_dict() for r in detector.records],
  )

  return {"run_dir": str(run_dir), "summary": summary}
