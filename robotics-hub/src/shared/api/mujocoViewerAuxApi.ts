import { getMujocoViewerAuxUrl } from "@/shared/constants";

export type ViewerAuxDetail = "minimal" | "standard" | "full";

export interface ViewerAuxStatus {
  xml_path: string;
  sim_time: number;
  timestep: number;
  step_count: number;
  paused: boolean;
  speed: number;
  viewer_open: boolean;
}

export interface ViewerAuxBodyRow {
  id: number;
  name: string;
  xpos: number[];
  xquat: number[];
  cvel: number[];
}

export interface ViewerAuxJointRow {
  id: number;
  name: string;
  type: string;
  qpos_adr: number;
  dof_adr: number;
  qpos: number[];
  qvel: number[];
}

export interface ViewerAuxContactRow {
  dist: number;
  pos: number[];
  geom1: number;
  geom2: number;
  geom1_name: string;
  geom2_name: string;
}

export interface ViewerAuxSnapshot {
  xml_path: string;
  sim_time: number;
  timestep: number;
  step_count: number;
  paused: boolean;
  speed: number;
  nq: number;
  nv: number;
  nu: number;
  nbody: number;
  njnt: number;
  ngeom: number;
  nsite: number;
  ncon: number;
  qpos: number[];
  qvel: number[];
  ctrl: number[];
  act: number[];
  bodies?: ViewerAuxBodyRow[];
  joints?: ViewerAuxJointRow[];
  actuator_names?: string[];
  qfrc_actuator?: number[];
  geoms?: Array<{
    id: number;
    name: string;
    body: number;
    xpos: number[];
    xmat: number[];
  }>;
  sites?: Array<{
    id: number;
    name: string;
    body: number;
    xpos: number[];
    xmat: number[];
  }>;
  contacts?: ViewerAuxContactRow[];
  sensors?: Record<string, number[]>;
}

export interface ViewerAuxVisFlagMeta {
  name: string;
  index: number;
  on: number;
}

export interface ViewerAuxDisplayState {
  vis_flags: ViewerAuxVisFlagMeta[];
  frame: number;
  frame_name: string;
  label: number;
  label_name: string;
  frame_choices: string[];
  label_choices: string[];
  vis_flag_names: string[];
}

function base(): string {
  return getMujocoViewerAuxUrl().replace(/\/$/, "");
}

async function readErr(res: Response, fb: string): Promise<string> {
  let t = "";
  try {
    t = await res.text();
  } catch {
    /* */
  }
  return t || fb;
}

export async function viewerAuxFetchHealth(customBase?: string): Promise<{ status: string; role?: string }> {
  const b = (customBase ?? base()).replace(/\/$/, "");
  const res = await fetch(`${b}/health`);
  if (!res.ok) throw new Error(await readErr(res, `health HTTP ${res.status}`));
  return (await res.json()) as { status: string; role?: string };
}

export async function viewerAuxFetchStatus(customBase?: string): Promise<ViewerAuxStatus> {
  const b = (customBase ?? base()).replace(/\/$/, "");
  const res = await fetch(`${b}/api/viewer/status`);
  if (!res.ok) throw new Error(await readErr(res, `status HTTP ${res.status}`));
  return (await res.json()) as ViewerAuxStatus;
}

export async function viewerAuxFetchSnapshot(
  detail: ViewerAuxDetail = "standard",
  customBase?: string
): Promise<ViewerAuxSnapshot> {
  const b = (customBase ?? base()).replace(/\/$/, "");
  const u = new URL(`${b}/api/viewer/snapshot`);
  u.searchParams.set("detail", detail);
  const res = await fetch(u.toString());
  if (!res.ok) throw new Error(await readErr(res, `snapshot HTTP ${res.status}`));
  return (await res.json()) as ViewerAuxSnapshot;
}

export async function viewerAuxFetchDisplay(customBase?: string): Promise<ViewerAuxDisplayState> {
  const b = (customBase ?? base()).replace(/\/$/, "");
  const res = await fetch(`${b}/api/viewer/display`);
  if (!res.ok) throw new Error(await readErr(res, `display HTTP ${res.status}`));
  return (await res.json()) as ViewerAuxDisplayState;
}

export async function viewerAuxPostControl(
  action:
    | "play"
    | "pause"
    | "stop"
    | "reset"
    | "restart"
    | "step_once"
    | "set_speed",
  opts?: { value?: number },
  customBase?: string
): Promise<{ status: string; action?: string }> {
  const b = (customBase ?? base()).replace(/\/$/, "");
  const body: Record<string, unknown> = { action };
  if (opts?.value !== undefined) body.value = opts.value;
  const res = await fetch(`${b}/api/viewer/control`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await readErr(res, `control HTTP ${res.status}`));
  return (await res.json()) as { status: string; action?: string };
}

export async function viewerAuxPostDisplay(
  patch: {
    vis_flag?: Record<string, boolean>;
    frame?: string;
    label?: string;
  },
  customBase?: string
): Promise<{ status: string }> {
  const b = (customBase ?? base()).replace(/\/$/, "");
  const res = await fetch(`${b}/api/viewer/display`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!res.ok) throw new Error(await readErr(res, `display POST HTTP ${res.status}`));
  return (await res.json()) as { status: string };
}
