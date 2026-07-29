import type { ImuDaemonStream } from "@/shared/hooks/useImuDaemonStream";
import { useFloatingPanelDrag } from "@/shared/hooks/useFloatingPanelDrag";
import ImuAttitudeGauges, { IMU_TILT_GAUGE_SIZE } from "@/shared/components/ImuAttitudeGauges";

type ImuAttitudeFloatingWindowProps = {
  open: boolean;
  onClose: () => void;
  stream: ImuDaemonStream;
};

/**
 * Pitch / Roll を、十字線＋赤い傾斜線の二連ゲージで表示（前後・左右軸ラベル付き）
 */
export default function ImuAttitudeFloatingWindow({
  open,
  onClose,
  stream,
}: ImuAttitudeFloatingWindowProps) {
  const { wsStatus, imuSample } = stream;

  const panelW = IMU_TILT_GAUGE_SIZE * 2 + 56;
  const panelH = 300;

  const { pos, headerPointerHandlers } = useFloatingPanelDrag({
    panelOpen: open,
    initial: { x: 360, y: 96 },
    panelWidth: panelW,
    panelHeight: panelH,
  });

  if (!open) return null;

  return (
    <div
      className="imu-attitude-float"
      style={{ left: pos.x, top: pos.y }}
      role="dialog"
      aria-labelledby="imu-attitude-title"
    >
      <div className="imu-float-header" {...headerPointerHandlers}>
        <span id="imu-attitude-title" className="imu-float-title">
          IMU 姿勢（ピッチ／ロール）
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

      <ImuAttitudeGauges
        pitch={imuSample?.angle?.pitch}
        roll={imuSample?.angle?.roll}
        connected={wsStatus === "connected"}
      />
    </div>
  );
}
