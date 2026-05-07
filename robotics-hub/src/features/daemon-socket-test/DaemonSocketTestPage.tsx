import { useEffect, useMemo, useRef, useState } from "react";
import { io, type Socket } from "socket.io-client";
import { SERVO_DAEMON_URL } from "@/shared/constants";
import "./DaemonSocketTestPage.css";

type WsStatus = "disconnected" | "connecting" | "connected";

interface LogEntry {
  id: number;
  time: string;
  message: string;
}

const MAX_LOGS = 200;

export default function DaemonSocketTestPage() {
  const [status, setStatus] = useState<WsStatus>("disconnected");
  const [channel, setChannel] = useState(0);
  const [mode, setMode] = useState<"logical" | "physical">("logical");
  const [angle, setAngle] = useState(0);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const socketRef = useRef<Socket | null>(null);
  const logIdRef = useRef(0);

  const wsUrl = useMemo(() => SERVO_DAEMON_URL, []);

  const pushLog = (message: string) => {
    const newEntry: LogEntry = {
      id: ++logIdRef.current,
      time: new Date().toLocaleTimeString(),
      message,
    };
    setLogs((prev) => [newEntry, ...prev].slice(0, MAX_LOGS));
  };

  const connect = () => {
    if (socketRef.current) return;

    setStatus("connecting");
    const socket = io(wsUrl, {
      transports: ["websocket"],
      reconnection: true,
      reconnectionAttempts: Infinity,
      reconnectionDelay: 500,
    });
    socketRef.current = socket;

    socket.on("connect", () => {
      setStatus("connected");
      pushLog(`[connect] connected: id=${socket.id}`);
    });

    socket.on("disconnect", (reason) => {
      setStatus("disconnected");
      pushLog(`[disconnect] reason=${reason}`);
    });

    socket.on("connection/status", (payload) => {
      pushLog(`[recv] connection/status ${JSON.stringify(payload)}`);
    });
    socket.on("servo/result", (payload) => {
      pushLog(`[recv] servo/result ${JSON.stringify(payload)}`);
    });
    socket.on("servo/result_multiple", (payload) => {
      pushLog(`[recv] servo/result_multiple ${JSON.stringify(payload)}`);
    });
    socket.on("servo/transition_started", (payload) => {
      pushLog(`[recv] servo/transition_started ${JSON.stringify(payload)}`);
    });
    socket.on("error", (payload) => {
      pushLog(`[recv] error ${JSON.stringify(payload)}`);
    });
  };

  const disconnect = () => {
    const socket = socketRef.current;
    if (!socket) return;
    socket.removeAllListeners();
    socket.disconnect();
    socketRef.current = null;
    setStatus("disconnected");
    pushLog("[action] disconnected manually");
  };

  const emitSetServo = () => {
    const socket = socketRef.current;
    if (!socket) {
      pushLog("[warn] socket not connected");
      return;
    }
    const payload = { ch: channel, mode, angle };
    socket.emit("servo/set", payload);
    pushLog(`[send] servo/set ${JSON.stringify(payload)}`);
  };

  useEffect(() => {
    return () => {
      const socket = socketRef.current;
      if (socket) {
        socket.removeAllListeners();
        socket.disconnect();
        socketRef.current = null;
      }
    };
  }, []);

  return (
    <div className="ws-test">
      <h1 className="ws-test-title">Daemon Socket Test</h1>
      <p className="ws-test-lead">
        `robot-daemon` との Socket.IO 接続とイベント送受信を確認するためのテスト画面です。
      </p>

      <section className="ws-test-card">
        <h2>接続</h2>
        <p>
          URL: <code>{wsUrl}</code>
        </p>
        <p>
          状態: <strong>{status}</strong>
        </p>
        <div className="ws-test-row">
          <button type="button" onClick={connect} disabled={status !== "disconnected"}>
            接続
          </button>
          <button type="button" onClick={disconnect} disabled={status === "disconnected"}>
            切断
          </button>
          <button type="button" onClick={() => setLogs([])}>
            ログクリア
          </button>
        </div>
      </section>

      <section className="ws-test-card">
        <h2>送信テスト（servo/set）</h2>
        <div className="ws-test-form">
          <label>
            channel
            <input
              type="number"
              value={channel}
              onChange={(e) => setChannel(Number(e.target.value))}
            />
          </label>
          <label>
            mode
            <select value={mode} onChange={(e) => setMode(e.target.value as "logical" | "physical")}>
              <option value="logical">logical</option>
              <option value="physical">physical</option>
            </select>
          </label>
          <label>
            angle
            <input
              type="number"
              step="0.1"
              value={angle}
              onChange={(e) => setAngle(Number(e.target.value))}
            />
          </label>
        </div>
        <div className="ws-test-row">
          <button type="button" onClick={emitSetServo} disabled={status !== "connected"}>
            servo/set を送信
          </button>
        </div>
      </section>

      <section className="ws-test-card">
        <h2>イベントログ</h2>
        <div className="ws-test-log">
          {logs.length === 0 ? <p className="ws-test-empty">ログはまだありません。</p> : null}
          {logs.map((entry) => (
            <p key={entry.id}>
              [{entry.time}] {entry.message}
            </p>
          ))}
        </div>
      </section>
    </div>
  );
}
