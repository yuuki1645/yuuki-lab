import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { CopAnklePanel } from "./CopAnklePanel";
import { JointTripleBar } from "./JointTripleBar";
import { RightFootSole } from "./RightFootSole";
import { StickCommandPad } from "./StickCommandPad";
import {
  LEG_BAR_DEFAULT,
  LEG_BAR_ITEMS,
  LEG_PLOT_DEFAULT,
  LEG_PLOT_ITEMS,
  LEG_ROWS,
  legJoint,
  type LegBarKey,
  type LegPlotKey,
  type LegSide,
} from "./rightLeg";
import type { M5LinkSource } from "./useM5TelemetryStream";
import { CycleSweep } from "./CycleSweep";
import { pwmRouteLabel } from "./m5Route";
import type { M5Cmd, M5Control, M5Frame, M5HistoryPoint, M5Route } from "./types";

type Props = {
  canCmd: boolean;
  /** atom は右脚だけ実在。isaac は 10 関節。未接続は null */
  source: M5LinkSource | null;
  control: M5Control | null;
  /** ボードの関節プロファイル。添字は論理関節。PWM の物理経路をカードに出す */
  routes: M5Route[];
  frame: M5Frame | null;
  history: M5HistoryPoint[];
  send: (cmd: M5Cmd) => void;
  /** 再生中は記録の時刻。ライブは null で、タイムラインが壁時計で進む。 */
  sweepClockSec?: number | null;
  /** ライブなら true。再生は記録時刻に合わせ、壁時計では動かさない。 */
  sweepLive?: boolean;
  /** 左カラム上段。実機カメラ（ライブ／再生） */
  cameraPane: ReactNode;
};

/** 指令バー無操作で自動ロック（誤タッチ防止） */
const CMD_IDLE_LOCK_MS = 12_000;
/** 制御タイムラインの開閉。このタブを開いているあいだだけ残す。 */
const SWEEP_OPEN_KEY = "m5-sweep-open";

function loadSweepOpen(): boolean {
  try {
    const raw = sessionStorage.getItem(SWEEP_OPEN_KEY);
    if (raw === "0") return false;
    if (raw === "1") return true;
  } catch {
    // 保存が読めないときは、今までどおり開いた状態にする。
  }
  return true;
}

function at<T>(xs: T[] | undefined, i: number): T | undefined {
  return xs && i >= 0 && i < xs.length ? xs[i] : undefined;
}

/**
 * 左右 5 行の操作画面。左列が左脚、右列が右脚。
 * 指令バーは操作ロック解除かつ PWM ON かつ、その関節が接続されているときだけ動く。
 */
export function RightLegTab({
  canCmd,
  source,
  control,
  routes,
  frame,
  history,
  send,
  cameraPane,
  sweepClockSec = null,
  sweepLive = true,
}: Props) {
  const [selected, setSelected] = useState<string>("right-kneePitch");
  const [plotOn, setPlotOn] = useState(LEG_PLOT_DEFAULT);
  const [barOn, setBarOn] = useState(LEG_BAR_DEFAULT);
  const [sweepOpen, setSweepOpen] = useState(loadSweepOpen);
  const [cmdLocked, setCmdLocked] = useState(true);
  const idleTimer = useRef<number | null>(null);

  const clearIdle = () => {
    if (idleTimer.current != null) {
      window.clearTimeout(idleTimer.current);
      idleTimer.current = null;
    }
  };

  const bumpIdle = () => {
    clearIdle();
    idleTimer.current = window.setTimeout(() => setCmdLocked(true), CMD_IDLE_LOCK_MS);
  };

  const lockCmd = () => {
    setCmdLocked(true);
    clearIdle();
  };

  const unlockCmd = () => {
    if (!canCmd) return;
    setCmdLocked(false);
    bumpIdle();
  };

  useEffect(() => () => clearIdle(), []);

  useEffect(() => {
    if (!canCmd) {
      setCmdLocked(true);
      clearIdle();
    }
  }, [canCmd]);

  const togglePlot = (key: LegPlotKey) => {
    setPlotOn((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const toggleBar = (key: LegBarKey) => {
    setBarOn((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const setCmd = (ch: number, deg: number) => {
    if (!canCmd || cmdLocked) return;
    // PWM はバーでは入れない。明示の PWM ON が必要
    if (!at(control?.out, ch)) return;
    send({ op: "joint", ch, deg });
    bumpIdle();
  };

  // 実機の片脚は右だけ。CoreS3（cmd が 10 本）と Isaac は両脚。
  const bothLegs = (frame?.cmd?.length ?? 0) >= 10;
  const jointLive = (side: LegSide, row: number): boolean => {
    const ch = legJoint(side, row).ch;
    if (source === "atom") {
      if (bothLegs) return true;
      return side === "right";
    }
    if (source !== "isaac") return false;
    // 再生スクリプトが関節角を載せ始めてから点灯する。指令だけの仮の 135° では点灯しない。
    return typeof at(frame?.corr, ch) === "number";
  };

  const pwmSide = (side: LegSide, on: boolean) => {
    if (!canCmd) return;
    LEG_ROWS.forEach((_, row) => {
      if (!jointLive(side, row)) return;
      send({ op: "out", ch: legJoint(side, row).ch, on });
    });
  };

  // 歩行再生は方策が関節を持つ。バーは目標角の表示で、ドラッグでは動かない。
  const policyOwned = frame?.stick != null;

  return (
    <section
      className="m5__section m5-leg"
      onContextMenu={(e) => e.preventDefault()}
    >
      <div className="m5-leg__toolbar">
        <p className="m5__meta">
          {policyOwned
            ? "歩行再生です。指令は方策の目標角、補正は今の関節角です。バーはドラッグできません。左の円が左スティック、横のバーが方策へ渡している前進です。"
            : "左列が左脚、右列が右脚です。同じ関節が同じ高さに並びます。指令バーはつまみを掴んでドラッグ。ライブ指令は 100〜170°。接続の無い脚と、電圧・電流が無い欄は枠を残して暗くします。"}
        </p>
        {policyOwned ? null : (
        <>
        <div className="m5-leg__lock" role="group" aria-label="指令バー操作ロック">
          <span
            className={
              "m5-leg__lock-badge" + (cmdLocked ? " m5-leg__lock-badge--on" : " m5-leg__lock-badge--off")
            }
          >
            {cmdLocked ? "操作ロック中" : "指令バー操作可"}
          </span>
          {cmdLocked ? (
            <button
              type="button"
              className="m5__btn m5__btn--warn"
              disabled={!canCmd}
              onClick={unlockCmd}
            >
              操作を解除
            </button>
          ) : (
            <button type="button" className="m5__btn" onClick={lockCmd}>
              操作をロック
            </button>
          )}
        </div>
        <button
          type="button"
          className="m5__btn m5__btn--on"
          disabled={!canCmd || !LEG_ROWS.some((_, row) => jointLive("left", row))}
          onClick={() => pwmSide("left", true)}
        >
          左脚 PWM ON
        </button>
        <button
          type="button"
          className="m5__btn"
          disabled={!canCmd || !LEG_ROWS.some((_, row) => jointLive("left", row))}
          onClick={() => pwmSide("left", false)}
        >
          左脚 PWM OFF
        </button>
        <button
          type="button"
          className="m5__btn m5__btn--on"
          disabled={!canCmd || !LEG_ROWS.some((_, row) => jointLive("right", row))}
          onClick={() => pwmSide("right", true)}
        >
          右脚 PWM ON
        </button>
        <button
          type="button"
          className="m5__btn"
          disabled={!canCmd || !LEG_ROWS.some((_, row) => jointLive("right", row))}
          onClick={() => pwmSide("right", false)}
        >
          右脚 PWM OFF
        </button>
        </>
        )}
        <div className="m5-leg__plot-togs" role="group" aria-label="バー表示項目">
          <span className="m5-leg__plot-togs-lab">バー</span>
          {LEG_BAR_ITEMS.map((item) => {
            const on = barOn[item.key];
            return (
              <button
                key={item.key}
                type="button"
                className={"m5-plot-tog" + (on ? " m5-plot-tog--on" : "")}
                style={{
                  color: item.color,
                  borderColor: on ? item.color : "rgba(255,255,255,0.18)",
                }}
                aria-pressed={on}
                onClick={() => toggleBar(item.key)}
              >
                {item.label}
              </button>
            );
          })}
        </div>
        <div className="m5-leg__plot-togs" role="group" aria-label="グラフ表示項目">
          <span className="m5-leg__plot-togs-lab">グラフ</span>
          {LEG_PLOT_ITEMS.map((item) => {
            const on = plotOn[item.key];
            return (
              <button
                key={item.key}
                type="button"
                className={"m5-plot-tog" + (on ? " m5-plot-tog--on" : "")}
                style={{
                  color: item.color,
                  borderColor: on ? item.color : "rgba(255,255,255,0.18)",
                }}
                aria-pressed={on}
                onClick={() => togglePlot(item.key)}
              >
                {item.label}
              </button>
            );
          })}
        </div>
        <div className="m5-leg__plot-togs" role="group" aria-label="制御タイムラインの表示">
          <span className="m5-leg__plot-togs-lab">タイムライン</span>
          <button
            type="button"
            className={"m5-plot-tog" + (sweepOpen ? " m5-plot-tog--on" : "")}
            style={{
              color: "#d6deea",
              borderColor: sweepOpen ? "#d6deea" : "rgba(255,255,255,0.18)",
            }}
            aria-pressed={sweepOpen}
            onClick={() => {
              const next = !sweepOpen;
              setSweepOpen(next);
              try {
                sessionStorage.setItem(SWEEP_OPEN_KEY, next ? "1" : "0");
              } catch {
                // 保存できなくても、この表示のあいだは押した状態のまま。
              }
            }}
          >
            表示
          </button>
        </div>
      </div>

      {sweepOpen ? (
        <CycleSweep history={history} clockSec={sweepClockSec} live={sweepLive} />
      ) : null}

      <div className="m5-leg__layout">
        {/* 左: 映像の下に足圧。中央バー／右グラフは従来幅をほぼ維持 */}
        <div className="m5-leg__sense">
          <div className="m5-leg__cam">{cameraPane}</div>
          {policyOwned && frame?.stick ? <StickCommandPad stick={frame.stick} /> : null}
          <div className="m5-leg__foot m5-leg__feet">
            <RightFootSole title="左足裏" sample={frame?.foot_left} large />
            <RightFootSole title="右足裏" sample={frame?.foot} large />
          </div>
        </div>
        <div className="m5-leg__rows">
          {LEG_ROWS.map((def, row) => (
            <div className="m5-leg__pair" key={def.id}>
              {(["left", "right"] as const).map((side) => {
                const j = legJoint(side, row);
                const live = jointLive(side, row);
                const pwmOn = Boolean(at(control?.out, j.ch));
                return (
                  <JointTripleBar
                    key={j.id}
                    joint={j}
                    routeLabel={pwmRouteLabel(routes[j.ch])}
                    cmd={policyOwned ? at(frame?.cmd, j.ch) : at(control?.cmd, j.ch)}
                    raw={live ? at(frame?.raw, j.ch) : null}
                    corr={at(frame?.corr, j.ch)}
                    pwmOn={pwmOn}
                    historyCmd={history.map((h) => at(h.cmd, j.ch))}
                    historyCorr={history.map((h) => at(h.corr, j.ch))}
                    historyVolt={history.map((h) => at(h.volt, j.ch))}
                    historyAmp={history.map((h) => at(h.amp, j.ch))}
                    volt={at(frame?.volt, j.ch)}
                    amp={at(frame?.amp, j.ch)}
                    plotOn={plotOn}
                    barOn={barOn}
                    selected={selected === j.id}
                    inactive={!live}
                    policyOwned={policyOwned && live}
                    disabled={policyOwned || !live || !canCmd || cmdLocked || !pwmOn}
                    onSelect={() => setSelected(j.id)}
                    onCommand={(deg) => setCmd(j.ch, deg)}
                  />
                );
              })}
            </div>
          ))}
        </div>
      </div>

      <CopAnklePanel canCmd={canCmd} cop={control?.cop} send={send} />
    </section>
  );
}
