import { useId } from "react";
import type { ImuDaemonStream } from "@/shared/hooks/useImuDaemonStream";
import { useFloatingPanelDrag } from "@/shared/hooks/useFloatingPanelDrag";

type ImuAttitudeFloatingWindowProps = {
  open: boolean;
  onClose: () => void;
  stream: ImuDaemonStream;
};

const SIZE = 240;
const CX = SIZE / 2;
const CY = SIZE / 2;
const R = (SIZE / 2) * 0.92;
/** 1° あたりの地平線の移動量（px） */
const PITCH_PX_PER_DEG = 2.8;
/** 表示するピッチのクランプ（過大な値で凡例が空白になるのを防ぐ） */
const MAX_PITCH_DEG = 45;
const MAX_ROLL_DEG = 90;

function clamp(n: number, lo: number, hi: number) {
  return Math.min(Math.max(n, lo), hi);
}

function fmtDeg(label: string, value?: number) {
  if (typeof value !== "number" || !Number.isFinite(value)) return `${label} —°`;
  return `${label} ${value.toFixed(1)}°`;
}

/**
 * 簡易人工水平儀：ロールで地平線を傾け、ピッチで上下にずらす。
 * （機体記号は画面中央に固定）
 */
export default function ImuAttitudeFloatingWindow({
  open,
  onClose,
  stream,
}: ImuAttitudeFloatingWindowProps) {
  const uid = useId().replace(/:/g, "");
  const clipId = `imu-attitude-clip-${uid}`;
  const skyGradId = `imu-attitude-sky-${uid}`;
  const groundGradId = `imu-attitude-ground-${uid}`;

  const { wsStatus, imuSample } = stream;

  const { pos, headerPointerHandlers } = useFloatingPanelDrag({
    panelOpen: open,
    initial: { x: 360, y: 96 },
    panelWidth: SIZE + 32,
    panelHeight: SIZE + 120,
  });

  const pitchRaw = imuSample?.angle?.pitch ?? 0;
  const rollRaw = imuSample?.angle?.roll ?? 0;
  const pitch = clamp(pitchRaw, -MAX_PITCH_DEG, MAX_PITCH_DEG);
  const roll = clamp(rollRaw, -MAX_ROLL_DEG, MAX_ROLL_DEG);
  const pitchPx = clamp(pitch * PITCH_PX_PER_DEG, -R * 1.25, R * 1.25);

  if (!open) return null;

  return (
    <div
      className="imu-attitude-float"
      style={{ left: pos.x, top: pos.y }}
      role="dialog"
      aria-labelledby="imu-attitude-title"
    >
      <div className="imu-float-header" {...headerPointerHandlers}>
        <span id="imu-attitude-title" className="imu-float-title">
          IMU 姿勢（ピッチ／ロール）
        </span>
        <button
          type="button"
          className="imu-float-close"
          aria-label="閉じる"
          onClick={onClose}
        >
          ×
        </button>
      </div>

      <div className="imu-attitude-body">
        <svg
          className={
            imuSample
              ? "imu-attitude-svg"
              : "imu-attitude-svg imu-attitude-svg--idle"
          }
          width={SIZE}
          height={SIZE}
          viewBox={`0 0 ${SIZE} ${SIZE}`}
          aria-hidden
        >
          <defs>
            <clipPath id={clipId}>
              <circle cx={CX} cy={CY} r={R} />
            </clipPath>
            <linearGradient id={skyGradId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#3d6fb8" />
              <stop offset="100%" stopColor="#6ba3e8" />
            </linearGradient>
            <linearGradient id={groundGradId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#6b4c2e" />
              <stop offset="100%" stopColor="#3d2a18" />
            </linearGradient>
          </defs>

          {/* 外枠 */}
          <circle
            cx={CX}
            cy={CY}
            r={R + 4}
            fill="none"
            stroke="rgba(200,210,255,0.35)"
            strokeWidth="3"
          />

          <g clipPath={`url(#${clipId})`}>
            {/* 地平線より奥：ロール → ピッチ の順で変換 */}
            <g transform={`translate(${CX} ${CY}) rotate(${roll}) translate(0 ${pitchPx})`}>
              <rect
                x={-SIZE * 2}
                y={-SIZE * 4}
                width={SIZE * 4}
                height={SIZE * 2}
                fill={`url(#${skyGradId})`}
              />
              <rect
                x={-SIZE * 2}
                y={0}
                width={SIZE * 4}
                height={SIZE * 4}
                fill={`url(#${groundGradId})`}
              />
              <line
                x1={-SIZE * 2}
                y1={0}
                x2={SIZE * 2}
                y2={0}
                stroke="#ffffff"
                strokeWidth="2.5"
                strokeOpacity={0.95}
              />
            </g>
          </g>

          {/* 機体記号（画面に対して固定） */}
          <g pointerEvents="none" className="imu-attitude-reticle">
            <circle
              cx={CX}
              cy={CY}
              r={R}
              fill="none"
              stroke="rgba(255,255,255,0.25)"
              strokeWidth="1"
            />
            {/* 翼 */}
            <line
              x1={CX - R * 0.55}
              y1={CY}
              x2={CX + R * 0.55}
              y2={CY}
              stroke="#ffeedd"
              strokeWidth="3"
              strokeLinecap="round"
            />
            {/* 機首 */}
            <polygon
              points={`${CX},${CY - 10} ${CX - 8},${CY + 6} ${CX + 8},${CY + 6}`}
              fill="#ffeedd"
              stroke="#1a1520"
              strokeWidth="1"
            />
            <circle cx={CX} cy={CY} r={4} fill="#1a1520" stroke="#ffeedd" strokeWidth="1.5" />
          </g>
        </svg>

        <div className="imu-attitude-readouts" aria-live="polite">
          <span className="imu-attitude-readout imu-attitude-readout--pitch">
            {fmtDeg("Pitch", imuSample?.angle?.pitch)}
          </span>
          <span className="imu-attitude-readout imu-attitude-readout--roll">
            {fmtDeg("Roll", imuSample?.angle?.roll)}
          </span>
        </div>

        {wsStatus !== "connected" || !imuSample ? (
          <p className="imu-attitude-hint">
            {wsStatus === "connected"
              ? "サンプル待ちです…"
              : "daemon に接続しています…"}
          </p>
        ) : null}
      </div>
    </div>
  );
}
