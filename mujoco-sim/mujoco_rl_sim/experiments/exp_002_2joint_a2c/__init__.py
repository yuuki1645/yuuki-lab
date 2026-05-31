"""exp_002: 膝・足首 2 関節 A2C（model/main.xml）。

パッケージ外から import しやすいよう主要クラスを再エクスポートする。
学習のエントリポイントは train.main。
"""

from agent import AgentExp002A2C
from env import EnvExp0022JointA2C
from observation import ObsExp002, Observation

__all__ = ["AgentExp002A2C", "EnvExp0022JointA2C", "ObsExp002", "Observation"]
