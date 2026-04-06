import type { PointerEvent } from "react";
import { hip1SpreadPx, type Vec2 } from "./poseKinematics";
import type { ActiveDrag, JointKey, LegId, LegPose } from "./poseEditorTypes";

/** Vite の `public/` からそのまま配信 */
const ARROW_IMAGE_BLUE = "/arrows/top_left.png";
const ARROW_IMAGE_RED = "/arrows/bottom_right.png";

const OVERVIEW_ARROW_SIZE = 30;
const OVERVIEW_ARROW_HIT_R = 22;

type OverviewPointerArrowProps = {
  cx: number;
  cy: number;
  rotDeg: number;
  href: string;
  active: boolean;
  onPointerDown: (e: PointerEvent<SVGGElement>) => void;
};

/** オーバービュー用：透明ヒット円＋回転した矢印 PNG（このファイル専用） */
function overviewPointerArrow({
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

export interface MiniLegProps {
  hipPos: Vec2;
  leg: LegId;
  pose: LegPose;
  legLen: number;
  /** 正面/背面の左右反転（1 または -1） */
  dir: 1 | -1;
  activeDrag: ActiveDrag | null;
  onArrowDown: (
    e: PointerEvent,
    partial: Omit<ActiveDrag, "startClient" | "startAngle">
  ) => void;
}

/**
 * オーバービュー用の簡略脚（縦1本＋股・足先のマーク）
 */
export function MiniLeg({
  hipPos,
  leg,
  pose,
  legLen,
  dir,
  activeDrag,
  onArrowDown,
}: MiniLegProps) {
  const stroke = leg === "L" ? "#1d4ed8" : "#b91c1c";
  const spread = hip1SpreadPx(pose.hip1);
  const hipX = hipPos.x + dir * (leg === "L" ? -spread : spread);
  const hipY = hipPos.y;
  const footX = hipX;
  const footY = hipY + legLen;

  const isActive = (key: JointKey, axis: "x" | "y") =>
    activeDrag != null &&
    activeDrag.leg === leg &&
    activeDrag.key === key &&
    activeDrag.axis === axis;

  return (
    <g>
      <line
        x1={hipX}
        y1={hipY}
        x2={footX}
        y2={footY}
        stroke={stroke}
        strokeWidth="3"
        strokeLinecap="round"
      />
      <circle
        cx={hipX}
        cy={hipY}
        r={6}
        fill="#fefcf6"
        stroke={stroke}
        strokeWidth="2"
      />
      <circle
        cx={footX}
        cy={footY}
        r={6}
        fill="#fefcf6"
        stroke={stroke}
        strokeWidth="2"
      />

      <text
        x={hipX}
        y={hipY - 10}
        textAnchor="middle"
        className="pose-joint-label"
      >
        HIP① {Math.round(pose.hip1)}°
      </text>
      <text
        x={footX - 50}
        y={footY - 25}
        textAnchor="middle"
        className="pose-joint-label"
      >
        かかと {Math.round(pose.heel)}°
      </text>

      {overviewPointerArrow({
        cx: hipX - 100,
        cy: hipY + 10,
        rotDeg: 90,
        href: ARROW_IMAGE_BLUE,
        active: isActive("hip1", "x"),
        onPointerDown: (e) =>
          onArrowDown(e, {
            leg,
            key: "hip1",
            axis: "x",
            sign: leg === "L" ? -1 : 1,
          }),
      })}
      {overviewPointerArrow({
        cx: footX - 33,
        cy: footY - 3,
        rotDeg: 0,
        href: ARROW_IMAGE_BLUE,
        active: isActive("hip2", "y"),
        onPointerDown: (e) =>
          onArrowDown(e, { leg, key: "hip2", axis: "y", sign: -1 }),
      })}
      {overviewPointerArrow({
        cx: footX - 10,
        cy: footY + 30,
        rotDeg: 0,
        href: ARROW_IMAGE_RED,
        active: isActive("heel", "y"),
        onPointerDown: (e) =>
          onArrowDown(e, { leg, key: "heel", axis: "y", sign: -1 }),
      })}
    </g>
  );
}
