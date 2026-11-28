/** Turn a failed apiRequest into the text worth showing. */

import { L } from "./labels";

export function errorText(err: unknown): string {
  const text = err instanceof Error ? err.message : String(err);
  try {
    const parsed = JSON.parse(text) as { detail?: string };
    if (typeof parsed.detail === "string") return parsed.detail;
  } catch {
    /* Response body was not JSON. */
  }
  return text || L.loading;
}

/** True for a fetch cancelled on purpose (view changed, page left). */
export function isAbort(err: unknown): boolean {
  return err instanceof DOMException && err.name === "AbortError";
}
