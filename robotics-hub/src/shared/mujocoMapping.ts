import type { Servo } from "@/shared/types";
import { CH_TO_SERVO_NAME, SERVO_CHANNELS } from "@/shared/constants";
import type { MujocoSimStateResponse } from "@/shared/api/mujocoSimApi";

/** サーボ名（L_HIP1 等）→ MJCF のヒンジ関節名（シミュの hinge_joint_rad のキー） */
export const SERVO_NAME_TO_MUJOCO_JOINT: Record<string, string> = {
  L_HIP1: "left_hip_roll",
  L_HIP2: "left_hip_pitch",
  L_KNEE: "left_knee_pitch",
  L_HEEL: "left_ankle_pitch",
  L_HEEL_ROLL: "left_ankle_roll",
  R_HIP1: "right_hip_roll",
  R_HIP2: "right_hip_pitch",
  R_KNEE: "right_knee_pitch",
  R_HEEL: "right_ankle_pitch",
  R_HEEL_ROLL: "right_ankle_roll",
};

/** サーボ名 → position アクチュエータ名（mujoco-sim の /api/set / /api/set_multiple のキー） */
export const SERVO_NAME_TO_MUJOCO_ACTUATOR: Record<string, string> = {
  L_HIP1: "left_hip_roll_motor",
  L_HIP2: "left_hip_pitch_motor",
  L_KNEE: "left_knee_pitch_motor",
  L_HEEL: "left_ankle_pitch_motor",
  L_HEEL_ROLL: "left_ankle_roll_motor",
  R_HIP1: "right_hip_roll_motor",
  R_HIP2: "right_hip_pitch_motor",
  R_KNEE: "right_knee_pitch_motor",
  R_HEEL: "right_ankle_pitch_motor",
  R_HEEL_ROLL: "right_ankle_roll_motor",
};

export function logicalDegreesToRadians(deg: number): number {
  return (deg * Math.PI) / 180;
}

export function radiansToLogicalDegrees(rad: number): number {
  return Math.round((rad * 180) / Math.PI);
}

/**
 * mujoco-sim の /api/state を useServos 互換の Servo 配列に変換する。
 *
 * サーバ側 kinematics で計算済みの ``logical_deg`` を最優先で使う（論理角）。
 * もし古いサーバや欠損などで取れなかった場合は、フォールバックとして
 * ``hinge_joint_rad`` を度に直した値（=MuJoCo 関節角の度表現）を使う。
 */
export function servosFromMujocoState(state: MujocoSimStateResponse): Servo[] {
  const logical = state.logical_deg ?? {};
  const hinge = state.hinge_joint_rad ?? {};
  const list: Servo[] = [];
  for (const ch of SERVO_CHANNELS) {
    const name = CH_TO_SERVO_NAME[ch];
    if (!name) continue;
    const actuator = SERVO_NAME_TO_MUJOCO_ACTUATOR[name];
    const jointName = SERVO_NAME_TO_MUJOCO_JOINT[name];

    let last_logical = 0;
    if (actuator !== undefined && logical[actuator] !== undefined) {
      last_logical = Math.round(logical[actuator]);
    } else if (jointName !== undefined && hinge[jointName] !== undefined) {
      last_logical = radiansToLogicalDegrees(hinge[jointName]);
    }

    list.push({
      name,
      ch,
      logical_lo: -90,
      logical_hi: 90,
      physical_min: 0,
      physical_max: 180,
      last_logical,
      last_physical: 90,
    });
  }
  return list;
}
