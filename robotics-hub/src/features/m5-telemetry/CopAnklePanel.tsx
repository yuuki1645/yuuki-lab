import { M5_COP_IDLE, type M5Cmd, type M5CopState } from "./types";

type Props = {
  canCmd: boolean;
  cop: M5CopState | undefined;
  send: (cmd: M5Cmd) => void;
};

function fmtDeg(v: number | null | undefined): string {
  if (typeof v !== "number" || !Number.isFinite(v)) return "—";
  return `${v.toFixed(1)}°`;
}

function fmtCopY(v: number | null | undefined): string {
  if (typeof v !== "number" || !Number.isFinite(v)) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(2)}`;
}

/** 確定または推定があれば P を開始できる */
function canStartP(st: M5CopState): boolean {
  return st.neutral_confirmed != null || st.neutral_estimated != null;
}

/**
 * かかとピッチだけで COP 前後を中心化する作業パネル。
 * 制御本体は PC の lab_debug.py。ここは指令と状態表示だけ。
 */
export function CopAnklePanel({ canCmd, cop, send }: Props) {
  const st = cop ?? M5_COP_IDLE;
  const display = st.neutral_display;
  const computing = st.sweep_on;
  const canP = canCmd && canStartP(st);

  return (
    <section className="m5-cop" aria-label="かかとピッチ COP 中心化">
      <header className="m5-cop__head">
        <h3>かかとピッチ COP 中心化</h3>
        <p>
          4軸は今の指令角で固定。踵ピッチだけ前後 COP を 0 へ。制御は PC（最大 {st.p_slew_dps}°/s、
          {st.cmd_min}〜{st.cmd_max}°）。
        </p>
      </header>

      <div className="m5-cop__neutral" aria-live="polite">
        <div className="m5-cop__neutral-main">
          <span className="m5-cop__neutral-lab">
            {st.sweep_on || computing ? "ニュートラル（計算中）" : "ニュートラル"}
          </span>
          <strong className="m5-cop__neutral-val">{fmtDeg(display)}</strong>
        </div>
        <div className="m5-cop__neutral-sub">
          <span>
            推定 <b>{fmtDeg(st.neutral_estimated)}</b>
          </span>
          <span>
            確定 <b>{fmtDeg(st.neutral_confirmed)}</b>
          </span>
        </div>
      </div>

      <dl className="m5-cop__metrics">
        <div>
          <dt>COP 前後</dt>
          <dd>{fmtCopY(st.cop_y)}</dd>
        </div>
        <div>
          <dt>合計</dt>
          <dd className={st.force_ok ? "" : "m5-cop__warn"}>{st.force_kg.toFixed(2)} kg</dd>
        </div>
        <div>
          <dt>符号</dt>
          <dd>{st.sign >= 0 ? "+" : "−"}</dd>
        </div>
        <div>
          <dt>Kp</dt>
          <dd>{st.kp.toFixed(0)}</dd>
        </div>
      </dl>

      <p className={"m5-cop__status" + (st.p_on ? " m5-cop__status--p" : "") + (st.sweep_on ? " m5-cop__status--sweep" : "")}>
        {st.status}
        {st.held ? "  ·  4軸固定中" : ""}
        {!st.force_ok ? "  ·  足圧不足時は角を保持" : ""}
      </p>

      <div className="m5-cop__row">
        <button
          type="button"
          className="m5__btn m5__btn--warn"
          disabled={!canCmd}
          onClick={() => send({ op: "cop_hold_fixed" })}
        >
          4軸を指令角で固定
        </button>
        <button
          type="button"
          className="m5__btn"
          disabled={!canCmd}
          onClick={() => send({ op: "cop_step", delta: -0.5 })}
        >
          踵 −0.5°
        </button>
        <button
          type="button"
          className="m5__btn"
          disabled={!canCmd}
          onClick={() => send({ op: "cop_step", delta: 0.5 })}
        >
          踵 +0.5°
        </button>
      </div>

      <div className="m5-cop__row">
        {st.sweep_on ? (
          <button
            type="button"
            className="m5__btn"
            disabled={!canCmd}
            onClick={() => send({ op: "cop_sweep_stop" })}
          >
            自動スイープ停止
          </button>
        ) : (
          <button
            type="button"
            className="m5__btn m5__btn--warn"
            disabled={!canCmd || st.p_on}
            onClick={() => send({ op: "cop_sweep_start" })}
          >
            自動スイープ（ゆっくり）
          </button>
        )}
        <button
          type="button"
          className="m5__btn"
          disabled={!canCmd}
          onClick={() => send({ op: "cop_neutral_confirm" })}
        >
          この角を確定
        </button>
        <button
          type="button"
          className="m5__btn"
          disabled={!canCmd || st.neutral_confirmed == null}
          onClick={() => send({ op: "cop_neutral_clear" })}
        >
          確定を解除
        </button>
      </div>

      <div className="m5-cop__row">
        {st.p_on ? (
          <button
            type="button"
            className="m5__btn"
            disabled={!canCmd}
            onClick={() => send({ op: "cop_p_off" })}
          >
            P制御 OFF
          </button>
        ) : (
          <button
            type="button"
            className="m5__btn m5__btn--on"
            disabled={!canP}
            onClick={() => send({ op: "cop_p_on" })}
          >
            P制御 ON
          </button>
        )}
        <button
          type="button"
          className="m5__btn"
          disabled={!canCmd}
          onClick={() => send({ op: "cop_sign", sign: st.sign >= 0 ? -1 : 1 })}
        >
          符号反転（今 {st.sign >= 0 ? "+" : "−"}）
        </button>
        <label className="m5-cop__kp">
          Kp
          <input
            type="number"
            min={1}
            max={40}
            step={1}
            disabled={!canCmd}
            value={st.kp}
            onChange={(e) => {
              const n = Number(e.target.value);
              if (!Number.isFinite(n)) return;
              send({ op: "cop_kp", kp: n });
            }}
          />
        </label>
      </div>
    </section>
  );
}
