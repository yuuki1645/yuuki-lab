"""チェックポイントをヘッドレス再生し、時系列と代表フレームを保存する（visualize 補助）。"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import mujoco
import numpy as np

from . import config
from .agent import AgentPPO
from .env import EnvBipedPPO
from .lib.actuators import JOINT_NAMES
from .warmup import WarmupContext, in_episode_warmup, resolve_warmup_action


@dataclass
class StepRecord:
  episode: int
  step: int
  phase: str
  reward: float
  return_cum: float
  upright: float
  imu_z: float
  imu_zaxis_x: float
  imu_x: float
  dx: float
  in_stance: float
  foot_dx: float
  action_norm: float
  left_knee_deg: float
  right_knee_deg: float
  termination_reason: str | None


def _parse_args() -> argparse.Namespace:
  p = argparse.ArgumentParser(description=__doc__)
  p.add_argument("--checkpoint", type=str, required=True)
  p.add_argument("--stochastic", action="store_true")
  p.add_argument("--episodes", type=int, default=8)
  p.add_argument("--out-dir", type=str, default=None)
  p.add_argument("--device", type=str, default="cpu")
  p.add_argument("--width", type=int, default=960)
  p.add_argument("--height", type=int, default=720)
  p.add_argument("--seed", type=int, default=0)
  return p.parse_args()


def _resolve_checkpoint(path_str: str) -> Path:
  path = Path(path_str).expanduser().resolve()
  if not path.is_file():
    raise SystemExit(f"checkpoint not found: {path}")
  return path


def _read_step_metrics(env: EnvBipedPPO, step_info: dict, *, dx: float) -> dict:
  data = env.data
  return {
    "upright": float(step_info["upright"]),
    "imu_z": float(data.site("imu_site").xpos[2]),
    "imu_zaxis_x": float(data.sensor("imu_zaxis").data[0]),
    "imu_x": float(data.site("imu_site").xpos[0]),
    "dx": dx,
    "in_stance": float(step_info.get("in_stance", 0.0)),
    "foot_dx": float(step_info.get("foot_dx", 0.0)),
    "left_knee_deg": float(np.degrees(data.joint("left_knee_pitch").qpos[0])),
    "right_knee_deg": float(np.degrees(data.joint("right_knee_pitch").qpos[0])),
  }


def _make_track_camera(model: mujoco.MjModel) -> mujoco.MjvCamera:
  """basket_thigh（ルート）を追従する自由カメラ。XML の track_robot と同等の見え方。"""
  cam = mujoco.MjvCamera()
  mujoco.mjv_defaultFreeCamera(model, cam)
  cam.type = mujoco.mjtCamera.mjCAMERA_TRACKING
  cam.trackbodyid = model.body("basket_thigh").id
  cam.distance = 2.8
  cam.elevation = -14.0
  cam.azimuth = 100.0
  return cam


def _render_frame(
  renderer: mujoco.Renderer,
  env: EnvBipedPPO,
  path: Path,
  *,
  camera: mujoco.MjvCamera,
) -> None:
  renderer.update_scene(env.data, camera=camera)
  path.parent.mkdir(parents=True, exist_ok=True)
  try:
    import imageio.v3 as iio

    iio.imwrite(path, renderer.render())
  except ImportError:
    from PIL import Image

    Image.fromarray(renderer.render()).save(path)


def main() -> None:
  args = _parse_args()
  np.random.seed(args.seed)
  ckpt = _resolve_checkpoint(args.checkpoint)
  out_dir = Path(args.out_dir).resolve() if args.out_dir else ckpt.parent / "rollout_analysis"
  frames_dir = out_dir / "frames"
  frames_dir.mkdir(parents=True, exist_ok=True)

  agent = AgentPPO.from_checkpoint(ckpt, map_location=args.device)
  act = (lambda obs: agent.act(obs)[0]) if args.stochastic else agent.act_eval

  env = EnvBipedPPO(enable_viewer=False)
  renderer = mujoco.Renderer(env.model, height=args.height, width=args.width)
  track_camera = _make_track_camera(env.model)
  warmup_steps = int(config.WARMUP_DURATION_S / config.CONTROL_TIMESTEP_S) if config.WARMUP_ENABLED else 0

  episode_summaries: list[dict] = []

  for ep in range(args.episodes):
    obs = env.reset()
    ep_return = 0.0
    ep_records: list[StepRecord] = []
    last_action = tuple(0.0 for _ in JOINT_NAMES)
    saved_tags: set[str] = set()
    first_low_upright_step: int | None = None
    prev_in_stance = 1.0

    for step in range(config.MAX_STEPS_PER_EPISODE):
      imu_x_before = float(env.data.site("imu_site").xpos[0])
      phase = "warmup" if config.WARMUP_ENABLED and in_episode_warmup(step) else "policy"

      if phase == "warmup":
        action = resolve_warmup_action(
          config.WARMUP_ACTION_FN,
          WarmupContext(
            obs=obs,
            elapsed_s=step * config.CONTROL_TIMESTEP_S,
            total_env_steps=0,
            episode_step=step,
            episode_index=ep,
          ),
        )
      else:
        action = act(obs)
        last_action = tuple(float(a) for a in action)

      obs, reward, terminated, step_info = env.step(action, episode_step=step)
      imu_x_after = float(env.data.site("imu_site").xpos[0])
      dx = imu_x_after - imu_x_before
      ep_return += float(reward)

      m = _read_step_metrics(env, step_info, dx=dx)
      rec = StepRecord(
        episode=ep + 1,
        step=step + 1,
        phase=phase,
        reward=float(reward),
        return_cum=ep_return,
        action_norm=float(np.linalg.norm(last_action)),
        termination_reason=step_info.get("termination_reason"),
        **m,
      )
      ep_records.append(rec)

      if phase == "policy" and rec.upright < 0.60 and first_low_upright_step is None:
        first_low_upright_step = step

      truncated = (step + 1) >= config.MAX_STEPS_PER_EPISODE
      done = terminated or truncated

      def _save(tag: str) -> None:
        if tag in saved_tags:
          return
        _render_frame(
          renderer,
          env,
          frames_dir / f"ep{ep+1:02d}_step{step+1:03d}_{tag}.png",
          camera=track_camera,
        )
        saved_tags.add(tag)

      if step == warmup_steps:
        _save("policy_start")
      if phase == "policy":
        ps = step - warmup_steps
        if ps == 15:
          _save("policy_p15")
        if ps == 40:
          _save("policy_p40")
      if first_low_upright_step == step:
        _save("upright_drop")
      if (
        phase == "policy"
        and prev_in_stance > 0.5
        and rec.in_stance < 0.5
      ):
        _save("aerial_start")
      prev_in_stance = rec.in_stance

      if done:
        reason = step_info.get("termination_reason") or "truncated"
        _save(f"end_{reason}")

      if done:
        break

    policy_recs = [r for r in ep_records if r.phase == "policy"]
    episode_summaries.append(
      {
        "episode": ep + 1,
        "steps": len(ep_records),
        "policy_steps": len(policy_recs),
        "return": ep_return,
        "reason": ep_records[-1].termination_reason if ep_records else None,
        "max_upright": max((r.upright for r in ep_records), default=0.0),
        "min_upright_policy": min((r.upright for r in policy_recs), default=0.0),
        "min_imu_z": min((r.imu_z for r in ep_records), default=0.0),
        "max_left_knee_deg": max((r.left_knee_deg for r in ep_records), default=0.0),
        "max_right_knee_deg": max((r.right_knee_deg for r in ep_records), default=0.0),
        "stance_ratio": float(np.mean([r.in_stance > 0.5 for r in ep_records])),
        "mean_dx_policy": float(np.mean([r.dx for r in policy_recs])) if policy_recs else 0.0,
        "total_dx_policy": float(sum(r.dx for r in policy_recs)),
        "final_imu_x": float(ep_records[-1].imu_x) if ep_records else 0.0,
        "policy_start_imu_x": float(policy_recs[0].imu_x) if policy_recs else 0.0,
      }
    )
    (out_dir / f"ep{ep+1:02d}_timeseries.json").write_text(
      json.dumps([asdict(r) for r in ep_records], indent=2),
      encoding="utf-8",
    )

  (out_dir / "episode_summaries.json").write_text(
    json.dumps(episode_summaries, indent=2),
    encoding="utf-8",
  )

  print(f"[analyze_rollout] output: {out_dir}")
  for s in episode_summaries:
    print(
      f"  ep{s['episode']:02d} return={s['return']:.1f} steps={s['steps']} "
      f"reason={s['reason']!r} min_upright_pol={s['min_upright_policy']:.3f} "
      f"dx_pol={s['total_dx_policy']:.3f}m imu_x={s.get('final_imu_x', 0):.3f}m"
    )


if __name__ == "__main__":
  main()
