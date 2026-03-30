import { SERVO_DAEMON_URL } from "@/shared/constants";
import { clamp } from "@/shared/utils";
import type { Servo, ServoMode } from "@/shared/types";

interface ServoApiResponse {
  name?: string;
  ch?: number;
  logical_lo?: number;
  logical_hi?: number;
  physical_min?: number;
  physical_max?: number;
  last_logical?: number;
  default_logical?: number;
  last_physical?: number;
  default_physical?: number;
}

interface ServosApiData {
  servos?: ServoApiResponse[];
}

/**
 * サーボ情報を取得
 */
export async function fetchServos(): Promise<Servo[]> {
  const response = await fetch(`${SERVO_DAEMON_URL}/servos`);

  if (!response.ok) {
    throw new Error("Failed to fetch servos");
  }

  const data = (await response.json()) as ServosApiData;
  const servosData = data.servos ?? [];

  const formattedServos: Servo[] = servosData.map((servo) => {
    const lo = servo.logical_lo ?? -90;
    const hi = servo.logical_hi ?? 90;
    const physMin = servo.physical_min ?? 0;
    const physMax = servo.physical_max ?? 180;
    const lastLogical = clamp(
      parseFloat(String(servo.last_logical ?? servo.default_logical ?? 0)),
      lo,
      hi
    );
    const lastPhysical = clamp(
      parseFloat(String(servo.last_physical ?? servo.default_physical ?? 90)),
      physMin,
      physMax
    );

    return {
      name: servo.name ?? "",
      ch: servo.ch ?? 0,
      logical_lo: lo,
      logical_hi: hi,
      physical_min: physMin,
      physical_max: physMax,
      last_logical: lastLogical,
      last_physical: lastPhysical,
    };
  });

  return formattedServos;
}

/**
 * サーボを動かす
 */
export async function moveServo(
  ch: number,
  mode: ServoMode,
  angle: number
): Promise<unknown> {
  const response = await fetch(`${SERVO_DAEMON_URL}/set`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      ch,
      mode,
      angle: parseFloat(String(angle)),
    }),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Server error: ${text}`);
  }

  return response.json();
}

/**
 * 複数のサーボを同時に動かす
 */
export async function moveServos(
  servoAngles: Record<number, number>,
  mode: ServoMode = "logical"
): Promise<unknown> {
  const angles: Record<string, number> = {};
  for (const [ch, angle] of Object.entries(servoAngles)) {
    angles[String(ch)] = parseFloat(String(angle));
  }

  const response = await fetch(`${SERVO_DAEMON_URL}/set_multiple`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      mode,
      angles,
    }),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Server error: ${text}`);
  }

  return response.json();
}

/**
 * 現在の角度から指定角度にゆっくり遷移させる
 */
export async function transitionServos(
  angles: Record<string, number>,
  mode: ServoMode = "logical",
  duration = 5.0
): Promise<unknown> {
  const response = await fetch(`${SERVO_DAEMON_URL}/transition`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      mode,
      angles,
      duration,
    }),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Server error: ${text}`);
  }

  return response.json();
}
