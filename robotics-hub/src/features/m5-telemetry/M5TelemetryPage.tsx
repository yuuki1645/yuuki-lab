import { useMemo, useState } from "react";
import { Sparkline } from "./Sparkline";
import "./M5TelemetryPage.css";
import {
  KIND_META,
  MAG_LABEL,
  M5_COLORS,
  M5_INA_CHS,
  M5_INA_DEFAULT_ASSIGNED,
  M5_INA_PLOT_COLORS,
  M5_JOINTS,
  M5_PANEL_COUNT,
  kindMeta,
  type M5FootRoute,
  type M5Route,
} from "./types";
import { buildTopoTree, type TopoItem } from "./topoTree";
import { RightLegTab } from "./RightLegTab";
import { M5CameraPane } from "./M5CameraPane";
import { M5RecordBar } from "./M5RecordBar";
import { M5RecordLibrary } from "./M5RecordLibrary";
import { useM5Camera } from "./useM5Camera";
import { useM5Recording } from "./useM5Recording";
import { useM5TelemetryStream } from "./useM5TelemetryStream";

type TabId = "right-leg" | "joint" | "power" | "time" | "topo" | "profile" | "cal" | "events";

const TABS: { id: TabId; label: string }[] = [
  { id: "right-leg", label: "右脚" },
  { id: "joint", label: "関節 / 試験" },
  { id: "power", label: "電源" },
  { id: "time", label: "周期" },
  { id: "topo", label: "トポロジ" },
  { id: "profile", label: "プロファイル" },
  { id: "cal", label: "校正" },
  { id: "events", label: "イベント" },
];

function fmt(v: number | null | undefined, unit: string): string {
  if (typeof v !== "number" || !Number.isFinite(v)) return `— ${unit}`;
  return `${v.toFixed(2).padStart(8, " ")} ${unit}`;
}

function fmtMs(us: number | undefined): string {
  if (typeof us !== "number" || !Number.isFinite(us)) return "— ms";
  return `${(us / 1000).toFixed(1).padStart(6, " ")} ms`;
}

function at<T>(xs: T[] | undefined, i: number): T | undefined {
  return xs && i >= 0 && i < xs.length ? xs[i] : undefined;
}

function emptyRoute(i: number): M5Route {
  return {
    enc_hub: i < 6 ? 0x70 : 0,
    enc_ch: i < 6 ? i : -1,
    enc_addr: i < 6 ? 0x36 : 0,
    act_hub: 0,
    act_ch: -1,
    act_addr: 0x25,
    servo_ch: i,
    ina_hub: i < M5_INA_DEFAULT_ASSIGNED ? 0x71 : 0,
    ina_ch: i < M5_INA_DEFAULT_ASSIGNED ? i : -1,
    ina_addr: i < M5_INA_DEFAULT_ASSIGNED ? 0x41 : 0,
  };
}

function emptyFoot(): M5FootRoute {
  return { hub: 0x71, ch: 2, addr: 0x28 };
}

function fmtFootRoute(r: M5FootRoute): string {
  if (!r.addr) return "なし";
  if (!r.hub) return `root  0x${r.addr.toString(16).toUpperCase().padStart(2, "0")}`;
  const hub = r.hub.toString(16).toUpperCase().padStart(2, "0");
  return `${hub} CH${r.ch}  0x${r.addr.toString(16).toUpperCase().padStart(2, "0")}`;
}

function parseFootOption(text: string): M5FootRoute | null {
  const s = text.trim();
  if (s === "なし" || s === "" || s === "—") return { hub: 0, ch: -1, addr: 0 };
  if (s.startsWith("root")) {
    const parts = s.split(/\s+/);
    const addr = Number.parseInt(parts[parts.length - 1] ?? "", 16);
    if (!Number.isFinite(addr)) return null;
    return { hub: 0, ch: -1, addr };
  }
  const bits = s.replace(/CH/i, " ").replace(/\s+/g, " ").trim().split(" ");
  const hub = Number.parseInt(bits[0] ?? "", 16);
  const ch = Number.parseInt(bits[1] ?? "", 10);
  const addr = Number.parseInt(bits[bits.length - 1] ?? "", 16);
  if (![hub, ch, addr].every(Number.isFinite)) return null;
  return { hub, ch, addr };
}

function fmtRouteField(key: keyof M5Route, n: number): string {
  if (key.endsWith("ch") || key === "servo_ch") return String(n);
  if (key.endsWith("hub") && n === 0) return "0";
  return `0x${n.toString(16).toUpperCase().padStart(2, "0")}`;
}

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
  const [topoSel, setTopoSel] = useState<number | null>(null);
  const [topoInaJoint, setTopoInaJoint] = useState(0);
  const [calCh, setCalCh] = useState(0);
  const [draftRoutes, setDraftRoutes] = useState<M5Route[] | null>(null);
  const [draftFoot, setDraftFoot] = useState<M5FootRoute | null>(null);

  const topoTree = useMemo(() => buildTopoTree(scan?.nodes ?? []), [scan?.nodes]);

  const routes = replaying ? (profile?.routes ?? []) : (draftRoutes ?? profile?.routes ?? []);
  const foot = replaying ? (profile?.foot ?? emptyFoot()) : (draftFoot ?? profile?.foot ?? emptyFoot());
  const atomOk = Boolean(status?.connected);
  // 再生中は実機へ指令を出さない。全停止だけツールバーに残す。
  const canCmd = stream.wsStatus === "connected" && atomOk && !replaying;

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

  const selectedNode = topoSel != null ? scan?.nodes[topoSel] : undefined;

  const applyDraft = (i: number, key: keyof M5Route, raw: string) => {
    const base = (draftRoutes ?? profile?.routes ?? Array.from({ length: M5_JOINTS }, (_, k) => emptyRoute(k))).map(
      (r) => ({ ...r })
    );
    while (base.length < M5_JOINTS) base.push(emptyRoute(base.length));
    const n = raw.trim().toLowerCase().startsWith("0x") ? parseInt(raw, 16) : Number(raw);
    if (!Number.isFinite(n)) return;
    const next: M5Route = { ...emptyRoute(i), ...base[i] };
    next[key] = n;
    base[i] = next;
    setDraftRoutes(base);
  };

  return (
    <div className="m5">
      <header className="m5__header">
        <h1>実機テレメトリ（M5）</h1>
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
                    min={40}
                    max={230}
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

      {tab === "topo" ? (
        <section className="m5__section">
          <div className="m5__toolbar">
            <button type="button" className="m5__btn" disabled={!canCmd} onClick={() => send({ op: "scan" })}>
              スキャン
            </button>
            <button
              type="button"
              className="m5__btn"
              disabled={!canCmd || !selectedNode}
              onClick={() => {
                if (!selectedNode) return;
                send({ op: "probe", hub: selectedNode.hub, ch: selectedNode.ch, addr: selectedNode.addr });
              }}
            >
              1回読む
            </button>
            <label>
              INA→関節
              <select value={topoInaJoint} onChange={(e) => setTopoInaJoint(Number(e.target.value))}>
                {Array.from({ length: M5_JOINTS }, (_, i) => (
                  <option key={i} value={i}>
                    {i}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              className="m5__btn m5__btn--on"
              disabled={!canCmd || selectedNode?.kind !== "ina226"}
              onClick={() => {
                if (!selectedNode || selectedNode.kind !== "ina226") return;
                const hub = selectedNode.hub === "root" ? 0 : parseInt(String(selectedNode.hub), 16) || 0;
                const addr = parseInt(String(selectedNode.addr), 16) || 0;
                send({
                  op: "ina_assign",
                  ch: topoInaJoint,
                  ina_hub: hub,
                  ina_ch: selectedNode.ch,
                  ina_addr: addr,
                });
              }}
            >
              選択を割当
            </button>
            <button
              type="button"
              className="m5__btn"
              disabled={!canCmd}
              onClick={() =>
                send({ op: "ina_assign", ch: topoInaJoint, ina_hub: 0, ina_ch: -1, ina_addr: 0 })
              }
            >
              割当を外す
            </button>
          </div>
          <div className="m5__legend">
            {Object.entries(KIND_META).map(([k, meta]) => (
              <span key={k} className="m5__legend-item">
                <i style={{ background: meta.color }} />
                {meta.label}
              </span>
            ))}
          </div>
          <div className="m5__tree">
            <div className="m5__tree-root">Grove I2C</div>
            {topoTree.map((item) => (
              <TopoNode
                key={`${item.kind}-${item.title}-${item.srcIndex}`}
                item={item}
                depth={0}
                selected={topoSel}
                onSelect={setTopoSel}
              />
            ))}
          </div>
          {!scan?.nodes?.length ? <p className="m5__meta">スキャン結果がありません。</p> : null}
        </section>
      ) : null}

      {tab === "profile" ? (
        <section className="m5__section">
          <div className="m5__toolbar">
            <button type="button" className="m5__btn" disabled={!canCmd} onClick={() => send({ op: "prof_get" })}>
              ボードから取得
            </button>
            <button
              type="button"
              className="m5__btn m5__btn--on"
              disabled={!canCmd}
              onClick={() => {
                send({
                  op: "prof_put",
                  routes: draftRoutes ?? profile?.routes ?? [],
                  foot: draftFoot ?? profile?.foot ?? emptyFoot(),
                });
                setDraftRoutes(null);
                setDraftFoot(null);
              }}
            >
              ボードへ送信
            </button>
            <button type="button" className="m5__btn" disabled={!canCmd} onClick={() => send({ op: "prof_default" })}>
              既定に戻す
            </button>
            <button
              type="button"
              className="m5__btn"
              disabled={!canCmd}
              onClick={() => send({ op: "prof_from_scan" })}
            >
              SCANから仮割当
            </button>
          </div>
          <div className="m5__table-wrap">
            <table className="m5__table">
              <thead>
                <tr>
                  <th>関節</th>
                  <th>enc_hub</th>
                  <th>enc_ch</th>
                  <th>enc_addr</th>
                  <th>act_hub</th>
                  <th>act_ch</th>
                  <th>act_addr</th>
                  <th>servo</th>
                  <th>ina_hub</th>
                  <th>ina_ch</th>
                  <th>ina_addr</th>
                </tr>
              </thead>
              <tbody>
                {Array.from({ length: M5_JOINTS }, (_, i) => {
                  const r = routes[i] ?? emptyRoute(i);
                  return (
                    <tr key={i}>
                      <td>{i}</td>
                      {(
                        [
                          "enc_hub",
                          "enc_ch",
                          "enc_addr",
                          "act_hub",
                          "act_ch",
                          "act_addr",
                          "servo_ch",
                          "ina_hub",
                          "ina_ch",
                          "ina_addr",
                        ] as const
                      ).map((key) => (
                        <td key={key}>
                          <input
                            disabled={!canCmd}
                            defaultValue={fmtRouteField(key, r[key])}
                            key={`${i}-${key}-${r[key]}`}
                            onBlur={(e) => applyDraft(i, key, e.target.value)}
                          />
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="m5-foot-prof">
            <p className="m5__meta">右足スレーブ（ATOM S3 Lite / DF9-40）。SCAN で見えた 0x28 を選べます。addr=0 は無効。</p>
            <label className="m5-foot-prof__lab">
              経路
              <select
                disabled={!canCmd}
                value={fmtFootRoute(foot)}
                onChange={(e) => {
                  const parsed = parseFootOption(e.target.value);
                  if (parsed) setDraftFoot(parsed);
                }}
              >
                {(
                  profile?.foot_options?.includes(fmtFootRoute(foot))
                    ? profile.foot_options
                    : [...(profile?.foot_options ?? ["なし"]), fmtFootRoute(foot)]
                ).map((opt) => (
                  <option key={opt} value={opt}>
                    {opt}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </section>
      ) : null}

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

      {tab === "events" ? (
        <section className="m5__section">
          <p className="m5__meta">
            本記録（センサ＋指令）は上のバーから開始します。保存先は ATOM 接続 PC の{" "}
            <code>atom-rt/data/recordings</code>。ライブラリで再生すると、この画面の全タブが同時刻に連動します。
          </p>
          <pre className="m5__events">{events.join("\n") || "（イベントなし）"}</pre>
        </section>
      ) : null}
    </div>
  );
}

function Metric({
  title,
  text,
  color,
  large,
}: {
  title: string;
  text: string;
  color: string;
  large?: boolean;
}) {
  return (
    <div className={"m5__metric" + (large ? " m5__metric--large" : "")}>
      <span>{title}</span>
      <strong style={{ color }}>{text}</strong>
    </div>
  );
}

function magColor(code: number): string {
  if (code === 0) return "#10ac84";
  if (code === 1 || code === 4) return "#ee5253";
  if (code === 2 || code === 3) return "#feca57";
  return "#8b9bb0";
}

function TopoNode({
  item,
  depth,
  selected,
  onSelect,
}: {
  item: TopoItem;
  depth: number;
  selected: number | null;
  onSelect: (i: number) => void;
}) {
  const meta = kindMeta(item.kind);
  const on = item.srcIndex != null && selected === item.srcIndex;
  const isHub = item.kind === "pahub";
  return (
    <div className={"m5__branch" + (depth > 0 ? " m5__branch--child" : "")}>
      <button
        type="button"
        className={
          "m5__node m5__node--" +
          item.kind +
          (on ? " m5__node--on" : "") +
          (isHub ? " m5__node--hub" : "")
        }
        style={{ borderLeftColor: meta.color }}
        onClick={() => {
          if (item.srcIndex != null) onSelect(item.srcIndex);
        }}
      >
        <span className="m5__kind" style={{ background: meta.color }}>
          {meta.label}
        </span>
        <span className="m5__node-title">{item.title}</span>
        <span className="m5__node-detail">{item.detail}</span>
        {item.magLabel ? (
          <span className="m5__node-mag" style={{ color: magColor(item.magCode) }}>
            {item.magLabel}
          </span>
        ) : null}
        {isHub ? (
          <span className="m5__node-count">{item.children.length} ch</span>
        ) : null}
      </button>
      {item.children.length ? (
        <div className="m5__kids">
          {item.children.map((ch) => (
            <TopoNode
              key={`${ch.kind}-${ch.title}-${ch.srcIndex}`}
              item={ch}
              depth={depth + 1}
              selected={selected}
              onSelect={onSelect}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

function NumField({
  label,
  value,
  disabled,
  onCommit,
}: {
  label: string;
  value: number;
  disabled?: boolean;
  onCommit: (v: number) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [local, setLocal] = useState(String(value));
  return (
    <label className="m5__num">
      {label}
      <input
        type="number"
        disabled={disabled}
        value={editing ? local : String(value)}
        onFocus={() => {
          setEditing(true);
          setLocal(String(value));
        }}
        onChange={(e) => setLocal(e.target.value)}
        onBlur={() => {
          setEditing(false);
          const n = Number(local);
          if (Number.isFinite(n)) onCommit(n);
        }}
      />
    </label>
  );
}

function inaSelectValue(route: M5Route | undefined): string {
  if (!route || !route.ina_addr) return "なし";
  const addr = `0x${route.ina_addr.toString(16).toUpperCase().padStart(2, "0")}`;
  if (!route.ina_hub) return `root  ${addr}`;
  const hub = route.ina_hub.toString(16).toUpperCase().padStart(2, "0");
  return `${hub} CH${route.ina_ch}  ${addr}`;
}

function parseInaOption(label: string): { hub: number; ch: number; addr: number } | null {
  const s = label.trim();
  if (s === "なし" || s === "" || s === "—") return { hub: 0, ch: -1, addr: 0 };
  if (s.startsWith("root")) {
    const parts = s.split(/\s+/);
    const last = parts[parts.length - 1];
    if (!last) return null;
    const addr = parseInt(last, 16);
    if (!Number.isFinite(addr)) return null;
    return { hub: 0, ch: -1, addr };
  }
  const bits = s.replace(/CH/i, " ").replace(/\s+/g, " ").trim().split(" ");
  const hubStr = bits[0];
  const chStr = bits[1];
  const addrStr = bits[bits.length - 1];
  if (!hubStr || !chStr || !addrStr || bits.length < 3) return null;
  const hub = parseInt(hubStr, 16);
  const ch = Number(chStr);
  const addr = parseInt(addrStr, 16);
  if (![hub, ch, addr].every((n) => Number.isFinite(n))) return null;
  return { hub, ch, addr };
}
