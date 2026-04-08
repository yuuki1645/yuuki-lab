import type { CSSProperties } from "react";
import { Link } from "react-router-dom";

const cardStyle: CSSProperties = {
  background: "#fff",
  borderRadius: 12,
  padding: 20,
  marginTop: 16,
  border: "1px solid #ddd",
  maxWidth: 520,
};

export default function HomePage() {
  return (
    <main style={{ padding: 24 }}>
      <h1 style={{ marginTop: 0 }}>Camera Relay Server</h1>
      <div style={cardStyle}>
        <ul style={{ margin: 0, paddingLeft: 20 }}>
          <li>
            <Link to="/camera">/camera</Link> — iPhone 側（カメラ送信）
          </li>
          <li>
            <Link to="/monitor">/monitor</Link> — Windows PC 側（受信表示）
          </li>
        </ul>
      </div>
      <p style={{ color: "#666", fontSize: 14, marginTop: 16 }}>
        同一 LAN 内の PC の IP とポート（既定 5000）でアクセスしてください。iPhone
        のカメラには HTTPS（cert.pem / key.pem）が必要です。
      </p>
    </main>
  );
}
