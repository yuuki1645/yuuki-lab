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

interface ImuStatusPayload {
  streaming?: boolean;
  rate_hz?: number;
  sensor?: {
    enabled?: boolean;
    error?: string;
    bus_id?: number;
    address?: number;
  };
}

interface ImuSamplePayload {
  timestamp?: number;
  accel?: { x?: number; y?: number; z?: number };
  gyro?: { x?: number; y?: number; z?: number };
  angle?: { pitch?: number; roll?: number; yaw?: number };
  mock?: boolean;
}

const MAX_LOGS = 200;

export default function DaemonSocketTestPage() {
  const [status, setStatus] = useState<WsStatus>("disconnected");
  const [channel, setChannel] = useState(0);
  const [mode, setMode] = useState<"logical" | "physical">("logical");
  const [angle, setAngle] = useState(0);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [imuRate, setImuRate] = useState(30);
  const [imuStatus, setImuStatus] = useState<ImuStatusPayload | null>(null);
  const [imuSample, setImuSample] = useState<ImuSamplePayload | null>(null);
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

  const fmt2 = (value?: number) => {
    if (typeof value !== "number" || !Number.isFinite(value)) return "-";
    return value.toFixed(2);
  };

  const fmtAligned = (value?: number, width = 8) => {
    console.log(value, width);
    if (typeof value !== "number" || !Number.isFinite(value)) return "-".padStart(width, " ");
    return value.toFixed(2).padStart(width, " ");
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
    socket.on("imu/status", (payload: ImuStatusPayload) => {
      setImuStatus(payload);
      if (typeof payload.rate_hz === "number") {
        setImuRate(Math.round(payload.rate_hz));
      }
      pushLog(`[recv] imu/status ${JSON.stringify(payload)}`);
    });
    socket.on("imu/sample", (payload: ImuSamplePayload) => {
      setImuSample(payload);
    });
    socket.on("imu/error", (payload) => {
      pushLog(`[recv] imu/error ${JSON.stringify(payload)}`);
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

  const postSetServo = async () => {
    try {
      const res = await fetch(`${SERVO_DAEMON_URL}/set`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ch: channel, mode, angle }),
      });
      const text = await res.text();
      pushLog(`[REST] POST /set status=${res.status} body=${text}`);
    } catch (e) {
      pushLog(`[REST] POST /set error: ${e instanceof Error ? e.message : String(e)}`);
    }
  };

  const emitImuStart = () => {
    const socket = socketRef.current;
    if (!socket) {
      pushLog("[warn] socket not connected");
      return;
    }
    const payload = { rate_hz: imuRate };
    socket.emit("imu/start", payload);
    pushLog(`[send] imu/start ${JSON.stringify(payload)}`);
  };

  const emitImuStop = () => {
    const socket = socketRef.current;
    if (!socket) {
      pushLog("[warn] socket not connected");
      return;
    }
    socket.emit("imu/stop");
    pushLog("[send] imu/stop");
  };

  const emitImuSetRate = () => {
    const socket = socketRef.current;
    if (!socket) {
      pushLog("[warn] socket not connected");
      return;
    }
    const payload = { rate_hz: imuRate };
    socket.emit("imu/set_rate", payload);
    pushLog(`[send] imu/set_rate ${JSON.stringify(payload)}`);
  };

  const requestImuStatus = () => {
    const socket = socketRef.current;
    if (!socket) {
      pushLog("[warn] socket not connected");
      return;
    }
    socket.emit("imu/status");
    pushLog("[send] imu/status");
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
        `robot-daemon` との Socket.IO（主に IMU）と、サーボの REST（POST /set）の確認用です。
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
        <h2>REST テスト（POST /set）</h2>
        <p>
          サーボ指令は HTTP。Socket 接続は不要です（未接続でも送信できます）。
        </p>
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
          <button type="button" onClick={() => void postSetServo()}>
            POST /set を送信
          </button>
        </div>
      </section>

      <section className="ws-test-card">
        <h2>IMU ストリーム</h2>
        <div className="ws-test-form">
          <label>
            rate_hz
            <input
              type="number"
              min={1}
              max={200}
              value={imuRate}
              onChange={(e) => setImuRate(Number(e.target.value))}
            />
          </label>
        </div>
        <div className="ws-test-row">
          <button type="button" onClick={emitImuStart} disabled={status !== "connected"}>
            imu/start
          </button>
          <button type="button" onClick={emitImuStop} disabled={status !== "connected"}>
            imu/stop
          </button>
          <button type="button" onClick={emitImuSetRate} disabled={status !== "connected"}>
            imu/set_rate
          </button>
          <button type="button" onClick={requestImuStatus} disabled={status !== "connected"}>
            imu/status
          </button>
        </div>
        <div className="ws-test-row">
          <p>
            streaming: <strong>{String(Boolean(imuStatus?.streaming))}</strong>
          </p>
          <p>
            sensor_enabled: <strong>{String(Boolean(imuStatus?.sensor?.enabled))}</strong>
          </p>
          <p>
            sensor_error: <code>{imuStatus?.sensor?.error || "-"}</code>
          </p>
        </div>
        <div className="ws-test-log">
          {!imuSample ? (
            <p>まだ受信していません。imu/start を送信してください。</p>
          ) : (
            <pre>
              <p>
                timestamp: {fmt2(imuSample.timestamp)} / mock: {String(Boolean(imuSample.mock))}
              </p>
              <p>
                accel(x,y,z): {fmtAligned(imuSample.accel?.x)}, {fmtAligned(imuSample.accel?.y)},{" "}
                {fmtAligned(imuSample.accel?.z)}
              </p>
              <p>
                gyro(x,y,z) : {fmtAligned(imuSample.gyro?.x)}, {fmtAligned(imuSample.gyro?.y)},{" "}
                {fmtAligned(imuSample.gyro?.z)}
              </p>
              <p>
                angle(p,r,y): {fmtAligned(imuSample.angle?.pitch)}, {fmtAligned(imuSample.angle?.roll)},{" "}
                {fmtAligned(imuSample.angle?.yaw)}
              </p>
            </pre>
          )}
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
