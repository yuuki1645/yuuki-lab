"""一定速度の指令に、エピソードで前へ進んだ距離の記録を足す。

距離は報酬に入れない。学習の式は変えない。W&B の
Metrics/base_velocity/forward_distance_m で、立っているだけなら 0 m 付近、
0.1 m/s を 10 秒維持すれば約 1 m になる。
"""

from __future__ import annotations

from collections.abc import Sequence

import torch

from isaaclab.envs.mdp.commands.velocity_command import UniformVelocityCommand


class SlowWalkVelocityCommand(UniformVelocityCommand):
    """世界の +x へ進んだ正味の距離を、エピソードごとに残す。"""

    def __init__(self, cfg, env):
        super().__init__(cfg, env)
        # 親の reset が metrics を平均してログする。ここに足すと Metrics に出る。
        self.metrics["forward_distance_m"] = torch.zeros(self.num_envs, device=self.device)
        self._forward_sum = torch.zeros(self.num_envs, device=self.device)
        self._prev_x = torch.zeros(self.num_envs, device=self.device)
        # 最初の1歩と、出現位置へ戻した直後は、差分を距離に足さない。
        self._have_prev = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)

    def _update_metrics(self):
        super()._update_metrics()
        # シーンのリセットより前に毎歩足す。リセット時にはカゴが出現位置へ戻っている。
        x = self.robot.data.root_pos_w.torch[:, 0]
        delta = x - self._prev_x
        self._forward_sum += torch.where(self._have_prev, delta, torch.zeros_like(delta))
        self._prev_x = x.detach()
        self._have_prev[:] = True

    def reset(self, env_ids: Sequence[int] | None = None) -> dict[str, float]:
        if env_ids is None:
            env_ids = slice(None)
        # 親は metrics を読んでから 0 にする。距離は読む前に入れておく。
        self.metrics["forward_distance_m"][env_ids] = self._forward_sum[env_ids]
        extras = super().reset(env_ids)
        self._forward_sum[env_ids] = 0.0
        # カゴはすでに出現位置。次の差分はこの位置から測る。
        self._prev_x[env_ids] = self.robot.data.root_pos_w.torch[env_ids, 0]
        self._have_prev[env_ids] = True
        return extras
