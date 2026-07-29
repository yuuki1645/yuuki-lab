import { memo } from "react";

type LiveMjpegViewProps = {
  /** MJPEG URL（再接続時のみ変わる想定） */
  streamUrl: string;
  onErrorChange?: (hasError: boolean) => void;
};

/**
 * 低遅延ライブ映像。
 * IMU など親の高頻度再描画から隔離するため memo 化する（iPad Chrome の MJPEG 対策）。
 */
function LiveMjpegView({ streamUrl, onErrorChange }: LiveMjpegViewProps) {
  return (
    <section className="live-capture__section" aria-label="ライブ">
      <h2 className="live-capture__section-title">ライブ（低遅延）</h2>
      <div className="live-capture__stage live-capture__stage--live">
        <img
          className="live-capture__img"
          src={streamUrl}
          alt="実機カメラのライブ映像"
          onError={() => onErrorChange?.(true)}
          onLoad={() => onErrorChange?.(false)}
        />
      </div>
    </section>
  );
}

export default memo(LiveMjpegView);
