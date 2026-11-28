import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { CopAnklePanel } from "./CopAnklePanel";
import { JointTripleBar } from "./JointTripleBar";
import { RightFootSole } from "./RightFootSole";
import { PolicyObservePanel } from "./PolicyObservePanel";
import { StickCommandPad } from "./StickCommandPad";
import {
  LEG_BAR_DEFAULT,
  LEG_BAR_ITEMS,
  LEG_PLOT_DEFAULT,
  LEG_PLOT_ITEMS,
  LEG_ROWS,
  SERVO_NEUTRAL_DEG,
  SM105_NEUTRAL_DEG,
  isSm105Channel,
  legJoint,
  sm105AngleWindow,
  sm105ServoId,
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
  /** 実機の方策が入っている。このあいだ関節バーは動かさない。 */
  policyOn?: boolean;
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
 * 実機の指令バーは、操作ロック解除かつ PWM ON かつ、その関節が接続されているときだけ動く。
 * Isaac はサーボを焼かないので、ロックせず PWM も常時 ON のままドラッグできる。
 */
export function RightLegTab({
  canCmd,
  source,
  control,
  routes,
  frame,
  history,
  send,
  policyOn = false,
  cameraPane,
  sweepClockSec = null,
  sweepLive = true,
}: Props) {
  const [selected, setSelected] = useState<string>("right-kneePitch");
  const [plotOn, setPlotOn] = useState(LEG_PLOT_DEFAULT);
  const [barOn, setBarOn] = useState(LEG_BAR_DEFAULT);
  const [sweepOpen, setSweepOpen] = useState(loadSweepOpen);
  // シミュは最初から解除。実機だけ、起動時ロックと無操作での再ロックを使う。
  const simDrive = source === "isaac";
  const [cmdLocked, setCmdLocked] = useState(!simDrive);
  const idleTimer = useRef<number | null>(null);

  const clearIdle = () => {
    if (idleTimer.current != null) {
      window.clearTimeout(idleTimer.current);
      idleTimer.current = null;
    }
  };

  const bumpIdle = () => {
    if (source === "isaac") return;
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
    // 切断で実機はロックに戻す。シミュは接続の有無でロックしない。
    if (source === "isaac") {
      setCmdLocked(false);
      clearIdle();
      return;
    }
    if (!canCmd) {
      setCmdLocked(true);
      clearIdle();
    }
  }, [canCmd, source]);

  const togglePlot = (key: LegPlotKey) => {
    setPlotOn((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const toggleBar = (key: LegBarKey) => {
    setBarOn((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  // ドラッグ直後はテレメトリの 0° が残る。届いた角度で消す。
  const [sm105Pending, setSm105Pending] = useState<Record<number, number>>({});
  const sm105PendingAt = useRef<Record<number, number>>({});

  const rememberSm105 = (ch: number, deg: number) => {
    sm105PendingAt.current[ch] = Date.now();
    setSm105Pending((prev) => ({ ...prev, [ch]: deg }));
  };

  const setCmd = (ch: number, deg: number) => {
    // 方策が入っているあいだは、ファームが関節指令を捨てる。
    if (policyOn) return;
    // シミュは操作ロックも PWM ゲートも掛けない。
    if (!canCmd || (source !== "isaac" && cmdLocked)) return;
    if (isSm105Channel(ch)) {
      // 実機は PWM ON が要らない。目標角を書いたときだけトルクが入る。
      rememberSm105(ch, deg);
      send({ op: "joint", ch, deg });
      bumpIdle();
      return;
    }
    // 実機の PWM はバーでは入れない。明示の PWM ON が必要。シミュは橋が常時 ON。
    if (source !== "isaac" && !at(control?.out, ch)) return;
    send({ op: "joint", ch, deg });
    bumpIdle();
  };

  useEffect(() => {
    const now = Date.now();
    setSm105Pending((prev) => {
      let next = prev;
      for (const key of Object.keys(prev)) {
        const ch = Number(key);
        const telem = at(frame?.cmd, ch);
        const want = prev[ch];
        if (typeof telem !== "number") continue;
        const age = now - (sm105PendingAt.current[ch] ?? now);
        const matched = Math.abs(telem - want) <= 0.75;
        // 全停止は指令を 0° に戻す。届かない角度を掴み続けない。
        if (matched || age > 500) {
          if (next === prev) next = { ...prev };
          delete next[ch];
        }
      }
      return next;
    });
  }, [frame]);

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
    if (!canCmd || policyOn) return;
    LEG_ROWS.forEach((_, row) => {
      const ch = legJoint(side, row).ch;
      // ひざ・かかとピッチは SM105BL。PWM ボタンでは動かさない。
      if (isSm105Channel(ch) || !jointLive(side, row)) return;
      send({ op: "out", ch, on });
    });
  };

  /**
   * 接続中の全関節の指令角を中立（135°）へ戻す。
   * 操作ロックはバーの誤タッチ用なので、この明示ボタンはロック中でも押せる。
   * PWM が OFF の軸は橋が角度だけ覚え、サーボは動かさない。ON の軸はそのまま 135° へ出る。
   */
  const sm105Receiving = (ch: number) => {
    const corr = at(frame?.corr, ch);
    const raw = at(frame?.raw, ch);
    return (
      typeof corr === "number" &&
      Number.isFinite(corr) &&
      (raw == null || !Number.isFinite(raw)) &&
      at(frame?.mag, ch) === 255
    );
  };

  const homeAllCmd = () => {
    if (!canCmd || policyOn) return;
    (["left", "right"] as const).forEach((side) => {
      LEG_ROWS.forEach((_, row) => {
        const ch = legJoint(side, row).ch;
        if (isSm105Channel(ch)) {
          // 受信している台だけ。真下 0° が中立で、未接続の ID には出さない。
          if (!sm105Receiving(ch)) return;
          rememberSm105(ch, SM105_NEUTRAL_DEG);
          send({ op: "joint", ch, deg: SM105_NEUTRAL_DEG });
          return;
        }
        if (!jointLive(side, row)) return;
        send({ op: "joint", ch, deg: SERVO_NEUTRAL_DEG });
      });
    });
  };

  const anyLive = LEG_ROWS.some((_, row) => jointLive("left", row) || jointLive("right", row));

  // 歩行再生は方策が、手動操作は逆運動学が関節を持つ。バーは表示だけで、ドラッグでは動かない。
  const policyOwned = frame?.stick != null;
  const heelOwned = frame?.drive === "heel";
  // 実機の方策も、再生のスティックと同じくバーを持たせる。
  const remoteOwned = policyOwned || heelOwned || policyOn;
  // 実機の補正はエンコーダ処理後。Isaac の同じ欄は、シミュレータの関節角。
  const corrLabel = source === "isaac" ? "補正（シミュ）" : "補正";

  return (
    <section
      className="m5__section m5-leg"
      onContextMenu={(e) => e.preventDefault()}
    >
      <div className="m5-leg__toolbar">
        <p className="m5__meta">
          {policyOn
            ? "方策が関節を持っています。バーは動きません。切るときは上の方策ボタンです。トルクまで切るときは全停止です。"
            : heelOwned
            ? "手動の踵操作です。指令は逆運動学の目標角、補正（シミュ）はシミュレータの関節角です。バーはドラッグできません。電圧・電流は未計測です。"
            : policyOwned
            ? "歩行再生です。指令は方策の目標角、補正（シミュ）は今の関節角です。バーはドラッグできません。左の円が左スティック、横のバーが方策へ渡している前進です。"
            : simDrive
              ? "シミュです。操作ロックは掛けず、PWM は常に ON です。ドラッグは人間の可動範囲で止まります。緑の細線とバー下の緑丸が中立、点線が 10°、バー下の赤線が外側 20° です。生角とズレは出ません。"
              : "左列が左脚、右列が右脚です。同じ関節が同じ高さに並びます。RDS51150 は PWM ON のあと、つまみを人間の可動範囲でドラッグします。緑の細線とバー下の緑丸が中立、点線が 10°、バー下の赤線が外側 20° です。SM105BL は真下 0° が中立です。ロックを外すと、受信中のカードをドラッグしたときだけトルクが入ります。生角とズレは出ません。"}
        </p>
        {remoteOwned ? null : simDrive ? (
        <>
        <span className="m5-leg__lock-badge m5-leg__lock-badge--off">指令バー操作可</span>
        <span className="m5-leg__lock-badge m5-leg__lock-badge--off">PWM ON</span>
        <button
          type="button"
          className="m5__btn"
          disabled={!canCmd || policyOn || !anyLive}
          title="RDS51150 は 135°、SM105BL は真下 0° へ戻します。シミュの出力は切らずに追従します。"
          onClick={homeAllCmd}
        >
          中立へ
        </button>
        </>
        ) : (
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
          disabled={!canCmd || policyOn || !LEG_ROWS.some((_, row) => jointLive("left", row))}
          onClick={() => pwmSide("left", true)}
        >
          左脚 PWM ON
        </button>
        <button
          type="button"
          className="m5__btn"
          disabled={!canCmd || policyOn || !LEG_ROWS.some((_, row) => jointLive("left", row))}
          onClick={() => pwmSide("left", false)}
        >
          左脚 PWM OFF
        </button>
        <button
          type="button"
          className="m5__btn m5__btn--on"
          disabled={!canCmd || policyOn || !LEG_ROWS.some((_, row) => jointLive("right", row))}
          onClick={() => pwmSide("right", true)}
        >
          右脚 PWM ON
        </button>
        <button
          type="button"
          className="m5__btn"
          disabled={!canCmd || policyOn || !LEG_ROWS.some((_, row) => jointLive("right", row))}
          onClick={() => pwmSide("right", false)}
        >
          右脚 PWM OFF
        </button>
        <button
          type="button"
          className="m5__btn"
          disabled={!canCmd || policyOn || !anyLive}
          title="RDS51150 は 135°、受信中の SM105BL は真下 0° へ動かします。SM105BL はここでトルクが入ります。"
          onClick={homeAllCmd}
        >
          中立へ
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
                {item.key === "corr" ? corrLabel : item.label}
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
                {item.key === "corr" ? corrLabel : item.label}
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
        <CycleSweep history={history} clockSec={sweepClockSec} live={sweepLive} corrLabel={corrLabel} />
      ) : null}

      {frame?.policy ? <PolicyObservePanel frame={frame} /> : null}

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
                const sm105 = isSm105Channel(j.ch);
                const corrSample = at(frame?.corr, j.ch);
                const rawSample = at(frame?.raw, j.ch);
                // 補正だけあって生角もあるのは、書き換える前の AS5600。SM105BL は生角を空にする。
                const sm105Live =
                  sm105 &&
                  typeof corrSample === "number" &&
                  Number.isFinite(corrSample) &&
                  (rawSample == null || !Number.isFinite(rawSample)) &&
                  at(frame?.mag, j.ch) === 255;
                const live = sm105 ? sm105Live : jointLive(side, row);
                const pwmOn = Boolean(at(control?.out, j.ch));
                const servoId = sm105ServoId(j.ch);
                const angleWindow = sm105AngleWindow(j.ch);
                const serial =
                  sm105 && servoId != null && angleWindow
                    ? { min: angleWindow.min, max: angleWindow.max, servoId }
                    : null;
                // 135° の PWM 指令が、サーボのいないカードに残らないようにする。
                const sm105Point = (
                  v: number | null | undefined,
                  corr: number | null | undefined,
                  raw: number | null | undefined
                ) =>
                  typeof corr === "number" && Number.isFinite(corr) && (raw == null || !Number.isFinite(raw))
                    ? v
                    : null;
                return (
                  <JointTripleBar
                    key={j.id}
                    joint={j}
                    routeLabel={sm105 && servoId != null ? `RS485 ID ${servoId}` : pwmRouteLabel(routes[j.ch])}
                    cmd={
                      sm105
                        ? sm105Live
                          ? (sm105Pending[j.ch] ?? at(frame?.cmd, j.ch))
                          : null
                        : remoteOwned
                          ? at(frame?.cmd, j.ch)
                          : at(control?.cmd, j.ch)
                    }
                    raw={sm105 ? null : live ? at(frame?.raw, j.ch) : null}
                    corr={sm105 ? (sm105Live ? corrSample : null) : at(frame?.corr, j.ch)}
                    pwmOn={pwmOn}
                    historyCmd={history.map((h) =>
                      sm105 ? sm105Point(at(h.cmd, j.ch), at(h.corr, j.ch), at(h.raw, j.ch)) : at(h.cmd, j.ch)
                    )}
                    historyCorr={history.map((h) =>
                      sm105 ? sm105Point(at(h.corr, j.ch), at(h.corr, j.ch), at(h.raw, j.ch)) : at(h.corr, j.ch)
                    )}
                    historyVolt={history.map((h) =>
                      sm105 ? sm105Point(at(h.volt, j.ch), at(h.corr, j.ch), at(h.raw, j.ch)) : at(h.volt, j.ch)
                    )}
                    historyAmp={history.map((h) =>
                      sm105 ? sm105Point(at(h.amp, j.ch), at(h.corr, j.ch), at(h.raw, j.ch)) : at(h.amp, j.ch)
                    )}
                    volt={sm105 ? (sm105Live ? at(frame?.volt, j.ch) : null) : at(frame?.volt, j.ch)}
                    amp={sm105 ? (sm105Live ? at(frame?.amp, j.ch) : null) : at(frame?.amp, j.ch)}
                    plotOn={plotOn}
                    barOn={barOn}
                    selected={selected === j.id}
                    inactive={!live}
                    policyOwned={!sm105 && remoteOwned && live}
                    corrLabel={corrLabel}
                    serial={serial}
                    disabled={
                      // シミュはロックも PWM OFF も理由にしない。方策と未接続だけ止める。
                      sm105
                        ? remoteOwned || !live || !canCmd || (!simDrive && cmdLocked)
                        : remoteOwned || !live || !canCmd || (!simDrive && (cmdLocked || !pwmOn))
                    }
                    onSelect={() => setSelected(j.id)}
                    onCommand={(deg) => setCmd(j.ch, deg)}
                  />
                );
              })}
            </div>
          ))}
        </div>
      </div>

      <CopAnklePanel canCmd={canCmd && !policyOn} cop={control?.cop} send={send} />
    </section>
  );
}
