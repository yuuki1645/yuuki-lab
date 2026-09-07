import { useCallback, useEffect, useRef, useState } from "react";
import { io } from "socket.io-client";
import { getPressureTelemetrySocketUrl } from "@/shared/constants";
import type {
  PressureTelemetryHelloPayload,
  PressureTelemetrySample,
} from "@/shared/types/pressureTelemetry";

export type PressureTelemetryWsStatus = "disconnected" | "connecting" | "connected";

export type PressureTelemetryStream = {
  wsStatus: PressureTelemetryWsStatus;
  url: string;
  lastHello: PressureTelemetryHelloPayload | null;
  lastSample: PressureTelemetrySample | null;
  sampleCount: number;
  lastError: string | null;
  /** 直近サンプル受信からの経過秒（接続中のみ更新） */
  staleSec: number | null;
  reconnect: () => void;
};

type HealthPayload = {
  ok?: boolean;
  sample_count?: number;
  last_sample?: PressureTelemetrySample | null;
  stale_sec?: number | null;
};

/**
 * Pico 圧力ブリッジ（``pressure_telemetry_server.py``、既定 :8793）を購読する。
 * Socket.IO を主経路とし、届かない場合に health HTTP を短い間隔でポーリングする。
 */
export function usePressureTelemetryStream(active: boolean): PressureTelemetryStream {
  const [wsStatus, setWsStatus] = useState<PressureTelemetryWsStatus>("disconnected");
  const [lastHello, setLastHello] = useState<PressureTelemetryHelloPayload | null>(null);
  const [lastSample, setLastSample] = useState<PressureTelemetrySample | null>(null);
  const [sampleCount, setSampleCount] = useState(0);
  const [lastError, setLastError] = useState<string | null>(null);
  const [staleSec, setStaleSec] = useState<number | null>(null);
  const [url] = useState(() => getPressureTelemetrySocketUrl());
  const [socketGen, setSocketGen] = useState(0);

  // Socket / HTTP どちらから来ても「見たことのある server 側連番」を共有
  const seenCountRef = useRef(0);
  const lastRecvMsRef = useRef(0);

  const reconnect = useCallback(() => {
    setSocketGen((g) => g + 1);
  }, []);

  const applySample = useCallback((sample: PressureTelemetrySample, serverCount?: number) => {
    setLastSample(sample);
    if (typeof serverCount === "number" && Number.isFinite(serverCount)) {
      seenCountRef.current = Math.max(seenCountRef.current, serverCount);
      setSampleCount(serverCount);
    } else {
      setSampleCount((c) => {
        const next = c + 1;
        seenCountRef.current = Math.max(seenCountRef.current, next);
        return next;
      });
    }
    lastRecvMsRef.current = performance.now();
    setStaleSec(0);
  }, []);

  useEffect(() => {
    if (!active) return;

    setWsStatus("connecting");
    setLastError(null);
    seenCountRef.current = 0;
    lastRecvMsRef.current = 0;

    const socket = io(url, {
      transports: ["polling", "websocket"],
      reconnection: true,
      reconnectionAttempts: Infinity,
      reconnectionDelay: 500,
      reconnectionDelayMax: 5000,
    });

    socket.on("connect_error", (err: Error) => {
      setLastError(
        `圧力テレメトリ接続失敗 (${url}): ${err.message}。` +
          "`robotics-hub/server/start_pressure.ps1`（または `npm run dev:pressure`）を起動し、" +
          "ポート 8793 が 1 プロセスだけか確認してください。"
      );
    });

    socket.on("connect", () => {
      setLastError(null);
      setWsStatus("connected");
    });

    socket.on("disconnect", () => {
      setWsStatus("disconnected");
    });

    socket.on("pressure/hello", (payload: PressureTelemetryHelloPayload) => {
      setLastHello(payload);
      if (typeof payload.stale_sec === "number") {
        setStaleSec(payload.stale_sec);
      }
      if (typeof payload.sample_count === "number") {
        seenCountRef.current = Math.max(seenCountRef.current, payload.sample_count);
      }
    });

    socket.on("pressure/sample", (payload: PressureTelemetrySample) => {
      applySample(payload);
    });

    // Socket.IO が詰まっても health で最新値を拾う（二重待ち受け事故の検知にも有効）
    const healthTimer = window.setInterval(async () => {
      try {
        const res = await fetch(`${url}/api/pressure/health`, { cache: "no-store" });
        if (!res.ok) return;
        const data = (await res.json()) as HealthPayload;
        const count = data.sample_count;
        const sample = data.last_sample;
        if (
          typeof count === "number" &&
          sample &&
          typeof sample.force_kg === "number" &&
          count > seenCountRef.current
        ) {
          applySample(sample, count);
        } else if (typeof data.stale_sec === "number" && lastRecvMsRef.current <= 0) {
          setStaleSec(data.stale_sec);
        }
      } catch {
        // ブリッジ未起動中は無視（Socket.IO 側のエラー表示に任せる）
      }
    }, 200);

    const staleTimer = window.setInterval(() => {
      if (lastRecvMsRef.current <= 0) return;
      setStaleSec((performance.now() - lastRecvMsRef.current) / 1000);
    }, 250);

    return () => {
      window.clearInterval(healthTimer);
      window.clearInterval(staleTimer);
      socket.disconnect();
    };
  }, [active, url, socketGen, applySample]);

  return {
    wsStatus,
    url,
    lastHello,
    lastSample,
    sampleCount,
    lastError,
    staleSec,
    reconnect,
  };
}
