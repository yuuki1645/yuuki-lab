/**
 * 関節プロファイル（AS5600 / サーボ / INA226 の経路）パネル。
 *
 * NVS の jprof に入るので、配線を変えてもファームの焼き直しは要らない。
 * 入力は下書きに溜め、「ボードへ送信」で初めて ATOM に渡す。
 */
import { useState } from "react";
import {
  emptyFoot,
  emptyRoute,
  fmtFootRoute,
  fmtRouteField,
  parseFootOption,
} from "./m5Route";
import { M5_JOINTS, type M5Cmd, type M5FootRoute, type M5Profile, type M5Route } from "./types";

const ROUTE_KEYS = [
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
] as const;

export function ProfilePanel({
  profile,
  canCmd,
  send,
}: {
  profile: M5Profile | null;
  canCmd: boolean;
  send: (cmd: M5Cmd) => void;
}) {
  const [draftRoutes, setDraftRoutes] = useState<M5Route[] | null>(null);
  const [draftFoot, setDraftFoot] = useState<M5FootRoute | null>(null);

  const routes = draftRoutes ?? profile?.routes ?? [];
  const foot = draftFoot ?? profile?.foot ?? emptyFoot();

  const applyDraft = (i: number, key: keyof M5Route, raw: string) => {
    const base = (
      draftRoutes ??
      profile?.routes ??
      Array.from({ length: M5_JOINTS }, (_, k) => emptyRoute(k))
    ).map((r) => ({ ...r }));
    while (base.length < M5_JOINTS) base.push(emptyRoute(base.length));
    const n = raw.trim().toLowerCase().startsWith("0x") ? parseInt(raw, 16) : Number(raw);
    if (!Number.isFinite(n)) return;
    const next: M5Route = { ...emptyRoute(i), ...base[i] };
    next[key] = n;
    base[i] = next;
    setDraftRoutes(base);
  };

  return (
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
        <button type="button" className="m5__btn" disabled={!canCmd} onClick={() => send({ op: "prof_from_scan" })}>
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
                  {ROUTE_KEYS.map((key) => (
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
        <p className="m5__meta">
          右足スレーブ（ATOM S3 Lite / DF9-40）。SCAN で見えた 0x28 を選べます。addr=0 は無効。
        </p>
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
            {(profile?.foot_options?.includes(fmtFootRoute(foot))
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
  );
}
