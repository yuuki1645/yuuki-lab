"""legacy argv を Hydra override に変換するブリッジ。"""

from __future__ import annotations

from collections.abc import Iterable
import sys

from lib.dispatch_cfg_merge import DISPATCH_KEY_TO_CFG_PATH


def _take_value(argv: list[str], i: int, option: str) -> tuple[str, int]:
  if i + 1 >= len(argv):
    raise SystemExit(f"{option} には値が必要です")
  return argv[i + 1], i + 2


def _convert_set_arg(raw: str) -> str:
  key, sep, value = str(raw).partition("=")
  if sep != "=":
    raise SystemExit(f"--set は key=value 形式です: {raw!r}")
  cfg_path = DISPATCH_KEY_TO_CFG_PATH.get(key.strip())
  if cfg_path is None:
    raise SystemExit(f"--set の未対応キーです: {key!r}")
  return f"{cfg_path}={value.strip()}"


def convert_legacy_argv_to_hydra_overrides(
  argv: Iterable[str] | None = None,
) -> tuple[list[str], list[str]]:
  """legacy 引数を (残す argv, hydra overrides) へ変換する。"""
  args = list(argv if argv is not None else sys.argv[1:])
  passthrough: list[str] = []
  overrides: list[str] = []

  i = 0
  while i < len(args):
    token = args[i]

    if token == "--wandb-run-name":
      value, i = _take_value(args, i, token)
      overrides.append(f"wandb.run_name={value}")
      continue
    if token == "--no-wandb":
      overrides.append("wandb.enabled=false")
      i += 1
      continue
    if token == "--wandb":
      overrides.append("wandb.enabled=true")
      i += 1
      continue
    if token == "--lr":
      value, i = _take_value(args, i, token)
      overrides.append(f"ppo.lr={value}")
      continue
    if token == "--num-updates":
      value, i = _take_value(args, i, token)
      overrides.append(f"training.num_updates={value}")
      continue
    if token == "--resume":
      value, i = _take_value(args, i, token)
      overrides.append(f"resume.checkpoint={value}")
      continue
    if token == "--load-optimizer":
      overrides.append("resume.load_optimizer=true")
      i += 1
      continue
    if token == "--seed":
      value, i = _take_value(args, i, token)
      overrides.append(f"training.seed={value}")
      continue
    if token == "--num-envs":
      value, i = _take_value(args, i, token)
      overrides.append(f"runtime.num_envs={value}")
      continue
    if token == "--viewer":
      overrides.append("runtime.viewer=true")
      i += 1
      continue
    if token == "--no-viewer":
      overrides.append("runtime.viewer=false")
      i += 1
      continue
    if token == "--telemetry":
      overrides.append("runtime.telemetry=true")
      i += 1
      continue
    if token == "--no-telemetry":
      overrides.append("runtime.telemetry=false")
      i += 1
      continue
    if token == "--telemetry-host":
      value, i = _take_value(args, i, token)
      overrides.append(f"runtime.telemetry_host={value}")
      continue
    if token == "--telemetry-port":
      value, i = _take_value(args, i, token)
      overrides.append(f"runtime.telemetry_port={value}")
      continue
    if token == "--step-wall-sleep":
      value, i = _take_value(args, i, token)
      overrides.append(f"runtime.step_wall_sleep_sec={value}")
      continue
    if token == "--viewer-fast":
      overrides.append("runtime.viewer=true")
      overrides.append("runtime.step_wall_sleep_sec=0.0")
      i += 1
      continue
    if token == "--no-training-dr":
      overrides.append("training.training_dr=false")
      i += 1
      continue
    if token == "--no-eval":
      overrides.append("training.post_train_eval=false")
      i += 1
      continue
    if token == "--set":
      value, i = _take_value(args, i, token)
      overrides.append(_convert_set_arg(value))
      continue

    passthrough.append(token)
    i += 1

  return passthrough, overrides


def bridge_legacy_argv_for_hydra() -> list[str]:
  """train.py 起動時に legacy argv を Hydra override へ変換する。"""
  passthrough, overrides = convert_legacy_argv_to_hydra_overrides(sys.argv[1:])
  if overrides:
    sys.argv = [sys.argv[0], *passthrough, *overrides]
  return overrides
