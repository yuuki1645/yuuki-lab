"""直立 170 cm の全身ヒューマノイドの寸法。

既存のカゴ・アルミ板・RDS51150 の配置は使わない。ここがこの機体の正本である。
身長の配分は、成人の肢節比に近い長さをこのロボット用に決めたもので、
実在の金具を測った値ではない。

座標系は x が前、y が左、z が上。原点は両足のあいだの床面。
全関節 0 は、脚を伸ばし、腕を体側へ下ろした直立。
"""

from __future__ import annotations

# 足裏から頭頂まで。この値に縦の寸法を合わせる。
STATURE_M = 1.700

# 足。長さは前後、幅は左右。中心は足首より少し前（正がつま先）。
FOOT_LENGTH_M = 0.260
FOOT_WIDTH_M = 0.100
FOOT_THICKNESS_M = 0.020
FOOT_CENTER_X_M = 0.040

# 床から関節中心まで。下腿と大腿は、人間の身長比 24〜25 % に近い 42 cm。
ANKLE_Z_M = 0.080
SHIN_M = 0.420
THIGH_M = 0.420
HIP_Z_M = ANKLE_Z_M + SHIN_M + THIGH_M
KNEE_Z_M = ANKLE_Z_M + SHIN_M

# 左右の股関節。骨盤の内側に置く。
HIP_Y_M = 0.100

# 胴。肩関節は天面より少し下で、腕が胴にめり込まない位置。
NECK_LENGTH_M = 0.080
HEAD_RADIUS_M = 0.090
# 球の頭頂が STATURE_M になるよう、首の上端を先に決める。
NECK_TOP_Z_M = STATURE_M - 2.0 * HEAD_RADIUS_M
TORSO_TOP_Z_M = NECK_TOP_Z_M - NECK_LENGTH_M
SHOULDER_Z_M = TORSO_TOP_Z_M - 0.040
SHOULDER_Y_M = 0.230

TORSO_SIZE_M = (0.220, 0.360, 0.460)
# 胴の下端が骨盤に 20 mm 入る。天面は首の付け根。
TORSO_CENTER_Z_M = TORSO_TOP_Z_M - TORSO_SIZE_M[2] / 2.0
PELVIS_SIZE_M = (0.200, 0.320, 0.160)

# 腕。肩から肘、肘から手首。手はその先へ下へ伸びる。
UPPER_ARM_M = 0.310
FOREARM_M = 0.180
HAND_SIZE_M = (0.080, 0.080, 0.100)
ELBOW_Z_M = SHOULDER_Z_M - UPPER_ARM_M
WRIST_Z_M = ELBOW_Z_M - FOREARM_M

# 関節ハウジング（円柱）。半径、軸方向の長さ。
HIP_JOINT_M = (0.055, 0.100)
KNEE_JOINT_M = (0.055, 0.090)
ANKLE_JOINT_M = (0.042, 0.080)
SHOULDER_JOINT_M = (0.050, 0.080)
ELBOW_JOINT_M = (0.040, 0.070)

# 肢の円柱半径。関節より細くして、ハウジングが外から見えるようにする。
THIGH_RADIUS_M = 0.060
SHIN_RADIUS_M = 0.045
ANKLE_POST_RADIUS_M = 0.030
UPPER_ARM_RADIUS_M = 0.040
FOREARM_RADIUS_M = 0.032
NECK_RADIUS_M = 0.045

# 見た目用。寸法には影響しない。RGBA。
COLOR_PELVIS = (0.22, 0.24, 0.28, 1.0)
COLOR_TORSO = (0.84, 0.86, 0.88, 1.0)
COLOR_LIMB = (0.55, 0.58, 0.62, 1.0)
COLOR_JOINT = (0.72, 0.20, 0.16, 1.0)
COLOR_HEAD = (0.93, 0.93, 0.90, 1.0)
COLOR_VISOR = (0.16, 0.45, 0.72, 1.0)
COLOR_FOOT = (0.12, 0.12, 0.13, 1.0)
COLOR_HAND = (0.18, 0.20, 0.22, 1.0)


def assert_consistent() -> None:
    """縦の足し算が身長と一致し、腕が床や胴に入らないことを確かめる。"""
    crown = NECK_TOP_Z_M + 2.0 * HEAD_RADIUS_M
    if abs(crown - STATURE_M) > 1.0e-12:
        raise RuntimeError(f"頭頂が身長と違います: {crown} と {STATURE_M}")
    torso_top = TORSO_CENTER_Z_M + TORSO_SIZE_M[2] / 2.0
    if abs(torso_top - TORSO_TOP_Z_M) > 1.0e-12:
        raise RuntimeError("胴の天面が首の付け根と一致しません")
    # 骨盤の上端が胴の下端より上なら、胴は骨盤に乗っている。
    pelvis_top = HIP_Z_M + PELVIS_SIZE_M[2] / 2.0
    torso_bottom = TORSO_CENTER_Z_M - TORSO_SIZE_M[2] / 2.0
    if pelvis_top <= torso_bottom:
        raise RuntimeError("胴が骨盤から離れています")
    hand_bottom = WRIST_Z_M - HAND_SIZE_M[2]
    if hand_bottom <= 0.0:
        raise RuntimeError("下ろした手が床に触れます")
    # 上腕の内側が胴の側面より外にあること。
    arm_inner = SHOULDER_Y_M - UPPER_ARM_RADIUS_M
    torso_outer = TORSO_SIZE_M[1] / 2.0
    if arm_inner <= torso_outer:
        raise RuntimeError("腕が胴に入ります")
    if HIP_Z_M <= KNEE_Z_M:
        raise RuntimeError("膝が股より上に来ています")


assert_consistent()
