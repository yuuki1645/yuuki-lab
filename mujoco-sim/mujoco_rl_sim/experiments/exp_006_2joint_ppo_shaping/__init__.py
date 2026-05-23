"""exp_006: 膝・足首 2 関節 PPO + exp_005 ベースの足底幾何観測（model/main.xml）。

パッケージ外から import しやすいよう主要クラスを再エクスポートする。
学習のエントリポイントは train.main。
"""

from .agent import AgentPPO
from .env import Env2JointPPO
from .observation import PolicyObs, Observation

__all__ = ["AgentPPO", "Env2JointPPO", "PolicyObs", "Observation"]
