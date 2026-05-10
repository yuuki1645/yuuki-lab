import { getMujocoSimUrl } from "@/shared/constants";

export interface MujocoSimStateResponse {
  time: number;
  qpos: number[];
  qvel: number[];
  ctrl: Record<string, number>;
  hinge_joint_rad: Record<string, number>;
  sensors: Record<string, number[]>;
}

export async function mujocoFetchState(): Promise<MujocoSimStateResponse> {
  const base = getMujocoSimUrl();
  const response = await fetch(`${base}/api/state`);
  if (!response.ok) {
    throw new Error(`MuJoCo state: HTTP ${response.status}`);
  }
  return (await response.json()) as MujocoSimStateResponse;
}

/**
 * mujoco-sim の `/api/step` を叩く。
 *
 * `mode` を `"deg"` にすると、`ctrl` の値はサーバー側で度→ラジアンに換算される。
 * 省略時 (`"rad"`) は MuJoCo ネイティブの単位そのまま。
 * ログを度のままで残したいときに `"deg"` を使う。
 */
export async function mujocoPostStep(body: {
  n: number;
  mode?: "rad" | "deg";
  ctrl?: Record<string, number>;
}): Promise<MujocoSimStateResponse> {
  const base = getMujocoSimUrl();
  const response = await fetch(`${base}/api/step`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    let detail = await response.text();
    try {
      const j = (await response.json()) as { error?: string };
      if (j.error) detail = j.error;
    } catch {
      /* keep text */
    }
    throw new Error(detail || `MuJoCo step: HTTP ${response.status}`);
  }
  return (await response.json()) as MujocoSimStateResponse;
}
