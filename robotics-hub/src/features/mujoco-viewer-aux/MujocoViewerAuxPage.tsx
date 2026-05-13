import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getMujocoViewerAuxUrl } from "@/shared/constants";
import type {
  ViewerAuxDetail,
  ViewerAuxDisplayState,
  ViewerAuxSnapshot,
  ViewerAuxStatus,
} from "@/shared/api/mujocoViewerAuxApi";
import {
  viewerAuxFetchDisplay,
  viewerAuxFetchHealth,
  viewerAuxFetchSnapshot,
  viewerAuxFetchStatus,
  viewerAuxPostControl,
  viewerAuxPostDisplay,
} from "@/shared/api/mujocoViewerAuxApi";
import "./MujocoViewerAuxPage.css";

const LS_BASE = "rh.mujocoViewerAuxUrl";

type TabId = "overview" | "bodies" | "joints" | "extra" | "display";

function fmt3(v: number[]): string {
  return v.map((x) => (Number.isFinite(x) ? x.toFixed(4) : "—")).join(", ");
}

export default function MujocoViewerAuxPage() {
  const [baseUrl, setBaseUrl] = useState(() => {
    if (typeof window !== "undefined") {
      const s = localStorage.getItem(LS_BASE);
      if (s && s.length > 0) return s.replace(/\/$/, "");
    }
    return getMujocoViewerAuxUrl();
  });
  const [pollMs, setPollMs] = useState(120);
  const [detail, setDetail] = useState<ViewerAuxDetail>("standard");
  const [connected, setConnected] = useState<boolean | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [snap, setSnap] = useState<ViewerAuxSnapshot | null>(null);
  const [status, setStatus] = useState<ViewerAuxStatus | null>(null);
  const [tab, setTab] = useState<TabId>("overview");
  const [display, setDisplay] = useState<ViewerAuxDisplayState | null>(null);
  const [flagFilter, setFlagFilter] = useState("");
  const [speedLocal, setSpeedLocal] = useState(1);
  const speedDebounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  const b = useMemo(() => baseUrl.replace(/\/$/, ""), [baseUrl]);

  const persistBase = () => {
    try {
      localStorage.setItem(LS_BASE, b);
    } catch {
      /* */
    }
  };

  const ping = useCallback(async () => {
    try {
      await viewerAuxFetchHealth(b);
      setConnected(true);
      setErr(null);
    } catch (e) {
      setConnected(false);
      setErr(e instanceof Error ? e.message : String(e));
    }
  }, [b]);

  const refreshDisplay = useCallback(async () => {
    try {
      const d = await viewerAuxFetchDisplay(b);
      setDisplay(d);
    } catch {
      /* optional */
    }
  }, [b]);

  const tick = useCallback(async () => {
    try {
      const [st, sn] = await Promise.all([
        viewerAuxFetchStatus(b),
        viewerAuxFetchSnapshot(detail, b),
      ]);
      setStatus(st);
      setSnap(sn);
      setSpeedLocal(st.speed);
      setConnected(true);
      setErr(null);
    } catch (e) {
      setConnected(false);
      setErr(e instanceof Error ? e.message : String(e));
    }
  }, [b, detail]);

  useEffect(() => {
    void ping();
  }, [ping]);

  useEffect(() => {
    const id = window.setInterval(() => {
      void tick();
    }, Math.max(40, pollMs));
    void tick();
    return () => window.clearInterval(id);
  }, [tick, pollMs]);

  useEffect(() => {
    if (tab === "display") void refreshDisplay();
  }, [tab, refreshDisplay, snap?.step_count]);

  const postCtl = async (action: Parameters<typeof viewerAuxPostControl>[0], value?: number) => {
    try {
      await viewerAuxPostControl(action, value !== undefined ? { value } : undefined, b);
      void tick();
      if (tab === "display") void refreshDisplay();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  };

  const debouncedSpeed = (v: number) => {
    if (speedDebounce.current) clearTimeout(speedDebounce.current);
    speedDebounce.current = setTimeout(() => {
      void viewerAuxPostControl("set_speed", { value: v }, b).catch((e) =>
        setErr(e instanceof Error ? e.message : String(e))
      );
    }, 200);
  };

  const onVisToggle = async (name: string, on: boolean) => {
    try {
      await viewerAuxPostDisplay({ vis_flag: { [name]: on } }, b);
      void refreshDisplay();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  };

  const filteredFlags = useMemo(() => {
    if (!display) return [];
    const q = flagFilter.trim().toLowerCase();
    if (!q) return display.vis_flags;
    return display.vis_flags.filter((f) => f.name.toLowerCase().includes(q));
  }, [display, flagFilter]);

  return (
    <div className="mjva">
      <h1 className="mjva__title">MuJoCo ビュワー補助</h1>
      <p className="mjva__intro">
        <code>mujoco_test_009.py</code> を起動すると MuJoCo のパッシブ viewer と同じシミュレーションに
        フックした補助 API（既定 <code>:8788</code>）が立ちます。このページから状態のモニタと再生制御、
        MuJoCo viewer の表示フラグを操作できます。
      </p>

      <div className="mjva__toolbar">
        <div className="mjva__field">
          <label htmlFor="mjva-base">接続先ベース URL</label>
          <input
            id="mjva-base"
            type="text"
            value={baseUrl}
            spellCheck={false}
            onChange={(e) => setBaseUrl(e.target.value.trim())}
            onBlur={persistBase}
          />
        </div>
        <div className="mjva__field mjva__field--narrow">
          <label htmlFor="mjva-poll">ポーリング ms</label>
          <input
            id="mjva-poll"
            type="number"
            min={40}
            step={10}
            value={pollMs}
            onChange={(e) => setPollMs(Math.max(40, Number(e.target.value) || 120))}
          />
        </div>
        <div className="mjva__field mjva__field--narrow">
          <label htmlFor="mjva-detail">スナップショット詳細度</label>
          <select
            id="mjva-detail"
            value={detail}
            onChange={(e) => setDetail(e.target.value as ViewerAuxDetail)}
          >
            <option value="minimal">minimal（軽量）</option>
            <option value="standard">standard</option>
            <option value="full">full（接触・geom 等）</option>
          </select>
        </div>
        <div className="mjva__btn-row">
          <span className={`mjva__pill ${connected ? "mjva__pill--ok" : "mjva__pill--err"}`}>
            {connected === null ? "未確認" : connected ? "接続中" : "未接続"}
          </span>
          <button type="button" className="mjva__btn mjva__btn--primary" onClick={() => void ping()}>
            接続テスト
          </button>
          <button type="button" className="mjva__btn" onClick={() => void tick()}>
            今すぐ更新
          </button>
        </div>
      </div>

      {err ? <p className="mjva__err">{err}</p> : null}

      <div className="mjva__btn-row">
        <button type="button" className="mjva__btn mjva__btn--primary" onClick={() => void postCtl("play")}>
          再生
        </button>
        <button type="button" className="mjva__btn" onClick={() => void postCtl("pause")}>
          一時停止
        </button>
        <button type="button" className="mjva__btn" onClick={() => void postCtl("stop")}>
          停止（= 一時停止）
        </button>
        <button type="button" className="mjva__btn" onClick={() => void postCtl("reset")}>
          リセット
        </button>
        <button type="button" className="mjva__btn mjva__btn--primary" onClick={() => void postCtl("restart")}>
          再スタート
        </button>
        <button type="button" className="mjva__btn" onClick={() => void postCtl("step_once")}>
          1 ステップ（停止中）
        </button>
        <label className="mjva__field" style={{ minWidth: 160, flex: "0 0 auto" }}>
          <span style={{ fontSize: "0.75rem", color: "#9aa4cc" }}>速度倍率</span>
          <input
            type="range"
            min={0.1}
            max={4}
            step={0.05}
            value={speedLocal}
            onChange={(e) => {
              const v = Number(e.target.value);
              setSpeedLocal(v);
              debouncedSpeed(v);
            }}
          />
          <span className="mjva__num">{speedLocal.toFixed(2)}×</span>
        </label>
      </div>

      <div className="mjva__tabs" role="tablist" aria-label="ビュワー補助タブ">
        {(
          [
            ["overview", "概要"],
            ["bodies", "剛体"],
            ["joints", "関節・速度"],
            ["extra", "接触・センサ"],
            ["display", "表示オプション"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            className={`mjva__tab ${tab === id ? "mjva__tab--active" : ""}`}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>

      <section className="mjva__panel" aria-live="polite">
        {tab === "overview" && (
          <>
            <h2>シミュレーション概要</h2>
            <div className="mjva__grid2">
              <div>
                <table>
                  <tbody>
                    <tr>
                      <th>XML</th>
                      <td className="mjva__num" style={{ whiteSpace: "normal", wordBreak: "break-all" }}>
                        {snap?.xml_path ?? "—"}
                      </td>
                    </tr>
                    <tr>
                      <th>シミュ時刻</th>
                      <td className="mjva__num">{snap !== null ? snap.sim_time.toFixed(5) : "—"}</td>
                    </tr>
                    <tr>
                      <th>タイムステップ</th>
                      <td className="mjva__num">{snap !== null ? snap.timestep.toExponential(3) : "—"}</td>
                    </tr>
                    <tr>
                      <th>ステップ数（ローカル）</th>
                      <td className="mjva__num">{snap !== null ? String(snap.step_count) : "—"}</td>
                    </tr>
                    <tr>
                      <th>速度倍率</th>
                      <td className="mjva__num">{snap !== null ? `${snap.speed.toFixed(2)}×` : "—"}</td>
                    </tr>
                    <tr>
                      <th>一時停止</th>
                      <td>{snap ? (snap.paused ? "はい" : "いいえ") : "—"}</td>
                    </tr>
                    <tr>
                      <th>viewer 接続（API）</th>
                      <td>{status ? (status.viewer_open ? "あり" : "なし") : "—"}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div>
                <h2 style={{ marginTop: 0 }}>ベクトル（先頭のみ抜粋）</h2>
                <p className="mjva__hint">完全な qpos / qvel は「関節」タブか JSON で確認してください。</p>
                <table>
                  <tbody>
                    <tr>
                      <th>qpos[0:6]</th>
                      <td className="mjva__num">
                        {snap ? fmt3(snap.qpos.slice(0, 6)) : "—"}
                      </td>
                    </tr>
                    <tr>
                      <th>qvel[0:6]</th>
                      <td className="mjva__num">
                        {snap ? fmt3(snap.qvel.slice(0, 6)) : "—"}
                      </td>
                    </tr>
                    <tr>
                      <th>ctrl 全列</th>
                      <td className="mjva__num">
                        {snap && snap.ctrl.length ? snap.ctrl.map((x) => x.toFixed(4)).join(", ") : "—"}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}

        {tab === "bodies" && (
          <>
            <h2>剛体（位置・姿勢・速度）</h2>
            {!snap?.bodies?.length ? (
              <p className="mjva__hint">詳細度を standard 以上にしてください。</p>
            ) : (
              <div className="mjva__table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>id</th>
                      <th>name</th>
                      <th>xpos</th>
                      <th>xquat (wxyz)</th>
                      <th>cvel (6)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {snap.bodies.map((row) => (
                      <tr key={row.id}>
                        <td className="mjva__num">{row.id}</td>
                        <td>{row.name}</td>
                        <td className="mjva__num">{fmt3(row.xpos)}</td>
                        <td className="mjva__num">{fmt3(row.xquat)}</td>
                        <td className="mjva__num">{fmt3(row.cvel)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}

        {tab === "joints" && (
          <>
            <h2>関節座標・速度・トルク</h2>
            {!snap?.joints?.length ? (
              <p className="mjva__hint">詳細度を standard 以上にしてください。</p>
            ) : (
              <div className="mjva__table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>name</th>
                      <th>type</th>
                      <th>qpos</th>
                      <th>qvel</th>
                    </tr>
                  </thead>
                  <tbody>
                    {snap.joints.map((row) => (
                      <tr key={row.id}>
                        <td>{row.name}</td>
                        <td>{row.type}</td>
                        <td className="mjva__num">{row.qpos.map((x) => x.toFixed(5)).join(", ")}</td>
                        <td className="mjva__num">{row.qvel.map((x) => x.toFixed(5)).join(", ")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {snap?.qfrc_actuator && snap.qfrc_actuator.length > 0 ? (
              <>
                <h2>qfrc_actuator（nv）</h2>
                <div className="mjva__table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>index</th>
                        <th>値</th>
                      </tr>
                    </thead>
                    <tbody>
                      {snap.qfrc_actuator.map((v, i) => (
                        <tr key={i}>
                          <td className="mjva__num">{i}</td>
                          <td className="mjva__num">{v.toExponential(4)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : null}
          </>
        )}

        {tab === "extra" && (
          <>
            <h2>接触・ジオメトリ・センサ</h2>
            {detail !== "full" ? (
              <p className="mjva__hint">接触・geom・サイト・センサの表は詳細度「full」のときのみ配信されます。</p>
            ) : null}
            {snap?.contacts && snap.contacts.length > 0 ? (
              <>
                <h3>接触</h3>
                <div className="mjva__table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>geom1</th>
                        <th>geom2</th>
                        <th>dist</th>
                        <th>pos</th>
                      </tr>
                    </thead>
                    <tbody>
                      {snap.contacts.map((c, i) => (
                        <tr key={i}>
                          <td>
                            {c.geom1_name} ({c.geom1})
                          </td>
                          <td>
                            {c.geom2_name} ({c.geom2})
                          </td>
                          <td className="mjva__num">{c.dist.toExponential(3)}</td>
                          <td className="mjva__num">{fmt3(c.pos)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : detail === "full" ? (
              <p className="mjva__hint">接触なし（ncon=0）</p>
            ) : null}

            {snap?.sensors && Object.keys(snap.sensors).length > 0 ? (
              <>
                <h3>センサ</h3>
                <div className="mjva__table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>name</th>
                        <th>values</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(snap.sensors).map(([name, vals]) => (
                        <tr key={name}>
                          <td>{name}</td>
                          <td className="mjva__num">{vals.map((x) => x.toFixed(6)).join(", ")}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : null}

            {snap?.geoms && snap.geoms.length > 0 ? (
              <>
                <h3>ジオメトリ</h3>
                <div className="mjva__table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>name</th>
                        <th>body</th>
                        <th>xpos</th>
                      </tr>
                    </thead>
                    <tbody>
                      {snap.geoms.map((g) => (
                        <tr key={g.id}>
                          <td>{g.name}</td>
                          <td className="mjva__num">{g.body}</td>
                          <td className="mjva__num">{fmt3(g.xpos)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : null}
          </>
        )}

        {tab === "display" && (
          <>
            <h2>MuJoCo viewer の表示</h2>
            {!display ? (
              <p className="mjva__hint">読み込み中… viewer が未起動のときはフラグが既定値のままです。</p>
            ) : (
              <>
                <div className="mjva__select-row">
                  <label>
                    座標フレーム（mjtFrame）
                    <select
                      value={display.frame_name}
                      onChange={async (e) => {
                        const frame = e.target.value;
                        try {
                          await viewerAuxPostDisplay({ frame }, b);
                          void refreshDisplay();
                        } catch (ex) {
                          setErr(ex instanceof Error ? ex.message : String(ex));
                        }
                      }}
                    >
                      {display.frame_choices.map((n) => (
                        <option key={n} value={n}>
                          {n}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    ラベル（mjtLabel）
                    <select
                      value={display.label_name}
                      onChange={async (e) => {
                        const label = e.target.value;
                        try {
                          await viewerAuxPostDisplay({ label }, b);
                          void refreshDisplay();
                        } catch (ex) {
                          setErr(ex instanceof Error ? ex.message : String(ex));
                        }
                      }}
                    >
                      {display.label_choices.map((n) => (
                        <option key={n} value={n}>
                          {n}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button type="button" className="mjva__btn" onClick={() => void refreshDisplay()}>
                    表示状態を再取得
                  </button>
                </div>

                <input
                  type="search"
                  className="mjva__search"
                  placeholder="表示フラグを絞り込み（例: CONTACT）"
                  value={flagFilter}
                  onChange={(e) => setFlagFilter(e.target.value)}
                />
                <div className="mjva__flag-grid">
                  {filteredFlags.map((f) => (
                    <label key={f.name} className="mjva__flag">
                      <input
                        type="checkbox"
                        checked={f.on !== 0}
                        onChange={(e) => void onVisToggle(f.name, e.target.checked)}
                      />
                      <span title={`index ${f.index}`}>{f.name}</span>
                    </label>
                  ))}
                </div>
              </>
            )}
          </>
        )}
      </section>
    </div>
  );
}
