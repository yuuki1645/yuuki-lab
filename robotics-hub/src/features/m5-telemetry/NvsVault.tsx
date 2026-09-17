/**
 * ATOM フラッシュ NVS の保管庫。実キーは USB nvs_list、意味は既知の名前空間で補う。
 */
import { useMemo } from "react";
import type { M5Cmd, M5Nvs, M5NvsEntry, M5Profile } from "./types";
import { M5_JOINTS } from "./types";
import "./NvsVault.css";

const NVS_TYPE: Record<number, string> = {
  0x01: "u8",
  0x11: "i8",
  0x02: "u16",
  0x12: "i16",
  0x04: "u32",
  0x14: "i32",
  0x08: "u64",
  0x18: "i64",
  0x21: "str",
  0x42: "blob",
};

type ExpectKey = { ns: string; key: string; hint: string };

function expectedKeys(): ExpectKey[] {
  const out: ExpectKey[] = [
    { ns: "jprof", key: "n", hint: "関節数" },
    { ns: "jprof", key: "r", hint: "JointRoute × 8（80 B）" },
    { ns: "jprof", key: "foot", hint: "FootRoute（3 B）" },
  ];
  for (let i = 0; i < M5_JOINTS; i += 1) {
    out.push({ ns: "cal", key: `mk${i}`, hint: `軸${i} マップ有効` });
    out.push({ ns: "cal", key: `mn${i}`, hint: `軸${i} 点数` });
    out.push({ ns: "cal", key: `mx${i}`, hint: `軸${i} unwrap` });
    out.push({ ns: "cal", key: `my${i}`, hint: `軸${i} 指令角` });
    out.push({ ns: "cal", key: `ok${i}`, hint: `軸${i} 旧フラグ` });
  }
  return out;
}

function typeLabel(t: number): string {
  return NVS_TYPE[t] ?? `0x${t.toString(16)}`;
}

function fmtRoute(r: M5Profile["routes"][number] | undefined): string {
  if (!r) return "—";
  const enc = r.enc_addr
    ? `${r.enc_hub ? r.enc_hub.toString(16) : "root"}/${r.enc_ch} @${r.enc_addr.toString(16)}`
    : "encなし";
  const ina = r.ina_addr ? ` ina ${r.ina_addr.toString(16)}` : "";
  return `servo ${r.servo_ch} · ${enc}${ina}`;
}

function hintFor(ns: string, key: string): string {
  return expectedKeys().find((e) => e.ns === ns && e.key === key)?.hint ?? "未知のキー";
}

export function NvsVault({
  nvs,
  profile,
  mapOk,
  canCmd,
  send,
}: {
  nvs: M5Nvs | null;
  profile: M5Profile | null;
  mapOk: boolean[];
  canCmd: boolean;
  send: (cmd: M5Cmd) => void;
}) {
  const entries = nvs?.entries ?? [];
  const byNs = useMemo(() => {
    const m = new Map<string, M5NvsEntry[]>();
    for (const e of entries) {
      const list = m.get(e.ns) ?? [];
      list.push(e);
      m.set(e.ns, list);
    }
    return m;
  }, [entries]);

  const vaults = ["jprof", "cal", ...[...byNs.keys()].filter((k) => k !== "jprof" && k !== "cal")];
  const used = nvs?.bytes ?? 0;
  const nKeys = entries.length;

  const decode = (e: M5NvsEntry): string => {
    if (e.ns === "jprof" && e.key === "n") return `${profile?.routes.length ?? "—"} 軸`;
    if (e.ns === "jprof" && e.key === "r") {
      const filled = (profile?.routes ?? []).filter((r) => r.enc_addr || r.ina_addr).length;
      return `経路 ${filled}/${M5_JOINTS} 割当`;
    }
    if (e.ns === "jprof" && e.key === "foot") {
      const f = profile?.foot;
      if (!f?.addr) return "右足なし";
      return `0x${f.hub.toString(16)} CH${f.ch} / 0x${f.addr.toString(16)}`;
    }
    const m = /^(mk|mn|mx|my|ok)(\d)$/.exec(e.key);
    if (e.ns === "cal" && m) {
      const i = Number(m[2]);
      const live = mapOk[i] ? "RAM 有効" : "RAM 空";
      if (e.key.startsWith("mk") || e.key.startsWith("ok")) return live;
      if (e.key.startsWith("mn")) return `${e.size >= 4 ? "点数キー" : live}`;
      return `${e.size} B · ${live}`;
    }
    return hintFor(e.ns, e.key);
  };

  const missing = (ns: string) =>
    expectedKeys().filter((k) => k.ns === ns && !entries.some((e) => e.ns === k.ns && e.key === k.key));

  return (
    <section className="nvs">
      <div className="nvs__chip">
        <div className="nvs__chip-meta">
          <span className="nvs__chip-mark">NVS</span>
          <div>
            <strong>0x9000</strong>
            <span>プログラム区画とは別。upload しても通常は残る。</span>
          </div>
        </div>
        <div className="nvs__chip-bar" aria-hidden="true">
          <i style={{ width: `${Math.min(100, 8 + used / 40)}%` }} />
        </div>
        <div className="nvs__chip-stats">
          <span>{nvs?.ok ? `${nKeys} キー` : "未読取"}</span>
          <span>{used} B</span>
        </div>
      </div>

      <div className="nvs__toolbar">
        <button type="button" className="m5__btn" disabled={!canCmd} onClick={() => send({ op: "nvs_list" })}>
          ボードから読む
        </button>
        <button
          type="button"
          className="m5__btn"
          disabled={!canCmd}
          onClick={() => send({ op: "prof_default" })}
        >
          経路を既定に戻す
        </button>
        <button
          type="button"
          className="m5__btn m5__btn--danger"
          disabled={!canCmd}
          onClick={() => {
            if (window.confirm("校正マップ（NVS cal）を全部消します。サーボは動きません。よろしいですか？")) {
              send({ op: "nvs_erase", ns: "cal" });
            }
          }}
        >
          校正を消す
        </button>
        <button
          type="button"
          className="m5__btn"
          disabled={!canCmd}
          onClick={() => {
            if (window.confirm("関節経路（NVS jprof）を消し、既定配線を書き込みます。よろしいですか？")) {
              send({ op: "nvs_erase", ns: "jprof" });
            }
          }}
        >
          経路を消して既定
        </button>
      </div>

      {!nvs?.ok ? (
        <p className="nvs__hint">
          「ボードから読む」で実キーを列挙します。新しいファーム（NVS 一覧コマンド）が必要です。
        </p>
      ) : null}

      <div className="nvs__vaults">
        {vaults.map((ns) => {
          const keys = byNs.get(ns) ?? [];
          const ghost = missing(ns);
          const bytes = keys.reduce((a, e) => a + e.size, 0);
          return (
            <article key={ns} className={"nvs__vault nvs__vault--" + ns}>
              <header>
                <h3>{ns}</h3>
                <span>
                  {keys.length} キー · {bytes} B
                </span>
              </header>
              <ul>
                {keys.map((e) => (
                  <li key={e.ns + "/" + e.key} className="nvs__row">
                    <span className="nvs__key">{e.key}</span>
                    <span className="nvs__type">{typeLabel(e.type)}</span>
                    <span className="nvs__size">{e.size} B</span>
                    <span className="nvs__bar">
                      <i style={{ width: `${Math.min(100, (e.size / 800) * 100)}%` }} />
                    </span>
                    <span className="nvs__hint-line">{decode(e)}</span>
                  </li>
                ))}
                {ghost.map((g) => (
                  <li key={"miss-" + g.key} className="nvs__row nvs__row--ghost">
                    <span className="nvs__key">{g.key}</span>
                    <span className="nvs__type">空</span>
                    <span className="nvs__size">—</span>
                    <span className="nvs__bar" />
                    <span className="nvs__hint-line">{g.hint}</span>
                  </li>
                ))}
              </ul>
              {ns === "jprof" && profile ? (
                <div className="nvs__decode">
                  {profile.routes.map((r, i) => (
                    <p key={i}>
                      J{i} {fmtRoute(r)}
                    </p>
                  ))}
                </div>
              ) : null}
            </article>
          );
        })}
      </div>
    </section>
  );
}
