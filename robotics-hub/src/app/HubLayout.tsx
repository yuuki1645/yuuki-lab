import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import HubWindowMenu from "@/app/components/HubWindowMenu";
import ImuFloatingWindow from "@/app/components/ImuFloatingWindow";
import { hubTools } from "@/app/hubTools";

export default function HubLayout() {
  const [imuWindowOpen, setImuWindowOpen] = useState(false);

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
          <HubWindowMenu onOpenImu={() => setImuWindowOpen(true)} />
        </nav>
      </header>
      <main className="hub-main">
        <Outlet />
      </main>
      <ImuFloatingWindow open={imuWindowOpen} onClose={() => setImuWindowOpen(false)} />
    </div>
  );
}
