"""exp_005: 膝・足首 2 関節 PPO + exp_004 同一の観測・報酬 shaping（model/main.xml）。

パッケージ外から import しやすいよう主要クラスを再エクスポートする。
学習のエントリポイントは train.main。
"""

from agent import AgentPPO
from env import Env2JointPPO
from observation import PolicyObs, Observation

__all__ = ["AgentPPO", "Env2JointPPO", "PolicyObs", "Observation"]
