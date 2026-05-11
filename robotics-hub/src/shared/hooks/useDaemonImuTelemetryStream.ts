import { useCallback, useEffect, useRef, useState } from "react";
import { io, type Socket } from "socket.io-client";
import { getTelemetryImuSocketUrl } from "@/shared/constants";
import type { ImuDaemonSamplePayload, ImuDaemonStatusPayload } from "@/shared/types/imuDaemon";

export type DaemonImuWsStatus = "disconnected" | "connecting" | "connected";

export type ImuLogStatusPayload = {
  ok?: boolean;
  reason?: string;
  recording?: boolean;
};

export type DaemonImuTelemetryStream = {
  wsStatus: DaemonImuWsStatus;
  url: string;
  lastSample: ImuDaemonSamplePayload | null;
  lastStatus: ImuDaemonStatusPayload | null;
  lastImuError: string | null;
  sampleCount: number;
  lastError: string | null;
  lastLogStatus: ImuLogStatusPayload | null;
  reconnect: () => void;
  requestImuStatus: () => void;
  startCsvLog: () => void;
  stopCsvLog: () => void;
};

const DEFAULT_RATE_HZ = 30;

/**
 * robot-daemon の IMU ストリーム（接続後に ``imu/start`` を送り ``imu/sample`` を購読）。
 * CSV ログは ``imu/log_start`` / ``imu/log_stop`` で制御する。
 */
export function useDaemonImuTelemetryStream(
  active: boolean,
  rateHz: number = DEFAULT_RATE_HZ
): DaemonImuTelemetryStream {
  const [wsStatus, setWsStatus] = useState<DaemonImuWsStatus>("disconnected");
  const [lastSample, setLastSample] = useState<ImuDaemonSamplePayload | null>(null);
  const [lastStatus, setLastStatus] = useState<ImuDaemonStatusPayload | null>(null);
  const [lastImuError, setLastImuError] = useState<string | null>(null);
  const [sampleCount, setSampleCount] = useState(0);
  const [lastError, setLastError] = useState<string | null>(null);
  const [lastLogStatus, setLastLogStatus] = useState<ImuLogStatusPayload | null>(null);
  const [url] = useState(() => getTelemetryImuSocketUrl());
  const [socketGen, setSocketGen] = useState(0);
  const socketRef = useRef<Socket | null>(null);

  const reconnect = useCallback(() => {
    setSocketGen((g) => g + 1);
  }, []);

  const requestImuStatus = useCallback(() => {
    socketRef.current?.emit("imu/status");
  }, []);

  const startCsvLog = useCallback(() => {
    socketRef.current?.emit("imu/log_start");
  }, []);

  const stopCsvLog = useCallback(() => {
    socketRef.current?.emit("imu/log_stop");
  }, []);

  useEffect(() => {
    if (!active) return;

    setWsStatus("connecting");
    setLastError(null);
    setLastImuError(null);
    setLastLogStatus(null);

    const socket = io(url, {
      // WebSocket を優先し、サンプル・perf 表示の遅延を抑える
      transports: ["websocket", "polling"],
      reconnection: true,
      reconnectionAttempts: Infinity,
      reconnectionDelay: 500,
      reconnectionDelayMax: 5000,
    });
    socketRef.current = socket;

    socket.on("connect_error", (err: Error) => {
      setLastError(
        `IMU (robot-daemon) 接続失敗 (${url}): ${err.message}。` +
          "デーモンを起動し、`VITE_TELEMETRY_IMU_SOCKET_URL` が正しいか確認してください（未設定時は `http://<hostname>:5000`）。"
      );
    });

    socket.on("connect", () => {
      setLastError(null);
      setWsStatus("connected");
      const hz = Math.max(1, Math.min(200, Number.isFinite(rateHz) ? rateHz : DEFAULT_RATE_HZ));
      socket.emit("imu/start", { rate_hz: hz });
    });

    socket.on("disconnect", () => {
      setWsStatus("disconnected");
    });

    socket.on("imu/status", (payload: ImuDaemonStatusPayload) => {
      setLastStatus(payload);
    });

    socket.on("imu/sample", (payload: ImuDaemonSamplePayload) => {
      setLastSample(payload);
      setSampleCount((c) => c + 1);
    });

    socket.on("imu/error", (payload: { message?: string; error_code?: string }) => {
      const msg =
        typeof payload?.message === "string"
          ? payload.message
          : JSON.stringify(payload ?? {});
      setLastImuError(msg);
    });

    socket.on("imu/log_status", (payload: ImuLogStatusPayload) => {
      if (payload.ok === false) {
        setLastLogStatus(payload);
      } else {
        setLastLogStatus(null);
      }
    });

    return () => {
      try {
        socket.emit("imu/stop");
      } catch {
        /* ignore */
      }
      socket.disconnect();
      socketRef.current = null;
    };
  }, [active, url, socketGen, rateHz]);

  return {
    wsStatus,
    url,
    lastSample,
    lastStatus,
    lastImuError,
    sampleCount,
    lastError,
    lastLogStatus,
    reconnect,
    requestImuStatus,
    startCsvLog,
    stopCsvLog,
  };
}
