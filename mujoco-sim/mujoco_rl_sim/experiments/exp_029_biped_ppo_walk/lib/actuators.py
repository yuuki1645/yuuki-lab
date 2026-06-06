"""12 関節アクチュエータ名・対応ジョイント（model/main.xml と順序を一致）。

順序::
  [0:5]   左脚: hip_roll, hip_pitch, knee, ankle_pitch, ankle_roll
  [5:10]  右脚: 同上
  [10:12] 胴体: basket_top_roll, balance_pitch
"""

ACTUATOR_NAMES: tuple[str, ...] = (
  "left_hip_roll_motor",
  "left_hip_pitch_motor",
  "left_knee_pitch_motor",
  "left_ankle_pitch_motor",
  "left_ankle_roll_motor",
  "right_hip_roll_motor",
  "right_hip_pitch_motor",
  "right_knee_pitch_motor",
  "right_ankle_pitch_motor",
  "right_ankle_roll_motor",
  "basket_top_roll_motor",
  "balance_pitch_motor",
)

JOINT_NAMES: tuple[str, ...] = tuple(
  name.replace("_motor", "") for name in ACTUATOR_NAMES
)

LEFT_JOINT_SLICE = slice(0, 5)
RIGHT_JOINT_SLICE = slice(5, 10)
TORSO_JOINT_SLICE = slice(10, 12)

LEFT_FOOT_GEOM = "foot_plate"
RIGHT_FOOT_GEOM = "right_foot_plate"
LEFT_FOOT_SITE = "foot_site"
RIGHT_FOOT_SITE = "right_foot_site"

THIGH_GEOM_IDS = ("thigh_link", "right_thigh_link")
SHANK_GEOM_IDS = ("shank_link", "right_shin_link")
