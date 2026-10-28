import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { Sparkline, type SparkSeries } from "./Sparkline";
import {
  LEG_BAR,
  LEG_PLOT_ITEMS,
  SERVO_MAX_DEG,
  SERVO_MIN_DEG,
  type LegBarVisibility,
  type LegPlotKey,
  type LegPlotVisibility,
  type RightLegJoint,
} from "./rightLeg";

type Props = {
  joint: RightLegJoint;
  /** PWM の物理経路。論理関節の ch とは別 */
  routeLabel: string;
  cmd: number | null | undefined;
  /** AS5600 の生角。0〜360°。未読は null */
  raw: number | null | undefined;
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
  /** 関節カードのバー。指令・生角・ズレ・補正を個別に出す */
  barOn: LegBarVisibility;
  selected: boolean;
  disabled: boolean;
  /** 歩行再生。バーは方策の目標で、ドラッグでは動かない */
  policyOwned?: boolean;
  /** この関節のセンサが無い。枠は残し、操作と色だけ落とす */
  inactive?: boolean;
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

/** 生角バー。エンコーダは 0〜360° なので、指令バーの 100〜170° とは別スケール */
const RAW_MIN_DEG = 0;
const RAW_MAX_DEG = 360;

function pctRaw(v: number): number {
  const t = (v - RAW_MIN_DEG) / (RAW_MAX_DEG - RAW_MIN_DEG);
  return Math.min(100, Math.max(0, t * 100));
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
  const [ip = "0", fp = ""] = Math.abs(v).toFixed(frac).split(".");
  const intPart = ip.length > intWidth ? ip.slice(-intWidth) : ip.padStart(intWidth, " ");
  const fracPart = (fp + "0".repeat(frac)).slice(0, frac);
  return `${sign}${intPart}.${fracPart} ${unit}`;
}

/**
 * 1 関節の指令・生角・ズレ・補正バーとスパークライン。
 * 指令バーはつまみ付近のドラッグのみ。PWM OFF / ロック中は disabled。
 */
export function JointTripleBar({
  joint,
  routeLabel,
  cmd,
  raw,
  corr,
  pwmOn,
  historyCmd,
  historyCorr,
  historyVolt,
  historyAmp,
  volt,
  amp,
  plotOn,
  barOn,
  selected,
  disabled,
  policyOwned = false,
  inactive = false,
  onSelect,
  onCommand,
}: Props) {
  const cmdVal = typeof cmd === "number" ? cmd : SERVO_MIN_DEG + (SERVO_MAX_DEG - SERVO_MIN_DEG) / 2;
  const corrVal = typeof corr === "number" && Number.isFinite(corr) ? corr : null;
  const rawVal = typeof raw === "number" && Number.isFinite(raw) ? raw : null;
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
  }, [barOn.cmd]);

  return (
    <article
      className={
        "m5-jrow" +
        (selected && !inactive ? " m5-jrow--on" : "") +
        (inactive ? " m5-jrow--idle" : "")
      }
      onClick={inactive ? undefined : onSelect}
      onContextMenu={(e) => e.preventDefault()}
    >
      <div className="m5-jrow__body">
        <div className="m5-jrow__left">
          <div className="m5-jrow__name">
            <header className="m5-jrow__head">
              <h2>{joint.label}</h2>
              <span>ch{joint.ch}</span>
              <span className={"m5-jrow__pwm" + ((pwmOn || policyOwned) && !inactive ? " m5-jrow__pwm--on" : "")}>
                {inactive ? "未接続" : policyOwned ? "方策" : pwmOn ? "PWM ON" : "PWM OFF"}
              </span>
            </header>
            {/* 見出しの ch は論理関節。ここは PaHub と 8Servos の出力先 */}
            <p className="m5-jrow__route" title="PWM の出力先。上の ch は論理関節番号です。">
              {routeLabel}
            </p>
          </div>
          <div className="m5-jrow__bars">
            {barOn.cmd ? (
            <BarRow label="指令" value={fmtDeg(shownCmd)} color={LEG_BAR.cmd}>
            <div
              ref={trackRef}
              className={"m5-bar m5-bar--cmd" + (disabled && !policyOwned ? " m5-bar--off" : "")}
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
            ) : null}

            {barOn.raw ? (
          <BarRow label="生角" value={fmtDeg(rawVal)} color={LEG_BAR.raw}>
            <div className="m5-bar">
              <i
                className="m5-bar__fill m5-bar__fill--hatch-raw"
                style={{ width: rawVal != null ? `${pctRaw(rawVal)}%` : "0%" }}
              />
            </div>
          </BarRow>
            ) : null}

            {barOn.err ? (
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
            ) : null}

            {barOn.corr ? (
          <BarRow label="補正" value={fmtDeg(corrVal)} color={LEG_BAR.corr}>
            <div className="m5-bar">
              <i
                className="m5-bar__fill m5-bar__fill--hatch-corr"
                style={{ width: corrVal != null ? `${pct(corrVal)}%` : "0%" }}
              />
            </div>
          </BarRow>
            ) : null}
          </div>
        </div>

        <div className="m5-jrow__plot">
          <PlotLiveReadout
            plotOn={plotOn}
            cmd={inactive ? null : shownCmd}
            corr={inactive ? null : corrVal}
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
  cmd: number | null;
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
        const value = values[item.key];
        // 数値が無い系列（シミュの電圧・電流など）は枠を残して色だけ落とす。
        const idle = typeof value !== "number" || !Number.isFinite(value);
        return (
          <span
            key={item.key}
            className={"m5-jrow__live-item" + (idle ? " m5-jrow__live-item--idle" : "")}
          >
            <span className="m5-jrow__live-lab" style={idle ? undefined : { color: item.color }}>
              {item.label}
            </span>
            <span className="m5-jrow__live-val" style={idle ? undefined : { color: item.color }}>
              {fmtLive(value, spec.intWidth, spec.frac, spec.unit)}
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
