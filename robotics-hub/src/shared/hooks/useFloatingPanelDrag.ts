import { useCallback, useEffect, useRef, useState } from "react";

type Options = {
  /** パネルが閉じたときなど、ドラッグ状態をリセットするトリガ */
  panelOpen: boolean;
  /** 初期位置（ビューポート左上からの px） */
  initial: { x: number; y: number };
  /** `left` + `panelWidth` がビューポートからはみ出さないようにクランプ */
  panelWidth: number;
  panelHeight: number;
};

/**
 * フローティングパネルのタイトルバーからドラッグ移動（デスクトップ・タッチ両対応）
 */
export function useFloatingPanelDrag({
  panelOpen,
  initial,
  panelWidth,
  panelHeight,
}: Options) {
  const [pos, setPos] = useState(initial);
  const dragRef = useRef<{ offsetX: number; offsetY: number } | null>(null);
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    if (!panelOpen) {
      dragRef.current = null;
      setDragging(false);
    }
  }, [panelOpen]);

  useEffect(() => {
    if (!dragging) return;
    const blockScroll = (ev: TouchEvent) => {
      ev.preventDefault();
    };
    document.body.addEventListener("touchmove", blockScroll, { passive: false });
    return () => {
      document.body.removeEventListener("touchmove", blockScroll);
    };
  }, [dragging]);

  const onHeaderPointerDown = useCallback(
    (e: React.PointerEvent) => {
      if ((e.target as HTMLElement).closest(".imu-float-close")) return;
      dragRef.current = {
        offsetX: e.clientX - pos.x,
        offsetY: e.clientY - pos.y,
      };
      setDragging(true);
      if (e.pointerType === "touch" || e.pointerType === "pen") {
        e.preventDefault();
      }
      e.currentTarget.setPointerCapture(e.pointerId);
    },
    [pos.x, pos.y]
  );

  const onHeaderPointerMove = useCallback((e: React.PointerEvent) => {
    if (!dragRef.current) return;
    if (e.pointerType === "touch" || e.pointerType === "pen") {
      e.preventDefault();
    }
    const nx = e.clientX - dragRef.current.offsetX;
    const ny = e.clientY - dragRef.current.offsetY;
    const margin = 8;
    const maxX = Math.max(margin, window.innerWidth - panelWidth - margin);
    const maxY = Math.max(margin, window.innerHeight - panelHeight - margin);
    setPos({
      x: Math.min(Math.max(margin, nx), maxX),
      y: Math.min(Math.max(margin, ny), maxY),
    });
  }, [panelWidth, panelHeight]);

  const onHeaderPointerUp = useCallback((e: React.PointerEvent) => {
    dragRef.current = null;
    setDragging(false);
    try {
      e.currentTarget.releasePointerCapture(e.pointerId);
    } catch {
      /* already released */
    }
  }, []);

  const headerPointerHandlers = {
    onPointerDown: onHeaderPointerDown,
    onPointerMove: onHeaderPointerMove,
    onPointerUp: onHeaderPointerUp,
    onPointerCancel: onHeaderPointerUp,
  };

  return { pos, headerPointerHandlers };
}
