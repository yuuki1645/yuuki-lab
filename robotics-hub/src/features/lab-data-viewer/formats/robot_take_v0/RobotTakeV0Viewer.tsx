import { useEffect, useMemo, useRef, useState } from "react";
import ImuAttitudeGauges from "@/shared/components/ImuAttitudeGauges";
import type { LabFormatViewerProps } from "@/features/lab-data-viewer/types";
import {
  commandsAround,
  nearestImuIndex,
  parseCommandJsonl,
  parseImuJsonl,
  type CommandJsonlRow,
  type ImuJsonlRow,
} from "@/features/lab-data-viewer/formats/robot_take_v0/parseTakeV0";

const CMD_WINDOW_SEC = 0.5;
const CMD_MAX = 20;

/**
 * format robot_take_v0: 動画 currentTime と video_t0_unix で IMU / 指令を突き合わせる。
 * mp4 が壊れている場合は HLS（index.m3u8）にフォールバック（Safari 向け）。
 */
export default function RobotTakeV0Viewer({ take, recorderBaseUrl }: LabFormatViewerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [imuRows, setImuRows] = useState<ImuJsonlRow[]>([]);
  const [cmdRows, setCmdRows] = useState<CommandJsonlRow[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  /** mp4 失敗時に HLS へ切替 */
  const [preferHls, setPreferHls] = useState(!take.video_url && Boolean(take.hls_url));
  const [mediaError, setMediaError] = useState<string | null>(null);

  const t0 = useMemo(() => {
    const v = take.meta.video_t0_unix;
    return typeof v === "number" && Number.isFinite(v) ? v : null;
  }, [take.meta]);

  const mp4Src = take.video_url ? recorderBaseUrl + take.video_url : null;
  const hlsSrc = take.hls_url ? recorderBaseUrl + take.hls_url : null;
  const videoSrc = preferHls ? hlsSrc : mp4Src ?? hlsSrc;
  const mediaKind = preferHls || (!mp4Src && hlsSrc) ? "HLS" : videoSrc ? "mp4" : null;

  useEffect(() => {
    // take 切替時は mp4 優先に戻す（無ければ HLS）
    setPreferHls(!take.video_url && Boolean(take.hls_url));
    setMediaError(null);
    setCurrentTime(0);
  }, [take.take_id, take.video_url, take.hls_url]);

  useEffect(() => {
    const ac = new AbortController();
    setLoadError(null);
    setImuRows([]);
    setCmdRows([]);

    (async () => {
      try {
        if (take.imu_url) {
          const res = await fetch(recorderBaseUrl + take.imu_url, {
            signal: ac.signal,
            cache: "no-store",
          });
          if (!res.ok) throw new Error("imu.jsonl HTTP " + String(res.status));
          setImuRows(parseImuJsonl(await res.text()));
        }
        if (take.commands_url) {
          const res = await fetch(recorderBaseUrl + take.commands_url, {
            signal: ac.signal,
            cache: "no-store",
          });
          if (!res.ok) throw new Error("servo.jsonl HTTP " + String(res.status));
          setCmdRows(parseCommandJsonl(await res.text()));
        }
      } catch (e) {
        if (ac.signal.aborted) return;
        setLoadError(e instanceof Error ? e.message : String(e));
      }
    })();

    return () => ac.abort();
  }, [take, recorderBaseUrl]);

  useEffect(() => {
    const el = videoRef.current;
    if (!el) return;
    const onTime = () => setCurrentTime(el.currentTime);
    const onPlay = () => setPlaying(true);
    const onPause = () => setPlaying(false);
    const onErr = () => {
      if (!preferHls && mp4Src && hlsSrc) {
        setPreferHls(true);
        setMediaError("mp4 を再生できなかったため HLS に切り替えました。");
        return;
      }
      setMediaError("映像を再生できません（mp4 / HLS とも失敗、または未対応）。");
    };
    el.addEventListener("timeupdate", onTime);
    el.addEventListener("seeked", onTime);
    el.addEventListener("play", onPlay);
    el.addEventListener("pause", onPause);
    el.addEventListener("error", onErr);
    return () => {
      el.removeEventListener("timeupdate", onTime);
      el.removeEventListener("seeked", onTime);
      el.removeEventListener("play", onPlay);
      el.removeEventListener("pause", onPause);
      el.removeEventListener("error", onErr);
    };
  }, [videoSrc, preferHls, mp4Src, hlsSrc]);

  const wallNow = t0 != null ? t0 + currentTime : null;
  const imuIdx = wallNow != null ? nearestImuIndex(imuRows, wallNow) : -1;
  const imu = imuIdx >= 0 ? imuRows[imuIdx] : null;
  const nearbyCmds =
    wallNow != null ? commandsAround(cmdRows, wallNow, CMD_WINDOW_SEC, CMD_MAX) : [];

  return (
    <div className="lab-dv__format">
      <div className="lab-dv__format-meta">
        <span>
          format: <code>robot_take_v0</code>
        </span>
        <span>
          video_t0_unix: {t0 != null ? t0.toFixed(3) : "—（meta に無し）"}
        </span>
        <span>
          IMU {imuRows.length} 行 / 指令 {cmdRows.length} 行
        </span>
        <span>{playing ? "再生中" : "停止"}</span>
        {mediaKind ? <span>media: {mediaKind}</span> : null}
      </div>

      {loadError ? (
        <div className="lab-dv__error" role="alert">
          {loadError}
        </div>
      ) : null}
      {mediaError ? (
        <div className="lab-dv__error" role="alert">
          {mediaError}
        </div>
      ) : null}

      <div className="lab-dv__format-grid">
        <section className="lab-dv__panel" aria-label="動画">
          <h3 className="lab-dv__panel-title">映像</h3>
          {!videoSrc ? (
            <p className="lab-dv__hint">video.mp4 / index.m3u8 がありません。</p>
          ) : (
            <video
              key={videoSrc}
              ref={videoRef}
              className="lab-dv__video"
              src={videoSrc}
              controls
              playsInline
              preload="metadata"
            />
          )}
          <p className="lab-dv__hint">
            t={currentTime.toFixed(3)}s
            {wallNow != null ? ` / wall=${wallNow.toFixed(3)}` : null}
            {hlsSrc && mp4Src ? (
              <>
                {" · "}
                <button
                  type="button"
                  className="lab-dv__linkish"
                  onClick={() => {
                    setPreferHls((v) => !v);
                    setMediaError(null);
                  }}
                >
                  {preferHls ? "mp4 を試す" : "HLS を使う"}
                </button>
              </>
            ) : null}
          </p>
        </section>

        <section className="lab-dv__panel" aria-label="IMU">
          <h3 className="lab-dv__panel-title">IMU（映像時刻）</h3>
          <ImuAttitudeGauges
            pitch={imu?.pitch}
            roll={imu?.roll}
            connected={imu != null}
          />
          <pre className="lab-dv__pre">
            {imu
              ? `wall=${imu.wall_unix.toFixed(3)}\npitch=${imu.pitch ?? "—"}\nroll=${imu.roll ?? "—"}\nyaw=${imu.yaw ?? "—"}`
              : t0 == null
                ? "meta.video_t0_unix が無いため同期できません"
                : "この時刻の IMU がありません"}
          </pre>
        </section>

        <section className="lab-dv__panel lab-dv__panel--wide" aria-label="指令">
          <h3 className="lab-dv__panel-title">指令（±{CMD_WINDOW_SEC}s）</h3>
          {nearbyCmds.length === 0 ? (
            <p className="lab-dv__hint">付近の指令はありません。</p>
          ) : (
            <ul className="lab-dv__cmd-list">
              {nearbyCmds.map((c, i) => (
                <li key={i}>
                  <code>{c.wall_unix.toFixed(3)}</code> {c.endpoint ?? "?"}{" "}
                  <span className="lab-dv__cmd-raw">
                    {JSON.stringify(c.raw).slice(0, 120)}
                    {JSON.stringify(c.raw).length > 120 ? "…" : ""}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
