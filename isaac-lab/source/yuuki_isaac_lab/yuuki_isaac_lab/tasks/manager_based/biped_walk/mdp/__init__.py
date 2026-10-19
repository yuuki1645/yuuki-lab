"""歩行タスクの MDP。"""

from .feet import foot_corner_kg
from .observations import command_forward_and_yaw, root_height
from .phase import FORWARD_SPEED_MPS, PERIOD_S, phase_sincos
from .rewards import (
    feet_apart,
    heel_to_toe,
    penalize_slide_and_yaw,
    stance_contact,
    swing_knee,
    track_forward_progress,
    upright,
)

__all__ = [
    "FORWARD_SPEED_MPS",
    "PERIOD_S",
    "command_forward_and_yaw",
    "feet_apart",
    "foot_corner_kg",
    "heel_to_toe",
    "penalize_slide_and_yaw",
    "phase_sincos",
    "root_height",
    "stance_contact",
    "swing_knee",
    "track_forward_progress",
    "upright",
]
