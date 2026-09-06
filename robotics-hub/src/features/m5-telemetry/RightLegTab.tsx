import { useState } from "react";
import { JointTripleBar } from "./JointTripleBar";
import { RightLegSchematic } from "./RightLegSchematic";
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
};

function at<T>(xs: T[] | undefined, i: number): T | undefined {
  return xs && i >= 0 && i < xs.length ? xs[i] : undefined;
}

/**
 * 右脚 5 軸の操作画面。指令バーを動かすと PWM をオンにして #CMD を送る。
 */
export function RightLegTab({ canCmd, control, frame, history, send }: Props) {
  const [selected, setSelected] = useState<RightLegJointId>("kneePitch");
  const [plotOn, setPlotOn] = useState(LEG_PLOT_DEFAULT);

  const togglePlot = (key: LegPlotKey) => {
    setPlotOn((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const angles = Object.fromEntries(
    RIGHT_LEG_JOINTS.map((j) => [j.id, at(frame?.corr, j.ch) ?? at(control?.cmd, j.ch)])
  ) as Record<RightLegJointId, number | null | undefined>;

  const setCmd = (ch: number, deg: number) => {
    if (!canCmd) return;
    if (!at(control?.out, ch)) {
      send({ op: "out", ch, on: true });
    }
    send({ op: "joint", ch, deg });
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
          右脚のみ。指令バーをドラッグするとその軸の PWM が入り、サーボが動きます。ズレは指令と補正の区間だけ赤く塗ります。
        </p>
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
        <div className="m5-leg__schematic">
          <RightLegSchematic angles={angles} selected={selected} onSelect={setSelected} />
        </div>
        <div className="m5-leg__rows">
          {RIGHT_LEG_JOINTS.map((j) => (
            <JointTripleBar
              key={j.id}
              joint={j}
              cmd={at(control?.cmd, j.ch)}
              corr={at(frame?.corr, j.ch)}
              pwmOn={Boolean(at(control?.out, j.ch))}
              historyCmd={history.map((h) => at(h.cmd, j.ch))}
              historyCorr={history.map((h) => at(h.corr, j.ch))}
              historyVolt={history.map((h) => at(h.volt, j.ch))}
              historyAmp={history.map((h) => at(h.amp, j.ch))}
              volt={at(frame?.volt, j.ch)}
              amp={at(frame?.amp, j.ch)}
              plotOn={plotOn}
              selected={selected === j.id}
              disabled={!canCmd}
              onSelect={() => setSelected(j.id)}
              onCommand={(deg) => setCmd(j.ch, deg)}
            />
          ))}
        </div>
      </div>
    </section>
  );
}
