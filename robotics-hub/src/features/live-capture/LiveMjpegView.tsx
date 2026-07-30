import { memo, useMemo } from "react";

type LiveMjpegViewProps = {
  /** MJPEG URL（再接続時のみ変わる想定） */
  streamUrl: string;
};

/**
 * 低遅延ライブ映像。
 *
 * React ツリー外の iframe に MJPEG を閉じ込める。
 * 親／兄弟（IMU ゲージ等）の高頻度再描画が iPad Chrome の multipart 描画を
 * 止める問題への対策。
 */
function LiveMjpegView({ streamUrl }: LiveMjpegViewProps) {
  // iframe 内は独立 Document。hub 側の DOM 更新の影響を受けない。
  const srcDoc = useMemo(() => {
    const safeUrl = streamUrl
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/</g, "&lt;");
    return `<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<meta name="color-scheme" content="dark"/>
<style>
  html, body {
    margin: 0;
    width: 100%;
    height: 100%;
    background: #000;
    overflow: hidden;
  }
  img {
    display: block;
    width: 100%;
    height: 100%;
    object-fit: contain;
    background: #000;
  }
</style>
</head>
<body>
  <img src="${safeUrl}" alt="実機カメラのライブ映像" />
</body>
</html>`;
  }, [streamUrl]);

  // 段タイトルは親（LiveCapturePage）が付ける。ここは映像ステージのみ。
  return (
    <div className="live-capture__stage live-capture__stage--live">
      <iframe
        key={streamUrl}
        className="live-capture__img live-capture__iframe"
        title="実機カメラのライブ映像"
        srcDoc={srcDoc}
        // スクリプト無効のままネットワーク画像（MJPEG）は読める
        sandbox=""
        // スクロールバーを出さない
        scrolling="no"
      />
    </div>
  );
}

export default memo(LiveMjpegView);
