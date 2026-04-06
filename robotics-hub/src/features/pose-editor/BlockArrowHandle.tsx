import type { PointerEvent } from "react";

export interface BlockArrowHandleProps {
  cx: number;
  cy: number;
  r: number;
  rotDeg: number;
  color: string;
  active: boolean;
  onPointerDown: (e: PointerEvent<SVGGElement>) => void;
}

/** オーバービュー用：太い軸＋台形矢印のブロック矢印（右向きが 0°） */
export function BlockArrowHandle({
  cx,
  cy,
  r,
  rotDeg,
  color,
  active,
  onPointerDown,
}: BlockArrowHandleProps) {
  const d =
    "M -26 -7 L 10 -7 L 10 -13 L 30 0 L 10 13 L 10 7 L -26 7 Z";
  return (
    <g
      className={`pose-arrow-handle pose-arrow-handle--block${active ? " pose-arrow-handle--active" : ""}`}
      transform={`translate(${cx} ${cy}) rotate(${rotDeg})`}
      onPointerDown={onPointerDown}
    >
      <circle r={r} className="pose-arrow-hit" />
      <path
        d={d}
        fill={color}
        stroke="#1a1a1a"
        strokeWidth="1.1"
        strokeLinejoin="round"
        opacity="0.95"
        style={{ filter: "url(#pose-wobble)" }}
      />
    </g>
  );
}
