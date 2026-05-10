import { getMujocoSimUrl } from "@/shared/constants";

export interface MujocoSimStateResponse {
  time: number;
  qpos: number[];
  qvel: number[];
  ctrl: Record<string, number>;
  hinge_joint_rad: Record<string, number>;
  sensors: Record<string, number[]>;
}

export type MujocoCtrlMode = "rad" | "deg";

async function readError(response: Response, fallback: string): Promise<string> {
  let detail = "";
  try {
    detail = await response.text();
  } catch {
    /* keep empty */
  }
  try {
    const j = JSON.parse(detail) as { error?: string };
    if (j.error) return j.error;
  } catch {
    /* keep text */
  }
  return detail || fallback;
}

export async function mujocoFetchState(): Promise<MujocoSimStateResponse> {
  const base = getMujocoSimUrl();
  const response = await fetch(`${base}/api/state`);
  if (!response.ok) {
    throw new Error(`MuJoCo state: HTTP ${response.status}`);
  }
  return (await response.json()) as MujocoSimStateResponse;
}

export interface MujocoSetServoResponse {
  status: "ok";
  actuator: string;
  rad: number;
  deg: number;
}

/**
 * mujoco-sim の `/api/set`（単一サーボ）を叩く。`robot-daemon` の `/set` と同型。
 *
 * シミュ本体の `mj_step` はサーバ側のスレッドが実時間で常時回しているため、
 * このエンドポイントは **目標角度（ctrl）の更新だけ** を行う。
 */
export async function mujocoSetServo(
  actuator: string,
  mode: MujocoCtrlMode,
  angle: number
): Promise<MujocoSetServoResponse> {
  const base = getMujocoSimUrl();
  const response = await fetch(`${base}/api/set`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ actuator, mode, angle }),
  });
  if (!response.ok) {
    const detail = await readError(response, `MuJoCo set: HTTP ${response.status}`);
    throw new Error(detail);
  }
  return (await response.json()) as MujocoSetServoResponse;
}

export interface MujocoSetServosResponse {
  status: "ok";
  applied: number;
}

/**
 * mujoco-sim の `/api/set_multiple`（複数サーボ）を叩く。`robot-daemon` の `/set_multiple` と同型。
 */
export async function mujocoSetServos(
  mode: MujocoCtrlMode,
  angles: Record<string, number>
): Promise<MujocoSetServosResponse> {
  const base = getMujocoSimUrl();
  const response = await fetch(`${base}/api/set_multiple`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode, angles }),
  });
  if (!response.ok) {
    const detail = await readError(response, `MuJoCo set_multiple: HTTP ${response.status}`);
    throw new Error(detail);
  }
  return (await response.json()) as MujocoSetServosResponse;
}
