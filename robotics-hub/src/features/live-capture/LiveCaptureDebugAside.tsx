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
 * 実機カメラ右ペイン。
 * IMU は Recorder（Pi→Recorder→Hub）をポーリングし、左の MJPEG 再描画を誘発しない。
 */
export default function LiveCaptureDebugAside() {
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

      <section className="live-capture__aside-card" aria-label="IMU 姿勢">
        <h3 className="live-capture__aside-card-title">IMU 姿勢（ピッチ／ロール）</h3>
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

      <section className="live-capture__aside-card live-capture__aside-card--placeholder">
        <h3 className="live-capture__aside-card-title">ログ・その他</h3>
        <p className="live-capture__hint">
          指令ログは Pi→Recorder（記録中のみ take に保存）。今後ここに足圧などを追加します。
        </p>
      </section>
    </aside>
  );
}
