/**
 * ATOM 接続 PC（lab_debug :8794）上の本記録 REST。
 * ブラウザはディスクを直接触れないので、この API 経由で一覧・配信・メモ編集する。
 */
import { getM5TelemetrySocketUrl } from "@/shared/constants";
import type { M5Frame, M5RecordDetail, M5RecordMeta, M5RecordStatus } from "./types";

function recordBaseUrl(): string {
  return getM5TelemetrySocketUrl().replace(/\/$/, "");
}

async function readError(response: Response, fallback: string): Promise<string> {
  let text = "";
  try {
    text = await response.text();
  } catch {
    /* keep empty */
  }
  try {
    const j = JSON.parse(text) as { error?: string; message?: string };
    if (typeof j.error === "string" && j.error) return j.error;
    if (typeof j.message === "string" && j.message) return j.message;
  } catch {
    /* keep text */
  }
  return text || fallback;
}

async function recordFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(recordBaseUrl() + path, {
    cache: "no-store",
    ...init,
  });
  if (!response.ok) {
    throw new Error(await readError(response, `HTTP ${response.status}`));
  }
  return (await response.json()) as T;
}

export async function fetchRecordStatus(): Promise<M5RecordStatus> {
  return recordFetch<M5RecordStatus>("/api/m5/record/status");
}

export async function fetchRecordings(): Promise<M5RecordMeta[]> {
  const data = await recordFetch<{ recordings: M5RecordMeta[] }>("/api/m5/recordings");
  return Array.isArray(data.recordings) ? data.recordings : [];
}

export async function fetchRecording(id: string): Promise<M5RecordDetail> {
  return recordFetch<M5RecordDetail>(`/api/m5/recordings/${encodeURIComponent(id)}`);
}

export async function fetchRecordingFrames(
  id: string,
  offset: number,
  limit: number
): Promise<{ frames: M5Frame[]; total: number; offset: number }> {
  const q = `offset=${offset}&limit=${limit}`;
  return recordFetch(`/api/m5/recordings/${encodeURIComponent(id)}/frames?${q}`);
}

/** 全サンプルをチャンクで読む。長い take でも iPad が一度に食わないようにする。 */
export async function fetchAllRecordingFrames(
  id: string,
  onProgress?: (loaded: number, total: number) => void
): Promise<M5Frame[]> {
  const chunk = 4000;
  const out: M5Frame[] = [];
  let offset = 0;
  let total = Infinity;
  while (offset < total) {
    const part = await fetchRecordingFrames(id, offset, chunk);
    total = part.total;
    if (!part.frames.length) break;
    out.push(...part.frames);
    offset += part.frames.length;
    onProgress?.(out.length, total);
    if (part.frames.length < chunk) break;
  }
  return out;
}

export async function patchRecording(
  id: string,
  body: { name?: string; notes?: string }
): Promise<M5RecordMeta> {
  return recordFetch<M5RecordMeta>(`/api/m5/recordings/${encodeURIComponent(id)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function deleteRecording(id: string): Promise<void> {
  await recordFetch(`/api/m5/recordings/${encodeURIComponent(id)}`, { method: "DELETE" });
}
