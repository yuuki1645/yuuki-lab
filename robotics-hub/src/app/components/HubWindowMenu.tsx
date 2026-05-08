import { useEffect, useRef, useState } from "react";

type HubWindowMenuProps = {
  onOpenImu: () => void;
  onOpenImuAttitude: () => void;
};

export default function HubWindowMenu({
  onOpenImu,
  onOpenImuAttitude,
}: HubWindowMenuProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDocPointerDown = (e: PointerEvent) => {
      if (rootRef.current?.contains(e.target as Node)) return;
      setOpen(false);
    };
    document.addEventListener("pointerdown", onDocPointerDown);
    return () => document.removeEventListener("pointerdown", onDocPointerDown);
  }, [open]);

  return (
    <div className="hub-window-menu" ref={rootRef}>
      <button
        type="button"
        className="hub-nav-link hub-window-menu-trigger"
        aria-expanded={open}
        aria-haspopup="menu"
        onClick={() => setOpen((v) => !v)}
      >
        ウィンドウ
      </button>
      {open ? (
        <div className="hub-window-menu-panel" role="menu" aria-label="ウィンドウ">
          <button
            type="button"
            role="menuitem"
            className="hub-window-menu-item"
            onClick={() => {
              onOpenImu();
              setOpen(false);
            }}
          >
            IMU（数値）
          </button>
          <button
            type="button"
            role="menuitem"
            className="hub-window-menu-item"
            onClick={() => {
              onOpenImuAttitude();
              setOpen(false);
            }}
          >
            IMU（姿勢）
          </button>
        </div>
      ) : null}
    </div>
  );
}
