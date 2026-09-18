/**
 * 机上ラボの 1 サーボ用バー。
 *
 * 実機テレメトリの右脚バー（JointTripleBar）と同じ見た目にしつつ、
 * 可動域は校正と同じ 40〜230° を通し、校正で重要な「生角」も出す。
 * AS5600 が付いていない単体テストでは、指令バーだけが生きる。
 */
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { UiHelp } from "@/shared/components/UiHelp";
import { BENCH_MAX_DEG, BENCH_MIN_DEG, BENCH_BAR } from "./benchConst";

/** つまみからの許容距離（px）。トラックの空きをタップしても指令しない */
const THUMB_HIT_PX = 28;

type Props = {
  /** 論理関節番号（= 8Servos の servo_ch 経路） */
  ch: number;
  cmd: number | null | undefined;
  raw: number | null | undefined;
  unwrap: number | null | undefined;
  corr: number | null | undefined;
  pwmOn: boolean;
  /** AS5600 が読めているか。false ならセンサ系のバーは薄く出す */
  encOk: boolean;
  showRaw: boolean;
  showUnwrap: boolean;
  disabled: boolean;
  onCommand: (deg: number) => void;
};

function clampCmd(v: number): number {
  return Math.round(Math.min(BENCH_MAX_DEG, Math.max(BENCH_MIN_DEG, v)) * 2) / 2;
}

/** 指令系（40〜230°）の割合 */
function pctCmd(v: number): number {
  return ((v - BENCH_MIN_DEG) / (BENCH_MAX_DEG - BENCH_MIN_DEG)) * 100;
}

/** 生角・unwrap は AS5600 の 0〜360° をそのまま割合にする */
function pctTurn(v: number): number {
  return Math.min(100, Math.max(0, (v / 360) * 100));
}

function fmtDeg(v: number | null | undefined): string {
  if (typeof v !== "number" || !Number.isFinite(v)) return "—";
  return `${v.toFixed(1)}°`;
}

function fmtSigned(v: number | null | undefined): string {
  if (typeof v !== "number" || !Number.isFinite(v)) return "—";
  return `${v > 0 ? "+" : ""}${v.toFixed(1)}°`;
}

export function BenchServoBars({
  ch,
  cmd,
  raw,
  unwrap,
  corr,
  pwmOn,
  encOk,
  showRaw,
  showUnwrap,
  disabled,
  onCommand,
}: Props) {
  const cmdVal = typeof cmd === "number" && Number.isFinite(cmd) ? cmd : 135;
  const corrVal = typeof corr === "number" && Number.isFinite(corr) ? corr : null;
  const rawVal = typeof raw === "number" && Number.isFinite(raw) ? raw : null;
  const unwrapVal = typeof unwrap === "number" && Number.isFinite(unwrap) ? unwrap : null;
  const err = corrVal != null ? corrVal - cmdVal : null;

  const [drag, setDrag] = useState<number | null>(null);
  const shownCmd = drag ?? cmdVal;
  const trackRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  const thumbX = useCallback((deg: number): number | null => {
    const el = trackRef.current;
    if (!el) return null;
    const r = el.getBoundingClientRect();
    if (r.width <= 0) return null;
    return r.left + ((deg - BENCH_MIN_DEG) / (BENCH_MAX_DEG - BENCH_MIN_DEG)) * r.width;
  }, []);

  const applyX = useCallback(
    (clientX: number) => {
      const el = trackRef.current;
      if (!el) return;
      const r = el.getBoundingClientRect();
      if (r.width <= 0) return;
      const t = Math.min(1, Math.max(0, (clientX - r.left) / r.width));
      const deg = clampCmd(BENCH_MIN_DEG + t * (BENCH_MAX_DEG - BENCH_MIN_DEG));
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
    <div className="bench-bars" onContextMenu={(e) => e.preventDefault()}>
      <header className="m5-jrow__head">
        <h2>サーボ ch{ch}</h2>
        <span className={"m5-jrow__pwm" + (pwmOn ? " m5-jrow__pwm--on" : "")}>
          {pwmOn ? "PWM ON" : "PWM OFF"}
        </span>
        <span className={"bench-bars__enc" + (encOk ? " bench-bars__enc--on" : "")}>
          {encOk ? "AS5600 あり" : "AS5600 なし"}
        </span>
      </header>

      <div className="m5-jrow__bars">
        <BarRow
          label="指令"
          help="ファームへ送る目標角です。つまみだけドラッグできます。PWM がオフのときは動きません。範囲は 40〜230° です。"
          value={fmtDeg(shownCmd)}
          color={BENCH_BAR.cmd}
          scale="40〜230°"
        >
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
            <i className="m5-bar__fill m5-bar__fill--hatch-cmd" style={{ width: `${pctCmd(shownCmd)}%` }} />
            <b className="m5-bar__thumb" style={{ left: `${pctCmd(shownCmd)}%` }} />
          </div>
        </BarRow>

        {showRaw ? (
          <BarRow
            label="生角"
            help="AS5600 の 0〜360° 読みです。磁石が回ったままの値で、サーボ指令の 40〜230° とは原点もスケールも違います。"
            value={fmtDeg(rawVal)}
            color={BENCH_BAR.raw}
            scale="0〜360°"
          >
            <div className={"m5-bar" + (encOk ? "" : " m5-bar--off")}>
              <i
                className="m5-bar__fill bench-bar__fill--raw"
                style={{ width: rawVal != null ? `${pctTurn(rawVal)}%` : "0%" }}
              />
            </div>
          </BarRow>
        ) : null}

        {showUnwrap ? (
          <BarRow
            label="unwrap"
            help="生角の飛びをほどいた連続角です。校正マップの入力側です。表示は必要なときだけオンにしてください。"
            value={fmtDeg(unwrapVal)}
            color={BENCH_BAR.unwrap}
            scale="0〜360°"
          >
            <div className={"m5-bar" + (encOk ? "" : " m5-bar--off")}>
              <i
                className="m5-bar__fill bench-bar__fill--unwrap"
                style={{ width: unwrapVal != null ? `${pctTurn(unwrapVal)}%` : "0%" }}
              />
            </div>
          </BarRow>
        ) : null}

        <BarRow
          label="ズレ"
          help="補正角 − 指令角です。マップがあれば、いまの追従誤差に近い値になります。センサが無いときは空です。"
          value={fmtSigned(err)}
          color={BENCH_BAR.err}
          scale="指令−補正"
        >
          <div className={"m5-bar m5-bar--err" + (encOk ? "" : " m5-bar--off")}>
            {corrVal != null ? (
              <i
                className="m5-bar__fill m5-bar__fill--err"
                style={{
                  left: `${Math.min(pctCmd(shownCmd), pctCmd(corrVal))}%`,
                  width: `${Math.max(0.8, Math.abs(pctCmd(corrVal) - pctCmd(shownCmd)))}%`,
                }}
              />
            ) : null}
          </div>
        </BarRow>

        <BarRow
          label="補正"
          help="校正マップで unwrap を指令角に直した値です。マップが無い、または AS5600 が読めないと出ません。"
          value={fmtDeg(corrVal)}
          color={BENCH_BAR.corr}
          scale="40〜230°"
        >
          <div className={"m5-bar" + (encOk ? "" : " m5-bar--off")}>
            <i
              className="m5-bar__fill m5-bar__fill--hatch-corr"
              style={{ width: corrVal != null ? `${pctCmd(corrVal)}%` : "0%" }}
            />
          </div>
        </BarRow>
      </div>
    </div>
  );
}

function BarRow({
  label,
  help,
  value,
  color,
  scale,
  children,
}: {
  label: string;
  help: string;
  value: string;
  color: string;
  /** バーの目盛りの意味。指令系と AS5600 系で範囲が違うので明示する */
  scale: string;
  children: ReactNode;
}) {
  return (
    <div className="m5-barrow bench-barrow">
      <span className="m5-barrow__lab" style={{ color }}>
        {label}
        <UiHelp title={label} size="sm">
          {help}
        </UiHelp>
      </span>
      <span className="m5-barrow__val" style={{ color }}>
        {value}
      </span>
      {children}
      <span className="bench-barrow__scale">{scale}</span>
    </div>
  );
}
