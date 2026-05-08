import { useCallback, useEffect, useRef, useState } from "react";
import { io, type Socket } from "socket.io-client";
import { SERVO_DAEMON_URL } from "@/shared/constants";
import type { ImuSamplePayload, ImuStatusPayload } from "@/shared/types/imu";

export type WsStatus = "disconnected" | "connecting" | "connected";

const DEFAULT_RATE_HZ = 30;

export type ImuDaemonStream = {
  wsStatus: WsStatus;
  rateHz: number;
  setRateHz: (n: number) => void;
  applyRate: () => void;
  imuStatus: ImuStatusPayload | null;
  imuSample: ImuSamplePayload | null;
  lastError: string | null;
};

/**
 * `active` が true の間だけ Socket.IO で IMU ストリームを開始する。
 * 数値ウィンドウと姿勢ウィンドウで共有する。
 */
export function useImuDaemonStream(active: boolean): ImuDaemonStream {
  const socketRef = useRef<Socket | null>(null);
  const [wsStatus, setWsStatus] = useState<WsStatus>("disconnected");
  const [rateHz, setRateHz] = useState(DEFAULT_RATE_HZ);
  const rateRef = useRef(rateHz);
  rateRef.current = rateHz;

  const [imuStatus, setImuStatus] = useState<ImuStatusPayload | null>(null);
  const [imuSample, setImuSample] = useState<ImuSamplePayload | null>(null);
  const [lastError, setLastError] = useState<string | null>(null);

  useEffect(() => {
    if (!active) return;

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
  }, [active]);

  const applyRate = useCallback(() => {
    const socket = socketRef.current;
    if (!socket?.connected) return;
    socket.emit("imu/set_rate", { rate_hz: rateRef.current });
  }, []);

  return {
    wsStatus,
    rateHz,
    setRateHz,
    applyRate,
    imuStatus,
    imuSample,
    lastError,
  };
}
