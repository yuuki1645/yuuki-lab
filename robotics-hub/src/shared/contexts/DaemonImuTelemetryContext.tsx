import { createContext, useContext, type ReactNode } from "react";
import {
  useDaemonImuTelemetryStream,
  type DaemonImuTelemetryStream,
} from "@/shared/hooks/useDaemonImuTelemetryStream";

const DaemonImuTelemetryContext = createContext<DaemonImuTelemetryStream | null>(null);

/**
 * robot-daemon への IMU Socket.IO をハブ全体で 1 接続維持する。
 * テレメトリ画面を離れても `imu/stop` を送らないため、CSV ログ（imu/log_start）が継続する。
 */
export function DaemonImuTelemetryProvider({ children }: { children: ReactNode }) {
  const value = useDaemonImuTelemetryStream(true, 30);
  return (
    <DaemonImuTelemetryContext.Provider value={value}>{children}</DaemonImuTelemetryContext.Provider>
  );
}

export function useDaemonImuTelemetry(): DaemonImuTelemetryStream {
  const ctx = useContext(DaemonImuTelemetryContext);
  if (!ctx) {
    throw new Error("useDaemonImuTelemetry must be used within DaemonImuTelemetryProvider");
  }
  return ctx;
}
