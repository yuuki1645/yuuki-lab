import { CH_TO_SERVO_NAME } from "@/shared/constants";
import { SERVO_NAME_TO_MUJOCO_ACTUATOR } from "@/shared/mujocoMapping";
import type { ServoBackendMode, ServoMode } from "@/shared/types";
import { mujocoSetServos } from "./mujocoSimApi";
import { moveServos } from "./servoApi";

export function mapChannelAnglesToMujocoActuators(
  servoAngles: Record<number, number>
): Record<string, number> {
  const angles: Record<string, number> = {};
  for (const [ch, angle] of Object.entries(servoAngles)) {
    const servoName = CH_TO_SERVO_NAME[Number(ch)];
    if (!servoName) continue;
    const actuator = SERVO_NAME_TO_MUJOCO_ACTUATOR[servoName];
    if (!actuator) continue;
    angles[actuator] = angle;
  }
  return angles;
}

export async function moveServosToBackend(
  backendMode: ServoBackendMode,
  servoAngles: Record<number, number>,
  mode: ServoMode = "logical"
): Promise<unknown> {
  if (backendMode === "daemon") {
    return moveServos(servoAngles, mode);
  }

  if (mode !== "logical") {
    throw new Error("MuJoCo backend supports logical motion angles only");
  }

  const angles = mapChannelAnglesToMujocoActuators(servoAngles);
  if (Object.keys(angles).length === 0) {
    return { status: "ok", applied: 0 };
  }
  return mujocoSetServos("logical", angles);
}
