#!/usr/bin/env python3
"""exp_001〜exp_024 を exp_025 同様のスタンドアロン構成に変換する（一括）。"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "mujoco_rl_sim" / "experiments"
TEMPLATE = EXPERIMENTS / "exp_025_biped_ppo_hop_balance"
RL_LIB = ROOT / "mujoco_rl_sim" / "lib"

PATHS_PY = '''"""スタンドアロン実行: 実験フォルダを sys.path 先頭に載せる。"""

from __future__ import annotations

import sys
from pathlib import Path

_EXP_ROOT = Path(__file__).resolve().parent


def install() -> Path:
  root = str(_EXP_ROOT)
  if root not in sys.path:
    sys.path.insert(0, root)
  return _EXP_ROOT
'''

PACKAGE_META_PY = '''"""実験フォルダ名から自動導出されるメタデータ。"""

from pathlib import Path

EXP_DIR = Path(__file__).resolve().parent
EXP_NAME = EXP_DIR.name
CHECKPOINT_ROOT = EXP_DIR / "runs" / EXP_NAME
CHECKPOINT_REL_FROM_EXP = f"runs/{EXP_NAME}"
CHECKPOINT_REL_FROM_MUJOCO_SIM = CHECKPOINT_REL_FROM_EXP
PACKAGE = EXP_NAME
'''

MUJOCO_PATHS_PY = '''"""実験フォルダ基準のパス解決（スタンドアロン用）。"""

from pathlib import Path

from package_meta import EXP_DIR


def exp_path(*parts: str) -> str:
  return str(EXP_DIR.joinpath(*parts))
'''

ENTRY_SCRIPTS = (
  "train.py",
  "visualize.py",
  "analyze_rollout.py",
  "preview_warmup.py",
  "debug.py",
)

BOOTSTRAP = (
  "from _paths import install\n\ninstall()\n\n"
)


def _copy_tree(src: Path, dst: Path) -> None:
  if not src.is_dir():
    return
  if dst.exists():
    shutil.rmtree(dst)
  shutil.copytree(src, dst)


def _copy_file(src: Path, dst: Path) -> None:
  dst.parent.mkdir(parents=True, exist_ok=True)
  shutil.copy2(src, dst)


def _needs(text: str, needle: str) -> bool:
  return needle in text


def _collect_text(exp_dir: Path) -> str:
  parts: list[str] = []
  for py in exp_dir.rglob("*.py"):
    parts.append(py.read_text(encoding="utf-8"))
  return "\n".join(parts)


def _vendor_bundle(exp_dir: Path, text: str) -> None:
  if _needs(text, "mujoco_rl_sim.contract") or _needs(text, "from contract"):
    for name in ("contract", "telemetry"):
      _copy_tree(TEMPLATE / name, exp_dir / name)
  if _needs(text, "mujoco_rl_sim.telemetry") or _needs(text, "from telemetry"):
    _copy_tree(TEMPLATE / "telemetry", exp_dir / "telemetry")
  if _needs(text, "mujoco_sim_common"):
    dst = exp_dir / "mujoco_sim_common"
    dst.mkdir(parents=True, exist_ok=True)
    _copy_file(TEMPLATE / "mujoco_sim_common" / "kinematics.py", dst / "kinematics.py")
    _copy_file(
      TEMPLATE / "mujoco_sim_common" / "viewer_visual_presets.py",
      dst / "viewer_visual_presets.py",
    )
    tel = dst / "telemetry"
    tel.mkdir(parents=True, exist_ok=True)
    _copy_file(
      TEMPLATE / "mujoco_sim_common" / "telemetry" / "hub_socketio_server.py",
      tel / "hub_socketio_server.py",
    )
    (dst / "__init__.py").write_text("", encoding="utf-8")
    (tel / "__init__.py").write_text(
      "from mujoco_sim_common.telemetry.hub_socketio_server import HubTelemetrySocketIoServer\n\n"
      '__all__ = ["HubTelemetrySocketIoServer"]\n',
      encoding="utf-8",
    )

  lib_dir = exp_dir / "lib"
  lib_dir.mkdir(parents=True, exist_ok=True)
  for fname in ("run_dir.py", "episode_rolling.py"):
    if _needs(text, fname.replace(".py", "")) or _needs(text, f"mujoco_rl_sim.lib.{fname[:-3]}"):
      src = RL_LIB / fname
      if src.is_file():
        _copy_file(src, lib_dir / fname)
  for fname in ("ctrl.py", "obs_norm.py", "terminal_bar.py"):
    if _needs(text, f"mujoco_rl_sim.lib.{fname[:-3]}"):
      src = RL_LIB / fname
      if src.is_file() and not (lib_dir / fname).is_file():
        _copy_file(src, lib_dir / fname)
  if _needs(text, "mujoco_paths"):
    _copy_file(Path(__file__).parent / "_mujoco_paths_stub.py", lib_dir / "mujoco_paths.py")


def _rewrite_imports(text: str, exp_name: str) -> str:
  pkg = f"mujoco_rl_sim.experiments.{exp_name}"
  text = re.sub(rf"from {re.escape(pkg)} import ", "import ", text)
  text = text.replace(pkg + ".", "")
  for pat, rep in [
    (r"from mujoco_rl_sim\.contract\.", "from contract."),
    (r"from mujoco_rl_sim\.contract import", "from contract import"),
    (r"from mujoco_rl_sim\.lib\.", "from lib."),
    (r"from mujoco_rl_sim\.telemetry\.", "from telemetry."),
    (r"from mujoco_sim_common\.", "from mujoco_sim_common."),
  ]:
    text = re.sub(pat, rep, text)

  def rel_sub(m: re.Match[str]) -> str:
    return f"from {m.group(1)} import"

  text = re.sub(r"^from \.([\w.]+) import", rel_sub, text, flags=re.M)
  text = re.sub(r"^from \. import ", "import ", text, flags=re.M)
  text = text.replace('"mujoco_rl_sim.contract"', '"contract"')
  text = text.replace("contract_package': 'mujoco_rl_sim.contract", "contract_package': 'contract")
  return text


def _fix_lib_submodules(exp_dir: Path) -> None:
  lib_dir = exp_dir / "lib"
  if not lib_dir.is_dir():
    return
  for py in lib_dir.glob("*.py"):
    if py.name == "__init__.py":
      continue
    text = py.read_text(encoding="utf-8")
    new = text
    for mod in ("actuators", "ctrl", "obs_norm", "pose", "contact", "action"):
      new = re.sub(
        rf"^from {mod} import",
        rf"from lib.{mod} import",
        new,
        flags=re.M,
      )
    if new != text:
      py.write_text(new, encoding="utf-8")


def _fix_relative_imports(exp_dir: Path) -> None:
  """関数内・TYPE_CHECKING 等に残る ``from .`` を除去（python train.py 用）。"""
  for py in exp_dir.rglob("*.py"):
    lines = py.read_text(encoding="utf-8").splitlines(keepends=True)
    new_lines: list[str] = []
    changed = False
    for line in lines:
      orig = line
      m = re.match(r"^(\s*)from \. import (.+)$", line.rstrip("\n"))
      if m:
        line = f"{m.group(1)}import {m.group(2)}\n"
      else:
        m2 = re.match(r"^(\s*)from \.([\w]+) import (.+)$", line.rstrip("\n"))
        if m2:
          line = f"{m2.group(1)}from {m2.group(2)} import {m2.group(3)}\n"
      if line != orig:
        changed = True
      new_lines.append(line)
    if changed:
      py.write_text("".join(new_lines), encoding="utf-8")


def _fix_lib_init(text: str) -> str:
  for mod in ("action", "ctrl", "obs_norm", "terminal_bar", "actuators", "pose", "contact"):
    text = re.sub(
      rf"^from {mod} import",
      rf"from lib.{mod} import",
      text,
      flags=re.M,
    )
  return text


def _add_bootstrap(path: Path) -> None:
  text = path.read_text(encoding="utf-8")
  if "from _paths import install" in text:
    # 誤って __future__ の前に入った bootstrap を直す
    if re.search(r"install\(\)\s*\n\s*from __future__", text):
      text = re.sub(
        r"(from _paths import install\s*\n\s*install\(\)\s*\n+)(from __future__)",
        r"\2\n\n\1",
        text,
        count=1,
      )
      path.write_text(text, encoding="utf-8")
    return
  bootstrap = BOOTSTRAP
  if "from __future__ import annotations" in text:
    text = text.replace(
      "from __future__ import annotations\n",
      "from __future__ import annotations\n\n" + bootstrap,
      1,
    )
  elif text.startswith('"""'):
    end = text.find('"""', 3)
    if end != -1:
      insert_at = end + 3
      if text[insert_at : insert_at + 1] == "\n":
        insert_at += 1
      text = text[:insert_at] + "\n\n" + bootstrap + text[insert_at:].lstrip("\n")
    else:
      text = bootstrap + text
  else:
    text = bootstrap + text
  path.write_text(text, encoding="utf-8")


def _fix_checkpoint_format(exp_dir: Path, exp_name: str) -> None:
  meta = exp_dir / "package_meta.py"
  if not meta.is_file():
    return
  text = meta.read_text(encoding="utf-8")
  if "CHECKPOINT_FORMAT" not in text:
    old = exp_dir / "checkpoint.py"
    fmt = None
    if old.is_file():
      m = re.search(r'CHECKPOINT_FORMAT\s*=\s*"([^"]+)"', old.read_text(encoding="utf-8"))
      if m:
        fmt = m.group(1)
    if fmt is None:
      fmt = f"{exp_name}_ppo_v1"
    text = text.rstrip() + f'\nCHECKPOINT_FORMAT = "{fmt}"\n'
    meta.write_text(text, encoding="utf-8")


def standaloneize(exp_dir: Path) -> None:
  if not exp_dir.is_dir() or not exp_dir.name.startswith("exp_"):
    return
  if exp_dir.name == "exp_025_biped_ppo_hop_balance":
    return

  exp_name = exp_dir.name
  text = _collect_text(exp_dir)

  (exp_dir / "_paths.py").write_text(PATHS_PY, encoding="utf-8")
  meta_path = exp_dir / "package_meta.py"
  old_meta = meta_path.read_text(encoding="utf-8") if meta_path.is_file() else ""
  fmt_m = re.search(r"CHECKPOINT_FORMAT\s*=\s*([^\n]+)", old_meta)
  meta_path.write_text(PACKAGE_META_PY, encoding="utf-8")
  if fmt_m:
    meta_path.write_text(
      meta_path.read_text(encoding="utf-8").rstrip() + f"\n{fmt_m.group(0).strip()}\n",
      encoding="utf-8",
    )
  else:
    _fix_checkpoint_format(exp_dir, exp_name)

  _vendor_bundle(exp_dir, text)
  text = _collect_text(exp_dir)

  for py in sorted(exp_dir.rglob("*.py")):
    if py.name == "_paths.py":
      continue
    rel = py.relative_to(exp_dir)
    raw = py.read_text(encoding="utf-8")
    new = _rewrite_imports(raw, exp_name)
    if rel.as_posix() == "lib/__init__.py":
      new = _fix_lib_init(new)
    if py.name == "biped_ppo.py" and "telemetry" in str(rel):
      new = new.replace("from env_wrapper import", "from telemetry.env_wrapper import")
    if py.name == "mujoco_paths.py" and "lib" in str(rel):
      new = MUJOCO_PATHS_PY
    if new != raw:
      py.write_text(new, encoding="utf-8")

  _fix_lib_submodules(exp_dir)
  _fix_relative_imports(exp_dir)

  for name in ENTRY_SCRIPTS:
    script = exp_dir / name
    if script.is_file() and 'if __name__ == "__main__"' in script.read_text(encoding="utf-8"):
      _add_bootstrap(script)

  # exp_001 checkpoint: use CHECKPOINT_ROOT
  ckpt = exp_dir / "checkpoint.py"
  if ckpt.is_file():
    c = ckpt.read_text(encoding="utf-8")
    if "mujoco_sim_asset_path" in c:
      c = c.replace(
        "from lib.mujoco_paths import mujoco_sim_asset_path\n",
        "from package_meta import CHECKPOINT_ROOT\n",
      )
      c = c.replace(
        "from mujoco_rl_sim.lib.mujoco_paths import mujoco_sim_asset_path\n",
        "from package_meta import CHECKPOINT_ROOT\n",
      )
      c = re.sub(
        r"Path\(mujoco_sim_asset_path\(config\.CHECKPOINT_DIR\)\)",
        "CHECKPOINT_ROOT",
        c,
      )
      ckpt.write_text(c, encoding="utf-8")


def main() -> None:
  stub = Path(__file__).parent / "_mujoco_paths_stub.py"
  stub.write_text(MUJOCO_PATHS_PY, encoding="utf-8")
  for exp_dir in sorted(EXPERIMENTS.iterdir()):
    standaloneize(exp_dir)
  print("done")


if __name__ == "__main__":
  main()
