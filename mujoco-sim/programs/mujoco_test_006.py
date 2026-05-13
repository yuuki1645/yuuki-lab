# type: ignore
"""
簡単な強化学習（PPO）サンプル: 浮遊ベース + 股関節 1 軸で **世界座標 +X 方向の前進** を報酬化する。

依存: ``pip install -e ".[rl]"``（gymnasium, stable-baselines3）

例::

  cd mujoco-sim/programs
  python mujoco_test_006.py
  python mujoco_test_006.py --timesteps 50000 --no-check-env
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SIM_ROOT = Path(__file__).resolve().parents[1]
if str(_SIM_ROOT) not in sys.path:
    sys.path.insert(0, str(_SIM_ROOT))

import mujoco  # noqa: E402
import numpy as np  # noqa: E402

try:
    import gymnasium as gym  # noqa: E402
    from gymnasium import spaces  # noqa: E402
    from stable_baselines3 import PPO  # noqa: E402
    from stable_baselines3.common.env_checker import check_env  # noqa: E402
    from stable_baselines3.common.monitor import Monitor  # noqa: E402
except ImportError as e:
    raise SystemExit(
        "gymnasium / stable-baselines3 が必要です。\n"
        "  cd mujoco-sim && pip install -e \".[rl]\""
    ) from e


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument(
        "--xml",
        type=str,
        default=str(_SIM_ROOT / "mujoco_sim_assets/xmls/004_leg_1joint/main.xml"),
        help="MJCF",
    )
    p.add_argument("--timesteps", type=int, default=25_000, help="PPO 学習ステップ数")
    p.add_argument("--max-episode-steps", type=int, default=400, help="1 エピソード上限")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--no-check-env", action="store_true", help="check_env をスキップ")
    p.add_argument(
        "--ckpt",
        type=str,
        default="",
        help="学習後に保存するベース名（.zip は付けない）。空なら保存しない",
    )
    return p.parse_args()


class ForwardXOneActuatorEnv(gym.Env):
    """
    観測: ルート位置 (xyz)、ルート角速度+並進速度 (6)、股関節角・角速度 (2) = 11 次元。
    行動: 1 次元 [-1,1] → hip_servo の ctrlrange に線形マップ。
    報酬: **+X 方向の並進速度**（``qvel[3]``）を主にし、行動の二乗ペナルティを少量加える。
    終了: 高さが低すぎる（転倒）またはステップ上限。
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        xml_path: str,
        *,
        max_episode_steps: int = 400,
        reward_vx_scale: float = 1.0,
        reward_ctrl_penalty: float = 0.02,
        min_base_z: float = 0.6,
        rng: np.random.Generator | None = None,
    ) -> None:
        super().__init__()
        self._xml_path = str(Path(xml_path).resolve())
        self.model = mujoco.MjModel.from_xml_path(self._xml_path)
        self.data = mujoco.MjData(self.model)
        self._max_episode_steps = int(max_episode_steps)
        self._reward_vx_scale = float(reward_vx_scale)
        self._reward_ctrl_penalty = float(reward_ctrl_penalty)
        self._min_base_z = float(min_base_z)
        self._rng = rng if rng is not None else np.random.default_rng()

        self._root_qpos_adr = int(self.model.jnt_qposadr[0])
        self._root_dof_adr = int(self.model.jnt_dofadr[0])
        self._hip_qpos_adr = int(self.model.jnt_qposadr[1])
        self._hip_dof_adr = int(self.model.jnt_dofadr[1])

        cr = self.model.actuator_ctrlrange[0]
        self._ctrl_lo = float(cr[0])
        self._ctrl_hi = float(cr[1])

        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(11,), dtype=np.float64
        )
        self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(1,), dtype=np.float64)

        self._step_count = 0

    def _get_obs(self) -> np.ndarray:
        d = self.data
        rq = self._root_qpos_adr
        rd = self._root_dof_adr
        pos = d.qpos[rq + 4 : rq + 7].astype(np.float64)
        root_vel = d.qvel[rd : rd + 6].astype(np.float64)
        hip_q = float(d.qpos[self._hip_qpos_adr])
        hip_dq = float(d.qvel[self._hip_dof_adr])
        return np.concatenate([pos, root_vel, [hip_q, hip_dq]], dtype=np.float64)

    def reset(self, *, seed: int | None = None, options=None):
        super().reset(seed=seed)
        if seed is not None:
            self._rng = np.random.default_rng(seed)

        mujoco.mj_resetData(self.model, self.data)

        rq = self._root_qpos_adr
        rd = self._root_dof_adr
        # 初期高さ付近・水平に近い姿勢・小さな水平速度ノイズ
        self.data.qpos[rq + 0 : rq + 4] = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)
        self.data.qpos[rq + 4] = self._rng.uniform(-0.05, 0.05)
        self.data.qpos[rq + 5] = self._rng.uniform(-0.05, 0.05)
        self.data.qpos[rq + 6] = 2.0 + self._rng.uniform(-0.05, 0.05)
        self.data.qvel[rd : rd + 6] = self._rng.normal(0.0, 0.02, size=6)
        self.data.qpos[self._hip_qpos_adr] = self._rng.uniform(-0.1, 0.1)
        self.data.qvel[self._hip_dof_adr] = self._rng.uniform(-0.1, 0.1)
        self.data.ctrl[:] = 0.0

        mujoco.mj_forward(self.model, self.data)
        self._step_count = 0
        return self._get_obs(), {}

    def step(self, action: np.ndarray):
        a = np.clip(np.asarray(action, dtype=np.float64).reshape(-1), -1.0, 1.0)[0]
        u = 0.5 * (a + 1.0)  # [-1,1] -> [0,1]
        self.data.ctrl[0] = self._ctrl_lo + u * (self._ctrl_hi - self._ctrl_lo)

        mujoco.mj_step(self.model, self.data)
        vx_after = float(self.data.qvel[self._root_dof_adr + 3])

        # 前進（+X）を主報酬: ステップ直後の世界座標 X 方向並進速度
        reward = self._reward_vx_scale * vx_after
        reward -= self._reward_ctrl_penalty * float(a * a)

        self._step_count += 1
        z = float(self.data.qpos[self._root_qpos_adr + 6])
        fallen = z < self._min_base_z
        terminated = bool(fallen)
        truncated = self._step_count >= self._max_episode_steps

        return self._get_obs(), float(reward), terminated, truncated, {}


def main() -> None:
    args = _parse_args()
    rng = np.random.default_rng(args.seed)

    env = ForwardXOneActuatorEnv(
        args.xml,
        max_episode_steps=args.max_episode_steps,
        rng=rng,
    )
    if not args.no_check_env:
        check_env(env, warn=True)
    env = Monitor(env)

    model = PPO(
        "MlpPolicy",
        env,
        learning_rate=3e-4,
        n_steps=1024,
        batch_size=256,
        gamma=0.99,
        verbose=1,
        seed=args.seed,
    )
    model.learn(total_timesteps=int(args.timesteps), progress_bar=False)

    if args.ckpt.strip():
        base = args.ckpt.strip()
        model.save(base)
        print(f"[006] saved {base}.zip")

    # 学習直後の方策で数エピソード評価（平均報酬の目安）
    n_eval = 3
    ep_returns: list[float] = []
    raw = env.unwrapped
    assert isinstance(raw, ForwardXOneActuatorEnv)
    for _ in range(n_eval):
        obs, _ = raw.reset(seed=None)
        done = False
        G = 0.0
        while not done:
            act, _ = model.predict(obs, deterministic=True)
            obs, r, term, trunc, _ = raw.step(act)
            G += float(r)
            done = term or trunc
        ep_returns.append(G)
    print(
        f"[006] eval mean return ({n_eval} eps): "
        f"{float(np.mean(ep_returns)):.3f} (std {float(np.std(ep_returns)):.3f})"
    )


if __name__ == "__main__":
    main()
