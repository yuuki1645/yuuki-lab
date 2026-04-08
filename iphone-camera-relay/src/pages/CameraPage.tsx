import { useEffect, useRef, useState } from "react";
import { io, type Socket } from "socket.io-client";

function getSocket(): Socket {
  return io({
    path: "/socket.io",
    transports: ["websocket", "polling"],
  });
}

/** iOS Safari などは HTTP では navigator.mediaDevices が無い（セキュアコンテキスト必須） */
function getMediaDevicesBlockMessage(): string | null {
  if (typeof window === "undefined" || typeof navigator === "undefined") {
    return null;
  }
  const httpsHint = [
    "このページは HTTP で開かれています。iPhone の Safari ではカメラを使えません。",
    "PC に iphone-camera-relay フォルダ直下へ cert.pem と key.pem を置き、npm run dev（または npm start）で起動したあと、",
    "アドレスバーを https://（例: https://192.168.x.x:5010/camera）に変更してアクセスしてください。",
    "初回は自己署名証明書の警告が出るので「詳細」→信頼して続行してください。",
  ].join(" ");

  if (!window.isSecureContext) {
    return httpsHint;
  }

  const md = navigator.mediaDevices as MediaDevices | undefined;
  if (md && typeof md.getUserMedia === "function") {
    return null;
  }
  return "このブラウザではカメラ API（getUserMedia）を利用できません。";
}

export default function CameraPage() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const socketRef = useRef<Socket | null>(null);

  const [status, setStatus] = useState("未接続");

  useEffect(() => {
    const socket = getSocket();
    socketRef.current = socket;
    socket.on("connect", () => setStatus("Socket接続済み"));
    socket.on("disconnect", () => setStatus("切断されました"));
    socket.on("connect_error", (err) =>
      setStatus(`接続エラー: ${err.message}`),
    );
    return () => {
      socket.disconnect();
      socketRef.current = null;
    };
  }, []);

  async function startCamera(): Promise<void> {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    const socket = socketRef.current;
    if (!video || !canvas || !socket) return;

    const block = getMediaDevicesBlockMessage();
    if (block) {
      setStatus(`カメラ起動失敗: ${block}`);
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: "environment" },
          width: { ideal: 640 },
          height: { ideal: 480 },
        },
        audio: false,
      });
      streamRef.current = stream;
      video.srcObject = stream;
      await video.play();
      setStatus("カメラ起動済み");

      const ctx = canvas.getContext("2d");
      if (!ctx) {
        setStatus("Canvas 非対応");
        return;
      }

      if (timerRef.current) clearInterval(timerRef.current);
      timerRef.current = setInterval(() => {
        if (!video.videoWidth || !video.videoHeight) return;
        const w = 320;
        const h = Math.round(video.videoHeight * (w / video.videoWidth));
        canvas.width = w;
        canvas.height = h;
        ctx.drawImage(video, 0, 0, w, h);
        canvas.toBlob(
          (blob) => {
            if (blob && socket.connected) {
              void blob.arrayBuffer().then((buf) => {
                socket.emit("camera_frame", buf);
              });
            }
          },
          "image/jpeg",
          0.6,
        );
      }, 100);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      console.error(err);
      setStatus(`カメラ起動失敗: ${message}`);
    }
  }

  function stopCamera(): void {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    setStatus("停止しました");
  }

  const cameraBlockHint = getMediaDevicesBlockMessage();

  return (
    <main style={{ padding: 16, maxWidth: 520 }}>
      <h2 style={{ marginTop: 0 }}>iPhone カメラ送信</h2>
      {cameraBlockHint ? (
        <div
          role="alert"
          style={{
            background: "#fff8e1",
            border: "1px solid #ffc107",
            borderRadius: 8,
            padding: 12,
            fontSize: 14,
            color: "#5d4037",
            marginBottom: 12,
          }}
        >
          {cameraBlockHint}
        </div>
      ) : null}
      <p style={{ color: "#666", fontSize: 14 }}>
        開始を押すとカメラ映像をサーバーへ送ります。
      </p>
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        style={{
          width: "100%",
          maxWidth: 480,
          border: "1px solid #ccc",
          borderRadius: 8,
          background: "#111",
        }}
      />
      <canvas ref={canvasRef} width={320} height={240} hidden />
      <div style={{ marginTop: 12 }}>
        <button
          type="button"
          onClick={() => void startCamera()}
          style={{
            padding: "12px 16px",
            fontSize: 16,
            marginRight: 8,
            cursor: "pointer",
          }}
        >
          開始
        </button>
        <button
          type="button"
          onClick={stopCamera}
          style={{
            padding: "12px 16px",
            fontSize: 16,
            cursor: "pointer",
          }}
        >
          停止
        </button>
      </div>
      <p style={{ color: "#666", fontSize: 14, marginTop: 12 }}>{status}</p>
    </main>
  );
}
