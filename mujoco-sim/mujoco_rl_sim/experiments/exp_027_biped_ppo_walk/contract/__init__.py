"""観測・報酬ログ・Hub テレメトリの契約（単一ソース）。"""

from contract.biped_v1 import BIPED_PPO_V1
from contract.biped_walk_v1 import BIPED_WALK_V1
from contract.session import PpoTrainBindings, run_ppo_train
from contract.spec import (
  ObservationSlice,
  ObservationSpec,
  RewardLogTerm,
  RewardLogSpec,
  TelemetryContract,
)
from contract.telemetry import build_reset_payload, build_step_payload
from contract.validate import assert_obs_vector, validate_obs_vector

__all__ = [
  "BIPED_PPO_V1",
  "BIPED_WALK_V1",
  "ObservationSlice",
  "ObservationSpec",
  "PpoTrainBindings",
  "RewardLogTerm",
  "RewardLogSpec",
  "TelemetryContract",
  "assert_obs_vector",
  "build_reset_payload",
  "build_step_payload",
  "run_ppo_train",
  "validate_obs_vector",
]
