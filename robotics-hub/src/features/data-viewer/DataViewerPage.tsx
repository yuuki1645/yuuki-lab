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

const SERVO_WINDOW_SEC = 0.35;
const SERVO_MAX_ROWS = 24;

function fmtFixed(n: number | undefined, digits: number): string {
  if (n === undefined || !Number.isFinite(n)) return "—";
  return n.toFixed(digits);
}

/** 先頭 1 文字を符号（負は `-`、正はスペース）、続く 8 文字に絶対値を左埋めし小数点位置を揃える（合計 9 桁想定。本体が 8 を超えるときはそのまま連結） */
const IMU_AXIS_SIGN_BODY = 8;

function fmtAxisAligned(n: number | undefined, fracDigits: number): string {
  if (n === undefined || !Number.isFinite(n)) {
    return "    —    ";
  }
  const sign = n < 0 ? "-" : " ";
  const body = Math.abs(n).toFixed(fracDigits);
  const padded = body.length >= IMU_AXIS_SIGN_BODY ? body : body.padStart(IMU_AXIS_SIGN_BODY, " ");
  return sign + padded;
}

function formatAccelAxisLine(row: ImuCsvRow): string {
  return `accel x=${fmtAxisAligned(row.accel_x, 4)} / y=${fmtAxisAligned(row.accel_y, 4)} / z=${fmtAxisAligned(row.accel_z, 4)}`;
}

function formatGyroAxisLine(row: ImuCsvRow): string {
  return `gyro x=${fmtAxisAligned(row.gyro_x, 4)} / y=${fmtAxisAligned(row.gyro_y, 4)} / z=${fmtAxisAligned(row.gyro_z, 4)}`;
}

function formatAngleAxisLine(row: ImuCsvRow): string {
  return `pitch=${fmtAxisAligned(row.angle_pitch, 4)} / roll=${fmtAxisAligned(row.angle_roll, 4)} / yaw=${fmtAxisAligned(row.angle_yaw, 4)}`;
}

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

  const [imuRows, setImuRows] = useState<ImuCsvRow[]>([]);
  const [servoRows, setServoRows] = useState<ServoCsvRow[]>([]);
  const [imuName, setImuName] = useState("");
  const [servoName, setServoName] = useState("");
  const [diskVideoFileName, setDiskVideoFileName] = useState("");
  const [videoSrc, setVideoSrc] = useState<string | null>(null);
  const [publicVideoPath, setPublicVideoPath] = useState("/data-viewer-videos/");

  const [videoAnchorPerf, setVideoAnchorPerf] = useState<number>(0);
  const [anchorTouched, setAnchorTouched] = useState(false);

  const [videoDuration, setVideoDuration] = useState(0);
  const [videoTime, setVideoTime] = useState(0);

  const [currentPerf, setCurrentPerf] = useState<number>(0);
  const [parseError, setParseError] = useState<string | null>(null);

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

  const onPickImu = async (f: File | null) => {
    setParseError(null);
    if (!f) return;
    try {
      const text = await f.text();
      const rows = parseImuCsv(text);
      setImuRows(rows);
      setImuName(f.name);
    } catch (e) {
      setImuRows([]);
      setImuName("");
      setParseError(e instanceof Error ? e.message : String(e));
    }
  };

  const onPickServo = async (f: File | null) => {
    setParseError(null);
    if (!f) return;
    try {
      const text = await f.text();
      const rows = parseServoCsv(text);
      setServoRows(rows);
      setServoName(f.name);
    } catch (e) {
      setServoRows([]);
      setServoName("");
      setParseError(e instanceof Error ? e.message : String(e));
    }
  };

  const onPickVideo = (f: File | null) => {
    setParseError(null);
    revokeVideoBlob();
    setVideoSrc(null);
    setDiskVideoFileName("");
    setVideoDuration(0);
    setVideoTime(0);
    if (!f) return;
    const url = URL.createObjectURL(f);
    videoBlobUrlRef.current = url;
    setVideoSrc(url);
    setDiskVideoFileName(f.name);
  };

  const loadPublicVideo = () => {
    setParseError(null);
    revokeVideoBlob();
    const raw = publicVideoPath.trim();
    if (!raw) {
      setParseError("動画のパスを入力してください（例: /data-viewer-videos/foo.mp4）");
      return;
    }
    const path = raw.startsWith("/") ? raw : `/${raw}`;
    setVideoSrc(path);
    setDiskVideoFileName("");
    setVideoDuration(0);
    setVideoTime(0);
  };

  useEffect(() => () => revokeVideoBlob(), []);

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
          <code className="data-viewer__code">wall_unix</code> は参考表示です。動画ファイルは{" "}
          <code className="data-viewer__code">robotics-hub/public/data-viewer-videos/</code>{" "}
          に置き、下の「公開パスから読み込み」で指定できます。
        </p>
      </header>

      <section className="data-viewer__panel" aria-label="ファイル読み込み">
        <h2 className="data-viewer__h2">読み込み</h2>
        <div className="data-viewer__loads">
          <label className="data-viewer__file">
            <span className="data-viewer__file-label">IMU CSV</span>
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={(e) => void onPickImu(e.target.files?.[0] ?? null)}
            />
            {imuName ? <span className="data-viewer__fname">{imuName}</span> : null}
          </label>
          <label className="data-viewer__file">
            <span className="data-viewer__file-label">サーボ CSV</span>
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={(e) => void onPickServo(e.target.files?.[0] ?? null)}
            />
            {servoName ? <span className="data-viewer__fname">{servoName}</span> : null}
          </label>
          <label className="data-viewer__file">
            <span className="data-viewer__file-label">動画ファイル</span>
            <input type="file" accept="video/*" onChange={(e) => onPickVideo(e.target.files?.[0] ?? null)} />
            {diskVideoFileName ? <span className="data-viewer__fname">{diskVideoFileName}</span> : null}
          </label>
        </div>
        <div className="data-viewer__public-row">
          <label className="data-viewer__public-label">
            公開パスから読み込み（Vite の public 直下）
            <input
              className="data-viewer__public-input"
              type="text"
              value={publicVideoPath}
              onChange={(e) => setPublicVideoPath(e.target.value)}
              placeholder="/data-viewer-videos/foo.mp4"
              spellCheck={false}
            />
          </label>
          <button type="button" className="data-viewer__btn" onClick={loadPublicVideo}>
            動画を適用
          </button>
        </div>
        {parseError ? <p className="data-viewer__error">{parseError}</p> : null}
      </section>

      <div className="data-viewer__grid">
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
                コントロールバーまたは上のスライダーで任意位置へ移動できます。
              </p>
            </>
          ) : (
            <p className="data-viewer__empty">動画を選択するか、公開パスから読み込んでください。</p>
          )}
        </section>

        <section className="data-viewer__panel" aria-label="時刻合わせ">
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
          <dl className="data-viewer__dl">
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
        </section>
      </div>

      <section className="data-viewer__panel" aria-label="IMU 行">
        <h2 className="data-viewer__h2">IMU（最も近い行）</h2>
        {!imuRows.length ? (
          <p className="data-viewer__empty">IMU CSV を読み込んでください。</p>
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
                  <th>加速度（各軸 g）</th>
                  <td className="data-viewer__td-num data-viewer__imu-mono">
                    {formatAccelAxisLine(imuNearest)}
                  </td>
                </tr>
                <tr>
                  <th>角速度（各軸 °/s）</th>
                  <td className="data-viewer__td-num data-viewer__imu-mono">
                    {formatGyroAxisLine(imuNearest)}
                  </td>
                </tr>
                <tr>
                  <th>姿勢角（pitch / roll / yaw、°）</th>
                  <td className="data-viewer__td-num data-viewer__imu-mono">
                    {formatAngleAxisLine(imuNearest)}
                  </td>
                </tr>
              </tbody>
            </table>
          </>
        )}
      </section>

      <section className="data-viewer__panel" aria-label="サーボ行">
        <h2 className="data-viewer__h2">サーボ（前後 {SERVO_WINDOW_SEC} 秒以内・近い順）</h2>
        {!servoRows.length ? (
          <p className="data-viewer__empty">サーボ CSV を読み込んでください。</p>
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
  );
}
