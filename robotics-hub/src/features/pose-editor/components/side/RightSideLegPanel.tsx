import type { PointerEvent } from "react";
import type { Servo } from "@/shared/types";
import { limitsFor } from "../../lib/servoUtils";
import type { ActiveDrag, LegPose } from "../../types";
import { PoseSketchFilters } from "../PoseSketchFilters";

export interface RightSideLegPanelProps {
  pose: LegPose;
  servos: Servo[];
  activeDrag: ActiveDrag | null;
  onArrowDown: (
    e: PointerEvent,
    partial: Omit<ActiveDrag, "startClient" | "startAngle">
  ) => void;
}

/** 右足・側面スケッチパネル */
export function RightSideLegPanel({
  pose,
  servos,
  onArrowDown,
}: RightSideLegPanelProps) {
  const stroke = "#b91c1c";

  const hip2Limits = limitsFor(servos, "R", "hip2");
  const kneeL = limitsFor(servos, "R", "knee");
  const heelL = limitsFor(servos, "R", "heel");
  const hrL = limitsFor(servos, "R", "heelRoll");

  const basketTopY = 10;
  const basketCenterX = 200;
  const basketWidth = 100;
  const basketLeftX = basketCenterX - basketWidth / 2;
  const basketRightX = basketCenterX + basketWidth / 2;
  const basketHeight = 50;
  const basketBottomY = basketTopY + basketHeight;

  function BasketFrame() {
    return (
      <g transform="translate(0 0)">
        <path
          d={`M ${basketLeftX} ${basketTopY} L ${basketLeftX} ${basketBottomY} L ${basketRightX} ${basketBottomY} L ${basketRightX} ${basketTopY}`}
          fill="none"
          stroke="#111"
          strokeWidth="2.2"
          strokeLinecap="round"
        />
      </g>
    );
  }

  const hipX = basketCenterX;
  const hipY = basketBottomY;
  const length1 = 20;
  const lengthHipToKnee = 80;
  const lengthShank = 70;
  const lengthHeel = 20;
  const lengthSole = 50;

  const logicalHip2 = pose.hip2;
  const logicalKnee = pose.knee;
  const logicalHeel = pose.heel;

  const Hip1 = { cx: hipX, cy: hipY };
  const Hip2 = { cx: hipX, cy: hipY + length1 };
  const angle1 = logicalHip2;
  const Knee = {
    cx: Hip2.cx - lengthHipToKnee * Math.cos(angle1 * Math.PI / 180),
    cy: Hip2.cy + lengthHipToKnee * Math.sin(angle1 * Math.PI / 180),
  };
  const angle2 = logicalHip2 + logicalKnee;
  const HeelRoll = {
    cx: Knee.cx - lengthShank * Math.cos(angle2 * Math.PI / 180),
    cy: Knee.cy + lengthShank * Math.sin(angle2 * Math.PI / 180),
  };
  const angle3 = logicalHip2 + logicalKnee + logicalHeel;
  const Heel = {
    cx: HeelRoll.cx - lengthHeel * Math.cos(angle3 * Math.PI / 180),
    cy: HeelRoll.cy + lengthHeel * Math.sin(angle3 * Math.PI / 180),
  };
  const angle4 = logicalHip2 + logicalKnee + logicalHeel - 90;
  const Sole = {
    cx: Heel.cx - lengthSole * Math.cos(angle4 * Math.PI / 180),
    cy: Heel.cy + lengthSole * Math.sin(angle4 * Math.PI / 180),
  };
  type BoneSegment = { x1: number; y1: number; x2: number; y2: number };

  const Hip1ToHip2: BoneSegment = {
    x1: Hip1.cx,
    y1: Hip1.cy,
    x2: Hip2.cx,
    y2: Hip2.cy,
  };
  const Thigh: BoneSegment = {
    x1: Hip2.cx,
    y1: Hip2.cy,
    x2: Knee.cx,
    y2: Knee.cy,
  };
  const Shank: BoneSegment = {
    x1: Knee.cx,
    y1: Knee.cy,
    x2: HeelRoll.cx,
    y2: HeelRoll.cy,
  };
  const HeelRollToHeel: BoneSegment = {
    x1: HeelRoll.cx,
    y1: HeelRoll.cy,
    x2: Heel.cx,
    y2: Heel.cy,
  };
  const HeelRollToSole: BoneSegment = {
    x1: Heel.cx,
    y1: Heel.cy,
    x2: Sole.cx,
    y2: Sole.cy,
  };

  const jointDot = (j: { cx: number; cy: number }) => (
    <circle
      cx={j.cx}
      cy={j.cy}
      r={6}
      fill="#fefcf6"
      stroke={stroke}
      strokeWidth={2}
    />
  );

  const boneLine = (s: BoneSegment) => (
    <line
      x1={s.x1}
      y1={s.y1}
      x2={s.x2}
      y2={s.y2}
      stroke={stroke}
      strokeWidth={3.5}
      strokeLinecap="round"
    />
  );

  return (
    <svg
      className="pose-side-svg"
      viewBox="0 0 400 320"
      role="img"
      aria-label="右足・横ビュー"
    >
      <PoseSketchFilters />
      <rect x="0" y="0" width="400" height="320" fill="transparent" />
      <g style={{ filter: "url(#pose-wobble)" }}>
        <BasketFrame />
        {jointDot(Hip1)}
        {boneLine(Hip1ToHip2)}
        {jointDot(Hip2)}
        {boneLine(Thigh)}
        {jointDot(Knee)}
        {boneLine(Shank)}
        {jointDot(HeelRoll)}
        {boneLine(HeelRollToHeel)}
        {jointDot(Heel)}

        <line
          x1={HeelRollToSole.x1}
          y1={HeelRollToSole.y1}
          x2={HeelRollToSole.x2}
          y2={HeelRollToSole.y2}
          stroke={stroke}
          strokeWidth={3.5}
          strokeLinecap="round"
        />

        <text x={30} y={100} className="pose-joint-label">
          HIP② {Math.round(pose.hip2)}°
        </text>

        <g transform="translate(50 130) rotate(-49)">
          <image
            href="/arrows/top_left.png"
            width={40}
            height={40}
            onPointerDown={(e) => onArrowDown(e, { leg: "R", key: "hip2", axis: "x", sign: 1 })}
          />
        </g>

        <text x={30} y={170} className="pose-joint-label">
          ひざ {Math.round(pose.knee)}°
        </text>

        <g transform="translate(50 205) rotate(-49)">
          <image
            href="/arrows/top_left.png"
            width={40}
            height={40}
            onPointerDown={(e) => onArrowDown(e, { leg: "R", key: "knee", axis: "x", sign: 1 })}
          />
        </g>

        <text x={250} y={200} className="pose-joint-label">
          かかと {Math.round(pose.heel)}°
        </text>

        <g transform="translate(250 250) rotate(-49)">
          <image
            href="/arrows/top_left.png"
            width={40}
            height={40}
            onPointerDown={(e) => onArrowDown(e, { leg: "R", key: "heel", axis: "x", sign: 1 })}
          />
        </g>
      </g>

      <text x="8" y="312" className="pose-hint">
        矢印をドラッグ／HIP② {hip2Limits.lo}°〜{hip2Limits.hi}° 膝 {kneeL.lo}°〜
        {kneeL.hi}° かかと {heelL.lo}°〜{heelL.hi}° ロール {hrL.lo}°〜{hrL.hi}°
      </text>
    </svg>
  );
}
