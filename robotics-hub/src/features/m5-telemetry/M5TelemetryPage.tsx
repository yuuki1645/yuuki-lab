import { useEffect, useMemo, useRef, useState } from "react";
import { Sparkline } from "./Sparkline";
import "./M5TelemetryPage.css";
import {
  MAG_LABEL,
  M5_COLORS,
  M5_INA_CHS,
  M5_INA_PLOT_COLORS,
  M5_JOINTS,
  M5_PANEL_COUNT,
} from "./types";
import { at, fmt, fmtMs, Metric, NumField } from "./m5Widgets";
import { inaSelectValue, parseInaOption } from "./m5Route";
import { ProfilePanel } from "./ProfilePanel";
import { TopologyPanel } from "./TopologyPanel";
import { RightLegTab } from "./RightLegTab";
import { M5CameraPane } from "./M5CameraPane";
import { M5RecordBar } from "./M5RecordBar";
import { M5RecordLibrary } from "./M5RecordLibrary";
import { useM5Camera } from "./useM5Camera";
import { useM5Recording } from "./useM5Recording";
import { useM5TelemetryStream } from "./useM5TelemetryStream";
import FieldManual, { useFieldManual } from "./field-manual/FieldManual";
import { NvsVault } from "./NvsVault";
import { EventsLog } from "./EventsLog";

type TabId = "right-leg" | "joint" | "power" | "time" | "topo" | "profile" | "cal" | "nvs" | "events";

const TABS: { id: TabId; label: string }[] = [
  { id: "right-leg", label: "右脚" },
  { id: "joint", label: "関節 / 試験" },
  { id: "power", label: "電源" },
  { id: "time", label: "周期" },
  { id: "topo", label: "トポロジ" },
  { id: "profile", label: "プロファイル" },
  { id: "cal", label: "校正" },
  { id: "nvs", label: "NVS" },
  { id: "events", label: "イベント" },
];

export default function M5TelemetryPage() {
  const stream = useM5TelemetryStream(true);
  const camera = useM5Camera({
    recordStatus: stream.recordStatus,
  });
  const rec = useM5Recording({
    recordStatus: stream.recordStatus,
    send: stream.send,
    startCamera: camera.startCapture,
    stopCamera: camera.stopCapture,
  });
  const replaying = rec.mode === "replay";
  const status = stream.status;
  const events = stream.events;
  const cal = stream.cal;
  const send = stream.send;
  const frame = replaying ? rec.frame : stream.frame;
  const history = replaying ? (rec.history ?? []) : stream.history;
  const control = replaying ? rec.control : stream.control;
  const scan = replaying ? (rec.replayScan ?? stream.scan) : stream.scan;
  const profile = replaying ? (rec.replayProfile ?? stream.profile) : stream.profile;
  const [tab, setTab] = useState<TabId>("right-leg");
  const [panels, setPanels] = useState<number[]>([0, 1]);
  const [plotJoint, setPlotJoint] = useState(0);
  const [plotLines, setPlotLines] = useState({
    cmd: true,
    raw: false,
    unwrap: false,
    corr: true,
    v: false,
    a: true,
    w: false,
  });
  const [calCh, setCalCh] = useState(0);
  const pinEvents = useRef(true);
  const manual = useFieldManual();

  const routes = profile?.routes ?? [];
  const atomOk = Boolean(status?.connected);
  // 再生中は実機へ指令を出さない。全停止だけツールバーに残す。
  const canCmd = stream.wsStatus === "connected" && atomOk && !replaying;

  // タブを開いているあいだは 1 回だけ。切断復帰のたびに nvs_list しない
  const nvsListed = useRef(false);
  useEffect(() => {
    if (tab !== "nvs") {
      nvsListed.current = false;
      return;
    }
    if (!canCmd || nvsListed.current) return;
    nvsListed.current = true;
    send({ op: "nvs_list" });
  }, [tab, canCmd, send]);

  const setPanelJoint = (panel: number, joint: number) => {
    setPanels((prev) => {
      const next = [...prev];
      next[panel] = joint;
      return next;
    });
  };

  const togglePlot = (key: keyof typeof plotLines) => {
    setPlotLines((p) => ({ ...p, [key]: !p[key] }));
  };

  const jointSeries = useMemo(() => {
    const j = plotJoint;
    const series = [];
    if (plotLines.cmd) {
      series.push({ key: "cmd", color: M5_COLORS.cmd, values: history.map((h) => at(h.cmd, j)) });
    }
    if (plotLines.raw) {
      series.push({ key: "raw", color: M5_COLORS.raw, values: history.map((h) => at(h.raw, j)) });
    }
    if (plotLines.unwrap) {
      series.push({
        key: "unwrap",
        color: M5_COLORS.unwrap,
        values: history.map((h) => at(h.unwrap, j)),
      });
    }
    if (plotLines.corr) {
      series.push({ key: "corr", color: M5_COLORS.corr, values: history.map((h) => at(h.corr, j)) });
    }
    return series;
  }, [history, plotJoint, plotLines]);

  const jointPwrSeries = useMemo(() => {
    const j = plotJoint;
    const series = [];
    if (plotLines.v) {
      series.push({ key: "v", color: M5_COLORS.volt, values: history.map((h) => at(h.volt, j)) });
    }
    if (plotLines.a) {
      series.push({ key: "a", color: M5_COLORS.amp, values: history.map((h) => at(h.amp, j)) });
    }
    if (plotLines.w) {
      series.push({ key: "w", color: M5_COLORS.watt, values: history.map((h) => at(h.watt, j)) });
    }
    return series;
  }, [history, plotJoint, plotLines]);

  const startCal = () => {
    const ok = window.confirm(
      `関節 ${calCh} を 40→230→40° で動かします。干渉・配線を確認しましたか？（数分かかります）`
    );
    if (!ok) return;
    send({ op: "cal_start", ch: calCh });
  };

  return (
    <div className="m5">
      <header className="m5__header">
        <div className="m5__header-title">
          <h1>実機テレメトリ（M5）</h1>
          <button type="button" className="m5__manual-btn" onClick={() => manual.openTo("map")}>
            ATOM 手帳
          </button>
        </div>
        <p>
          記録開始でセンサと実機カメラを同時に残します。再生するとバー・足圧・映像が同じ時刻になります。
        </p>
      </header>

      <div className="m5__status">
        <span className={"m5__badge m5__badge--" + stream.wsStatus}>
          {stream.wsStatus === "connected"
            ? "ブリッジ接続"
            : stream.wsStatus === "connecting"
              ? "接続中"
              : "未接続"}
        </span>
        <span className="m5__url">{stream.url}</span>
        <span className={"m5__badge " + (atomOk ? "m5__badge--connected" : "m5__badge--disconnected")}>
          {atomOk ? `ATOM ${status?.name || status?.port || ""}` : "ATOM 未接続"}
        </span>
        {status?.hello ? <span className="m5__meta">{status.hello}</span> : null}
        <span className="m5__meta">モード {replaying ? (frame?.mode || rec.meta?.mode || "—") : status?.mode || "—"}</span>
        {replaying ? <span className="m5__badge m5__badge--replay">再生表示</span> : null}
        {stream.recordStatus?.recording ? <span className="m5__badge m5__badge--rec">記録中</span> : null}
      </div>

      {stream.lastError ? <div className="m5__error">{stream.lastError}</div> : null}

      <div className="m5__toolbar">
        <button type="button" className="m5__btn m5__btn--danger" onClick={() => send({ op: "hold" })}>
          全停止
        </button>
        <button
          type="button"
          className={"m5__btn " + (status?.mode === "robot" ? "m5__btn--on" : "")}
          disabled={!canCmd}
          onClick={() => send({ op: "mode", robot: status?.mode !== "robot" })}
        >
          {status?.mode === "robot" ? "Robot" : "Lab"}
        </button>
        <button type="button" className="m5__btn" disabled={!canCmd} onClick={() => send({ op: "scan" })}>
          スキャン
        </button>
        <button
          type="button"
          className={"m5__btn " + (control?.auto_scan ? "m5__btn--on" : "")}
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

      <M5RecordBar rec={rec} camera={camera} atomOk={atomOk && stream.wsStatus === "connected"} />
      <M5RecordLibrary
        open={rec.libraryOpen}
        onClose={() => rec.setLibraryOpen(false)}
        rows={rec.library}
        loading={rec.libraryLoading}
        error={rec.libraryError}
        busy={rec.busy}
        playingId={replaying ? rec.meta?.id ?? null : null}
        onRefresh={() => void rec.refreshLibrary()}
        onPlay={(id) => void rec.loadReplay(id)}
        onSave={(id, name, notes) => rec.saveMeta(id, name, notes)}
        onDelete={(id) => rec.removeRecording(id)}
      />

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

      {tab === "right-leg" ? (
        <RightLegTab
          canCmd={canCmd}
          control={control}
          frame={frame}
          history={history}
          send={send}
          cameraPane={
            <M5CameraPane
              camera={camera}
              replaying={replaying}
              replayCamera={rec.meta?.camera}
              playheadSec={
                replaying && rec.frame && typeof rec.meta?.camera?.video_t0_unix === "number"
                  ? Math.max(0, rec.frame.t - rec.meta.camera.video_t0_unix)
                  : rec.tNow
              }
              playing={rec.playing}
            />
          }
        />
      ) : null}

      {tab === "joint" ? (
        <section className="m5__section">
          <div className="m5__panels">
            {Array.from({ length: M5_PANEL_COUNT }, (_, p) => {
              const j = panels[p] ?? p;
              const mag = at(frame?.mag, j) ?? 255;
              return (
                <article key={p} className="m5__card">
                  <div className="m5__card-head">
                    <label>
                      関節
                      <select
                        value={j}
                        onChange={(e) => setPanelJoint(p, Number(e.target.value))}
                      >
                        {Array.from({ length: M5_JOINTS }, (_, i) => (
                          <option key={i} value={i}>
                            {i}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <div className="m5__metrics">
                    <Metric title="指令" color={M5_COLORS.cmd} text={fmt(at(frame?.cmd, j), "°")} />
                    <Metric title="磁石" color="#10ac84" text={MAG_LABEL[mag] ?? String(mag)} />
                    <Metric title="生角" color={M5_COLORS.raw} text={fmt(at(frame?.raw, j), "°")} />
                    <Metric title="AGC" color="#8b9bb0" text={at(frame?.agc, j) === 255 ? "—" : String(at(frame?.agc, j) ?? "—")} />
                    <Metric title="unwrap" color={M5_COLORS.unwrap} text={fmt(at(frame?.unwrap, j), "°")} />
                    <Metric title="電圧" color={M5_COLORS.volt} text={fmt(at(frame?.volt, j), "V")} />
                    <Metric title="補正" color={M5_COLORS.corr} text={fmt(at(frame?.corr, j), "°")} />
                    <Metric title="電流" color={M5_COLORS.amp} text={fmt(at(frame?.amp, j), "A")} />
                    <Metric title="電力" color={M5_COLORS.watt} text={fmt(at(frame?.watt, j), "W")} />
                  </div>
                  <label className="m5__check">
                    <input
                      type="checkbox"
                      checked={Boolean(at(control?.out, j))}
                      disabled={!canCmd}
                      onChange={(e) => send({ op: "out", ch: j, on: e.target.checked })}
                    />
                    PWM 出力する
                  </label>
                  <input
                    className="m5__slider"
                    type="range"
                    min={100}
                    max={170}
                    step={0.5}
                    disabled={!canCmd}
                    value={at(control?.cmd, j) ?? 135}
                    onChange={(e) => send({ op: "joint", ch: j, deg: Number(e.target.value) })}
                  />
                  <label className="m5__check m5__check--warn">
                    <input
                      type="checkbox"
                      checked={Boolean(at(control?.rand, j))}
                      disabled={!canCmd}
                      onChange={(e) => send({ op: "random", ch: j, on: e.target.checked })}
                    />
                    ランダム動作
                  </label>
                  {profile?.ina_options?.length ? (
                    <label className="m5__ina">
                      INA226
                      <select
                        disabled={!canCmd}
                        value={inaSelectValue(routes[j])}
                        onChange={(e) => {
                          const parsed = parseInaOption(e.target.value);
                          if (!parsed) return;
                          send({
                            op: "ina_assign",
                            ch: j,
                            ina_hub: parsed.hub,
                            ina_ch: parsed.ch,
                            ina_addr: parsed.addr,
                          });
                        }}
                      >
                        {(profile.ina_options.includes(inaSelectValue(routes[j]))
                          ? profile.ina_options
                          : [...profile.ina_options, inaSelectValue(routes[j])]
                        ).map((opt) => (
                          <option key={opt} value={opt}>
                            {opt}
                          </option>
                        ))}
                      </select>
                    </label>
                  ) : null}
                </article>
              );
            })}
          </div>

          <div className="m5__rand">
            <span>ランダム設定</span>
            <NumField
              label="最小°"
              value={control?.rand_min ?? 40}
              disabled={!canCmd}
              onCommit={(v) => send({ op: "rand_settings", rand_min: v })}
            />
            <NumField
              label="最大°"
              value={control?.rand_max ?? 230}
              disabled={!canCmd}
              onCommit={(v) => send({ op: "rand_settings", rand_max: v })}
            />
            <NumField
              label="保持min秒"
              value={control?.rand_hold_min ?? 0.7}
              disabled={!canCmd}
              onCommit={(v) => send({ op: "rand_settings", rand_hold_min: v })}
            />
            <NumField
              label="保持max秒"
              value={control?.rand_hold_max ?? 1.4}
              disabled={!canCmd}
              onCommit={(v) => send({ op: "rand_settings", rand_hold_max: v })}
            />
            <NumField
              label="最小ジャンプ°"
              value={control?.rand_jump ?? 25}
              disabled={!canCmd}
              onCommit={(v) => send({ op: "rand_settings", rand_jump: v })}
            />
          </div>

          <div className="m5__plot-bar">
            <label>
              グラフ関節
              <select value={plotJoint} onChange={(e) => setPlotJoint(Number(e.target.value))}>
                {Array.from({ length: M5_JOINTS }, (_, i) => (
                  <option key={i} value={i}>
                    {i}
                  </option>
                ))}
              </select>
            </label>
            {(
              [
                ["cmd", "指令", M5_COLORS.cmd],
                ["raw", "生角", M5_COLORS.raw],
                ["unwrap", "unwrap", M5_COLORS.unwrap],
                ["corr", "補正", M5_COLORS.corr],
                ["v", "電圧", M5_COLORS.volt],
                ["a", "電流", M5_COLORS.amp],
                ["w", "電力", M5_COLORS.watt],
              ] as const
            ).map(([key, label, color]) => (
              <label key={key} style={{ color }}>
                <input type="checkbox" checked={plotLines[key]} onChange={() => togglePlot(key)} />
                {label}
              </label>
            ))}
          </div>
          <Sparkline series={jointSeries} yMin={0} yMax={360} />
          {jointPwrSeries.length ? <Sparkline series={jointPwrSeries} autoScale height={100} /> : null}
        </section>
      ) : null}

      {tab === "power" ? (
        <section className="m5__section">
          <div className="m5__rand">
            <NumField
              label="PC 電流監視 [A]"
              value={control?.amp_limit ?? 8}
              disabled={!canCmd}
              onCommit={(v) => send({ op: "amp_limit", amp_limit: v })}
            />
            <span className="m5__meta">超過時の #HOLD は PC プロセス側で実行されます</span>
          </div>
          <div className="m5__panels">
            {Array.from({ length: M5_INA_CHS }, (_, i) => (
              <article key={i} className="m5__card">
                <h2>関節 {i} の電源</h2>
                <Metric title="電圧" color={M5_COLORS.volt} text={fmt(at(frame?.volt, i), "V")} large />
                <Metric title="電流" color={M5_COLORS.amp} text={fmt(at(frame?.amp, i), "A")} large />
                <Metric title="電力" color={M5_COLORS.watt} text={fmt(at(frame?.watt, i), "W")} large />
              </article>
            ))}
          </div>
          <h3>電力 [W]</h3>
          <Sparkline
            autoScale
            series={Array.from({ length: M5_INA_CHS }, (_, i) => ({
              key: `w${i}`,
              color: M5_INA_PLOT_COLORS[i % M5_INA_PLOT_COLORS.length],
              values: history.map((h) => at(h.watt, i)),
            }))}
          />
          <h3>電圧 [V]</h3>
          <Sparkline
            autoScale
            series={Array.from({ length: M5_INA_CHS }, (_, i) => ({
              key: `v${i}`,
              color: M5_INA_PLOT_COLORS[i % M5_INA_PLOT_COLORS.length],
              values: history.map((h) => at(h.volt, i)),
            }))}
          />
        </section>
      ) : null}

      {tab === "time" ? (
        <section className="m5__section">
          <div className="m5__time-row">
            <Metric title="周期" color={M5_COLORS.period} text={fmtMs(frame?.period_us)} />
            <Metric title="ループ" color={M5_COLORS.loop} text={fmtMs(frame?.loop_us)} />
            <Metric title="センサ" color={M5_COLORS.sense} text={fmtMs(frame?.sense_us)} />
            <Metric title="ジッタ" color={M5_COLORS.period} text={fmtMs(frame?.jitter_us)} />
            <Metric title="I2C累計" color={M5_COLORS.period} text={String(frame?.i2c_err ?? "—")} />
            <Metric title="8Servos" color={frame?.servo_ok ? "#10ac84" : "#ee5253"} text={frame?.servo_ok ? "OK" : "なし"} />
          </div>
          <Sparkline
            yMin={0}
            yMax={80}
            series={[
              { key: "period", color: M5_COLORS.period, values: history.map((h) => h.period_ms) },
              { key: "loop", color: M5_COLORS.loop, values: history.map((h) => h.loop_ms) },
              { key: "sense", color: M5_COLORS.sense, values: history.map((h) => h.sense_ms) },
            ]}
          />
        </section>
      ) : null}

      {tab === "topo" ? <TopologyPanel scan={scan} canCmd={canCmd} send={send} /> : null}

      {/* タブを外しても下書き（有効チェック）を残す */}
      <div hidden={tab !== "profile"}>
        <ProfilePanel profile={profile} canCmd={canCmd} send={send} />
      </div>

      {tab === "cal" ? (
        <section className="m5__section">
          <p className="m5__meta">
            周囲を空けてから実行。40→230→40° でマップを作り NVS に保存します。JSON ファイルの読み書きは PC 側です。
          </p>
          <div className="m5__toolbar">
            <label>
              関節
              <select value={calCh} onChange={(e) => setCalCh(Number(e.target.value))}>
                {Array.from({ length: M5_JOINTS }, (_, i) => (
                  <option key={i} value={i}>
                    {i}
                  </option>
                ))}
              </select>
            </label>
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
              onClick={() => send({ op: "map_get", ch: calCh })}
            >
              マップ取得
            </button>
          </div>
          <p>状態: {cal?.status || "—"}</p>
          <p className="m5__meta">
            マップ ch{cal?.map_ch ?? 0} / 点数 {cal?.map_count ?? 0}
          </p>
        </section>
      ) : null}

      {tab === "nvs" ? <NvsVault nvs={stream.nvs} canCmd={canCmd} send={send} /> : null}

      {tab === "events" ? (
        <section className="m5__section">
          <p className="m5__meta">
            本記録（センサ＋指令）は上のバーから開始します。保存先は ATOM 接続 PC の{" "}
            <code>atom-rt/data/recordings</code>。ライブラリで再生すると、この画面の全タブが同時刻に連動します。
          </p>
          <EventsLog
            className="m5__events"
            lines={events}
            headSeq={stream.eventHeadSeq}
            tailSeq={stream.eventTailSeq}
            pinBottom={pinEvents}
          />
        </section>
      ) : null}

      <FieldManual
        open={manual.open}
        chapterId={manual.chapterId}
        onChapter={manual.selectChapter}
        onClose={manual.close}
      />
    </div>
  );
}

