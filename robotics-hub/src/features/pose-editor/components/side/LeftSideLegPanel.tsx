import type { PointerEvent } from "react";
import type { Servo } from "@/shared/types";
import { computeSideViewLeg, type Vec2 } from "../../lib/kinematics";
import { limitsFor } from "../../lib/servoUtils";
import type { ActiveDrag, JointKey, LegPose } from "../../types";
import { PoseSketchFilters } from "../PoseSketchFilters";

function SideLegArrowHandle(props: {
  cx: number;
  cy: number;
  r: number;
  rotDeg: number;
  color: string;
  active: boolean;
  onPointerDown: (e: PointerEvent) => void;
}) {
  const { cx, cy, r, rotDeg, color, active, onPointerDown } = props;
  return (
    <g
      className={`pose-arrow-handle${active ? " pose-arrow-handle--active" : ""}`}
      transform={`translate(${cx} ${cy}) rotate(${rotDeg})`}
      onPointerDown={onPointerDown}
    >
      <circle r={r} className="pose-arrow-hit" />
      <path
        d="M0 -6 L14 0 L0 6 L4 0 Z"
        fill={color}
        stroke="#1a1a1a"
        strokeWidth="0.6"
        opacity="0.92"
        style={{ filter: "url(#pose-wobble)" }}
      />
    </g>
  );
}

export interface LeftSideLegPanelProps {
  pose: LegPose;
  servos: Servo[];
  activeDrag: ActiveDrag | null;
  onArrowDown: (
    e: PointerEvent,
    partial: Omit<ActiveDrag, "startClient" | "startAngle">
  ) => void;
}

/** 左足・側面スケッチパネル */
export function LeftSideLegPanel({
  pose,
  servos,
  activeDrag,
  onArrowDown,
}: LeftSideLegPanelProps) {
  const stroke = "#1d4ed8";
  const upperLen = 88;
  const lowerLen = 76;
  const footLen = 28;
  const hipBase: Vec2 = { x: 200, y: 36 };
  const geo = computeSideViewLeg(
    hipBase,
    upperLen,
    lowerLen,
    footLen,
    pose.hip2,
    pose.knee,
    pose.heel
  );

  const isActive = (key: JointKey, axis: "x" | "y") =>
    activeDrag != null &&
    activeDrag.leg === "L" &&
    activeDrag.key === key &&
    activeDrag.axis === axis;

  const mk = (
    key: JointKey,
    axis: "x" | "y",
    sign: 1 | -1,
    cx: number,
    cy: number,
    rot: number,
    color: string
  ) => (
    <SideLegArrowHandle
      key={`${key}-${axis}-${rot}-${cx}`}
      cx={cx}
      cy={cy}
      r={26}
      rotDeg={rot}
      color={color}
      active={isActive(key, axis)}
      onPointerDown={(e) =>
        onArrowDown(e, { leg: "L", key, axis, sign })
      }
    />
  );

  const hip2Limits = limitsFor(servos, "L", "hip2");
  const kneeL = limitsFor(servos, "L", "knee");
  const heelL = limitsFor(servos, "L", "heel");
  const hrL = limitsFor(servos, "L", "heelRoll");

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
    )
  }

  const hipX = basketCenterX;
  const hipY = basketBottomY;
  const length1 = 20;
  const lengthHipToKnee = 80;
  const lengthShank = 70;
  const lengthHeel = 20;
  const lengthSole = 50;

  const logicalHip2 = pose.hip2;
  // const logicalHip2 = 40;
  // console.log("logicalHip2", logicalHip2);
  // const logicalKnee = pose.knee;
  const logicalKnee = 30;
  // console.log("logicalKnee", logicalKnee);
  // const logicalHeelRoll = pose.heelRoll;
  const logicalHeelRoll = 90;
  // console.log("logicalHeelRoll", logicalHeelRoll);
  
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
  const angle3 = logicalHip2 + logicalKnee + (logicalHeelRoll - 90);
  const Heel = { 
    cx: HeelRoll.cx - lengthHeel * Math.cos(angle3 * Math.PI / 180), 
    cy: HeelRoll.cy + lengthHeel * Math.sin(angle3 * Math.PI / 180),
  };
  const angle4 = logicalHip2 + logicalKnee + (logicalHeelRoll - 90) - 90;
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
      aria-label="左足・横ビュー"
    >
      <PoseSketchFilters />
      <rect x="0" y="0" width="400" height="320" fill="transparent" />
      <g style={{ filter: "url(#pose-wobble)" }}>
        {/* <text x="200" y="28" textAnchor="middle" className="pose-sketch-title">
          横（側面）
        </text> */}

        <BasketFrame />

        {/* <text x="90" y="48" textAnchor="middle" className="pose-front-marker">
          aaa前
        </text> */}
        {jointDot(Hip1)}
        {boneLine(Hip1ToHip2)}
        {jointDot(Hip2)}
        {boneLine(Thigh)}
        {jointDot(Knee)}
        {boneLine(Shank)}
        {jointDot(HeelRoll)}
        {boneLine(HeelRollToHeel)}
        {jointDot(Heel)}
        {boneLine(HeelRollToSole)}

        <g transform="translate(50 130) rotate(-49)">
          <image
            href="/arrows/top_left.png"
            width={40}
            height={40}
            onPointerDown={(e) => onArrowDown(e, { leg: "L", key: "hip2", axis: "x", sign: 1 })}
          />
        </g>

        <text x={30} y={100} className="pose-joint-label">
          HIP② {Math.round(pose.hip2)}°
        </text>
        {/* <text x={geo.knee.x + 14} y={geo.knee.y + 22} className="pose-joint-label">
          ひざ {Math.round(pose.knee)}°
        </text>
        <text x={geo.ankle.x - 52} y={geo.ankle.y + 6} className="pose-joint-label">
          かかと {Math.round(pose.heel)}°
        </text>
        <text x={geo.ankle.x + 18} y={geo.ankle.y + 26} className="pose-joint-label">
          ロール {Math.round(pose.heelRoll)}°
        </text> */}
      </g>

      {/* {mk("hip2", "y", -1, geo.hip.x - 36, geo.hip.y, 90, "#1d4ed8")}
      {mk("hip2", "x", 1, geo.hip.x + 40, geo.hip.y, 0, "#b91c1c")}
      {mk("knee", "y", -1, geo.knee.x - 34, geo.knee.y, 90, "#b91c1c")}
      {mk("knee", "x", -1, geo.knee.x + 36, geo.knee.y, 180, "#1d4ed8")}
      {mk("heel", "y", -1, geo.ankle.x - 30, geo.ankle.y + 8, 90, "#b91c1c")}
      {mk("heelRoll", "x", 1, geo.ankle.x + 34, geo.ankle.y, 0, "#1d4ed8")} */}

      <text x="8" y="312" className="pose-hint">
        矢印をドラッグ／HIP② {hip2Limits.lo}°〜{hip2Limits.hi}° 膝 {kneeL.lo}°〜
        {kneeL.hi}° かかと {heelL.lo}°〜{heelL.hi}° ロール {hrL.lo}°〜{hrL.hi}°
      </text>
    </svg>
  );
}
