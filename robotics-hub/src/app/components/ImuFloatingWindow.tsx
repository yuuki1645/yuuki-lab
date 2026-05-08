import type { ImuDaemonStream } from "@/shared/hooks/useImuDaemonStream";
import { useFloatingPanelDrag } from "@/shared/hooks/useFloatingPanelDrag";

function fmt2(value?: number) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  return value.toFixed(2);
}

type ImuFloatingWindowProps = {
  open: boolean;
  onClose: () => void;
  stream: ImuDaemonStream;
};

const PANEL_W = 320;
const PANEL_H = 420;

export default function ImuFloatingWindow({ open, onClose, stream }: ImuFloatingWindowProps) {
  const {
    wsStatus,
    rateHz,
    setRateHz,
    applyRate,
    imuStatus,
    imuSample,
    lastError,
  } = stream;

  const { pos, headerPointerHandlers } = useFloatingPanelDrag({
    panelOpen: open,
    initial: { x: 24, y: 96 },
    panelWidth: PANEL_W,
    panelHeight: PANEL_H,
  });

  if (!open) return null;

  return (
    <div
      className="imu-float"
      style={{ left: pos.x, top: pos.y, width: PANEL_W }}
      role="dialog"
      aria-labelledby="imu-float-title"
    >
      <div className="imu-float-header" {...headerPointerHandlers}>
        <span id="imu-float-title" className="imu-float-title">
          IMU センサー
        </span>
        <button
          type="button"
          className="imu-float-close"
          aria-label="閉じる"
          onClick={onClose}
        >
          ×
        </button>
      </div>

      <div className="imu-float-body">
        <div className="imu-float-meta">
          <span>
            接続: <strong>{wsStatus}</strong>
          </span>
          <span>
            ストリーム:{" "}
            <strong>{imuStatus?.streaming ? "ON" : "—"}</strong>
          </span>
          <label className="imu-float-rate">
            Hz
            <input
              type="number"
              min={1}
              max={200}
              value={rateHz}
              disabled={wsStatus !== "connected"}
              onChange={(e) => setRateHz(Number(e.target.value))}
              onBlur={applyRate}
            />
          </label>
        </div>

        {lastError ? (
          <p className="imu-float-error" role="alert">
            {lastError}
          </p>
        ) : null}

        <div className="imu-float-status">
          <span>sensor: {imuStatus?.sensor?.enabled ? "OK" : "—"}</span>
          <span className="imu-float-status-err">
            {imuStatus?.sensor?.error ?? ""}
          </span>
        </div>

        {!imuSample ? (
          <p className="imu-float-placeholder">
            {wsStatus === "connected"
              ? "サンプル待ちです…"
              : "daemon に接続しています…"}
          </p>
        ) : (
          <dl className="imu-float-readings">
            <div className="imu-float-row">
              <dt>時刻</dt>
              <dd>{fmt2(imuSample.timestamp)}</dd>
            </div>
            <div className="imu-float-row">
              <dt>モック</dt>
              <dd>{imuSample.mock ? "はい" : "いいえ"}</dd>
            </div>
            <div className="imu-float-row">
              <dt>加速度 (x,y,z)</dt>
              <dd>
                {fmt2(imuSample.accel?.x)}, {fmt2(imuSample.accel?.y)},{" "}
                {fmt2(imuSample.accel?.z)}
              </dd>
            </div>
            <div className="imu-float-row">
              <dt>角速度 (x,y,z)</dt>
              <dd>
                {fmt2(imuSample.gyro?.x)}, {fmt2(imuSample.gyro?.y)},{" "}
                {fmt2(imuSample.gyro?.z)}
              </dd>
            </div>
            <div className="imu-float-row">
              <dt>姿勢 pitch / roll / yaw</dt>
              <dd>
                {fmt2(imuSample.angle?.pitch)} / {fmt2(imuSample.angle?.roll)} /{" "}
                {fmt2(imuSample.angle?.yaw)}
              </dd>
            </div>
          </dl>
        )}
      </div>
    </div>
  );
}
