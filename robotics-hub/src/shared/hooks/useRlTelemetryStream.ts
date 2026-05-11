import { useCallback, useEffect, useState } from "react";
import { io } from "socket.io-client";
import { getRlTelemetrySocketUrl } from "@/shared/constants";
import type {
  RlTelemetryHelloPayload,
  RlTelemetryResetPayload,
  RlTelemetryStepPayload,
} from "@/shared/types/rlTelemetry";

export type RlTelemetryWsStatus = "disconnected" | "connecting" | "connected";

export type RlTelemetryStream = {
  wsStatus: RlTelemetryWsStatus;
  url: string;
  lastHello: RlTelemetryHelloPayload | null;
  lastReset: RlTelemetryResetPayload | null;
  lastStep: RlTelemetryStepPayload | null;
  stepCount: number;
  lastError: string | null;
  reconnect: () => void;
};

/**
 * 学習スクリプトの Socket.IO から ``rl_telemetry/*`` を購読する。
 */
export function useRlTelemetryStream(active: boolean): RlTelemetryStream {
  const [wsStatus, setWsStatus] = useState<RlTelemetryWsStatus>("disconnected");
  const [lastHello, setLastHello] = useState<RlTelemetryHelloPayload | null>(null);
  const [lastReset, setLastReset] = useState<RlTelemetryResetPayload | null>(null);
  const [lastStep, setLastStep] = useState<RlTelemetryStepPayload | null>(null);
  const [stepCount, setStepCount] = useState(0);
  const [lastError, setLastError] = useState<string | null>(null);
  const [url] = useState(() => getRlTelemetrySocketUrl());
  const [socketGen, setSocketGen] = useState(0);

  const reconnect = useCallback(() => {
    setSocketGen((g) => g + 1);
  }, []);

  useEffect(() => {
    if (!active) return;

    setWsStatus("connecting");
    setLastError(null);

    const socket = io(url, {
      transports: ["polling", "websocket"],
      reconnection: true,
      reconnectionAttempts: Infinity,
      reconnectionDelay: 500,
      reconnectionDelayMax: 5000,
    });

    socket.on("connect_error", (err: Error) => {
      setLastError(
        `Socket.IO 接続失敗 (${url}): ${err.message}。` +
          "`python -m mujoco_rl_sim.scripts.train_002_full_actuators` を起動し、" +
          "`VITE_RL_TELEMETRY_SOCKET_URL` が学習ホストと一致しているか確認してください。"
      );
    });

    socket.on("connect", () => {
      setLastError(null);
      setWsStatus("connected");
    });

    socket.on("disconnect", () => {
      setWsStatus("disconnected");
    });

    socket.on("rl_telemetry/hello", (payload: RlTelemetryHelloPayload) => {
      setLastHello(payload);
    });

    socket.on("rl_telemetry/reset", (payload: RlTelemetryResetPayload) => {
      setLastReset(payload);
      setStepCount(0);
    });

    socket.on("rl_telemetry/step", (payload: RlTelemetryStepPayload) => {
      setLastStep(payload);
      setStepCount((c) => c + 1);
    });

    return () => {
      socket.disconnect();
    };
  }, [active, url, socketGen]);

  return {
    wsStatus,
    url,
    lastHello,
    lastReset,
    lastStep,
    stepCount,
    lastError,
    reconnect,
  };
}
