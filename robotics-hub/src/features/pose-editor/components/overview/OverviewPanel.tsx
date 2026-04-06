import type { PointerEvent } from "react";
import type { Vec2 } from "../../lib/kinematics";
import { OverviewLeftLeg } from "./OverviewLeftLeg";
import { OverviewRightLeg } from "./OverviewRightLeg";
import type { ActiveDrag, LegPose, OverviewFace } from "../../types";
import { PoseSketchFilters } from "../PoseSketchFilters";

export interface OverviewPanelProps {
  left: LegPose;
  right: LegPose;
  face: OverviewFace;
  activeDrag: ActiveDrag | null;
  onArrowDown: (
    e: PointerEvent,
    partial: Omit<ActiveDrag, "startClient" | "startAngle">
  ) => void;
}

/**
 * 両脚オーバービュー（正面／背面）とカゴフレーム
 */
export function OverviewPanel({
  left,
  right,
  face,
  activeDrag,
  onArrowDown,
}: OverviewPanelProps) {
  const legLen = 150;
  const mirror = face === "back";
  const dir: 1 | -1 = mirror ? -1 : 1;

  const faceLabel = face === "front" ? "正面" : "背面";

  const basketCenterX = 220;
  const basketHeight = 50;
  const basketWidth = 150;
  const basketTopY = 15;
  const basketBottomY = basketTopY + basketHeight;
  const basketLeftX = basketCenterX - basketWidth / 2;
  const basketRightX = basketCenterX + basketWidth / 2;
  const hipPosL: Vec2 = { x: basketLeftX + 20, y: basketBottomY };
  const hipPosR: Vec2 = { x: basketRightX - 20, y: basketBottomY };

  return (
    <svg
      className="pose-overview-svg"
      viewBox="0 0 440 278"
      role="img"
      aria-label={`オーバービュー（${faceLabel}）`}
    >
      <PoseSketchFilters />

      {/* カゴ（上辺＋左右脚位置へ下ろす U 字フレーム） */}
      <g style={{ filter: "url(#pose-wobble)" }} aria-hidden>
        <path
          d={`M ${basketLeftX} ${basketTopY} L ${basketLeftX} ${basketBottomY} L ${basketRightX} ${basketBottomY} L ${basketRightX} ${basketTopY}`}
          fill="none"
          stroke="black"
          strokeWidth="3.4"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
      </g>

      <OverviewLeftLeg
        hipPos={hipPosL}
        pose={left}
        legLen={legLen}
        dir={dir}
        activeDrag={activeDrag}
        onArrowDown={onArrowDown}
      />
      <OverviewRightLeg
        hipPos={hipPosR}
        pose={right}
        legLen={legLen}
        dir={dir}
        activeDrag={activeDrag}
        onArrowDown={onArrowDown}
      />

      <text x="220" y="266" textAnchor="middle" className="pose-legend">
        青は左足／赤は右足
      </text>
    </svg>
  );
}
