import { useEffect, useRef, useState } from "react";
import { io, type Socket } from "socket.io-client";

function getSocket(): Socket {
  return io({
    path: "/socket.io",
    transports: ["websocket", "polling"],
  });
}

export default function MonitorPage() {
  const lastUrlRef = useRef<string | null>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const [status, setStatus] = useState("待機中...");

  useEffect(() => {
    const socket = getSocket();
    const img = imgRef.current;

    socket.on("connect", () =>
      setStatus("Socket接続済み。映像待機中..."),
    );
    socket.on("disconnect", () => setStatus("切断されました"));
    socket.on("connect_error", (err) =>
      setStatus(`接続エラー: ${err.message}`),
    );

    socket.on("frame_update", (data: unknown) => {
      let chunk: ArrayBuffer | null = null;
      if (data instanceof ArrayBuffer) chunk = data;
      else if (data instanceof Uint8Array) {
        chunk = data.buffer.slice(
          data.byteOffset,
          data.byteOffset + data.byteLength,
        );
      }
      if (!chunk) return;
      const blob = new Blob([chunk], { type: "image/jpeg" });
      const url = URL.createObjectURL(blob);
      if (img) img.src = url;
      setStatus("受信中");
      if (lastUrlRef.current) URL.revokeObjectURL(lastUrlRef.current);
      lastUrlRef.current = url;
    });

    return () => {
      socket.disconnect();
      if (lastUrlRef.current) {
        URL.revokeObjectURL(lastUrlRef.current);
        lastUrlRef.current = null;
      }
    };
  }, []);

  return (
    <main style={{ padding: 16 }}>
      <h2 style={{ marginTop: 0 }}>受信映像モニター</h2>
      <p style={{ color: "#666", fontSize: 14, marginBottom: 12 }}>
        {status}
      </p>
      <img
        ref={imgRef}
        alt="camera stream"
        style={{
          width: "100%",
          maxWidth: 960,
          border: "1px solid #ccc",
          borderRadius: 8,
          background: "#111",
          minHeight: 240,
        }}
      />
    </main>
  );
}
