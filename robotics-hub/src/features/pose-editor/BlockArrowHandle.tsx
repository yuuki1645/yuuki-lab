import { faArrowRight } from "@fortawesome/free-solid-svg-icons";
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

/** 親 SVG の viewBox 単位での矢印の表示幅・高さ（脚の線幅と釣り合うよう控えめに） */
const ICON_SIZE = 18;

function faIconPathD(icon: typeof faArrowRight): string {
  const raw = icon.icon[4];
  return Array.isArray(raw) ? raw.join(" ") : raw;
}

/**
 * オーバービュー用の矢印ハンドル（Font Awesome Solid の右矢印パス）。
 * ネスト SVG に width/height/viewBox を明示し、親座標系で巨大化しないようにする。
 */
export function BlockArrowHandle({
  cx,
  cy,
  r,
  rotDeg,
  color,
  active,
  onPointerDown,
}: BlockArrowHandleProps) {
  const half = ICON_SIZE / 2;
  const [vbW, vbH] = [faArrowRight.icon[0], faArrowRight.icon[1]] as [
    number,
    number,
  ];
  const d = faIconPathD(faArrowRight);

  return (
    <g
      className={`pose-arrow-handle pose-arrow-handle--block${active ? " pose-arrow-handle--active" : ""}`}
      transform={`translate(${cx} ${cy}) rotate(${rotDeg})`}
      onPointerDown={onPointerDown}
    >
      <circle r={r} className="pose-arrow-hit" />
      <g transform={`translate(${-half} ${-half})`}>
        <svg
          width={ICON_SIZE}
          height={ICON_SIZE}
          viewBox={`0 0 ${vbW} ${vbH}`}
          aria-hidden
        >
          <path d={d} fill={color} />
        </svg>
      </g>
    </g>
  );
}
