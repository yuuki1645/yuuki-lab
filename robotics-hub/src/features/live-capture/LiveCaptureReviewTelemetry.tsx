import { useEffect, useMemo, useState } from "react";
import ImuAttitudeGauges from "@/shared/components/ImuAttitudeGauges";
import {
  commandsAround,
  nearestImuIndex,
  parseCommandJsonl,
  parseImuJsonl,
  type CommandJsonlRow,
  type ImuJsonlRow,
} from "@/features/lab-data-viewer/formats/robot_take_v0/parseTakeV0";

const CMD_WINDOW_SEC = 0.5;
const CMD_MAX = 16;

export type LiveCaptureReviewTelemetryProps = {
  recorderBaseUrl: string;
  /** 相対パス（/data/...）または null */
  imuUrl: string | null;
  commandsUrl: string | null;
  videoT0Unix: number | null;
  /** 見返し video の currentTime（秒） */
  reviewCurrentTime: number;
  /** 録画中は jsonl を定期再取得 */
  recording: boolean;
  enabled: boolean;
};

/**
 * 見返し映像の再生時刻に同期した IMU / 指令表示。
 * ライブ用ゲージとは別カードで併記する。
 */
export default function LiveCaptureReviewTelemetry({
  recorderBaseUrl,
  imuUrl,
  commandsUrl,
  videoT0Unix,
  reviewCurrentTime,
  recording,
  enabled,
}: LiveCaptureReviewTelemetryProps) {
  const [imuRows, setImuRows] = useState<ImuJsonlRow[]>([]);
  const [cmdRows, setCmdRows] = useState<CommandJsonlRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [rowsUpdatedAt, setRowsUpdatedAt] = useState<number | null>(null);

  useEffect(() => {
    if (!enabled) {
      setImuRows([]);
      setCmdRows([]);
      return;
    }
    let cancelled = false;

    const load = async () => {
      try {
        const tasks: Promise<void>[] = [];
        if (imuUrl) {
          tasks.push(
            (async () => {
              const res = await fetch(recorderBaseUrl + imuUrl, { cache: "no-store" });
              if (!res.ok) throw new Error("imu.jsonl HTTP " + String(res.status));
              const rows = parseImuJsonl(await res.text());
              if (!cancelled) setImuRows(rows);
            })()
          );
        } else if (!cancelled) {
          setImuRows([]);
        }
        if (commandsUrl) {
          tasks.push(
            (async () => {
              const res = await fetch(recorderBaseUrl + commandsUrl, {
                cache: "no-store",
              });
              if (!res.ok) throw new Error("servo.jsonl HTTP " + String(res.status));
              const rows = parseCommandJsonl(await res.text());
              if (!cancelled) setCmdRows(rows);
            })()
          );
        } else if (!cancelled) {
          setCmdRows([]);
        }
        await Promise.all(tasks);
        if (!cancelled) {
          setError(null);
          setRowsUpdatedAt(Date.now());
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    };

    void load();
    const intervalMs = recording ? 1500 : 0;
    const id =
      intervalMs > 0
        ? window.setInterval(() => {
            void load();
          }, intervalMs)
        : 0;
    return () => {
      cancelled = true;
      if (id) window.clearInterval(id);
    };
  }, [enabled, recorderBaseUrl, imuUrl, commandsUrl, recording]);

  const wallNow = useMemo(() => {
    if (videoT0Unix == null || !Number.isFinite(videoT0Unix)) return null;
    return videoT0Unix + reviewCurrentTime;
  }, [videoT0Unix, reviewCurrentTime]);

  const imuIdx = wallNow != null ? nearestImuIndex(imuRows, wallNow) : -1;
  const imu = imuIdx >= 0 ? imuRows[imuIdx] : null;
  const nearbyCmds =
    wallNow != null ? commandsAround(cmdRows, wallNow, CMD_WINDOW_SEC, CMD_MAX) : [];

  if (!enabled) {
    return (
      <section className="live-capture__data-card live-capture__data-card--placeholder">
        <h3 className="live-capture__data-card-title">見返し時点のデータ</h3>
        <p className="live-capture__hint">
          録画を開始すると、見返し映像の再生位置に対応する IMU / 指令がここに出ます（ライブ表示とは別）。
        </p>
      </section>
    );
  }

  return (
    <section className="live-capture__data-card" aria-label="見返し時点のデータ">
      <h3 className="live-capture__data-card-title">見返し時点のデータ</h3>
      <p className="live-capture__data-meta">
        t={reviewCurrentTime.toFixed(2)}s
        {wallNow != null ? ` / wall=${wallNow.toFixed(3)}` : " / t0 未設定"}
        {" · "}
        IMU {imuRows.length} 行 / 指令 {cmdRows.length} 行
        {rowsUpdatedAt != null ? " · 更新済" : null}
      </p>
      {error ? (
        <p className="live-capture__hint" role="alert">
          {error}
        </p>
      ) : null}
      <ImuAttitudeGauges
        pitch={imu?.pitch}
        roll={imu?.roll}
        connected={imu != null}
      />
      <pre className="live-capture__review-pre">
        {imu
          ? `pitch=${imu.pitch?.toFixed(2) ?? "—"}°  roll=${imu.roll?.toFixed(2) ?? "—"}°\nyaw=${imu.yaw?.toFixed(2) ?? "—"}°`
          : videoT0Unix == null
            ? "video_t0_unix が無いため同期できません"
            : "この再生位置の IMU がまだありません"}
      </pre>
      <h4 className="live-capture__data-subhead">指令（±{CMD_WINDOW_SEC}s）</h4>
      {nearbyCmds.length === 0 ? (
        <p className="live-capture__hint">付近の指令はありません。</p>
      ) : (
        <ul className="live-capture__cmd-list">
          {nearbyCmds.map((c, i) => (
            <li key={i}>
              <code>{(c.wall_unix - (videoT0Unix ?? c.wall_unix)).toFixed(2)}s</code>{" "}
              {c.endpoint ?? "?"}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
