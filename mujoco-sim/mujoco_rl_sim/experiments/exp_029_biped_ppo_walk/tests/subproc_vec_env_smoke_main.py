"""Subproc VecEnv スモーク（Windows spawn 用・``__main__`` ガード付き）。"""

from __future__ import annotations

import sys
from pathlib import Path

# ``python tests/...py`` 実行時は sys.path[0] が tests/ になるため実験ルートを先頭に載せる
_EXP_ROOT = Path(__file__).resolve().parent.parent
if str(_EXP_ROOT) not in sys.path:
  sys.path.insert(0, str(_EXP_ROOT))

import _paths

_paths.install()

import config
from sim.subproc_vec_env import SubprocVecEnvBiped


def main() -> None:
  vec = SubprocVecEnvBiped(
    2,
    training_dr_enabled=False,
    training_seed=0,
    step_wall_sleep_sec=0.0,
  )
  try:
    obs_list = vec.reset_all(start_episode_index=0)
    assert len(obs_list) == 2
    assert len(obs_list[0]) == config.OBS_DIM

    zero_action = tuple(0.0 for _ in range(config.ACTION_DIM))
    batch = vec.step([zero_action, zero_action])
    assert len(batch.observations) == 2
    assert batch.rewards.shape == (2,)

    obs_reset = vec.reset_env(0, episode_index=5)
    assert len(obs_reset) == config.OBS_DIM
  finally:
    vec.close()

  print("subproc_vec_env_smoke_ok")


if __name__ == "__main__":
  main()
