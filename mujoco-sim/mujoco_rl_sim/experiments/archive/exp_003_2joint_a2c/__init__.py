"""exp_003: 膝・足首 2 関節 A2C（model/main.xml）。

パッケージ外から import しやすいよう主要クラスを再エクスポートする。
学習のエントリポイントは train.main。
"""

from agent import AgentA2C
from env import Env2JointA2C
from observation import PolicyObs, Observation

__all__ = ["AgentA2C", "Env2JointA2C", "PolicyObs", "Observation"]
