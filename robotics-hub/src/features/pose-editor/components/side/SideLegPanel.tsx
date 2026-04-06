import type { PointerEvent } from "react";
import type { Servo } from "@/shared/types";
import { computeSideViewLeg, type Vec2 } from "../../lib/kinematics";
import { limitsFor } from "../../lib/servoUtils";
import type { ActiveDrag, JointKey, LegId, LegPose } from "../../types";
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

export interface SideLegPanelProps {
  leg: LegId;
  pose: LegPose;
  servos: Servo[];
  activeDrag: ActiveDrag | null;
  onArrowDown: (
    e: PointerEvent,
    partial: Omit<ActiveDrag, "startClient" | "startAngle">
  ) => void;
}

/**
 * 単脚の側面スケッチとドラッグ用矢印ハンドル
 */
export function SideLegPanel({
  leg,
  pose,
  servos,
  activeDrag,
  onArrowDown,
}: SideLegPanelProps) {
  const stroke = leg === "L" ? "#1d4ed8" : "#b91c1c";
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
    activeDrag.leg === leg &&
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
      onPointerDown={(e) => onArrowDown(e, { leg, key, axis, sign })}
    />
  );

  const hip2Limits = limitsFor(servos, leg, "hip2");
  const kneeL = limitsFor(servos, leg, "knee");
  const heelL = limitsFor(servos, leg, "heel");
  const hrL = limitsFor(servos, leg, "heelRoll");

  return (
    <svg
      className="pose-side-svg"
      viewBox="0 0 400 320"
      role="img"
      aria-label={leg === "L" ? "左足・横ビュー" : "右足・横ビュー"}
    >
      <PoseSketchFilters />
      <rect x="0" y="0" width="400" height="320" fill="transparent" />
      <g style={{ filter: "url(#pose-wobble)" }}>
        <text x="200" y="28" textAnchor="middle" className="pose-sketch-title">
          横（側面）
        </text>
        <g transform="translate(0 8)">
          <path
            d="M 118 52 L 62 52 L 62 120"
            fill="none"
            stroke="#111"
            strokeWidth="2.2"
            strokeLinecap="round"
          />
          <text x="90" y="48" textAnchor="middle" className="pose-front-marker">
            前
          </text>
        </g>

        <line
          x1={geo.hip.x}
          y1={geo.hip.y}
          x2={geo.knee.x}
          y2={geo.knee.y}
          stroke={stroke}
          strokeWidth="3.5"
          strokeLinecap="round"
        />
        <line
          x1={geo.knee.x}
          y1={geo.knee.y}
          x2={geo.ankle.x}
          y2={geo.ankle.y}
          stroke={stroke}
          strokeWidth="3.5"
          strokeLinecap="round"
        />
        <line
          x1={geo.ankle.x}
          y1={geo.ankle.y}
          x2={geo.foot.x}
          y2={geo.foot.y}
          stroke={stroke}
          strokeWidth="3.2"
          strokeLinecap="round"
        />

        {[geo.hip, geo.knee, geo.ankle].map((p, i) => (
          <circle
            key={i}
            cx={p.x}
            cy={p.y}
            r={7}
            fill="#fefcf6"
            stroke={stroke}
            strokeWidth="2.4"
          />
        ))}

        <text x={geo.hip.x + 18} y={geo.hip.y - 8} className="pose-joint-label">
          HIP② {Math.round(pose.hip2)}°
        </text>
        <text x={geo.knee.x + 14} y={geo.knee.y + 22} className="pose-joint-label">
          ひざ {Math.round(pose.knee)}°
        </text>
        <text x={geo.ankle.x - 52} y={geo.ankle.y + 6} className="pose-joint-label">
          かかと {Math.round(pose.heel)}°
        </text>
        <text x={geo.ankle.x + 18} y={geo.ankle.y + 26} className="pose-joint-label">
          ロール {Math.round(pose.heelRoll)}°
        </text>
      </g>

      {mk("hip2", "y", -1, geo.hip.x - 36, geo.hip.y, 90, "#1d4ed8")}
      {mk("hip2", "x", 1, geo.hip.x + 40, geo.hip.y, 0, "#b91c1c")}
      {mk("knee", "y", -1, geo.knee.x - 34, geo.knee.y, 90, "#b91c1c")}
      {mk("knee", "x", -1, geo.knee.x + 36, geo.knee.y, 180, "#1d4ed8")}
      {mk("heel", "y", -1, geo.ankle.x - 30, geo.ankle.y + 8, 90, "#b91c1c")}
      {mk("heelRoll", "x", 1, geo.ankle.x + 34, geo.ankle.y, 0, "#1d4ed8")}

      <text x="8" y="312" className="pose-hint">
        矢印をドラッグ／HIP② {hip2Limits.lo}°〜{hip2Limits.hi}° 膝 {kneeL.lo}°〜
        {kneeL.hi}° かかと {heelL.lo}°〜{heelL.hi}° ロール {hrL.lo}°〜{hrL.hi}°
      </text>
    </svg>
  );
}
