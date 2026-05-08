import { useCallback, useEffect, useRef, useState } from "react";
import { io, type Socket } from "socket.io-client";
import { SERVO_DAEMON_URL } from "@/shared/constants";
import type { ImuSamplePayload, ImuStatusPayload } from "@/shared/types/imu";

type WsStatus = "disconnected" | "connecting" | "connected";

const DEFAULT_RATE_HZ = 30;

function fmt2(value?: number) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  return value.toFixed(2);
}

type ImuFloatingWindowProps = {
  open: boolean;
  onClose: () => void;
};

export default function ImuFloatingWindow({ open, onClose }: ImuFloatingWindowProps) {
  const [pos, setPos] = useState({ x: 24, y: 96 });
  const dragRef = useRef<{ offsetX: number; offsetY: number } | null>(null);
  const [dragging, setDragging] = useState(false);
  const socketRef = useRef<Socket | null>(null);

  const [wsStatus, setWsStatus] = useState<WsStatus>("disconnected");
  const [rateHz, setRateHz] = useState(DEFAULT_RATE_HZ);
  const rateRef = useRef(rateHz);
  rateRef.current = rateHz;

  const [imuStatus, setImuStatus] = useState<ImuStatusPayload | null>(null);
  const [imuSample, setImuSample] = useState<ImuSamplePayload | null>(null);
  const [lastError, setLastError] = useState<string | null>(null);

  const onHeaderPointerDown = useCallback(
    (e: React.PointerEvent) => {
      if ((e.target as HTMLElement).closest(".imu-float-close")) return;
      dragRef.current = {
        offsetX: e.clientX - pos.x,
        offsetY: e.clientY - pos.y,
      };
      setDragging(true);
      if (e.pointerType === "touch" || e.pointerType === "pen") {
        e.preventDefault();
      }
      e.currentTarget.setPointerCapture(e.pointerId);
    },
    [pos.x, pos.y]
  );

  const onHeaderPointerMove = useCallback((e: React.PointerEvent) => {
    if (!dragRef.current) return;
    if (e.pointerType === "touch" || e.pointerType === "pen") {
      e.preventDefault();
    }
    const nx = e.clientX - dragRef.current.offsetX;
    const ny = e.clientY - dragRef.current.offsetY;
    const margin = 8;
    const maxX = Math.max(margin, window.innerWidth - 320 - margin);
    const maxY = Math.max(margin, window.innerHeight - 120 - margin);
    setPos({
      x: Math.min(Math.max(margin, nx), maxX),
      y: Math.min(Math.max(margin, ny), maxY),
    });
  }, []);

  const onHeaderPointerUp = useCallback((e: React.PointerEvent) => {
    dragRef.current = null;
    setDragging(false);
    try {
      e.currentTarget.releasePointerCapture(e.pointerId);
    } catch {
      /* already released */
    }
  }, []);

  useEffect(() => {
    if (!open) return;

    setWsStatus("connecting");
    setLastError(null);
    setImuSample(null);
    setImuStatus(null);

    const socket = io(SERVO_DAEMON_URL, {
      transports: ["websocket"],
      reconnection: true,
      reconnectionAttempts: Infinity,
      reconnectionDelay: 500,
    });
    socketRef.current = socket;

    socket.on("connect", () => {
      setWsStatus("connected");
      socket.emit("imu/start", { rate_hz: rateRef.current });
    });

    socket.on("disconnect", () => {
      setWsStatus("disconnected");
    });

    socket.on("imu/status", (payload: ImuStatusPayload) => {
      setImuStatus(payload);
      if (typeof payload.rate_hz === "number") {
        setRateHz(Math.round(payload.rate_hz));
      }
    });

    socket.on("imu/sample", (payload: ImuSamplePayload) => {
      setImuSample(payload);
    });

    socket.on("imu/error", (payload: unknown) => {
      setLastError(
        typeof payload === "object" && payload !== null && "message" in payload
          ? String((payload as { message?: string }).message)
          : JSON.stringify(payload)
      );
    });

    return () => {
      if (socket.connected) {
        socket.emit("imu/stop");
      }
      socket.removeAllListeners();
      socket.disconnect();
      socketRef.current = null;
      setWsStatus("disconnected");
    };
  }, [open]);

  useEffect(() => {
    if (!open) {
      dragRef.current = null;
      setDragging(false);
    }
  }, [open]);

  /** iPad / iOS WebKit: ドラッグ中に背後ページへ touchmove が伝わってスクロールするのを防ぐ */
  useEffect(() => {
    if (!dragging) return;
    const blockScroll = (ev: TouchEvent) => {
      ev.preventDefault();
    };
    document.body.addEventListener("touchmove", blockScroll, { passive: false });
    return () => {
      document.body.removeEventListener("touchmove", blockScroll);
    };
  }, [dragging]);

  const applyRate = useCallback(() => {
    const socket = socketRef.current;
    if (!socket?.connected) return;
    socket.emit("imu/set_rate", { rate_hz: rateRef.current });
  }, []);

  if (!open) return null;

  return (
    <div
      className="imu-float"
      style={{ left: pos.x, top: pos.y }}
      role="dialog"
      aria-labelledby="imu-float-title"
    >
      <div
        className="imu-float-header"
        onPointerDown={onHeaderPointerDown}
        onPointerMove={onHeaderPointerMove}
        onPointerUp={onHeaderPointerUp}
        onPointerCancel={onHeaderPointerUp}
      >
        <span id="imu-float-title" className="imu-float-title">
          IMU センサー
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

      <div className="imu-float-body">
        <div className="imu-float-meta">
          <span>
            接続: <strong>{wsStatus}</strong>
          </span>
          <span>
            ストリーム:{" "}
            <strong>{imuStatus?.streaming ? "ON" : "—"}</strong>
          </span>
          <label className="imu-float-rate">
            Hz
            <input
              type="number"
              min={1}
              max={200}
              value={rateHz}
              disabled={wsStatus !== "connected"}
              onChange={(e) => setRateHz(Number(e.target.value))}
              onBlur={applyRate}
            />
          </label>
        </div>

        {lastError ? (
          <p className="imu-float-error" role="alert">
            {lastError}
          </p>
        ) : null}

        <div className="imu-float-status">
          <span>sensor: {imuStatus?.sensor?.enabled ? "OK" : "—"}</span>
          <span className="imu-float-status-err">
            {imuStatus?.sensor?.error ?? ""}
          </span>
        </div>

        {!imuSample ? (
          <p className="imu-float-placeholder">
            {wsStatus === "connected"
              ? "サンプル待ちです…"
              : "daemon に接続しています…"}
          </p>
        ) : (
          <dl className="imu-float-readings">
            <div className="imu-float-row">
              <dt>時刻</dt>
              <dd>{fmt2(imuSample.timestamp)}</dd>
            </div>
            <div className="imu-float-row">
              <dt>モック</dt>
              <dd>{imuSample.mock ? "はい" : "いいえ"}</dd>
            </div>
            <div className="imu-float-row">
              <dt>加速度 (x,y,z)</dt>
              <dd>
                {fmt2(imuSample.accel?.x)}, {fmt2(imuSample.accel?.y)},{" "}
                {fmt2(imuSample.accel?.z)}
              </dd>
            </div>
            <div className="imu-float-row">
              <dt>角速度 (x,y,z)</dt>
              <dd>
                {fmt2(imuSample.gyro?.x)}, {fmt2(imuSample.gyro?.y)},{" "}
                {fmt2(imuSample.gyro?.z)}
              </dd>
            </div>
            <div className="imu-float-row">
              <dt>姿勢 pitch / roll / yaw</dt>
              <dd>
                {fmt2(imuSample.angle?.pitch)} / {fmt2(imuSample.angle?.roll)} /{" "}
                {fmt2(imuSample.angle?.yaw)}
              </dd>
            </div>
          </dl>
        )}
      </div>
    </div>
  );
}
