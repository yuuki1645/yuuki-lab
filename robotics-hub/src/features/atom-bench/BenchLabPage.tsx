/**
 * ATOM 机上ラボ。
 *
 * 机の上で ATOM + サーボ 1 本（＋任意で AS5600 / INA226）を扱う画面。
 * 実機テレメトリ（M5）と同じ lab_debug.py（Socket.IO :8794）につなぐので、
 * ファームの焼き分けは不要。違いは「机上向けに Lab を保ち、1 軸だけ触る」点。
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
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
import { UiHelp } from "@/shared/components/UiHelp";
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

const TAB_QUERY = "tab";
const TAB_DEFAULT: TabId = "servo";

function isTabId(v: string | null): v is TabId {
  return TABS.some((t) => t.id === v);
}

/** 再読み込みでも同じタブを開く。URL は ?tab=profile など */
function tabFromSearch(params: URLSearchParams): TabId {
  const raw = params.get(TAB_QUERY);
  return isTabId(raw) ? raw : TAB_DEFAULT;
}

export default function BenchLabPage() {
  const stream = useM5TelemetryStream(true);
  const { status, frame, control, profile, scan, cal, events, eventHeadSeq, eventTailSeq, history, send } = stream;

  const [searchParams, setSearchParams] = useSearchParams();
  const tab = tabFromSearch(searchParams);
  const setTab = (id: TabId) => {
    const next = new URLSearchParams(searchParams);
    if (id === TAB_DEFAULT) {
      next.delete(TAB_QUERY);
    } else {
      next.set(TAB_QUERY, id);
    }
    setSearchParams(next, { replace: true });
  };
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
          <h1>
            ATOM 机上ラボ
            <UiHelp title="机上ラボ" wide>
              机の上の ATOM とサーボ 1 本向けです。機体用の実機テレメトリと同じ lab_debug.py に繋ぐので、ファームの焼き分けは不要です。違いは Lab モードを保ち、1 軸だけ触ることです。詳しい層の話は「ATOM 手帳」にあります。
            </UiHelp>
          </h1>
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
        <UiHelp title="操作" wide>
          全停止は全軸の PWM を切ります。Lab に戻すは Robot のときだけ使います。スキャンは今刺さっている I2C を一度読みます。自動 SCAN は毎周期近く走るので overrun の原因になります。Identify は本体 LED を虹色にします。再接続は Hub と Python の Socket.IO です（COM の抜き差しではありません）。
        </UiHelp>
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
          <UiHelp title="対象サーボ">
            この画面が触る論理関節です。8Servos の物理 ch はプロファイルの経路で決まります。机上では ch0 が典型です。
          </UiHelp>
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
          <UiHelp title="関節の有効" placement="bottom">
            経路（アドレス）は残したまま、20 Hz の I2C と PWM から外すスイッチです。PWM の ON/OFF とは別です。変更はプロファイルタブで「ボードへ送信」するまでフラッシュに残りません。
          </UiHelp>
        </span>
        <span className={"bench__chip" + (encOk ? " bench__chip--ok" : "")}>
          磁石 {MAG_LABEL[magCode] ?? String(magCode)}
          <UiHelp title="磁石 STATUS">
            AS5600 が見ている磁石の状態です。なし・遠い・弱いときはホルダの向きと隙間を見てください。関節が無効だと読みに行きません。
          </UiHelp>
        </span>
        <span className="bench__chip">
          AGC {at(frame?.agc, ch) === 255 ? "—" : (at(frame?.agc, ch) ?? "—")}
          <UiHelp title="AGC">
            AS5600 の自動ゲインです。255 は未読。極端に高い・低いときは磁石が遠すぎるか近すぎます。
          </UiHelp>
        </span>
        <span className={"bench__chip" + (mapOk ? " bench__chip--ok" : "")}>
          マップ {mapOk ? "あり" : "なし"}
          <UiHelp title="校正マップ">
            NVS の cal に、この軸の unwrap→指令 の対応があるかです。ないと補正角は作れません。校正タブで掃引して作ります。
          </UiHelp>
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
        <UiHelp title="タブ" wide>
          サーボは机上の 1 軸操作、校正は PC 掃引、プロファイルは経路と有効マスク、NVS はフラッシュの実キーです。タブは URL の ?tab= に残るので、再読み込みしても同じページに戻れます。
        </UiHelp>
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
                <UiHelp title="PWM と指令" wide>
                  PWM を入れないと角度は出ません。プリセットは 40〜230° の安全域です。ランダム動作は PC 側の共通レンジ（既定 100〜170°）で動くので、机上のフル可動域とは違います。指令バーはつまみだけドラッグできます。
                </UiHelp>
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
                <span className="m5-leg__plot-togs-lab">
                  バー
                  <UiHelp title="バー">
                    指令は 40〜230° の可動域、生角と unwrap は AS5600 の 0〜360° です。校正では生角が主役なので、必要なときだけ unwrap を足してください。
                  </UiHelp>
                </span>
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
                <span className="m5-leg__plot-togs-lab">
                  グラフ
                  <UiHelp title="グラフ">
                    直近の履歴を折線にします。角度は 0〜360° 軸、電源は自動スケールです。色はバーと同じです。
                  </UiHelp>
                </span>
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
                <UiHelp title="校正" wide>
                  PC が PWM を握って 40→230→40° を 1° 刻みで掃引し、できたマップを NVS の cal に書きます。AS5600 が読めていないと点は溜まりません。JSON の保存は lab_debug.py 側です。マップ取得はボードからチャンクで吸い上げます（この間テレメトリは止まります）。
                </UiHelp>
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

      <BenchDock
        events={events}
        eventHeadSeq={eventHeadSeq}
        eventTailSeq={eventTailSeq}
        onLayout={onDockLayout}
      />

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
        <h2>
          電源（INA226）
          <UiHelp title="INA226">
            この軸の電流センサです。割当はプロファイルの ina_hub / ch / addr で、ここから仮に変えられます。ボードへ送信するまでフラッシュには残りません。欠測のまま有効だと I2C エラーが増えます。
          </UiHelp>
        </h2>
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
