from pathlib import Path

# mujoco_rl_sim/lib -> mujoco-sim
_MUJOCO_SIM_ROOT = Path(__file__).resolve().parents[2]


def mujoco_sim_asset_path(*parts: str) -> str:
  """mujoco-sim 配下のパスを CWD に依存せず解決する。"""
  return str(_MUJOCO_SIM_ROOT.joinpath(*parts))
