import type { Servo } from "@/shared/types";
import type { JointKey, LegId, LegPose } from "./poseEditorTypes";

const SERVO_SUFFIX: Record<JointKey, string> = {
  hip1: "HIP1",
  hip2: "HIP2",
  knee: "KNEE",
  heel: "HEEL",
  heelRoll: "HEEL_ROLL",
};

export function servoName(leg: LegId, key: JointKey): string {
  return `${leg}_${SERVO_SUFFIX[key]}`;
}

export function readLegFromServos(servos: Servo[], leg: LegId): LegPose {
  const get = (k: JointKey) => {
    const name = servoName(leg, k);
    const s = servos.find((x) => x.name === name);
    return s ? Math.round(s.last_logical) : 0;
  };
  return {
    hip1: get("hip1"),
    hip2: get("hip2"),
    knee: get("knee"),
    heel: get("heel"),
    heelRoll: get("heelRoll"),
  };
}

export function limitsFor(servos: Servo[], leg: LegId, key: JointKey) {
  const name = servoName(leg, key);
  const s = servos.find((x) => x.name === name);
  return {
    lo: s?.logical_lo ?? -90,
    hi: s?.logical_hi ?? 90,
  };
}
