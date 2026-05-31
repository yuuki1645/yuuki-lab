"""exp_021 が採用する Hub / 観測契約（exp_020 と同一の biped_ppo_v1）。"""

from contract.biped_v1 import BIPED_PPO_V1

# 学習・テレメトリ・観測検証はすべてこの契約を参照する。
TELEMETRY_CONTRACT = BIPED_PPO_V1
