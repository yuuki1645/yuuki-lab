/**
 * 丸に「?」の解説チップ。
 *
 * ステータスバーは overflow でポップアップが切れるので、本文は document.body へ出す。
 * マウスオーバーとキーボードフォーカスで開き、タップ（またはクリック）で固定できる。
 */
import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import "./UiHelp.css";

export type UiHelpPlacement = "top" | "bottom";

type Props = {
  /** ポップアップ先頭の短い見出し */
  title: string;
  /** 本文。文で書く */
  children: ReactNode;
  /** ステータスバーは上向き。画面中ほどは下向きが読みやすい */
  placement?: UiHelpPlacement;
  /** 長い説明用に幅を広げる */
  wide?: boolean;
  /** ステータスバー向けの小さい丸 */
  size?: "sm" | "md";
};

const GAP = 8;
const VIEW_PAD = 8;

export function UiHelp({ title, children, placement = "bottom", wide = false, size = "md" }: Props) {
  const btnRef = useRef<HTMLButtonElement>(null);
  const popRef = useRef<HTMLDivElement>(null);
  const tipId = useId();
  const [hover, setHover] = useState(false);
  const [pinned, setPinned] = useState(false);
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null);
  const open = hover || pinned;

  const updatePos = useCallback(() => {
    const btn = btnRef.current;
    const pop = popRef.current;
    if (!btn || !pop) return;
    const a = btn.getBoundingClientRect();
    const p = pop.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    let left = a.left + a.width / 2 - p.width / 2;
    left = Math.min(vw - p.width - VIEW_PAD, Math.max(VIEW_PAD, left));
    let top = placement === "top" ? a.top - GAP - p.height : a.bottom + GAP;
    if (placement === "top" && top < VIEW_PAD) {
      top = a.bottom + GAP;
    } else if (placement === "bottom" && top + p.height > vh - VIEW_PAD) {
      top = a.top - GAP - p.height;
    }
    top = Math.min(vh - p.height - VIEW_PAD, Math.max(VIEW_PAD, top));
    setPos({ left, top });
  }, [placement]);

  useLayoutEffect(() => {
    if (!open) {
      setPos(null);
      return;
    }
    updatePos();
  }, [open, updatePos, children, title]);

  useEffect(() => {
    if (!open) return;
    const onWin = () => updatePos();
    window.addEventListener("resize", onWin);
    window.addEventListener("scroll", onWin, true);
    return () => {
      window.removeEventListener("resize", onWin);
      window.removeEventListener("scroll", onWin, true);
    };
  }, [open, updatePos]);

  useEffect(() => {
    if (!pinned) return;
    const onDoc = (ev: PointerEvent) => {
      const t = ev.target as Node | null;
      if (btnRef.current?.contains(t) || popRef.current?.contains(t)) return;
      setPinned(false);
    };
    const onKey = (ev: KeyboardEvent) => {
      if (ev.key === "Escape") setPinned(false);
    };
    document.addEventListener("pointerdown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [pinned]);

  return (
    <span className={"ui-help" + (open ? " ui-help--open" : "")}>
      <button
        ref={btnRef}
        type="button"
        className={"ui-help__btn" + (size === "sm" ? " ui-help__btn--sm" : "")}
        aria-label={`${title}の解説`}
        aria-expanded={open}
        aria-describedby={open ? tipId : undefined}
        onMouseEnter={() => setHover(true)}
        onMouseLeave={() => setHover(false)}
        onFocus={() => setHover(true)}
        onBlur={() => setHover(false)}
        onClick={(e) => {
          // 親のタブ切替などを踏まない。タップでは固定して読めるようにする
          e.preventDefault();
          e.stopPropagation();
          setPinned((v) => !v);
        }}
      >
        ?
      </button>
      {open
        ? createPortal(
            <div
              ref={popRef}
              id={tipId}
              role="tooltip"
              className={"ui-help__pop" + (wide ? " ui-help__pop--wide" : "")}
              style={pos ? { left: pos.left, top: pos.top } : { left: 0, top: 0, visibility: "hidden" }}
            >
              <strong>{title}</strong>
              <div className="ui-help__body">{children}</div>
            </div>,
            document.body
          )
        : null}
    </span>
  );
}
