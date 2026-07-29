import { useCallback, useMemo, useState } from "react";
import { getCaptureRealtimeBaseUrl, getCaptureRealtimeStreamUrl } from "@/shared/constants";
import "./LiveCapturePage.css";

/**
 * メインPC上の serve_realtime.py（MJPEG :8766）を Hub から監視するページ。
 * iPad では robotics-hub と同じ hostname の :8766 へ接続する。
 */
export default function LiveCapturePage() {
  const baseUrl = useMemo(() => getCaptureRealtimeBaseUrl(), []);
  // 再接続時にキャッシュを避けるため nonce を付与
  const [nonce, setNonce] = useState(() => Date.now());
  const [imgError, setImgError] = useState(false);

  const streamUrl = useMemo(
    () => getCaptureRealtimeStreamUrl() + "?t=" + String(nonce),
    [nonce]
  );

  const reconnect = useCallback(() => {
    setImgError(false);
    setNonce(Date.now());
  }, []);

  return (
    <div className="live-capture">
      <header className="live-capture__header">
        <h1>実機カメラ（ライブ）</h1>
        <p>
          メインPCの <code>serve_realtime.py</code>（MJPEG）を表示します。低遅延監視用で、巻き戻しはできません。
          Hub と同時起動する場合は <code>npm run dev:lab</code> を使ってください。
        </p>
      </header>

      <div className="live-capture__meta">
        <span className="live-capture__url">{baseUrl}</span>
        <button type="button" className="live-capture__btn" onClick={reconnect}>
          再接続
        </button>
      </div>

      {imgError ? (
        <div className="live-capture__error" role="alert">
          映像を取得できません。<code>serve_realtime.py</code> が起動しているか、Streaming Center
          がデバイスを占有していないか、ファイアウォール（TCP 8766）を確認してください。
        </div>
      ) : null}

      <div className="live-capture__stage">
        {/* video ではなく img。MJPEG multipart を低遅延表示する */}
        <img
          key={streamUrl}
          className="live-capture__img"
          src={streamUrl}
          alt="実機カメラのライブ映像"
          onError={() => setImgError(true)}
          onLoad={() => setImgError(false)}
        />
      </div>
    </div>
  );
}
