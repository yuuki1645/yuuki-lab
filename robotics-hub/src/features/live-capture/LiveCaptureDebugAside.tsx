import { useEffect, useState } from "react";
import ImuAttitudeGauges from "@/shared/components/ImuAttitudeGauges";
import LiveCaptureReviewTelemetry, {
  type LiveCaptureReviewTelemetryProps,
} from "@/features/live-capture/LiveCaptureReviewTelemetry";
import { fetchRecorderImuLatest } from "@/shared/recorderApi";
import type { ImuDaemonSamplePayload } from "@/shared/types/imuDaemon";

type BridgeUi = {
  status: string;
  url?: string;
  lastError?: string | null;
};

type LiveCaptureDebugAsideProps = {
  /** 見返し再生時刻に同期したテレメトリ（ライブ表示とは別） */
  review: LiveCaptureReviewTelemetryProps;
};

/**
 * 実機カメラ右ペイン。
 * - 上: ライブ IMU（Pi→Recorder の最新値）
 * - 下: 見返し映像の再生位置に同期した IMU / 指令
 */
export default function LiveCaptureDebugAside({ review }: LiveCaptureDebugAsideProps) {
  const [sample, setSample] = useState<ImuDaemonSamplePayload | null>(null);
  const [bridge, setBridge] = useState<BridgeUi>({ status: "connecting" });
  const [pollError, setPollError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const tick = async () => {
      try {
        const { sample: s, imu_bridge: b } = await fetchRecorderImuLatest();
        if (cancelled) return;
        setSample(s);
        setBridge({
          status: b?.status ?? "unknown",
          url: b?.url,
          lastError: b?.last_error ?? null,
        });
        setPollError(null);
      } catch (e) {
        if (cancelled) return;
        setPollError(e instanceof Error ? e.message : String(e));
        setBridge((prev) => ({ ...prev, status: "error" }));
      }
    };

    void tick();
    const id = window.setInterval(() => {
      void tick();
    }, 125);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  const statusClass =
    bridge.status === "connected"
      ? "connected"
      : bridge.status === "connecting"
        ? "connecting"
        : "disconnected";

  return (
    <aside className="live-capture__aside" aria-label="デバッグ・センサー">
      <header className="live-capture__aside-header">
        <h2 className="live-capture__aside-title">デバッグ / センサー</h2>
        <p className="live-capture__aside-sub">
          via robot-recorder
          {bridge.url ? ` ← ${bridge.url}` : null}
        </p>
      </header>

      <section className="live-capture__aside-card" aria-label="ライブ IMU">
        <h3 className="live-capture__aside-card-title">ライブ IMU（リアルタイム）</h3>
        <p className="live-capture__aside-meta">
          ブリッジ:{" "}
          <span className={"live-capture__ws live-capture__ws--" + statusClass}>
            {bridge.status}
          </span>
          {bridge.lastError ? ` / ${bridge.lastError}` : null}
          {pollError ? ` / ${pollError}` : null}
        </p>
        <ImuAttitudeGauges
          pitch={sample?.angle?.pitch}
          roll={sample?.angle?.roll}
          connected={bridge.status === "connected"}
        />
      </section>

      <LiveCaptureReviewTelemetry {...review} />
    </aside>
  );
}
