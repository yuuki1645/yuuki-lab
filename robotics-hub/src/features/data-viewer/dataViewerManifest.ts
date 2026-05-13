/**
 * データビュワー用データセットの manifest.json スキーマ。
 * 省略キーは後方互換のため既定値を使う。
 */

export type DataViewerAcquisition = "robot" | "mujoco" | "other";

export type DataViewerManifest = {
  /** 動画 currentTime=0 に対応する perf 軸の値（秒） */
  perf_timestamp_at_video_zero?: number;
  video_file?: string;
  video?: string;
  /**
   * データ取得経路。省略時は実機ログとみなす（`"robot"`）。
   */
  acquisition?: DataViewerAcquisition;
  /** manifest / CSV 解釈の版（将来拡張用） */
  schema_version?: number;
  /**
   * 取得方法ごとの付加情報（JSON オブジェクト任意）。
   * 例: MuJoCo なら mjcf パス、fps、加速度の単位など。
   */
  acquisition_detail?: Record<string, unknown>;
};

const ALLOWED_ACQUISITION: ReadonlySet<string> = new Set(["robot", "mujoco", "other"]);

function asFiniteNumber(v: unknown): number | undefined {
  if (typeof v !== "number" || !Number.isFinite(v)) return undefined;
  return v;
}

function asAcquisition(v: unknown): DataViewerAcquisition | undefined {
  if (typeof v !== "string") return undefined;
  const s = v.trim().toLowerCase();
  if (!ALLOWED_ACQUISITION.has(s)) return undefined;
  return s as DataViewerAcquisition;
}

function asDetail(v: unknown): Record<string, unknown> | undefined {
  if (typeof v !== "object" || v === null || Array.isArray(v)) return undefined;
  return { ...(v as Record<string, unknown>) };
}

/**
 * manifest.json をパースする。不正な acquisition は無視して `robot` 相当に落とさないため `undefined` にする。
 */
export function parseDataViewerManifest(text: string): DataViewerManifest | null {
  try {
    const o = JSON.parse(text) as unknown;
    if (typeof o !== "object" || o === null) return null;
    const r = o as Record<string, unknown>;
    const out: DataViewerManifest = {};

    const p = r.perf_timestamp_at_video_zero;
    if (typeof p === "number" && Number.isFinite(p)) {
      out.perf_timestamp_at_video_zero = p;
    }
    if (typeof r.video_file === "string" && r.video_file.length > 0) {
      out.video_file = r.video_file;
    }
    if (typeof r.video === "string" && r.video.length > 0) {
      out.video = r.video;
    }

    const acq = asAcquisition(r.acquisition);
    if (acq !== undefined) {
      out.acquisition = acq;
    }
    const sv = asFiniteNumber(r.schema_version);
    if (sv !== undefined) {
      out.schema_version = Math.floor(sv);
    }
    const det = asDetail(r.acquisition_detail);
    if (det !== undefined) {
      out.acquisition_detail = det;
    }

    return out;
  } catch {
    return null;
  }
}

/** 表示・パース分岐用。未指定は実機。 */
export function effectiveAcquisition(m: DataViewerManifest | null): DataViewerAcquisition {
  const a = m?.acquisition;
  if (a === "mujoco" || a === "other" || a === "robot") return a;
  return "robot";
}
