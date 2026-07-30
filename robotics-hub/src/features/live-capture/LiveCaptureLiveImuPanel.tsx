import { useEffect, useState } from "react";
import ImuAttitudeGauges from "@/shared/components/ImuAttitudeGauges";
import { fetchRecorderImuLatest } from "@/shared/recorderApi";
import type { ImuDaemonSamplePayload } from "@/shared/types/imuDaemon";

type BridgeUi = {
  status: string;
  url?: string;
  lastError?: string | null;
};

/**
 * ライブ段の右カラム: Pi→Recorder 経由のリアルタイム IMU。
 * （見返し同期データとは別コンポーネント）
 */
export default function LiveCaptureLiveImuPanel() {
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
    <section className="live-capture__data-card" aria-label="ライブ IMU">
      <h3 className="live-capture__data-card-title">ライブ IMU（リアルタイム）</h3>
      <p className="live-capture__data-meta">
        via robot-recorder
        {bridge.url ? ` ← ${bridge.url}` : null}
      </p>
      <p className="live-capture__data-meta">
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
  );
}
