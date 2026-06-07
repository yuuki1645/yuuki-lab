"""Subproc VecEnv: 親が方策、子プロセスが MuJoCo sim（SB3 SubprocVecEnv 相当）。

Windows ``spawn`` 向けに worker はモジュールトップレベル関数とする。
"""

from __future__ import annotations

from dataclasses import dataclass
from multiprocessing import Pipe, Process
from multiprocessing.connection import Connection
from typing import Any, Sequence

import numpy as np

from sim.step_info_ipc import lite_step_info

# 実験ルート（子プロセスへ明示的に渡す）
_EXP_ROOT = str(__import__("pathlib").Path(__file__).resolve().parent.parent)


def _install_exp_root(exp_root: str) -> None:
  """spawn 子プロセス用: 実験ルートを sys.path 先頭に載せ、古い import キャッシュを消す。"""
  import sys

  if exp_root not in sys.path:
    sys.path.insert(0, exp_root)
  for name in list(sys.modules):
    if name == "sim" or name.startswith("sim."):
      del sys.modules[name]
    if name == "mujoco_sim_common" or name.startswith("mujoco_sim_common."):
      del sys.modules[name]


def _subproc_env_worker(
  conn: Connection,
  exp_root: str,
  *,
  training_dr_enabled: bool,
  training_seed: int | None,
  step_wall_sleep_sec: float,
) -> None:
  """子プロセス: Pipe 経由で step / reset を受け、MuJoCo env を実行する。"""
  _install_exp_root(exp_root)

  # 遅延 import（spawn 子プロセスの起動コストと循環 import 回避）
  from sim.env import EnvBipedPPO

  env = EnvBipedPPO(
    enable_viewer=False,
    training_dr_enabled=training_dr_enabled,
    training_seed=training_seed,
  )
  env.set_step_wall_sleep_sec(step_wall_sleep_sec)

  try:
    while True:
      msg = conn.recv()
      if not isinstance(msg, tuple) or len(msg) < 1:
        conn.send(("error", "invalid message"))
        continue

      cmd = msg[0]

      if cmd == "close":
        conn.send(("ok",))
        break

      if cmd == "reset":
        if len(msg) != 2:
          conn.send(("error", "reset expects episode_index"))
          continue
        episode_index = int(msg[1])
        obs = env.reset(episode_index=episode_index)
        conn.send(("reset_result", list(obs)))

      elif cmd == "step":
        if len(msg) != 2:
          conn.send(("error", "step expects action"))
          continue
        action = tuple(float(x) for x in msg[1])

        obs, reward, terminated, step_info = env.step(
          action,
          visualize=False,
          episode_step=0,
        )
        conn.send(
          (
            "step_result",
            list(obs),
            float(reward),
            bool(terminated),
            lite_step_info(step_info),
          )
        )

      else:
        conn.send(("error", f"unknown command: {cmd!r}"))

  except Exception as exc:
    conn.send(("error", repr(exc)))
    raise
  finally:
    conn.close()


@dataclass(frozen=True)
class VecStepBatch:
  """1 回のベクトル step の結果。"""

  observations: list[tuple[float, ...]]
  rewards: np.ndarray
  terminated: np.ndarray
  infos: list[dict[str, Any]]


class SubprocVecEnvBiped:
  """N 個の ``EnvBipedPPO`` を子プロセスで並列に step する VecEnv。"""

  def __init__(
    self,
    num_envs: int,
    *,
    training_dr_enabled: bool,
    training_seed: int | None,
    step_wall_sleep_sec: float,
  ):
    if num_envs < 1:
      raise ValueError(f"num_envs must be >= 1, got {num_envs}")

    self.num_envs = int(num_envs)
    self._processes: list[Process] = []
    self._parent_conns: list[Connection] = []

    for _ in range(self.num_envs):
      parent_conn, child_conn = Pipe(duplex=True)
      proc = Process(
        target=_subproc_env_worker,
        args=(child_conn, _EXP_ROOT),
        kwargs={
          "training_dr_enabled": training_dr_enabled,
          "training_seed": training_seed,
          "step_wall_sleep_sec": step_wall_sleep_sec,
        },
        daemon=True,
      )
      proc.start()
      child_conn.close()
      self._processes.append(proc)
      self._parent_conns.append(parent_conn)

  def _recv(self, conn: Connection) -> tuple:
    msg = conn.recv()
    if not isinstance(msg, tuple) or len(msg) < 1:
      raise RuntimeError(f"invalid worker message: {msg!r}")
    if msg[0] == "error":
      raise RuntimeError(f"subproc env worker error: {msg[1]}")
    return msg

  def reset_env(self, env_id: int, *, episode_index: int) -> tuple[float, ...]:
    """単一 env を reset する。"""
    conn = self._parent_conns[env_id]
    conn.send(("reset", int(episode_index)))
    msg = self._recv(conn)
    if msg[0] != "reset_result":
      raise RuntimeError(f"expected reset_result, got {msg[0]!r}")
    return tuple(float(x) for x in msg[1])

  def reset_all(
    self,
    *,
    start_episode_index: int,
  ) -> list[tuple[float, ...]]:
    """全 env を reset し、互いに異なる episode_index を割り当てる。"""
    obs_list: list[tuple[float, ...]] = []
    for env_id in range(self.num_envs):
      obs = self.reset_env(
        env_id,
        episode_index=int(start_episode_index) + env_id,
      )
      obs_list.append(obs)
    return obs_list

  def step(self, actions: Sequence[Sequence[float]]) -> VecStepBatch:
    """全 env に action を送り、並列 step の結果をまとめて受け取る。"""
    if len(actions) != self.num_envs:
      raise ValueError(
        f"actions length {len(actions)} != num_envs {self.num_envs}"
      )

    # 親→子: 先に全 worker へ送信（子は並列に MuJoCo を実行できる）
    for env_id, conn in enumerate(self._parent_conns):
      action = tuple(float(x) for x in actions[env_id])
      conn.send(("step", action))

    observations: list[tuple[float, ...]] = []
    rewards = np.zeros(self.num_envs, dtype=np.float64)
    terminated = np.zeros(self.num_envs, dtype=bool)
    infos: list[dict[str, Any]] = []

    for env_id, conn in enumerate(self._parent_conns):
      msg = self._recv(conn)
      if msg[0] != "step_result":
        raise RuntimeError(f"expected step_result, got {msg[0]!r}")
      obs = tuple(float(x) for x in msg[1])
      observations.append(obs)
      rewards[env_id] = float(msg[2])
      terminated[env_id] = bool(msg[3])
      infos.append(dict(msg[4]))

    return VecStepBatch(
      observations=observations,
      rewards=rewards,
      terminated=terminated,
      infos=infos,
    )

  def close(self) -> None:
    """子プロセスを終了する。"""
    for conn in self._parent_conns:
      try:
        conn.send(("close",))
        conn.recv()
      except (BrokenPipeError, EOFError, OSError):
        pass
      finally:
        conn.close()

    for proc in self._processes:
      proc.join(timeout=5.0)
      if proc.is_alive():
        proc.terminate()
        proc.join(timeout=2.0)

    self._parent_conns.clear()
    self._processes.clear()
