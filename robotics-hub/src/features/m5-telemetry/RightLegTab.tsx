import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { JointTripleBar } from "./JointTripleBar";
import { RightFootSole } from "./RightFootSole";
import {
  LEG_PLOT_DEFAULT,
  LEG_PLOT_ITEMS,
  RIGHT_LEG_JOINTS,
  type LegPlotKey,
  type RightLegJointId,
} from "./rightLeg";
import type { M5Cmd, M5Control, M5Frame, M5HistoryPoint } from "./types";

type Props = {
  canCmd: boolean;
  control: M5Control | null;
  frame: M5Frame | null;
  history: M5HistoryPoint[];
  send: (cmd: M5Cmd) => void;
  /** 左カラム上段。実機カメラ（ライブ／再生） */
  cameraPane: ReactNode;
};

/** 指令バー無操作で自動ロック（誤タッチ防止） */
const CMD_IDLE_LOCK_MS = 12_000;

function at<T>(xs: T[] | undefined, i: number): T | undefined {
  return xs && i >= 0 && i < xs.length ? xs[i] : undefined;
}

/**
 * 右脚 5 軸の操作画面。
 * 指令バーは操作ロック解除かつ PWM ON の軸だけ動く。バー操作では PWM を入れない。
 */
export function RightLegTab({ canCmd, control, frame, history, send, cameraPane }: Props) {
  const [selected, setSelected] = useState<RightLegJointId>("kneePitch");
  const [plotOn, setPlotOn] = useState(LEG_PLOT_DEFAULT);
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

  const setCmd = (ch: number, deg: number) => {
    if (!canCmd || cmdLocked) return;
    // PWM はバーでは入れない。明示の PWM ON が必要
    if (!at(control?.out, ch)) return;
    send({ op: "joint", ch, deg });
    bumpIdle();
  };

  const pwmAll = (on: boolean) => {
    if (!canCmd) return;
    for (const j of RIGHT_LEG_JOINTS) {
      send({ op: "out", ch: j.ch, on });
    }
  };

  return (
    <section
      className="m5__section m5-leg"
      onContextMenu={(e) => e.preventDefault()}
    >
      <div className="m5-leg__toolbar">
        <p className="m5__meta">
          右脚のみ。指令バーはつまみを掴んでドラッグ。PWM は下のボタンで入れます。ズレは指令と補正の区間だけ赤く塗ります。
        </p>
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
        <button type="button" className="m5__btn m5__btn--on" disabled={!canCmd} onClick={() => pwmAll(true)}>
          右脚 PWM ON
        </button>
        <button type="button" className="m5__btn" disabled={!canCmd} onClick={() => pwmAll(false)}>
          右脚 PWM OFF
        </button>
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
      </div>

      <div className="m5-leg__layout">
        {/* 左: 映像の下に足圧。中央バー／右グラフは従来幅をほぼ維持 */}
        <div className="m5-leg__sense">
          <div className="m5-leg__cam">{cameraPane}</div>
          <div className="m5-leg__foot">
            <RightFootSole sample={frame?.foot} large />
          </div>
        </div>
        <div className="m5-leg__rows">
          {RIGHT_LEG_JOINTS.map((j) => {
            const pwmOn = Boolean(at(control?.out, j.ch));
            return (
              <JointTripleBar
                key={j.id}
                joint={j}
                cmd={at(control?.cmd, j.ch)}
                corr={at(frame?.corr, j.ch)}
                pwmOn={pwmOn}
                historyCmd={history.map((h) => at(h.cmd, j.ch))}
                historyCorr={history.map((h) => at(h.corr, j.ch))}
                historyVolt={history.map((h) => at(h.volt, j.ch))}
                historyAmp={history.map((h) => at(h.amp, j.ch))}
                volt={at(frame?.volt, j.ch)}
                amp={at(frame?.amp, j.ch)}
                plotOn={plotOn}
                selected={selected === j.id}
                disabled={!canCmd || cmdLocked || !pwmOn}
                onSelect={() => setSelected(j.id)}
                onCommand={(deg) => setCmd(j.ch, deg)}
              />
            );
          })}
        </div>
      </div>
    </section>
  );
}
