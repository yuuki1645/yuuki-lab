import { useCallback, useEffect, useState } from "react";
import { io } from "socket.io-client";
import { getTelemetryImuSocketUrl } from "@/shared/constants";
import type { ImuDaemonSamplePayload, ImuDaemonStatusPayload } from "@/shared/types/imuDaemon";

export type DaemonImuWsStatus = "disconnected" | "connecting" | "connected";

export type DaemonImuTelemetryStream = {
  wsStatus: DaemonImuWsStatus;
  url: string;
  lastSample: ImuDaemonSamplePayload | null;
  lastStatus: ImuDaemonStatusPayload | null;
  lastImuError: string | null;
  sampleCount: number;
  lastError: string | null;
  reconnect: () => void;
};

const DEFAULT_RATE_HZ = 30;

/**
 * robot-daemon の IMU ストリーム（接続後に ``imu/start`` を送り ``imu/sample`` を購読）。
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
  const [url] = useState(() => getTelemetryImuSocketUrl());
  const [socketGen, setSocketGen] = useState(0);

  const reconnect = useCallback(() => {
    setSocketGen((g) => g + 1);
  }, []);

  useEffect(() => {
    if (!active) return;

    setWsStatus("connecting");
    setLastError(null);
    setLastImuError(null);

    const socket = io(url, {
      transports: ["polling", "websocket"],
      reconnection: true,
      reconnectionAttempts: Infinity,
      reconnectionDelay: 500,
      reconnectionDelayMax: 5000,
    });

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

    return () => {
      try {
        socket.emit("imu/stop");
      } catch {
        /* ignore */
      }
      socket.disconnect();
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
    reconnect,
  };
}
