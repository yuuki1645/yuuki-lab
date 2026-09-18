/**
 * ATOM 机上ラボ。
 *
 * 机の上で ATOM + サーボ 1 本（＋任意で AS5600 / INA226）を扱う画面。
 * 実機テレメトリ（M5）と同じ lab_debug.py（Socket.IO :8794）につなぐので、
 * ファームの焼き分けは不要。違いは「机上向けに Lab を保ち、1 軸だけ触る」点。
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import "@/features/m5-telemetry/M5TelemetryPage.css";
import "./BenchLabPage.css";
import { NvsVault } from "@/features/m5-telemetry/NvsVault";
import { ProfilePanel } from "@/features/m5-telemetry/ProfilePanel";
import { Sparkline, type SparkSeries } from "@/features/m5-telemetry/Sparkline";
import { TopologyPanel } from "@/features/m5-telemetry/TopologyPanel";
import FieldManual, { useFieldManual } from "@/features/m5-telemetry/field-manual/FieldManual";
import { at, fmt, Metric } from "@/features/m5-telemetry/m5Widgets";
import { inaSelectValue, parseInaOption } from "@/features/m5-telemetry/m5Route";
import { useM5TelemetryStream } from "@/features/m5-telemetry/useM5TelemetryStream";
import {
  MAG_LABEL,
  M5_JOINTS,
  type M5Cmd,
  type M5Frame,
  type M5HistoryPoint,
  type M5Route,
} from "@/features/m5-telemetry/types";
import { BenchServoBars } from "./BenchServoBars";
import { BenchStatusBar } from "./BenchStatusBar";
import { BenchDock } from "./BenchDock";
import {
  BENCH_BAR,
  BENCH_MAX_DEG,
  BENCH_MIN_DEG,
  BENCH_NEUTRAL_DEG,
  BENCH_PLOT_DEFAULT,
  BENCH_PLOT_ITEMS,
  BENCH_PRESETS,
  type BenchPlotKey,
  type BenchPlotVisibility,
} from "./benchConst";

/** トポロジは常設パネルに移したのでタブからは外している。イベントは下部ドック */
type TabId = "servo" | "cal" | "profile" | "nvs";

const TABS: { id: TabId; label: string }[] = [
  { id: "servo", label: "サーボ" },
  { id: "cal", label: "校正" },
  { id: "profile", label: "プロファイル" },
  { id: "nvs", label: "NVS" },
];

export default function BenchLabPage() {
  const stream = useM5TelemetryStream(true);
  const { status, frame, control, profile, scan, cal, events, history, send } = stream;

  const [tab, setTab] = useState<TabId>("servo");
  /** 下部ドック（イベント等）の本体高さ。0 ならタブ帯だけ */
  const [dockBodyH, setDockBodyH] = useState(0);
  const onDockLayout = useCallback((_open: boolean, heightPx: number) => {
    setDockBodyH(heightPx);
  }, []);
  /** 机上はいまのところ 1 軸だけ触る。対象はここで選ぶ */
  const [ch, setCh] = useState(0);
  const [plotOn, setPlotOn] = useState<BenchPlotVisibility>(BENCH_PLOT_DEFAULT);
  /** 校正中は生角が主役。unwrap は必要なときだけ足す */
  const [showRaw, setShowRaw] = useState(true);
  const [showUnwrap, setShowUnwrap] = useState(false);
  const manual = useFieldManual();

  const atomOk = Boolean(status?.connected);
  const canCmd = stream.wsStatus === "connected" && atomOk;
  const isRobot = status?.mode === "robot";
  const pwmOn = Boolean(at(control?.out, ch));
  const encOk = Boolean(at(frame?.as_ok, ch));
  const mapOk = Boolean(at(frame?.map_ok, ch));
  const magCode = at(frame?.mag, ch) ?? 255;
  const routes = profile?.routes ?? [];

  // NVS タブを開いたときだけ実キーを取り直す
  useEffect(() => {
    if (tab !== "nvs" || !canCmd) return;
    send({ op: "nvs_list" });
  }, [tab, canCmd, send]);

  /** 机上は 40〜230° を通す。wide を付けないと PC 側で 100〜170° に丸められる */
  const sendCmd = (deg: number) => {
    if (!canCmd) return;
    send({ op: "joint", ch, deg, wide: true });
  };

  const setPwm = (on: boolean) => {
    if (!canCmd) return;
    send({ op: "out", ch, on, wide: true });
  };

  const togglePlot = (key: BenchPlotKey) => {
    setPlotOn((p) => ({ ...p, [key]: !p[key] }));
  };

  const angleSeries = useMemo(
    () => buildAngleSeries(plotOn, history, ch),
    [plotOn, history, ch]
  );
  const powerSeries = useMemo(
    () => buildPowerSeries(plotOn, history, ch),
    [plotOn, history, ch]
  );

  const startCal = () => {
    if (!canCmd) return;
    const ok = window.confirm(
      `サーボ ch${ch} を ${BENCH_MIN_DEG}→${BENCH_MAX_DEG}→${BENCH_MIN_DEG}° で掃引します。` +
        "机上の干渉と AS5600 の追従を確認しましたか？（約 2 分）"
    );
    if (!ok) return;
    send({ op: "cal_start", ch });
  };

  return (
    <div
      className="m5 bench"
      style={{ ["--bench-dock-h" as string]: `${dockBodyH}px` }}
    >
      <header className="m5__header">
        <div className="m5__header-title">
          <h1>ATOM 机上ラボ</h1>
          <button type="button" className="m5__manual-btn" onClick={() => manual.openTo("map")}>
            ATOM 手帳
          </button>
        </div>
        <p>
          机の上の 1 サーボを対象にした校正・単体テスト用。実機テレメトリ（M5）と同じ{" "}
          <code>lab_debug.py</code> につなぐので、ファームの焼き直しは要りません。指令は{" "}
          {BENCH_MIN_DEG}〜{BENCH_MAX_DEG}°（ファームの可動域）です。
        </p>
      </header>

      {/* 接続・モード・周期などの動く値は下の固定ステータスバーに集約した */}
      <div className="m5__status">
        <span className="m5__url">{stream.url}</span>
        {status?.hello ? <span className="m5__meta">{status.hello}</span> : null}
      </div>

      {stream.lastError ? <div className="m5__error">{stream.lastError}</div> : null}

      {isRobot ? (
        <div className="bench__warn">
          Robot モードです。机上では全軸に PWM が出て 135° に保持されます。Lab に戻してください。
        </div>
      ) : null}

      <div className="m5__toolbar">
        <button type="button" className="m5__btn m5__btn--danger" onClick={() => send({ op: "hold" })}>
          全停止
        </button>
        <button
          type="button"
          className={"m5__btn" + (isRobot ? " m5__btn--warn" : "")}
          disabled={!canCmd || !isRobot}
          onClick={() => send({ op: "mode", robot: false })}
        >
          Lab に戻す
        </button>
        <button type="button" className="m5__btn" disabled={!canCmd} onClick={() => send({ op: "scan" })}>
          スキャン
        </button>
        <button
          type="button"
          className={"m5__btn" + (control?.auto_scan ? " m5__btn--on" : "")}
          disabled={!canCmd}
          onClick={() => send({ op: "auto_scan", on: !control?.auto_scan })}
        >
          自動SCAN
        </button>
        <button type="button" className="m5__btn" disabled={!canCmd} onClick={() => send({ op: "identify" })}>
          Identify
        </button>
        <button type="button" className="m5__btn" onClick={() => stream.reconnect()}>
          再接続
        </button>
      </div>

      <div className="bench__target">
        <label className="bench__target-lab">
          対象サーボ
          <select value={ch} onChange={(e) => setCh(Number(e.target.value))}>
            {Array.from({ length: M5_JOINTS }, (_, i) => (
              <option key={i} value={i}>
                ch{i}
              </option>
            ))}
          </select>
        </label>
        <span className="m5__meta">
          8Servos 0x25 の servo{routes[ch]?.servo_ch ?? ch} / AS5600{" "}
          {routes[ch]?.enc_addr
            ? `0x${routes[ch]!.enc_addr.toString(16).toUpperCase()} CH${routes[ch]!.enc_ch}`
            : "なし"}
        </span>
        <span className={"bench__chip" + (routes[ch]?.enabled === false ? " bench__chip--bad" : " bench__chip--ok")}>
          {routes[ch]?.enabled === false ? "関節 無効" : "関節 有効"}
        </span>
        <span className={"bench__chip" + (encOk ? " bench__chip--ok" : "")}>
          磁石 {MAG_LABEL[magCode] ?? String(magCode)}
        </span>
        <span className="bench__chip">AGC {at(frame?.agc, ch) === 255 ? "—" : (at(frame?.agc, ch) ?? "—")}</span>
        <span className={"bench__chip" + (mapOk ? " bench__chip--ok" : "")}>
          マップ {mapOk ? "あり" : "なし"}
        </span>
      </div>

      <div className="m5__tabs" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            className={"m5__tab" + (tab === t.id ? " m5__tab--on" : "")}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* トポロジはどのタブでも見えるよう左に常設し、右カラムだけタブで切り替える */}
      <div className="bench__layout">
        <aside className="bench__side">
          <TopologyPanel scan={scan} canCmd={canCmd} send={send} compact />
        </aside>

        <div className="bench__main">
          {tab === "servo" ? (
            <section className="m5__section bench__servo">
              <div className="m5__toolbar">
                <button
                  type="button"
                  className={"m5__btn" + (pwmOn ? " m5__btn--on" : "")}
                  disabled={!canCmd}
                  onClick={() => setPwm(!pwmOn)}
                >
                  {pwmOn ? "PWM ON（切る）" : "PWM を入れる"}
                </button>
                {BENCH_PRESETS.map((deg) => (
                  <button
                    key={deg}
                    type="button"
                    className="m5__btn"
                    disabled={!canCmd || !pwmOn}
                    onClick={() => sendCmd(deg)}
                  >
                    {deg}°
                  </button>
                ))}
                <button
                  type="button"
                  className={"m5__btn" + (at(control?.rand, ch) ? " m5__btn--warn" : "")}
                  disabled={!canCmd}
                  onClick={() => send({ op: "random", ch, on: !at(control?.rand, ch) })}
                >
                  {at(control?.rand, ch) ? "ランダム停止" : "ランダム動作"}
                </button>
              </div>
              <p className="m5__meta">
                指令バーはつまみを掴んでドラッグ。PWM を入れないと角度は出ません。ランダム動作は PC 側の
                共通設定（既定 100〜170°）で動きます。
              </p>

              <div className="bench__bar-togs" role="group" aria-label="バー表示項目">
                <span className="m5-leg__plot-togs-lab">バー</span>
                <button
                  type="button"
                  className={"m5-plot-tog" + (showRaw ? " m5-plot-tog--on" : "")}
                  style={{ color: BENCH_BAR.raw, borderColor: showRaw ? BENCH_BAR.raw : "rgba(255,255,255,0.18)" }}
                  aria-pressed={showRaw}
                  onClick={() => setShowRaw((v) => !v)}
                >
                  生角
                </button>
                <button
                  type="button"
                  className={"m5-plot-tog" + (showUnwrap ? " m5-plot-tog--on" : "")}
                  style={{
                    color: BENCH_BAR.unwrap,
                    borderColor: showUnwrap ? BENCH_BAR.unwrap : "rgba(255,255,255,0.18)",
                  }}
                  aria-pressed={showUnwrap}
                  onClick={() => setShowUnwrap((v) => !v)}
                >
                  unwrap
                </button>
              </div>

              <BenchServoBars
                ch={ch}
                cmd={at(control?.cmd, ch) ?? at(frame?.cmd, ch) ?? BENCH_NEUTRAL_DEG}
                raw={at(frame?.raw, ch)}
                unwrap={at(frame?.unwrap, ch)}
                corr={at(frame?.corr, ch)}
                pwmOn={pwmOn}
                encOk={encOk}
                showRaw={showRaw}
                showUnwrap={showUnwrap}
                disabled={!canCmd || !pwmOn}
                onCommand={sendCmd}
              />

              <div className="bench__plot-togs" role="group" aria-label="グラフ表示項目">
                <span className="m5-leg__plot-togs-lab">グラフ</span>
                {BENCH_PLOT_ITEMS.map((item) => {
                  const on = plotOn[item.key];
                  return (
                    <button
                      key={item.key}
                      type="button"
                      className={"m5-plot-tog" + (on ? " m5-plot-tog--on" : "")}
                      style={{ color: item.color, borderColor: on ? item.color : "rgba(255,255,255,0.18)" }}
                      aria-pressed={on}
                      onClick={() => togglePlot(item.key)}
                    >
                      {item.label}
                    </button>
                  );
                })}
              </div>
              {angleSeries.length ? <Sparkline series={angleSeries} showAxes yMin={0} yMax={360} /> : null}
              {powerSeries.length ? <Sparkline series={powerSeries} showAxes autoScale height={110} /> : null}

              <InaPanel ch={ch} frame={frame} canCmd={canCmd} routes={routes} profile={profile} send={send} />
            </section>
          ) : null}

          {tab === "cal" ? (
            <section className="m5__section">
              <p className="m5__meta">
                PC が PWM を {BENCH_MIN_DEG}→{BENCH_MAX_DEG}→{BENCH_MIN_DEG}°（1° 刻み・静止待ち）で掃引し、
                AS5600 と組んだマップを NVS の <code>cal</code> に書きます。周囲を空けてから実行してください。
              </p>
              <div className="m5__toolbar">
                <span className="m5__meta">対象 ch{ch}</span>
                <button type="button" className="m5__btn m5__btn--warn" disabled={!canCmd} onClick={startCal}>
                  校正開始
                </button>
                <button type="button" className="m5__btn m5__btn--danger" onClick={() => send({ op: "cal_abort" })}>
                  中止
                </button>
                <button
                  type="button"
                  className="m5__btn"
                  disabled={!canCmd}
                  onClick={() => send({ op: "map_get", ch })}
                >
                  マップ取得
                </button>
              </div>
              <p>状態: {cal?.status || "—"}</p>
              <p className="m5__meta">
                マップ ch{cal?.map_ch ?? 0} / 点数 {cal?.map_count ?? 0} / この軸のマップ{" "}
                {mapOk ? "あり" : "なし"}
              </p>
              <p className="m5__meta">
                AS5600 が {encOk ? "読めています" : "読めていません"}。読めないまま掃引しても点が溜まりません。
                JSON の保存・読込は PC 側（<code>lab_debug.py</code> の校正タブ）です。
              </p>
            </section>
          ) : null}

          {/* タブを外しても下書き（有効チェック）を残す */}
          <div hidden={tab !== "profile"}>
            <ProfilePanel profile={profile} canCmd={canCmd} send={send} />
          </div>

          {tab === "nvs" ? <NvsVault nvs={stream.nvs} canCmd={canCmd} send={send} /> : null}
        </div>
      </div>

      <FieldManual
        open={manual.open}
        chapterId={manual.chapterId}
        onChapter={manual.selectChapter}
        onClose={manual.close}
      />

      <BenchDock events={events} onLayout={onDockLayout} />

      <BenchStatusBar
        wsStatus={stream.wsStatus}
        status={status}
        frame={frame}
        control={control}
        ch={ch}
      />
    </div>
  );
}

/** 選択軸の電源。INA226 の割当もここから変えられる */
function InaPanel({
  ch,
  frame,
  canCmd,
  routes,
  profile,
  send,
}: {
  ch: number;
  frame: M5Frame | null;
  canCmd: boolean;
  routes: M5Route[];
  profile: { ina_options?: string[] } | null;
  send: (cmd: M5Cmd) => void;
}) {
  const inaOk = Boolean(at(frame?.ina_ok, ch));
  const current = inaSelectValue(routes[ch]);
  const options = profile?.ina_options?.length ? profile.ina_options : ["なし"];
  return (
    <article className="m5__card bench__ina">
      <div className="m5__card-head">
        <h2>電源（INA226）</h2>
        <label className="m5__ina">
          割当
          <select
            disabled={!canCmd}
            value={current}
            onChange={(e) => {
              const parsed = parseInaOption(e.target.value);
              if (!parsed) return;
              send({
                op: "ina_assign",
                ch,
                ina_hub: parsed.hub,
                ina_ch: parsed.ch,
                ina_addr: parsed.addr,
              });
            }}
          >
            {(options.includes(current) ? options : [...options, current]).map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
        </label>
        <span className={"bench__chip" + (inaOk ? " bench__chip--ok" : "")}>
          {inaOk ? "計測中" : "欠測"}
        </span>
      </div>
      <div className="m5__metrics">
        <Metric title="電圧" color={BENCH_BAR.volt} text={fmt(at(frame?.volt, ch), "V")} large />
        <Metric title="電流" color={BENCH_BAR.amp} text={fmt(at(frame?.amp, ch), "A")} large />
        <Metric title="電力" color={BENCH_BAR.watt} text={fmt(at(frame?.watt, ch), "W")} large />
      </div>
    </article>
  );
}

/** 角度系（左軸 0〜360°）。指令・補正は 40〜230° だが同じ軸に載せて比べる */
function buildAngleSeries(
  plotOn: BenchPlotVisibility,
  history: M5HistoryPoint[],
  ch: number
): SparkSeries[] {
  const out: SparkSeries[] = [];
  const push = (key: BenchPlotKey, color: string, pick: (h: M5HistoryPoint) => number | null) => {
    if (!plotOn[key]) return;
    out.push({
      key,
      color,
      values: history.map(pick),
      yMin: 0,
      yMax: 360,
      axis: "left",
      unit: "°",
    });
  };
  push("cmd", BENCH_BAR.cmd, (h) => at(h.cmd, ch) ?? null);
  push("raw", BENCH_BAR.raw, (h) => at(h.raw, ch) ?? null);
  push("unwrap", BENCH_BAR.unwrap, (h) => at(h.unwrap, ch) ?? null);
  push("corr", BENCH_BAR.corr, (h) => at(h.corr, ch) ?? null);
  return out;
}

/** 電源系。自動スケールなので単位だけ渡す */
function buildPowerSeries(
  plotOn: BenchPlotVisibility,
  history: M5HistoryPoint[],
  ch: number
): SparkSeries[] {
  const out: SparkSeries[] = [];
  if (plotOn.volt) {
    out.push({
      key: "volt",
      color: BENCH_BAR.volt,
      values: history.map((h) => at(h.volt, ch) ?? null),
      axis: "left",
      unit: "V",
    });
  }
  if (plotOn.amp) {
    out.push({
      key: "amp",
      color: BENCH_BAR.amp,
      values: history.map((h) => at(h.amp, ch) ?? null),
      axis: "right",
      unit: "A",
    });
  }
  if (plotOn.watt) {
    out.push({
      key: "watt",
      color: BENCH_BAR.watt,
      values: history.map((h) => at(h.watt, ch) ?? null),
      axis: "right",
      unit: "W",
    });
  }
  return out;
}
