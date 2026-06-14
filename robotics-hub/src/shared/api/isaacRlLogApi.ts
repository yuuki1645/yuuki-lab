import { getIsaacRlLogApiUrl } from "@/shared/constants";
import type {
  IsaacRlLogHealth,
  IsaacRlLogRunMeta,
  IsaacRlLogRunsResponse,
  IsaacRlLogScalarsResponse,
} from "@/shared/types/isaacRlLog";

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

function baseUrl(override?: string): string {
  return (override ?? getIsaacRlLogApiUrl()).replace(/\/$/, "");
}

export async function isaacRlLogFetchHealth(apiBase?: string): Promise<IsaacRlLogHealth> {
  const response = await fetch(`${baseUrl(apiBase)}/api/health`);
  if (!response.ok) {
    throw new Error(await readError(response, `HTTP ${response.status}`));
  }
  return (await response.json()) as IsaacRlLogHealth;
}

export async function isaacRlLogFetchExperiments(apiBase?: string): Promise<string[]> {
  const response = await fetch(`${baseUrl(apiBase)}/api/experiments`);
  if (!response.ok) {
    throw new Error(await readError(response, `HTTP ${response.status}`));
  }
  const data = (await response.json()) as { experiments: string[] };
  return data.experiments ?? [];
}

export async function isaacRlLogFetchRuns(
  experiment: string,
  apiBase?: string
): Promise<IsaacRlLogRunsResponse> {
  const response = await fetch(`${baseUrl(apiBase)}/api/experiments/${encodeURIComponent(experiment)}/runs`);
  if (!response.ok) {
    throw new Error(await readError(response, `HTTP ${response.status}`));
  }
  return (await response.json()) as IsaacRlLogRunsResponse;
}

export async function isaacRlLogFetchScalars(
  experiment: string,
  runId: string,
  apiBase?: string
): Promise<IsaacRlLogScalarsResponse> {
  const response = await fetch(
    `${baseUrl(apiBase)}/api/experiments/${encodeURIComponent(experiment)}/runs/${encodeURIComponent(runId)}/scalars`
  );
  if (!response.ok) {
    throw new Error(await readError(response, `HTTP ${response.status}`));
  }
  return (await response.json()) as IsaacRlLogScalarsResponse;
}

export async function isaacRlLogFetchRunMeta(
  experiment: string,
  runId: string,
  apiBase?: string
): Promise<IsaacRlLogRunMeta> {
  const response = await fetch(
    `${baseUrl(apiBase)}/api/experiments/${encodeURIComponent(experiment)}/runs/${encodeURIComponent(runId)}/meta`
  );
  if (!response.ok) {
    throw new Error(await readError(response, `HTTP ${response.status}`));
  }
  return (await response.json()) as IsaacRlLogRunMeta;
}
