import { useEffect, useMemo } from "react";
import { useDaemonImuTelemetry } from "@/shared/contexts/DaemonImuTelemetryContext";
import {
  ACC_LABELS,
  ANGLE_LABELS,
  GYRO_LABELS,
  ImuPerfTimestampReadout,
  VecTable,
  daemonSampleToAccelGyroAngle,
  wsStatusLabel,
} from "./telemetryUi";
import "./TelemetryPage.css";

export default function DeviceTelemetryPage() {
  const imuStream = useDaemonImuTelemetry();
  const csvRecording = imuStream.lastStatus?.csv_recording === true;
  const csvEnabledOnServer = imuStream.lastStatus?.csv_enabled !== false;
  const imuStreaming = Boolean(imuStream.lastStatus?.streaming);

  const { acc, gyro, angle } = useMemo(
    () => daemonSampleToAccelGyroAngle(imuStream.lastSample),
    [imuStream.lastSample]
  );

  useEffect(() => {
    if (imuStream.wsStatus === "connected") {
      imuStream.requestImuStatus();
    }
  }, [imuStream.wsStatus, imuStream.requestImuStatus]);

  return (
    <div className="telemetry">
      <header className="telemetry__header">
        <h1>実機テレメトリ</h1>
        <p>
          <code>robot-daemon</code> の IMU（<code>imu/start</code> 後の <code>imu/sample</code>
          ）を表示します。ラズパイへの CSV ログは <code>imu/log_start</code> /{" "}
          <code>imu/log_stop</code> で開始・停止します（ハブ内の別画面に移っても接続は維持されます）。
        </p>
      </header>

      <div className="telemetry__status">
        <span className={"telemetry__status-badge telemetry__status-badge--" + imuStream.wsStatus}>
          {wsStatusLabel(imuStream.wsStatus)}
        </span>
        <span className="telemetry__url">{imuStream.url}</span>
        <span className="telemetry__meta">
          streaming: {String(Boolean(imuStream.lastStatus?.streaming))}
        </span>
        <span className="telemetry__meta">受信サンプル数: {imuStream.sampleCount}</span>
        <span className="telemetry__meta">
          CSV ログ: {csvRecording ? "記録中" : "停止"}
          {imuStream.lastStatus?.csv_enabled === false ? "（サーバ無効）" : ""}
        </span>
        {imuStream.lastSample?.mock ? (
          <span className="telemetry__logical-tag">モック IMU</span>
        ) : null}
      </div>

      <div className="telemetry__perf-readout" aria-live="polite">
        <span className="telemetry__perf-label">
          perf_timestamp（ラズパイ <code>perf_counter</code>、秒）
        </span>
        <ImuPerfTimestampReadout perfS={imuStream.lastSample?.timestamp} />
      </div>

      {imuStream.lastError && <div className="telemetry__error">{imuStream.lastError}</div>}
      {imuStream.lastImuError && (
        <div className="telemetry__error">IMU: {imuStream.lastImuError}</div>
      )}
      {imuStream.lastLogStatus?.ok === false && (
        <div className="telemetry__error">
          CSV ログ:{" "}
          {imuStream.lastLogStatus.reason === "csv_disabled"
            ? "サーバで CSV が無効です（IMU_LOG_DISABLE 等）"
            : imuStream.lastLogStatus.reason === "imu_not_streaming"
              ? "先に IMU ストリームを開始してください"
              : imuStream.lastLogStatus.reason ?? "開始に失敗しました"}
        </div>
      )}

      <div className="telemetry__actions">
        <button type="button" className="telemetry__btn" onClick={() => imuStream.reconnect()}>
          IMU 再接続（imu/start を再送）
        </button>
        <button
          type="button"
          className="telemetry__btn"
          onClick={() => imuStream.startCsvLog()}
          disabled={
            imuStream.wsStatus !== "connected" ||
            !imuStreaming ||
            !csvEnabledOnServer ||
            csvRecording
          }
        >
          CSV ログ開始
        </button>
        <button
          type="button"
          className="telemetry__btn"
          onClick={() => imuStream.stopCsvLog()}
          disabled={imuStream.wsStatus !== "connected" || !csvRecording}
        >
          CSV ログ停止
        </button>
      </div>

      <div className="telemetry__data-zones">
        <div className="telemetry__grid">
          <div className="telemetry__panel">
            <h2>実機 IMU（局所・robot-daemon）</h2>
            <p className="telemetry__meta">
              MPU6050 の生スケールを 16384 で割った値（g）。
            </p>
            <VecTable
              title="加速度（スケール g 相当）"
              labels={ACC_LABELS}
              values={acc}
              valueHeader="値"
              noPanel
            />
            <VecTable
              title="角速度 (deg/s)"
              labels={GYRO_LABELS}
              values={gyro}
              valueHeader="値"
              noPanel
            />
          </div>
          <div className="telemetry__panel">
            <h2>実機 IMU（推定角 deg）</h2>
            <VecTable
              title=""
              labels={ANGLE_LABELS}
              values={angle}
              valueHeader="値"
              noPanel
              showTitle={false}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
