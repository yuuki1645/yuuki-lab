/** Pitch / Roll の傾斜ゲージ（フローティング窓・実機カメラ右ペインで共用） */

/** 1 ゲージの SVG 一辺（px） */
export const IMU_TILT_GAUGE_SIZE = 132;
const CX = IMU_TILT_GAUGE_SIZE / 2;
const CY = IMU_TILT_GAUGE_SIZE / 2;

function safeAngle(deg: number | undefined): number {
  if (typeof deg !== "number" || !Number.isFinite(deg)) return 0;
  return deg;
}

function fmtNum(deg: number | undefined) {
  if (typeof deg !== "number" || !Number.isFinite(deg)) return "—";
  return `${deg.toFixed(1)}°`;
}

type TiltGaugeProps = {
  /** 赤線の回転角（°）。センサー値をそのまま使用。SVG は Y 下向きなので表示と整合させるため符号を反転 */
  angleDeg: number;
  leftLabel: string;
  rightLabel: string;
  title: string;
  variant: "pitch" | "roll";
  dimmed: boolean;
};

function TiltGauge({
  angleDeg,
  leftLabel,
  rightLabel,
  title,
  variant,
  dimmed,
}: TiltGaugeProps) {
  const r = 58;
  const halfLine = r - 4;
  const rot = angleDeg;
  const GAUGE = IMU_TILT_GAUGE_SIZE;

  const labelClass =
    variant === "pitch"
      ? "imu-tilt-gauge-label imu-tilt-gauge-label--pitch"
      : "imu-tilt-gauge-label imu-tilt-gauge-label--roll";

  return (
    <div className={`imu-tilt-gauge ${dimmed ? "imu-tilt-gauge--idle" : ""}`}>
      <div className="imu-tilt-gauge-title">{title}</div>
      <svg
        className="imu-tilt-gauge-svg"
        width={GAUGE}
        height={GAUGE}
        viewBox={`0 0 ${GAUGE} ${GAUGE}`}
        aria-hidden
      >
        <circle
          cx={CX}
          cy={CY}
          r={r}
          fill="#0a0f1e"
          stroke="rgba(200, 210, 255, 0.38)"
          strokeWidth="2"
        />
        <line
          x1={CX - r}
          y1={CY}
          x2={CX + r}
          y2={CY}
          stroke="#5a6378"
          strokeWidth="1.5"
        />
        <line
          x1={CX}
          y1={CY - r}
          x2={CX}
          y2={CY + r}
          stroke="#5a6378"
          strokeWidth="1.5"
        />
        <text
          x={8}
          y={CY + 4}
          className={labelClass}
          textAnchor="start"
          fontSize="13"
          fontWeight={600}
        >
          {leftLabel}
        </text>
        <text
          x={GAUGE - 8}
          y={CY + 4}
          className={labelClass}
          textAnchor="end"
          fontSize="13"
          fontWeight={600}
        >
          {rightLabel}
        </text>
        <circle cx={CX} cy={CY} r={3} fill="#e8ecff" opacity={0.85} />
        <g transform={`rotate(${rot} ${CX} ${CY})`}>
          <line
            x1={CX - halfLine}
            y1={CY}
            x2={CX + halfLine}
            y2={CY}
            stroke="#d62828"
            strokeWidth="5"
            strokeLinecap="round"
          />
        </g>
      </svg>
    </div>
  );
}

export type ImuAttitudeGaugesProps = {
  pitch?: number;
  roll?: number;
  /** Socket.IO 接続済みか */
  connected: boolean;
  className?: string;
};

/**
 * Pitch / Roll を、十字線＋赤い傾斜線の二連ゲージで表示する。
 */
export default function ImuAttitudeGauges({
  pitch,
  roll,
  connected,
  className,
}: ImuAttitudeGaugesProps) {
  const dimmed = pitch === undefined && roll === undefined;
  const pitchAngle = safeAngle(pitch);
  const rollAngle = safeAngle(roll);

  return (
    <div className={"imu-attitude-body imu-attitude-body--tilt" + (className ? ` ${className}` : "")}>
      <div className="imu-tilt-gauges" aria-live="polite">
        <div className="imu-tilt-col">
          <TiltGauge
            angleDeg={pitchAngle}
            leftLabel="前"
            rightLabel="後"
            title="Pitch（ピッチ）"
            variant="pitch"
            dimmed={dimmed}
          />
          <div className="imu-tilt-value imu-tilt-value--pitch">
            Pitch <span className="imu-tilt-value-num">{fmtNum(pitch)}</span>
          </div>
        </div>
        <div className="imu-tilt-col">
          <TiltGauge
            angleDeg={rollAngle}
            leftLabel="左"
            rightLabel="右"
            title="Roll（ロール）"
            variant="roll"
            dimmed={dimmed}
          />
          <div className="imu-tilt-value imu-tilt-value--roll">
            Roll <span className="imu-tilt-value-num">{fmtNum(roll)}</span>
          </div>
        </div>
      </div>

      {!connected || dimmed ? (
        <p className="imu-attitude-hint">
          {connected ? "サンプル待ちです…" : "daemon に接続しています…"}
        </p>
      ) : null}
    </div>
  );
}
