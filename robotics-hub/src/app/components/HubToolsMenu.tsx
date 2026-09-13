import { useEffect, useRef, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import {
  hubToolGroupLabels,
  hubToolGroupOrder,
  hubTools,
  type HubTool,
  type HubToolGroupId,
} from "@/app/hubTools";

type HubToolsMenuProps = {
  /** 現在ページの表示名。未一致時は「ツール」 */
  currentLabel: string | null;
};

/**
 * グローバルヘッダーのツール切替ドロップダウン。
 * 項目数が増えてもバーが折り返さないよう、一覧はパネル内にグループ表示する。
 */
export default function HubToolsMenu({ currentLabel }: HubToolsMenuProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const location = useLocation();

  // ページ遷移したらパネルを閉じる
  useEffect(() => {
    setOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!open) return;
    const onDocPointerDown = (e: PointerEvent) => {
      if (rootRef.current?.contains(e.target as Node)) return;
      setOpen(false);
    };
    document.addEventListener("pointerdown", onDocPointerDown);
    return () => document.removeEventListener("pointerdown", onDocPointerDown);
  }, [open]);

  const grouped = groupTools(hubTools);

  return (
    <div className="hub-tools-menu" ref={rootRef}>
      <button
        type="button"
        className={
          "hub-nav-link hub-tools-menu-trigger" +
          (open ? " hub-nav-link--active" : "")
        }
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label="ツール切替"
        title="ツール切替"
        onClick={() => setOpen((v) => !v)}
      >
        <span className="hub-tools-menu-trigger-label">{currentLabel ?? "ツール"}</span>
      </button>
      {open ? (
        <div className="hub-tools-menu-panel" role="menu" aria-label="ツール切替">
          {hubToolGroupOrder.map((groupId) => {
            const tools = grouped.get(groupId);
            if (!tools?.length) return null;
            return (
              <section key={groupId} className="hub-tools-menu-group">
                <h2 className="hub-tools-menu-group-title">{hubToolGroupLabels[groupId]}</h2>
                {tools.map((t) => (
                  <NavLink
                    key={t.id}
                    to={t.path}
                    role="menuitem"
                    className={({ isActive }) =>
                      "hub-tools-menu-item" + (isActive ? " hub-tools-menu-item--active" : "")
                    }
                    title={t.description}
                  >
                    {t.label}
                  </NavLink>
                ))}
              </section>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

/** 定義順を保ったままグループへ振り分ける */
function groupTools(tools: HubTool[]): Map<HubToolGroupId, HubTool[]> {
  const map = new Map<HubToolGroupId, HubTool[]>();
  for (const groupId of hubToolGroupOrder) {
    map.set(groupId, []);
  }
  for (const tool of tools) {
    map.get(tool.group)?.push(tool);
  }
  return map;
}
