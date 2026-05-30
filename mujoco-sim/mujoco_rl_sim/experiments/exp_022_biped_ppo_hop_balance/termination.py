"""両脚バイペッド向け早期終了（姿勢のみ。contact 走査なし）。"""

from dataclasses import dataclass

import mujoco

REASON_TRUNCATED = "truncated"
REASON_IMU_Z = "imu_z"
REASON_LOW_UPRIGHT = "low_upright"
REASON_BACKWARD_LEAN = "backward_lean"

# MuJoCo の位置/ベクトルは [x, y, z] の順で格納される。
WORLD_X = 0
WORLD_Z = 2

TERMINATION_REASONS = (
  REASON_TRUNCATED,
  REASON_IMU_Z,
  REASON_LOW_UPRIGHT,
  REASON_BACKWARD_LEAN,
)


@dataclass(frozen=True)
class TerminationOutcome:
  reason: str | None
  penalty: float

  @property
  def terminated(self) -> bool:
    return self.reason is not None


NOT_TERMINATED = TerminationOutcome(None, 0.0)


class Termination:
  def done_reason_pose(self, data: mujoco.MjData) -> TerminationOutcome:
    # ここだけ読めば「何を見て、どの閾値で落とすか」が分かるようにする。

    # imu_site の世界 Z [m]。これ未満で転倒終了（低すぎ＝しゃがみすぎ／倒れ）。
    MIN_IMU_Z = 0.40
    # imu_zaxis の Z 成分（上向き成分）。1 に近いほど直立。これ未満で姿勢不良終了。
    MIN_IMU_UPRIGHT = 0.52
    # imu_zaxis の X 成分の後傾限界。imu_zaxis_x < -MAX_BACKWARD_LEAN で後ろ倒れ終了。
    MAX_BACKWARD_LEAN = 0.38
    # 上記いずれかの理由でエピソード終了したときに報酬へ加算するペナルティ。
    POSE_TERMINATION_PENALTY = -30.0

    imu_z = float(data.site("imu_site").xpos[WORLD_Z])
    imu_zaxis = data.sensor("imu_zaxis").data
    upright = float(imu_zaxis[WORLD_Z])
    imu_zaxis_x = float(imu_zaxis[WORLD_X])

    if imu_z < MIN_IMU_Z:
      return TerminationOutcome(REASON_IMU_Z, POSE_TERMINATION_PENALTY)

    if upright < MIN_IMU_UPRIGHT:
      return TerminationOutcome(REASON_LOW_UPRIGHT, POSE_TERMINATION_PENALTY)

    if imu_zaxis_x < -MAX_BACKWARD_LEAN:
      return TerminationOutcome(REASON_BACKWARD_LEAN, POSE_TERMINATION_PENALTY)

    return NOT_TERMINATED
