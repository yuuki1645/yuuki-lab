from mujoco_rl_sim.experiments.exp_002_2joint_a2c import config

# done_reason / wandb 用の終了理由ラベル
REASON_IMU_Z = "imu_z"  # IMU 高さが下限を下回った（しゃがみ／倒れ込み）
REASON_LOW_UPRIGHT = "low_upright"  # 体軸が鉛直から大きく外れた（横倒しなど）
REASON_BACKWARD_LEAN = "backward_lean"  # 後傾しすぎ（−X 方向へ倒れ）
REASON_TRUNCATED = "truncated"  # 最大ステップ到達（train.py で判定。本クラスでは未使用）

TERMINATION_REASONS = (
  REASON_IMU_Z,
  REASON_LOW_UPRIGHT,
  REASON_BACKWARD_LEAN,
  REASON_TRUNCATED,
)


class Termination:
  """エピソード早期終了（転倒・姿勢崩れ）の判定。

  入力は observation.ObservationRaw と同じ物理量:
    - imu_z       : imu_site のワールド Z 座標 [m]（低いほどしゃがみ／倒れ）
    - upright     : imu_zaxis の Z 成分（= imu_zaxis_z）。1 に近いほど直立
    - imu_zaxis_x : imu 体軸のワールド X 成分。負 = 後方向（−x）へ傾いている

  下記のいずれかを満たしたステップで terminated=True（env.step）。
  最大ステップによる打ち切りは train.py 側（REASON_TRUNCATED）。
  """

  def done_reason(
    self,
    *,
    imu_z: float,
    upright: float,
    imu_zaxis_x: float,
  ) -> str | None:
    """最初に満たした終了条件の識別子。終了しない場合は None。

    判定は上から順に評価し、複数条件を同時に満たしても先頭の理由のみ返す。
    """
    # (1) 高さ低下: IMU が地面近くまで落ちた → 転倒・しゃがみ込みとみなす
    if imu_z < config.MIN_IMU_Z:  # 既定 0.42 m
      return REASON_IMU_Z

    # (2) 直立度不足: 体軸が鉛直から外れすぎ → 横倒し・大きな傾きなど
    if upright < config.MIN_IMU_UPRIGHT:  # 既定 0.55（1=完全直立）
      return REASON_LOW_UPRIGHT

    # (3) 後傾過多: 体軸の X 成分が -MAX より小さい（より負）→ 後ろに倒れすぎ
    if imu_zaxis_x < -config.MAX_BACKWARD_LEAN:  # 既定 -0.40 未満で終了
      return REASON_BACKWARD_LEAN

    return None

  def is_done(
    self,
    *,
    imu_z: float,
    upright: float,
    imu_zaxis_x: float,
  ) -> bool:
    return self.done_reason(
      imu_z=imu_z,
      upright=upright,
      imu_zaxis_x=imu_zaxis_x,
    ) is not None
