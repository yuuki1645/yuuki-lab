"""exp_008: 片脚（モノポッド）ホッパ PPO + 足底幾何観測。

【重要】この実験は両脚歩行（バイペッド）ではない。
  - 脚は物理的に 1 本（knee + ankle の 2 関節 = 「2joint」の意味）
  - タスク: ホッピング（立脚 → 飛翔 → 着地）
  - 詳細: README.md / AGENTS.md

学習のエントリポイントは train.main。
"""

from .agent import AgentPPO
from .env import Env2JointPPO
from .observation import PolicyObs, Observation

__all__ = ["AgentPPO", "Env2JointPPO", "PolicyObs", "Observation"]
