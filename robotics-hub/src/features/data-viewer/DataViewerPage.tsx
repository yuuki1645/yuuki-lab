import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  parseImuCsv,
  parseServoCsv,
  type ImuCsvRow,
  type ServoCsvRow,
} from "./csvParse";
import {
  maxPerfTimestamp,
  minPerfTimestamp,
  nearestImuIndexByPerf,
  servoRowsAroundPerf,
} from "./telemetryTimeSync";
import "./DataViewerPage.css";
import dataViewerDatasets from "./dataViewerDatasets.json";
import {
  effectiveAcquisition,
  parseDataViewerManifest,
  type DataViewerManifest,
} from "./dataViewerManifest";

const SERVO_WINDOW_SEC = 0.35;
const SERVO_MAX_ROWS = 24;
const SEEK_KEYBOARD_STEP_SEC = 0.1;

const DATA_VIEWER_DATASETS_BASE = "/data-viewer-datasets/";
const DATASET_IMU_FILE = "imu.csv";
const DATASET_SERVO_FILE = "servo.csv";
const DATASET_MANIFEST_FILE = "manifest.json";
const VIDEO_FALLBACK_NAMES = ["video.mp4", "session.mp4", "recording.mp4"] as const;

async function fetchManifest(
  base: string,
  signal: AbortSignal
): Promise<DataViewerManifest | null> {
  const r = await fetch(`${base}${DATASET_MANIFEST_FILE}`, { signal });
  if (!r.ok) return null;
  const text = await r.text();
  return parseDataViewerManifest(text);
}

async function resolvePublicVideoUrl(
  base: string,
  manifest: DataViewerManifest | null,
  signal: AbortSignal
): Promise<string | null> {
  const names: string[] = [];
  if (manifest?.video_file) names.push(manifest.video_file);
  if (manifest?.video) names.push(manifest.video);
  for (const f of VIDEO_FALLBACK_NAMES) names.push(f);
  const uniq = [...new Set(names)];
  for (const name of uniq) {
    if (name.includes("/") || name.includes("\\") || name.includes("..")) continue;
    const url = `${base}${name}`;
    try {
      const head = await fetch(url, { method: "HEAD", signal });
      if (head.ok) return url;
      if (!signal.aborted && (head.status === 404 || head.status === 405)) {
        const get = await fetch(url, {
          method: "GET",
          signal,
          headers: { Range: "bytes=0-0" },
        });
        if (get.ok || get.status === 206) return url;
      }
    } catch (e) {
      if (signal.aborted) throw e;
    }
  }
  return null;
}

function fmtFixed(n: number | undefined, digits: number): string {
  if (n === undefined || !Number.isFinite(n)) return "—";
  return n.toFixed(digits);
}

/** 負は `-0.1234` のように数値先頭にマイナス。全体を左スペース埋めして小数点を縦に揃える */
const IMU_NUM_FIELD_WIDTH = 10;

function fmtSignedNumPadded(n: number | undefined, fracDigits: number): string {
  if (n === undefined || !Number.isFinite(n)) {
    return "    —    ".slice(0, IMU_NUM_FIELD_WIDTH).padStart(IMU_NUM_FIELD_WIDTH, " ");
  }
  const body = Math.abs(n).toFixed(fracDigits);
  const signed = n < 0 ? `-${body}` : body;
  return signed.length >= IMU_NUM_FIELD_WIDTH ? signed : signed.padStart(IMU_NUM_FIELD_WIDTH, " ");
}

/** `label=` を固定幅にし、その直後に数値フィールド（fmtSignedNumPadded）を連結 */
function fmtLabeledImuValue(
  label: string,
  n: number | undefined,
  fracDigits: number,
  labelWithEqWidth: number
): string {
  return (label + "=").padEnd(labelWithEqWidth, " ") + fmtSignedNumPadded(n, fracDigits);
}

const IMU_LABEL_XYZ = 3; // "x=", "y=", "z="
const IMU_LABEL_ANGLE = 6; // "pitch=" までで roll=/yaw= を揃える

/** 動画オーバーレイと同様、秒を経過時間として HH:MM:SS.ss（百分の一秒）で表す */
function formatPerfSecondsAsHMSss(sec: number | undefined): string {
  if (sec === undefined || !Number.isFinite(sec)) return "—";
  const neg = sec < 0;
  let t = Math.abs(sec);

  let centis = Math.round((t % 1) * 100);
  let whole = Math.floor(t);
  if (centis >= 100) {
    centis -= 100;
    whole += 1;
  }

  const h = Math.floor(whole / 3600);
  let rem = whole % 3600;
  const m = Math.floor(rem / 60);
  const s = rem % 60;

  const pad = (n: number) => String(n).padStart(2, "0");
  const core = `${pad(h)}:${pad(m)}:${pad(s)}.${pad(centis)}`;
  return neg ? `-${core}` : core;
}

function wallToLocalString(wall: number): string {
  try {
    return new Date(wall * 1000).toLocaleString();
  } catch {
    return String(wall);
  }
}

function rowsWithPerfSortedImu(rows: ImuCsvRow[]): ImuCsvRow[] {
  return [...rows]
    .filter((r) => r.perf_timestamp !== undefined && Number.isFinite(r.perf_timestamp))
    .sort((a, b) => a.perf_timestamp! - b.perf_timestamp!);
}

function rowsWithPerfSortedServo(rows: ServoCsvRow[]): ServoCsvRow[] {
  return [...rows]
    .filter((r) => r.perf_timestamp !== undefined && Number.isFinite(r.perf_timestamp))
    .sort((a, b) => a.perf_timestamp! - b.perf_timestamp!);
}

export default function DataViewerPage() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const videoBlobUrlRef = useRef<string | null>(null);
  const loadDatasetAbortRef = useRef<AbortController | null>(null);

  const [imuRows, setImuRows] = useState<ImuCsvRow[]>([]);
  const [servoRows, setServoRows] = useState<ServoCsvRow[]>([]);
  const [imuName, setImuName] = useState("");
  const [servoName, setServoName] = useState("");
  const [videoSrc, setVideoSrc] = useState<string | null>(null);

  const firstDatasetId = dataViewerDatasets[0]?.id ?? "";
  const [selectedDatasetId, setSelectedDatasetId] = useState(firstDatasetId);
  const [datasetLoading, setDatasetLoading] = useState(false);
  const [videoHint, setVideoHint] = useState<string | null>(null);

  const [videoAnchorPerf, setVideoAnchorPerf] = useState<number>(0);
  const [anchorTouched, setAnchorTouched] = useState(false);

  const [videoDuration, setVideoDuration] = useState(0);
  const [videoTime, setVideoTime] = useState(0);

  const [currentPerf, setCurrentPerf] = useState<number>(0);
  const [parseError, setParseError] = useState<string | null>(null);
  const [datasetManifest, setDatasetManifest] = useState<DataViewerManifest | null>(null);

  const datasetAcquisition = useMemo(
    () => effectiveAcquisition(datasetManifest),
    [datasetManifest]
  );

  const imuColumnTitles = useMemo(() => {
    const acq = datasetAcquisition;
    const d = datasetManifest?.acquisition_detail;
    const accelLabel =
      typeof d?.imu_accel_column_label === "string"
        ? (d.imu_accel_column_label as string)
        : undefined;
    const gyroLabel =
      typeof d?.imu_gyro_column_label === "string"
        ? (d.imu_gyro_column_label as string)
        : undefined;
    if (acq === "mujoco") {
      return { accel: "加速度（m/s²）", gyro: "角速度（rad/s）", angle: "姿勢角（°）" };
    }
    if (acq === "other") {
      return {
        accel: accelLabel ?? "加速度",
        gyro: gyroLabel ?? "角速度",
        angle: "姿勢角（°）",
      };
    }
    return { accel: "加速度（g）", gyro: "角速度（°/s）", angle: "姿勢角（°）" };
  }, [datasetAcquisition, datasetManifest]);

  const acquisitionLabelJa = useMemo(() => {
    switch (datasetAcquisition) {
      case "mujoco":
        return "MuJoCo シミュレーション";
      case "other":
        return "その他";
      default:
        return "実機";
    }
  }, [datasetAcquisition]);

  const imuByPerf = useMemo(() => rowsWithPerfSortedImu(imuRows), [imuRows]);
  const servoByPerf = useMemo(() => rowsWithPerfSortedServo(servoRows), [servoRows]);

  const csvRange = useMemo(() => {
    const lo = minPerfTimestamp(imuRows, servoRows);
    const hi = maxPerfTimestamp(imuRows, servoRows);
    return { lo, hi };
  }, [imuRows, servoRows]);

  useEffect(() => {
    if (anchorTouched) return;
    const lo = csvRange.lo;
    if (lo !== null && Number.isFinite(lo)) {
      setVideoAnchorPerf(lo);
    }
  }, [csvRange.lo, anchorTouched]);

  const revokeVideoBlob = () => {
    const u = videoBlobUrlRef.current;
    if (u) {
      URL.revokeObjectURL(u);
      videoBlobUrlRef.current = null;
    }
  };

  const loadDatasetFromPublic = useCallback(async () => {
    const id = selectedDatasetId.trim();
    if (!id) {
      setParseError("データセットを選んでください。");
      return;
    }

    loadDatasetAbortRef.current?.abort();
    const ac = new AbortController();
    loadDatasetAbortRef.current = ac;
    const { signal } = ac;

    setParseError(null);
    setVideoHint(null);
    setDatasetLoading(true);

    const base = `${DATA_VIEWER_DATASETS_BASE}${id}/`;

    try {
      const manifest = await fetchManifest(base, signal);

      const imuRes = await fetch(`${base}${DATASET_IMU_FILE}`, { signal });
      if (!imuRes.ok) {
        throw new Error(`imu.csv が取得できません (${imuRes.status})`);
      }
      const imuText = await imuRes.text();
      const imuParsed = parseImuCsv(imuText);

      const servoRes = await fetch(`${base}${DATASET_SERVO_FILE}`, { signal });
      if (!servoRes.ok) {
        throw new Error(`servo.csv が取得できません (${servoRes.status})`);
      }
      const servoText = await servoRes.text();
      const servoParsed = parseServoCsv(servoText);

      revokeVideoBlob();
      setImuRows(imuParsed);
      setServoRows(servoParsed);
      setImuName(`${id}/${DATASET_IMU_FILE}`);
      setServoName(`${id}/${DATASET_SERVO_FILE}`);
      setDatasetManifest(manifest);

      const perfAnchor = manifest?.perf_timestamp_at_video_zero;
      if (typeof perfAnchor === "number" && Number.isFinite(perfAnchor)) {
        setVideoAnchorPerf(perfAnchor);
        setAnchorTouched(true);
      } else {
        setAnchorTouched(false);
      }

      const videoUrl = await resolvePublicVideoUrl(base, manifest, signal);
      if (videoUrl) {
        setVideoSrc(videoUrl);
        setVideoHint(null);
      } else {
        setVideoSrc(null);
        setVideoDuration(0);
        setVideoTime(0);
        setVideoHint(
          "動画ファイルが見つかりませんでした。manifest.json に video_file を書くか、video.mp4 / session.mp4 を置いてください。"
        );
      }
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      setImuRows([]);
      setServoRows([]);
      setImuName("");
      setServoName("");
      setDatasetManifest(null);
      revokeVideoBlob();
      setVideoSrc(null);
      setParseError(e instanceof Error ? e.message : String(e));
    } finally {
      if (loadDatasetAbortRef.current === ac) {
        setDatasetLoading(false);
      }
    }
  }, [selectedDatasetId]);

  useEffect(() => {
    return () => {
      loadDatasetAbortRef.current?.abort();
      const u = videoBlobUrlRef.current;
      if (u) {
        URL.revokeObjectURL(u);
        videoBlobUrlRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    const el = videoRef.current;
    if (!el || !Number.isFinite(el.currentTime)) return;
    setCurrentPerf(videoAnchorPerf + el.currentTime);
  }, [videoAnchorPerf]);

  const syncPerfFromVideo = useCallback(() => {
    const el = videoRef.current;
    if (!el) return;
    const t = el.currentTime;
    setVideoTime(t);
    setCurrentPerf(videoAnchorPerf + t);
  }, [videoAnchorPerf]);

  const seekVideo = useCallback(
    (sec: number) => {
      const el = videoRef.current;
      if (!el || !Number.isFinite(sec)) return;
      const d = el.duration;
      const clamped =
        Number.isFinite(d) && d > 0 ? Math.min(Math.max(0, sec), d) : Math.max(0, sec);
      el.currentTime = clamped;
      setVideoTime(clamped);
      setCurrentPerf(videoAnchorPerf + clamped);
    },
    [videoAnchorPerf]
  );

  useEffect(() => {
    if (!videoSrc) return;

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
      const t = e.target;
      if (
        t instanceof HTMLInputElement ||
        t instanceof HTMLTextAreaElement ||
        t instanceof HTMLSelectElement
      ) {
        return;
      }
      if (t instanceof HTMLElement && t.isContentEditable) return;

      const el = videoRef.current;
      if (!el || !Number.isFinite(el.currentTime)) return;

      e.preventDefault();
      const delta = e.key === "ArrowRight" ? SEEK_KEYBOARD_STEP_SEC : -SEEK_KEYBOARD_STEP_SEC;
      seekVideo(el.currentTime + delta);
    };

    window.addEventListener("keydown", onKeyDown, { capture: true });
    return () => window.removeEventListener("keydown", onKeyDown, { capture: true });
  }, [videoSrc, seekVideo]);

  const onVideoTime = () => {
    syncPerfFromVideo();
  };

  const onLoadedMeta = () => {
    const el = videoRef.current;
    if (!el) return;
    setVideoDuration(Number.isFinite(el.duration) ? el.duration : 0);
    syncPerfFromVideo();
  };

  const imuIdx = useMemo(
    () => nearestImuIndexByPerf(imuByPerf, currentPerf),
    [imuByPerf, currentPerf]
  );
  const imuNearest = imuIdx >= 0 ? imuByPerf[imuIdx] : undefined;
  const imuDeltaMs =
    imuNearest !== undefined && imuNearest.perf_timestamp !== undefined
      ? (currentPerf - imuNearest.perf_timestamp) * 1000
      : null;

  const servoNear = useMemo(
    () =>
      servoRowsAroundPerf(servoByPerf, currentPerf, SERVO_WINDOW_SEC, SERVO_MAX_ROWS),
    [servoByPerf, currentPerf]
  );

  const nudgeAnchor = (deltaSec: number) => {
    setAnchorTouched(true);
    setVideoAnchorPerf((a) => a + deltaSec);
  };

  const resetAnchorToCsvStart = () => {
    setAnchorTouched(false);
    const lo = csvRange.lo;
    if (lo !== null) setVideoAnchorPerf(lo);
  };

  const scrubberMax = videoDuration > 0 ? videoDuration : 1;
  const scrubberValue = videoDuration > 0 ? videoTime : 0;

  return (
    <div className="data-viewer">
      <header className="data-viewer__head">
        <h1 className="data-viewer__title">データビュワー</h1>
        <p className="data-viewer__lead">
          IMU / サーボの CSV と動画を突き合わせ、再生位置に対応するログ行を確認します。時刻合わせの基準は{" "}
          <code className="data-viewer__code">perf_timestamp</code>（
          <code className="data-viewer__code">perf_counter</code> 秒）で、{" "}
          <code className="data-viewer__code">wall_unix</code> は参考表示です。データセットは{" "}
          <code className="data-viewer__code">robotics-hub/public/data-viewer-datasets/</code> 直下のフォルダ（例:{" "}
          <code className="data-viewer__code">YuukiLab001</code>）に{" "}
          <code className="data-viewer__code">imu.csv</code>・
          <code className="data-viewer__code">servo.csv</code>・任意の{" "}
          <code className="data-viewer__code">manifest.json</code> と動画を置き、下の一覧から選んで読み込んでください。
        </p>
      </header>

      <section className="data-viewer__panel" aria-label="データセット読み込み">
        <h2 className="data-viewer__h2">読み込み</h2>
        <div className="data-viewer__dataset-row">
          <label className="data-viewer__dataset-label">
            データセット（<code className="data-viewer__code">public/data-viewer-datasets/</code> 内）
            <select
              className="data-viewer__select"
              value={selectedDatasetId}
              onChange={(e) => setSelectedDatasetId(e.target.value)}
              disabled={datasetLoading}
            >
              {dataViewerDatasets.length === 0 ? (
                <option value="">（データセット未登録）</option>
              ) : (
                dataViewerDatasets.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.title} ({d.id})
                  </option>
                ))
              )}
            </select>
          </label>
          <button
            type="button"
            className="data-viewer__btn"
            onClick={() => void loadDatasetFromPublic()}
            disabled={datasetLoading || !dataViewerDatasets.length}
          >
            {datasetLoading ? "読み込み中…" : "データセットを読み込み"}
          </button>
        </div>
        {videoHint ? <p className="data-viewer__muted data-viewer__video-hint">{videoHint}</p> : null}
        {imuName ? (
          <>
            <p className="data-viewer__muted data-viewer__loaded-meta">
              読み込み: <code className="data-viewer__code">{imuName}</code>{" "}
              <code className="data-viewer__code">{servoName}</code>
              {videoSrc ? (
                <>
                  {" "}
                  <code className="data-viewer__code">{videoSrc}</code>
                </>
              ) : null}
            </p>
            <p className="data-viewer__muted">
              取得方法: <strong>{acquisitionLabelJa}</strong>
              {datasetManifest?.schema_version !== undefined ? (
                <>
                  {" "}
                  · schema_version={datasetManifest.schema_version}
                </>
              ) : null}
            </p>
          </>
        ) : null}
        {parseError ? <p className="data-viewer__error">{parseError}</p> : null}
      </section>

      <div className="data-viewer__main-row">
        <section className="data-viewer__panel data-viewer__panel--video" aria-label="動画">
          <h2 className="data-viewer__h2">動画</h2>
          {videoSrc ? (
            <>
              <video
                ref={videoRef}
                className="data-viewer__video"
                src={videoSrc}
                controls
                playsInline
                onLoadedMetadata={onLoadedMeta}
                onTimeUpdate={onVideoTime}
                onSeeking={onVideoTime}
                onSeeked={onVideoTime}
              />
              <div className="data-viewer__seek">
                <label className="data-viewer__seek-label">
                  シーク（再生時間 {fmtFixed(videoTime, 3)} s / {fmtFixed(videoDuration, 3)} s）
                  <input
                    type="range"
                    className="data-viewer__range"
                    min={0}
                    max={scrubberMax}
                    step={0.001}
                    value={scrubberValue}
                    onChange={(e) => seekVideo(Number(e.target.value))}
                  />
                </label>
              </div>
              <p className="data-viewer__hint">
                コントロールバー・スライダーで任意位置へ移動できます。左右キーで{" "}
                {SEEK_KEYBOARD_STEP_SEC} 秒単位にシークします（入力欄にフォーカスがあるときは無効）。
              </p>
            </>
          ) : (
            <p className="data-viewer__empty">
              動画がありません。上でデータセットを読み込むか、フォルダ内に動画（または manifest の video_file）を追加してください。
            </p>
          )}
        </section>

        <div className="data-viewer__main-right">
          <section className="data-viewer__panel data-viewer__panel--stack" aria-label="IMU 行">
            <h2 className="data-viewer__h2">IMU（最も近い行）</h2>
            {!imuRows.length ? (
              <p className="data-viewer__empty">データセットを読み込んでください。</p>
            ) : !imuByPerf.length ? (
              <p className="data-viewer__empty">
                IMU 行に <code className="data-viewer__code">perf_timestamp</code> がありません。
              </p>
            ) : imuNearest === undefined ? (
              <p className="data-viewer__empty">該当行がありません。</p>
            ) : (
              <>
                <p className="data-viewer__muted">
                  現在位置との差分:{" "}
                  {imuDeltaMs !== null ? (
                    <code className="data-viewer__code">{imuDeltaMs.toFixed(1)} ms</code>
                  ) : (
                    "—"
                  )}
                </p>
                <table className="data-viewer__table">
                  <tbody>
                    <tr>
                      <th>perf_timestamp</th>
                      <td className="data-viewer__td-num">{fmtFixed(imuNearest.perf_timestamp, 6)}</td>
                    </tr>
                    <tr>
                      <th>HH:MM:SS.ss</th>
                      <td className="data-viewer__td-num">{formatPerfSecondsAsHMSss(imuNearest.perf_timestamp)}</td>
                    </tr>
                    <tr>
                      <th>wall_unix</th>
                      <td className="data-viewer__td-num">{fmtFixed(imuNearest.wall_unix, 6)}</td>
                    </tr>
                    <tr>
                      <th>mock</th>
                      <td>{imuNearest.mock === undefined ? "—" : imuNearest.mock ? "true" : "false"}</td>
                    </tr>
                    <tr>
                      <td colSpan={2} className="data-viewer__imu-vector-block">
                        <table
                          className="data-viewer__imu-3col"
                          aria-label="加速度・角速度・姿勢角（各列で軸を縦に表示）"
                        >
                          <thead>
                            <tr>
                              <th scope="col">{imuColumnTitles.accel}</th>
                              <th scope="col">{imuColumnTitles.gyro}</th>
                              <th scope="col">{imuColumnTitles.angle}</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr>
                              <td className="data-viewer__td-num data-viewer__imu-mono">
                                {fmtLabeledImuValue("x", imuNearest.accel_x, 4, IMU_LABEL_XYZ)}
                              </td>
                              <td className="data-viewer__td-num data-viewer__imu-mono">
                                {fmtLabeledImuValue("x", imuNearest.gyro_x, 4, IMU_LABEL_XYZ)}
                              </td>
                              <td className="data-viewer__td-num data-viewer__imu-mono">
                                {fmtLabeledImuValue("pitch", imuNearest.angle_pitch, 4, IMU_LABEL_ANGLE)}
                              </td>
                            </tr>
                            <tr>
                              <td className="data-viewer__td-num data-viewer__imu-mono">
                                {fmtLabeledImuValue("y", imuNearest.accel_y, 4, IMU_LABEL_XYZ)}
                              </td>
                              <td className="data-viewer__td-num data-viewer__imu-mono">
                                {fmtLabeledImuValue("y", imuNearest.gyro_y, 4, IMU_LABEL_XYZ)}
                              </td>
                              <td className="data-viewer__td-num data-viewer__imu-mono">
                                {fmtLabeledImuValue("roll", imuNearest.angle_roll, 4, IMU_LABEL_ANGLE)}
                              </td>
                            </tr>
                            <tr>
                              <td className="data-viewer__td-num data-viewer__imu-mono">
                                {fmtLabeledImuValue("z", imuNearest.accel_z, 4, IMU_LABEL_XYZ)}
                              </td>
                              <td className="data-viewer__td-num data-viewer__imu-mono">
                                {fmtLabeledImuValue("z", imuNearest.gyro_z, 4, IMU_LABEL_XYZ)}
                              </td>
                              <td className="data-viewer__td-num data-viewer__imu-mono">
                                {fmtLabeledImuValue("yaw", imuNearest.angle_yaw, 4, IMU_LABEL_ANGLE)}
                              </td>
                            </tr>
                          </tbody>
                        </table>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </>
            )}
          </section>

          <section className="data-viewer__panel data-viewer__panel--stack" aria-label="サーボ行">
            <h2 className="data-viewer__h2">サーボ（前後 {SERVO_WINDOW_SEC} 秒以内・近い順）</h2>
            {!servoRows.length ? (
              <p className="data-viewer__empty">データセットを読み込んでください。</p>
            ) : !servoByPerf.length ? (
              <p className="data-viewer__empty">
                サーボ行に <code className="data-viewer__code">perf_timestamp</code> がありません。
              </p>
            ) : servoNear.length === 0 ? (
              <p className="data-viewer__empty">この付近にサーボログがありません。</p>
            ) : (
              <div className="data-viewer__table-wrap">
                <table className="data-viewer__table data-viewer__table--wide">
                  <thead>
                    <tr>
                      <th>Δ ms（perf）</th>
                      <th>perf_timestamp</th>
                      <th>wall_unix</th>
                      <th>ch</th>
                      <th>mode</th>
                      <th>logical°</th>
                      <th>physical°</th>
                      <th>endpoint</th>
                    </tr>
                  </thead>
                  <tbody>
                    {servoNear.map((r, i) => {
                      const p = r.perf_timestamp!;
                      const dms = (p - currentPerf) * 1000;
                      return (
                        <tr key={`${p}-${r.ch}-${i}`}>
                          <td className="data-viewer__td-num">{dms.toFixed(1)}</td>
                          <td className="data-viewer__td-num">{fmtFixed(r.perf_timestamp, 6)}</td>
                          <td className="data-viewer__td-num">{fmtFixed(r.wall_unix, 6)}</td>
                          <td>{r.ch ?? "—"}</td>
                          <td>{r.mode ?? "—"}</td>
                          <td className="data-viewer__td-num">{fmtFixed(r.logical_deg, 3)}</td>
                          <td className="data-viewer__td-num">{fmtFixed(r.physical_deg, 3)}</td>
                          <td>{r.endpoint ?? "—"}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>
      </div>

      <section className="data-viewer__panel data-viewer__panel--sync" aria-label="時刻合わせ">
        <h2 className="data-viewer__h2">時刻合わせ</h2>
        <p className="data-viewer__muted">
          動画の 0 秒が、次の <code className="data-viewer__code">perf_timestamp</code>（
          <code className="data-viewer__code">perf_counter</code> 秒）に対応します。CSV の{" "}
          <code className="data-viewer__code">perf_timestamp</code> と揃えてください。
        </p>
        {(imuRows.length > 0 || servoRows.length > 0) &&
        csvRange.lo === null &&
        csvRange.hi === null ? (
          <p className="data-viewer__error" role="status">
            読み込んだ CSV に有限な <code className="data-viewer__code">perf_timestamp</code>{" "}
            がありません。daemon の新しいログ形式（perf 列付き）を使うか、列を追加してください。
          </p>
        ) : null}
        <div className="data-viewer__sync-body">
          <div className="data-viewer__anchor-row">
            <label className="data-viewer__anchor-label">
              アンカー perf_timestamp
              <input
                type="number"
                className="data-viewer__anchor-input"
                step="0.001"
                value={Number.isFinite(videoAnchorPerf) ? videoAnchorPerf : 0}
                onChange={(e) => {
                  setAnchorTouched(true);
                  const v = Number(e.target.value);
                  if (Number.isFinite(v)) setVideoAnchorPerf(v);
                }}
              />
            </label>
            <div className="data-viewer__nudge">
              <button type="button" className="data-viewer__btn" onClick={() => nudgeAnchor(-1)}>
                −1s
              </button>
              <button type="button" className="data-viewer__btn" onClick={() => nudgeAnchor(-0.1)}>
                −0.1s
              </button>
              <button type="button" className="data-viewer__btn" onClick={() => nudgeAnchor(0.1)}>
                +0.1s
              </button>
              <button type="button" className="data-viewer__btn" onClick={() => nudgeAnchor(1)}>
                +1s
              </button>
              <button type="button" className="data-viewer__btn" onClick={resetAnchorToCsvStart}>
                CSV 先頭に合わせる
              </button>
            </div>
          </div>
          <dl className="data-viewer__dl data-viewer__dl--sync">
            <div>
              <dt>現在の perf_timestamp</dt>
              <dd>
                <code className="data-viewer__code">{fmtFixed(currentPerf, 6)}</code>
              </dd>
            </div>
            <div>
              <dt>最も近い IMU 行の wall_unix（参考・ローカル）</dt>
              <dd>
                {imuNearest !== undefined ? (
                  <>
                    <code className="data-viewer__code">{fmtFixed(imuNearest.wall_unix, 6)}</code>
                    {" · "}
                    {wallToLocalString(imuNearest.wall_unix)}
                  </>
                ) : (
                  "—"
                )}
              </dd>
            </div>
            <div>
              <dt>CSV perf 範囲</dt>
              <dd>
                {csvRange.lo !== null && csvRange.hi !== null ? (
                  <>
                    <code className="data-viewer__code">{fmtFixed(csvRange.lo, 3)}</code>
                    {" — "}
                    <code className="data-viewer__code">{fmtFixed(csvRange.hi, 3)}</code>
                  </>
                ) : imuRows.length > 0 || servoRows.length > 0 ? (
                  "perf なし"
                ) : (
                  "CSV 未読込"
                )}
              </dd>
            </div>
          </dl>
        </div>
      </section>
    </div>
  );
}
