/**
 * 関節プロファイル（AS5600 / サーボ / INA226 の経路）パネル。
 *
 * NVS の jprof に入るので、配線を変えてもファームの焼き直しは要らない。
 * 入力は下書きに溜め、「ボードへ送信」で初めて ATOM に渡す。
 *
 * 有効チェックは経路と独立。機体のアドレスはそのまま残し、無効軸は
 * 20 Hz の I2C と PWM から外す（机上で未配線の軸を切る用）。
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

function isOn(r: { enabled?: boolean } | undefined): boolean {
  return r?.enabled !== false;
}

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

  // 下書きは「ボードから取得 / 既定 / SCAN」以外では捨てない。
  // 送信エコーが古い全オンのまま来ても、チェックが勝手に戻らないようにする。

  const baseRoutes = (): M5Route[] => {
    const base = (
      draftRoutes ??
      profile?.routes ??
      Array.from({ length: M5_JOINTS }, (_, k) => emptyRoute(k))
    ).map((r) => ({ ...r }));
    while (base.length < M5_JOINTS) base.push(emptyRoute(base.length));
    return base;
  };

  const applyDraft = (i: number, key: (typeof ROUTE_KEYS)[number], raw: string) => {
    const base = baseRoutes();
    const n = raw.trim().toLowerCase().startsWith("0x") ? parseInt(raw, 16) : Number(raw);
    if (!Number.isFinite(n)) return;
    const next: M5Route = { ...emptyRoute(i), ...base[i] };
    next[key] = n;
    base[i] = next;
    setDraftRoutes(base);
  };

  const setJointEnabled = (i: number, on: boolean) => {
    const base = baseRoutes();
    base[i] = { ...emptyRoute(i), ...base[i], enabled: on };
    setDraftRoutes(base);
  };

  return (
    <section className="m5__section">
      <div className="m5__toolbar">
        <button
          type="button"
          className="m5__btn"
          disabled={!canCmd}
          onClick={() => {
            setDraftRoutes(null);
            setDraftFoot(null);
            send({ op: "prof_get" });
          }}
        >
          ボードから取得
        </button>
        <button
          type="button"
          className="m5__btn m5__btn--on"
          disabled={!canCmd}
          onClick={() => {
            send({
              op: "prof_put",
              routes: Array.from({ length: M5_JOINTS }, (_, i) => routes[i] ?? emptyRoute(i)),
              foot,
            });
          }}
        >
          ボードへ送信
        </button>
        <button
          type="button"
          className="m5__btn"
          disabled={!canCmd}
          onClick={() => {
            setDraftRoutes(null);
            setDraftFoot(null);
            send({ op: "prof_default" });
          }}
        >
          既定に戻す
        </button>
        <button
          type="button"
          className="m5__btn"
          disabled={!canCmd}
          onClick={() => {
            setDraftRoutes(null);
            setDraftFoot(null);
            send({ op: "prof_from_scan" });
          }}
        >
          SCANから仮割当
        </button>
      </div>
      <p className="m5__meta">
        経路は機体構成のまま残せます。左の「有効」を外すとその軸の AS5600 / INA / PWM
        を読まなくなります。机上では使わない軸を切ってください。送信するまでボードには入りません。
      </p>
      <div className="m5__table-wrap">
        <table className="m5__table">
          <thead>
            <tr>
              <th>有効</th>
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
              const on = isOn(r);
              return (
                <tr key={i} className={on ? "" : "m5__table-row--off"}>
                  <td>
                    <label className="m5-en">
                      <input
                        type="checkbox"
                        disabled={!canCmd}
                        checked={on}
                        onChange={(e) => setJointEnabled(i, e.target.checked)}
                        aria-label={`関節 ${i} を有効`}
                      />
                    </label>
                  </td>
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
      <div className={"m5-foot-prof" + (isOn(foot) ? "" : " m5-foot-prof--off")}>
        <label className="m5-en">
          <input
            type="checkbox"
            disabled={!canCmd}
            checked={isOn(foot)}
            onChange={(e) => {
              const cur = draftFoot ?? profile?.foot ?? emptyFoot();
              setDraftFoot({ ...cur, enabled: e.target.checked });
            }}
            aria-label="右足スレーブを有効"
          />
          有効
        </label>
        <p className="m5__meta">
          右足スレーブ（ATOM S3 Lite / DF9-40）。経路は残したまま、無効にすると 20 Hz の読みを止めます。
        </p>
        <label className="m5-foot-prof__lab">
          経路
          <select
            disabled={!canCmd}
            value={fmtFootRoute(foot)}
            onChange={(e) => {
              const parsed = parseFootOption(e.target.value);
              if (parsed) setDraftFoot({ ...parsed, enabled: isOn(foot) });
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
