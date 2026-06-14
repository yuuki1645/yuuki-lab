import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import HubWindowMenu from "@/app/components/HubWindowMenu";
import ImuAttitudeFloatingWindow from "@/app/components/ImuAttitudeFloatingWindow";
import ImuFloatingWindow from "@/app/components/ImuFloatingWindow";
import { hubTools } from "@/app/hubTools";
import { DaemonImuTelemetryProvider } from "@/shared/contexts/DaemonImuTelemetryContext";
import { useImuDaemonStream } from "@/shared/hooks/useImuDaemonStream";

function HubLayoutInner() {
  const [imuWindowOpen, setImuWindowOpen] = useState(false);
  const [imuAttitudeOpen, setImuAttitudeOpen] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const location = useLocation();

  const imuStreamActive = imuWindowOpen || imuAttitudeOpen;
  const imuStream = useImuDaemonStream(imuStreamActive);
  const currentTool = hubTools.find((t) => t.path === location.pathname);

  // ページ遷移したらモバイルメニューを閉じる
  useEffect(() => {
    setNavOpen(false);
  }, [location.pathname]);

  return (
    <div className="hub-root">
      <header className="hub-header">
        <div className="hub-brand">
          <span className="hub-brand-title">Robotics Hub</span>
          <span className="hub-brand-sub">ロボット用ツール集</span>
          {currentTool ? (
            <span className="hub-brand-current" aria-current="page">
              {currentTool.label}
            </span>
          ) : null}
        </div>
        <button
          type="button"
          className="hub-nav-toggle"
          aria-expanded={navOpen}
          aria-controls="hub-nav-panel"
          onClick={() => setNavOpen((v) => !v)}
        >
          {navOpen ? "閉じる" : "メニュー"}
        </button>
        <nav
          id="hub-nav-panel"
          className={"hub-nav" + (navOpen ? " hub-nav--open" : "")}
          aria-label="ツール切替"
        >
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
