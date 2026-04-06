import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { moveServo } from "@/shared/api/servoApi";
import { SERVO_NAME_TO_CH } from "@/shared/constants";
import { clamp } from "@/shared/utils";
import type { Servo } from "@/shared/types";
import { useServos } from "@/shared/hooks/useServos";
import { computeSideViewLeg, type Vec2 } from "./poseKinematics";
import { OverviewLeftLeg } from "./OverviewLeftLeg";
import { OverviewRightLeg } from "./OverviewRightLeg";
import type { ActiveDrag, JointKey, LegId, LegPose } from "./poseEditorTypes";
import "./PoseEditorPage.css";

const SERVO_SUFFIX: Record<JointKey, string> = {
  hip1: "HIP1",
  hip2: "HIP2",
  knee: "KNEE",
  heel: "HEEL",
  heelRoll: "HEEL_ROLL",
};

function servoName(leg: LegId, key: JointKey): string {
  return `${leg}_${SERVO_SUFFIX[key]}`;
}

function readLegFromServos(servos: Servo[], leg: LegId): LegPose {
  const get = (k: JointKey) => {
    const name = servoName(leg, k);
    const s = servos.find((x) => x.name === name);
    return s ? Math.round(s.last_logical) : 0;
  };
  return {
    hip1: get("hip1"),
    hip2: get("hip2"),
    knee: get("knee"),
    heel: get("heel"),
    heelRoll: get("heelRoll"),
  };
}

function limitsFor(servos: Servo[], leg: LegId, key: JointKey) {
  const name = servoName(leg, key);
  const s = servos.find((x) => x.name === name);
  return {
    lo: s?.logical_lo ?? -90,
    hi: s?.logical_hi ?? 90,
  };
}

const SENS = 0.32;

function SketchFilters() {
  return (
    <defs>
      <filter id="pose-wobble" x="-5%" y="-5%" width="110%" height="110%">
        <feTurbulence
          type="fractalNoise"
          baseFrequency="0.04"
          numOctaves="2"
          result="noise"
        />
        <feDisplacementMap in="SourceGraphic" in2="noise" scale="1.2" />
      </filter>
    </defs>
  );
}

function ArrowHandle(props: {
  cx: number;
  cy: number;
  r: number;
  rotDeg: number;
  color: string;
  active: boolean;
  onPointerDown: (e: React.PointerEvent) => void;
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

interface SideLegPanelProps {
  leg: LegId;
  pose: LegPose;
  servos: Servo[];
  activeDrag: ActiveDrag | null;
  onArrowDown: (e: React.PointerEvent, partial: Omit<ActiveDrag, "startClient" | "startAngle">) => void;
}

function SideLegPanel({
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
    <ArrowHandle
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
      <SketchFilters />
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

type OverviewFace = "front" | "back";

interface OverviewProps {
  left: LegPose;
  right: LegPose;
  face: OverviewFace;
  activeDrag: ActiveDrag | null;
  onArrowDown: (e: React.PointerEvent, partial: Omit<ActiveDrag, "startClient" | "startAngle">) => void;
}

function OverviewPanel({
  left,
  right,
  face,
  activeDrag,
  onArrowDown,
}: OverviewProps) {
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
      <SketchFilters />

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

export default function PoseEditorPage() {
  const { servos, loading, error } = useServos();
  const [left, setLeft] = useState<LegPose>({
    hip1: 0,
    hip2: 90,
    knee: 0,
    heel: 0,
    heelRoll: 0,
  });
  const [right, setRight] = useState<LegPose>({
    hip1: 0,
    hip2: 90,
    knee: 0,
    heel: 0,
    heelRoll: 0,
  });
  const [sideTab, setSideTab] = useState<LegId>("L");
  const [overviewFace, setOverviewFace] = useState<OverviewFace>("front");
  const [activeDrag, setActiveDrag] = useState<ActiveDrag | null>(null);

  const initRef = useRef(false);
  const dragRef = useRef<ActiveDrag | null>(null);
  const poseRef = useRef<{ L: LegPose; R: LegPose }>({ L: left, R: right });
  const apiTimers = useRef<Partial<Record<number, ReturnType<typeof setTimeout>>>>({});
  const moveSeqRef = useRef(0);
  const servosRef = useRef<Servo[]>(servos);

  useEffect(() => {
    poseRef.current = { L: left, R: right };
  }, [left, right]);

  useEffect(() => {
    servosRef.current = servos;
  }, [servos]);

  useEffect(() => {
    if (!servos.length || initRef.current) return;
    const L = readLegFromServos(servos, "L");
    const R = readLegFromServos(servos, "R");
    setLeft(L);
    setRight(R);
    poseRef.current = { L, R };
    initRef.current = true;
  }, [servos]);

  const setLegAngle = useCallback((leg: LegId, key: JointKey, v: number) => {
    const loHi = limitsFor(servosRef.current, leg, key);
    const clamped = clamp(v, loHi.lo, loHi.hi);
    if (leg === "L") {
      setLeft((p) => {
        const next = { ...p, [key]: clamped };
        poseRef.current = { ...poseRef.current, L: next };
        return next;
      });
    } else {
      setRight((p) => {
        const next = { ...p, [key]: clamped };
        poseRef.current = { ...poseRef.current, R: next };
        return next;
      });
    }
    return clamped;
  }, []);

  const pushServo = useCallback(
    (leg: LegId, key: JointKey, angle: number, immediate = false) => {
    if (error) return;

    const name = servoName(leg, key);
    const ch = SERVO_NAME_TO_CH[name];
    if (ch === undefined) return;

    const run = async () => {
      const seq = ++moveSeqRef.current;
      try {
        await moveServo(ch, "logical", angle);
      } catch (err) {
        if (seq !== moveSeqRef.current) return;
        window.alert(
          `サーボ指令エラー (${name}):\n${err instanceof Error ? err.message : String(err)}`
        );
      } finally {
        delete apiTimers.current[ch];
      }
    };

    if (immediate) {
      clearTimeout(apiTimers.current[ch]);
      void run();
      return;
    }
    clearTimeout(apiTimers.current[ch]);
    apiTimers.current[ch] = setTimeout(run, 95);
  },
    [error]
  );

  const flushDragPointerUp = useCallback(() => {
    const d = dragRef.current;
    if (!d) return;
    const snap = poseRef.current[d.leg][d.key];
    pushServo(d.leg, d.key, snap, true);
  }, [pushServo]);

  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      const d = dragRef.current;
      if (!d) return;
      console.log("onMove");
      const cur = d.axis === "x" ? e.clientX : e.clientY;
      const delta = cur - d.startClient;
      const next = d.startAngle + delta * SENS * d.sign;
      const v = setLegAngle(d.leg, d.key, next);
      pushServo(d.leg, d.key, v, false);
    };

    const onUp = () => {
      flushDragPointerUp();
      dragRef.current = null;
      setActiveDrag(null);
    };

    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", onUp);
    };
  }, [setLegAngle, pushServo, flushDragPointerUp]);

  const onArrowDown = useCallback(
    (e: React.PointerEvent, partial: Omit<ActiveDrag, "startClient" | "startAngle">) => {
      e.preventDefault();
      e.stopPropagation();
      console.log("onArrowDown", partial);
      const pose = poseRef.current[partial.leg];
      const startAngle = pose[partial.key];
      const startClient = partial.axis === "x" ? e.clientX : e.clientY;
      const next: ActiveDrag = {
        ...partial,
        startClient,
        startAngle,
      };
      dragRef.current = next;
      setActiveDrag(next);
      try {
        (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
      } catch {
        /* noop */
      }
    },
    []
  );

  const readout = useMemo(() => ({ L: left, R: right }), [left, right]);

  if (loading) {
    return (
      <div className="pose-editor pose-editor--centered">
        <h1 className="pose-editor-title">ポーズエディタ</h1>
        <p>読み込み中…</p>
      </div>
    );
  }

  return (
    <div className="pose-editor">
      <header className="pose-editor-header">
        <h1 className="pose-editor-title">ポーズエディタ</h1>
        <p className="pose-editor-lead">
          メモ風の脚スケッチをドラッグして関節角を変えます。数値は論理角（度）です。
        </p>
        {error ? (
          <p className="pose-editor-warn" role="alert">
            サーボ API に接続できませんでした（{error}）。表示とドラッグは試せますが、実機への反映は失敗します。
          </p>
        ) : null}
      </header>

      <div className="pose-editor-grid">
        <section className="pose-card" aria-labelledby="pose-overview-heading">
          <div className="pose-overview-card-head">
            <h2 id="pose-overview-heading" className="pose-card-title">
              オーバービュー
            </h2>
            <div
              className="pose-overview-toggle"
              role="group"
              aria-label="正面・背面の切り替え"
            >
              <button
                type="button"
                className={`pose-face-btn${overviewFace === "front" ? " pose-face-btn--on" : ""}`}
                aria-pressed={overviewFace === "front"}
                onClick={() => setOverviewFace("front")}
              >
                正面
              </button>
              <button
                type="button"
                className={`pose-face-btn${overviewFace === "back" ? " pose-face-btn--on" : ""}`}
                aria-pressed={overviewFace === "back"}
                onClick={() => setOverviewFace("back")}
              >
                背面
              </button>
            </div>
          </div>
          <OverviewPanel
            left={readout.L}
            right={readout.R}
            face={overviewFace}
            activeDrag={activeDrag}
            onArrowDown={onArrowDown}
          />
        </section>

        <section className="pose-card" aria-labelledby="pose-side-heading">
          <div className="pose-side-head">
            <h2 id="pose-side-heading" className="pose-card-title">
              詳細（横から）
            </h2>
            <div className="pose-tabs" role="tablist" aria-label="足の選択">
              <button
                type="button"
                role="tab"
                aria-selected={sideTab === "L"}
                className={`pose-tab${sideTab === "L" ? " pose-tab--on" : ""}`}
                onClick={() => setSideTab("L")}
              >
                左足（青）
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={sideTab === "R"}
                className={`pose-tab${sideTab === "R" ? " pose-tab--on" : ""}`}
                onClick={() => setSideTab("R")}
              >
                右足（赤）
              </button>
            </div>
          </div>

          <SideLegPanel
            leg={sideTab}
            pose={sideTab === "L" ? readout.L : readout.R}
            servos={servos}
            activeDrag={activeDrag}
            onArrowDown={onArrowDown}
          />

          <dl className="pose-readout">
            <div className="pose-readout-row">
              <dt>HIP①</dt>
              <dd>{Math.round((sideTab === "L" ? readout.L : readout.R).hip1)}°</dd>
            </div>
            <div className="pose-readout-row">
              <dt>HIP②</dt>
              <dd>{Math.round((sideTab === "L" ? readout.L : readout.R).hip2)}°</dd>
            </div>
            <div className="pose-readout-row">
              <dt>ひざ</dt>
              <dd>{Math.round((sideTab === "L" ? readout.L : readout.R).knee)}°</dd>
            </div>
            <div className="pose-readout-row">
              <dt>かかと</dt>
              <dd>{Math.round((sideTab === "L" ? readout.L : readout.R).heel)}°</dd>
            </div>
            <div className="pose-readout-row">
              <dt>かかとロール</dt>
              <dd>{Math.round((sideTab === "L" ? readout.L : readout.R).heelRoll)}°</dd>
            </div>
          </dl>
        </section>
      </div>
    </div>
  );
}
