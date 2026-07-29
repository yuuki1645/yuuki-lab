import ImuAttitudeGauges from "@/shared/components/ImuAttitudeGauges";
import { useDaemonImuTelemetry } from "@/shared/contexts/DaemonImuTelemetryContext";

/**
 * 実機カメラ右ペイン。IMU 購読をここに閉じ込めて左の MJPEG 再描画を誘発しない。
 */
export default function LiveCaptureDebugAside() {
  const imu = useDaemonImuTelemetry();

  return (
    <aside className="live-capture__aside" aria-label="デバッグ・センサー">
      <header className="live-capture__aside-header">
        <h2 className="live-capture__aside-title">デバッグ / センサー</h2>
        <p className="live-capture__aside-sub">robot-daemon（{imu.url}）</p>
      </header>

      <section className="live-capture__aside-card" aria-label="IMU 姿勢">
        <h3 className="live-capture__aside-card-title">IMU 姿勢（ピッチ／ロール）</h3>
        <p className="live-capture__aside-meta">
          状態:{" "}
          <span className={"live-capture__ws live-capture__ws--" + imu.wsStatus}>
            {imu.wsStatus}
          </span>
          {imu.lastError ? ` / ${imu.lastError}` : null}
        </p>
        <ImuAttitudeGauges
          pitch={imu.lastSample?.angle?.pitch}
          roll={imu.lastSample?.angle?.roll}
          connected={imu.wsStatus === "connected"}
        />
      </section>

      <section className="live-capture__aside-card live-capture__aside-card--placeholder">
        <h3 className="live-capture__aside-card-title">ログ・その他</h3>
        <p className="live-capture__hint">今後、デバッグログや他センサーをここに追加します。</p>
      </section>
    </aside>
  );
}
