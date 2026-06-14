/** Isaac Lab RSL-RL TensorBoard ログ API の型定義 */

export interface IsaacRlLogAccessUrls {
  port: number;
  localhost: string;
  lan: string[];
  tailscale: string | null;
  tailscale_ip: string | null;
}

export interface IsaacRlLogHealth {
  status: string;
  log_root: string;
  log_root_exists: boolean;
  access_urls?: IsaacRlLogAccessUrls;
}

export interface IsaacRlLogRunSummary {
  id: string;
  mtime: number;
  mtime_iso: string;
  latest_iteration: number | null;
  has_events: boolean;
  checkpoints: string[];
}

export interface IsaacRlLogRunsResponse {
  experiment: string;
  runs: IsaacRlLogRunSummary[];
}

export interface IsaacRlLogScalarPoint {
  step: number;
  value: number;
  wall_time: number;
}

export interface IsaacRlLogScalarsResponse {
  experiment: string;
  run_id: string;
  latest_iteration: number | null;
  events_mtime: number | null;
  events_mtime_iso: string | null;
  series: Record<string, IsaacRlLogScalarPoint[]>;
  latest: Record<string, { step: number; value: number }>;
}

export interface IsaacRlLogRunMeta {
  experiment: string;
  run_id: string;
  agent: Record<string, unknown> | null;
  env: Record<string, unknown> | null;
  checkpoints: string[];
  events_file: string | null;
}
