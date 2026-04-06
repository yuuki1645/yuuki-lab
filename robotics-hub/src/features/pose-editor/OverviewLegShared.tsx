import type { PointerEvent } from "react";
import type { ActiveDrag, LegPose } from "./poseEditorTypes";
import type { Vec2 } from "./poseKinematics";

/** Vite の `public/` からそのまま配信 */
export const ARROW_IMAGE_BLUE = "/arrows/top_left.png";
export const ARROW_IMAGE_RED = "/arrows/bottom_right.png";

export const OVERVIEW_ARROW_SIZE = 30;
export const OVERVIEW_ARROW_HIT_R = 22;

export type OverviewLegBaseProps = {
  hipPos: Vec2;
  pose: LegPose;
  legLen: number;
  /** 正面/背面の左右反転（1 または -1） */
  dir: 1 | -1;
  activeDrag: ActiveDrag | null;
  onArrowDown: (
    e: PointerEvent,
    partial: Omit<ActiveDrag, "startClient" | "startAngle">
  ) => void;
};

type OverviewPointerArrowProps = {
  cx: number;
  cy: number;
  rotDeg: number;
  href: string;
  active: boolean;
  onPointerDown: (e: PointerEvent<SVGGElement>) => void;
};

/** オーバービュー用：透明ヒット円＋回転した矢印 PNG */
export function overviewPointerArrow({
  cx,
  cy,
  rotDeg,
  href,
  active,
  onPointerDown,
}: OverviewPointerArrowProps) {
  const half = OVERVIEW_ARROW_SIZE / 2;
  return (
    <g
      className={`pose-arrow-handle pose-arrow-handle--block${active ? " pose-arrow-handle--active" : ""}`}
      transform={`translate(${cx} ${cy}) rotate(${rotDeg})`}
      onPointerDown={onPointerDown}
    >
      <circle r={OVERVIEW_ARROW_HIT_R} className="pose-arrow-hit" />
      <g transform={`translate(${-half} ${-half})`}>
        <image
          href={href}
          width={OVERVIEW_ARROW_SIZE}
          height={OVERVIEW_ARROW_SIZE}
          preserveAspectRatio="xMidYMid meet"
          aria-hidden
        />
      </g>
    </g>
  );
}
