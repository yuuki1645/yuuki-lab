import { useCallback, useEffect, useState } from "react";
import { io } from "socket.io-client";
import { getTrainingTelemetrySocketUrl } from "@/shared/constants";
import type {
  TrainingTelemetryHelloPayload,
  TrainingTelemetryResetPayload,
  TrainingTelemetryStepPayload,
} from "@/shared/types/trainingTelemetry";

export type TrainingTelemetryWsStatus = "disconnected" | "connecting" | "connected";

export type TrainingTelemetryStream = {
  wsStatus: TrainingTelemetryWsStatus;
  url: string;
  lastHello: TrainingTelemetryHelloPayload | null;
  lastReset: TrainingTelemetryResetPayload | null;
  lastStep: TrainingTelemetryStepPayload | null;
  stepCount: number;
  lastError: string | null;
  reconnect: () => void;
};

/**
 * mujoco-sim（Hub 向け Socket.IO）の ``rl_telemetry/*`` を購読する。
 */
export function useTrainingTelemetryStream(active: boolean): TrainingTelemetryStream {
  const [wsStatus, setWsStatus] = useState<TrainingTelemetryWsStatus>("disconnected");
  const [lastHello, setLastHello] = useState<TrainingTelemetryHelloPayload | null>(null);
  const [lastReset, setLastReset] = useState<TrainingTelemetryResetPayload | null>(null);
  const [lastStep, setLastStep] = useState<TrainingTelemetryStepPayload | null>(null);
  const [stepCount, setStepCount] = useState(0);
  const [lastError, setLastError] = useState<string | null>(null);
  const [url] = useState(() => getTrainingTelemetrySocketUrl());
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
        `学習テレメトリ Socket.IO 接続失敗 (${url}): ${err.message}。` +
          "`python -m mujoco_rl_sim.experiments.exp_019_biped_ppo_hop_balance.train` を起動し、" +
          "`VITE_TELEMETRY_SOCKET_URL`（旧: `VITE_RL_TELEMETRY_SOCKET_URL`）が学習ホストと一致しているか確認してください。"
      );
    });

    socket.on("connect", () => {
      setLastError(null);
      setWsStatus("connected");
    });

    socket.on("disconnect", () => {
      setWsStatus("disconnected");
    });

    socket.on("rl_telemetry/hello", (payload: TrainingTelemetryHelloPayload) => {
      setLastHello(payload);
    });

    socket.on("rl_telemetry/reset", (payload: TrainingTelemetryResetPayload) => {
      setLastReset(payload);
      setStepCount(0);
    });

    socket.on("rl_telemetry/step", (payload: TrainingTelemetryStepPayload) => {
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
