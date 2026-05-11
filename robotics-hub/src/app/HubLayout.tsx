import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import HubWindowMenu from "@/app/components/HubWindowMenu";
import ImuAttitudeFloatingWindow from "@/app/components/ImuAttitudeFloatingWindow";
import ImuFloatingWindow from "@/app/components/ImuFloatingWindow";
import { hubTools } from "@/app/hubTools";
import { DaemonImuTelemetryProvider } from "@/shared/contexts/DaemonImuTelemetryContext";
import { useImuDaemonStream } from "@/shared/hooks/useImuDaemonStream";

function HubLayoutInner() {
  const [imuWindowOpen, setImuWindowOpen] = useState(false);
  const [imuAttitudeOpen, setImuAttitudeOpen] = useState(false);

  const imuStreamActive = imuWindowOpen || imuAttitudeOpen;
  const imuStream = useImuDaemonStream(imuStreamActive);

  return (
    <div className="hub-root">
      <header className="hub-header">
        <div className="hub-brand">
          <span className="hub-brand-title">Robotics Hub</span>
          <span className="hub-brand-sub">ロボット用ツール集</span>
        </div>
        <nav className="hub-nav" aria-label="ツール切替">
          {hubTools.map((t) => (
            <NavLink
              key={t.id}
              to={t.path}
              className={({ isActive }) =>
                isActive ? "hub-nav-link hub-nav-link--active" : "hub-nav-link"
              }
              title={t.description}
            >
              {t.label}
            </NavLink>
          ))}
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
