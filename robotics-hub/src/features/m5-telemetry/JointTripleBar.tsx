import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { Sparkline, type SparkSeries } from "./Sparkline";
import {
  LEG_BAR,
  LEG_PLOT_ITEMS,
  SERVO_MAX_DEG,
  SERVO_MIN_DEG,
  type LegPlotKey,
  type LegPlotVisibility,
  type RightLegJoint,
} from "./rightLeg";

type Props = {
  joint: RightLegJoint;
  cmd: number | null | undefined;
  corr: number | null | undefined;
  pwmOn: boolean;
  historyCmd: Array<number | null | undefined>;
  historyCorr: Array<number | null | undefined>;
  historyVolt: Array<number | null | undefined>;
  historyAmp: Array<number | null | undefined>;
  volt: number | null | undefined;
  amp: number | null | undefined;
  /** 5 軸共通。指令・補正は左軸(°)、電圧・電流は右軸 */
  plotOn: LegPlotVisibility;
  selected: boolean;
  disabled: boolean;
  onSelect: () => void;
  onCommand: (deg: number) => void;
};

/** つまみからの許容距離（px）。トラックの空き部分をタップしても指令しない */
const THUMB_HIT_PX = 28;

function clampServo(v: number): number {
  return Math.round(Math.min(SERVO_MAX_DEG, Math.max(SERVO_MIN_DEG, v)) * 2) / 2;
}

function pct(v: number): number {
  return ((v - SERVO_MIN_DEG) / (SERVO_MAX_DEG - SERVO_MIN_DEG)) * 100;
}

function fmtDeg(v: number | null | undefined): string {
  if (typeof v !== "number" || !Number.isFinite(v)) return "—";
  return `${v.toFixed(1)}°`;
}

function fmtSigned(v: number | null | undefined): string {
  if (typeof v !== "number" || !Number.isFinite(v)) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(1)}°`;
}

/**
 * グラフ上の現在値。整数部を左スペース埋めして小数点位置を固定する。
 * 例: "  40.0 °" / " 135.0 °" / " 230.0 °"
 */
function fmtLive(
  v: number | null | undefined,
  intWidth: number,
  frac: number,
  unit: string
): string {
  const bodyWidth = 1 + intWidth + 1 + frac; // 符号 + 整数 + 小数点 + 小数
  if (typeof v !== "number" || !Number.isFinite(v)) {
    return `${"—".padStart(bodyWidth, " ")} ${unit}`;
  }
  const sign = v < 0 ? "-" : " ";
  const [ip, fp = ""] = Math.abs(v).toFixed(frac).split(".");
  const intPart = ip.length > intWidth ? ip.slice(-intWidth) : ip.padStart(intWidth, " ");
  const fracPart = (fp + "0".repeat(frac)).slice(0, frac);
  return `${sign}${intPart}.${fracPart} ${unit}`;
}

/**
 * 1 関節の指令・ズレ・補正バーとスパークライン。
 * 指令バーはつまみ付近のドラッグのみ。PWM OFF / ロック中は disabled。
 */
export function JointTripleBar({
  joint,
  cmd,
  corr,
  pwmOn,
  historyCmd,
  historyCorr,
  historyVolt,
  historyAmp,
  volt,
  amp,
  plotOn,
  selected,
  disabled,
  onSelect,
  onCommand,
}: Props) {
  const cmdVal = typeof cmd === "number" ? cmd : SERVO_MIN_DEG + (SERVO_MAX_DEG - SERVO_MIN_DEG) / 2;
  const corrVal = typeof corr === "number" && Number.isFinite(corr) ? corr : null;
  const err = corrVal != null ? corrVal - cmdVal : null;

  const [drag, setDrag] = useState<number | null>(null);
  const shownCmd = drag ?? cmdVal;
  const trackRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  const thumbX = useCallback(
    (deg: number): number | null => {
      const el = trackRef.current;
      if (!el) return null;
      const r = el.getBoundingClientRect();
      if (r.width <= 0) return null;
      const t = (deg - SERVO_MIN_DEG) / (SERVO_MAX_DEG - SERVO_MIN_DEG);
      return r.left + t * r.width;
    },
    []
  );

  const applyX = useCallback(
    (clientX: number) => {
      const el = trackRef.current;
      if (!el) return;
      const r = el.getBoundingClientRect();
      if (r.width <= 0) return;
      const t = Math.min(1, Math.max(0, (clientX - r.left) / r.width));
      const deg = clampServo(SERVO_MIN_DEG + t * (SERVO_MAX_DEG - SERVO_MIN_DEG));
      setDrag(deg);
      onCommand(deg);
    },
    [onCommand]
  );

  // iOS は CSS だけでは長押しメニューが残ることがある
  useEffect(() => {
    const el = trackRef.current;
    if (!el) return;
    const block = (e: Event) => e.preventDefault();
    el.addEventListener("selectstart", block);
    el.addEventListener("contextmenu", block);
    return () => {
      el.removeEventListener("selectstart", block);
      el.removeEventListener("contextmenu", block);
    };
  }, []);

  return (
    <article
      className={"m5-jrow" + (selected ? " m5-jrow--on" : "")}
      onClick={onSelect}
      onContextMenu={(e) => e.preventDefault()}
    >
      <div className="m5-jrow__body">
        <div className="m5-jrow__left">
          <header className="m5-jrow__head">
            <h2>{joint.label}</h2>
            <span>ch{joint.ch}</span>
            <span className={"m5-jrow__pwm" + (pwmOn ? " m5-jrow__pwm--on" : "")}>
              {pwmOn ? "PWM ON" : "PWM OFF"}
            </span>
          </header>
          <div className="m5-jrow__bars">
            <BarRow label="指令" value={fmtDeg(shownCmd)} color={LEG_BAR.cmd}>
            <div
              ref={trackRef}
              className={"m5-bar m5-bar--cmd" + (disabled ? " m5-bar--off" : "")}
              onContextMenu={(e) => e.preventDefault()}
              onPointerDown={(e) => {
                if (disabled) return;
                const tx = thumbX(shownCmd);
                if (tx == null || Math.abs(e.clientX - tx) > THUMB_HIT_PX) return;
                e.currentTarget.setPointerCapture(e.pointerId);
                e.preventDefault();
                dragging.current = true;
                onSelect();
                setDrag(shownCmd);
              }}
              onPointerMove={(e) => {
                if (disabled || !dragging.current) return;
                applyX(e.clientX);
              }}
              onPointerUp={() => {
                dragging.current = false;
                setDrag(null);
              }}
              onPointerCancel={() => {
                dragging.current = false;
                setDrag(null);
              }}
            >
              <i className="m5-bar__fill m5-bar__fill--hatch-cmd" style={{ width: `${pct(shownCmd)}%` }} />
              <b className="m5-bar__thumb" style={{ left: `${pct(shownCmd)}%` }} />
            </div>
          </BarRow>

          <BarRow label="ズレ" value={fmtSigned(err)} color={LEG_BAR.err}>
            <div className="m5-bar m5-bar--err">
              {corrVal != null ? (
                <i
                  className="m5-bar__fill m5-bar__fill--err"
                  style={{
                    left: `${Math.min(pct(shownCmd), pct(corrVal))}%`,
                    width: `${Math.max(0.8, Math.abs(pct(corrVal) - pct(shownCmd)))}%`,
                  }}
                />
              ) : null}
            </div>
          </BarRow>

          <BarRow label="補正" value={fmtDeg(corrVal)} color={LEG_BAR.corr}>
            <div className="m5-bar">
              <i
                className="m5-bar__fill m5-bar__fill--hatch-corr"
                style={{ width: corrVal != null ? `${pct(corrVal)}%` : "0%" }}
              />
            </div>
          </BarRow>
          </div>
        </div>

        <div className="m5-jrow__plot">
          <PlotLiveReadout
            plotOn={plotOn}
            cmd={shownCmd}
            corr={corrVal}
            volt={volt}
            amp={amp}
          />
          <Sparkline
            className="m5-spark m5-spark--row"
            height={112}
            showAxes
            series={buildPlotSeries(plotOn, historyCmd, historyCorr, historyVolt, historyAmp)}
          />
        </div>
      </div>
    </article>
  );
}

/** トグルで選んだ系列だけ、物理単位のまま左右軸へ載せる */
function buildPlotSeries(
  plotOn: LegPlotVisibility,
  historyCmd: Array<number | null | undefined>,
  historyCorr: Array<number | null | undefined>,
  historyVolt: Array<number | null | undefined>,
  historyAmp: Array<number | null | undefined>
): SparkSeries[] {
  const series: SparkSeries[] = [];
  if (plotOn.cmd) {
    series.push({
      key: "cmd",
      color: LEG_BAR.cmd,
      values: historyCmd,
      yMin: SERVO_MIN_DEG,
      yMax: SERVO_MAX_DEG,
      axis: "left",
      unit: "°",
    });
  }
  if (plotOn.corr) {
    series.push({
      key: "corr",
      color: LEG_BAR.corr,
      values: historyCorr,
      yMin: SERVO_MIN_DEG,
      yMax: SERVO_MAX_DEG,
      axis: "left",
      unit: "°",
    });
  }
  if (plotOn.volt) {
    series.push({
      key: "volt",
      color: LEG_BAR.volt,
      values: historyVolt,
      yMin: 0,
      yMax: 15,
      axis: "right",
      unit: "V",
    });
  }
  if (plotOn.amp) {
    series.push({
      key: "amp",
      color: LEG_BAR.amp,
      values: historyAmp,
      yMin: 0,
      yMax: 8,
      axis: "right",
      unit: "A",
    });
  }
  return series;
}

const LIVE_FMT: Record<LegPlotKey, { intWidth: number; frac: number; unit: string }> = {
  cmd: { intWidth: 3, frac: 1, unit: "°" },
  corr: { intWidth: 3, frac: 1, unit: "°" },
  volt: { intWidth: 2, frac: 2, unit: "V" },
  amp: { intWidth: 2, frac: 2, unit: "A" },
};

/** トグル中の系列の現在値。等幅固定桁でグラフの上に出す */
function PlotLiveReadout({
  plotOn,
  cmd,
  corr,
  volt,
  amp,
}: {
  plotOn: LegPlotVisibility;
  cmd: number;
  corr: number | null;
  volt: number | null | undefined;
  amp: number | null | undefined;
}) {
  const values: Record<LegPlotKey, number | null | undefined> = { cmd, corr, volt, amp };
  const items = LEG_PLOT_ITEMS.filter((item) => plotOn[item.key]);
  if (!items.length) return null;
  return (
    <div className="m5-jrow__live">
      {items.map((item) => {
        const spec = LIVE_FMT[item.key];
        return (
          <span key={item.key} className="m5-jrow__live-item">
            <span className="m5-jrow__live-lab" style={{ color: item.color }}>
              {item.label}
            </span>
            <span className="m5-jrow__live-val" style={{ color: item.color }}>
              {fmtLive(values[item.key], spec.intWidth, spec.frac, spec.unit)}
            </span>
          </span>
        );
      })}
    </div>
  );
}

function BarRow({
  label,
  value,
  color,
  children,
}: {
  label: string;
  value: string;
  color: string;
  children: ReactNode;
}) {
  return (
    <div className="m5-barrow">
      <span className="m5-barrow__lab" style={{ color }}>
        {label}
      </span>
      <span className="m5-barrow__val" style={{ color }}>
        {value}
      </span>
      {children}
    </div>
  );
}
