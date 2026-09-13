import { useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import HubToolsMenu from "@/app/components/HubToolsMenu";
import HubWindowMenu from "@/app/components/HubWindowMenu";
import ImuAttitudeFloatingWindow from "@/app/components/ImuAttitudeFloatingWindow";
import ImuFloatingWindow from "@/app/components/ImuFloatingWindow";
import { hubTools } from "@/app/hubTools";
import { DaemonImuTelemetryProvider } from "@/shared/contexts/DaemonImuTelemetryContext";
import { useImuDaemonStream } from "@/shared/hooks/useImuDaemonStream";

function HubLayoutInner() {
  const [imuWindowOpen, setImuWindowOpen] = useState(false);
  const [imuAttitudeOpen, setImuAttitudeOpen] = useState(false);
  const location = useLocation();

  const imuStreamActive = imuWindowOpen || imuAttitudeOpen;
  const imuStream = useImuDaemonStream(imuStreamActive);
  const currentTool = hubTools.find((t) => t.path === location.pathname);

  return (
    <div className="hub-root">
      {/* ツール一覧はドロップダウンにまとめ、ヘッダーは常に1行 */}
      <header className="hub-header">
        <div className="hub-brand">
          <span className="hub-brand-title">Robotics Hub</span>
          <span className="hub-brand-sub">ロボット用ツール集</span>
        </div>
        <nav className="hub-nav" aria-label="ツール切替">
          <HubToolsMenu currentLabel={currentTool?.label ?? null} />
          <HubWindowMenu
            onOpenImu={() => setImuWindowOpen(true)}
            onOpenImuAttitude={() => setImuAttitudeOpen(true)}
          />
        </nav>
      </header>
      <main className="hub-main">
        <Outlet />
      </main>
      <ImuFloatingWindow
        open={imuWindowOpen}
        onClose={() => setImuWindowOpen(false)}
        stream={imuStream}
      />
      <ImuAttitudeFloatingWindow
        open={imuAttitudeOpen}
        onClose={() => setImuAttitudeOpen(false)}
        stream={imuStream}
      />
    </div>
  );
}

export default function HubLayout() {
  return (
    <DaemonImuTelemetryProvider>
      <HubLayoutInner />
    </DaemonImuTelemetryProvider>
  );
}
