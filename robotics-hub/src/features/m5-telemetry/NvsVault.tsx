/**
 * ATOM フラッシュ NVS の保管庫。キーだけでなく実バイトを解読して見せる。
 */
import { useEffect, useMemo, useState } from "react";
import type { M5Cmd, M5Nvs, M5NvsEntry } from "./types";
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
    { ns: "jprof", key: "r", hint: "JointRoute × 8" },
    { ns: "jprof", key: "foot", hint: "FootRoute" },
    { ns: "jprof", key: "jen", hint: "関節有効マスク" },
    { ns: "jprof", key: "fen", hint: "足スレーブ有効" },
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

function hexToBytes(hex: string): Uint8Array {
  const h = hex.replace(/[^0-9a-fA-F]/g, "");
  const n = Math.floor(h.length / 2);
  const out = new Uint8Array(n);
  for (let i = 0; i < n; i += 1) {
    out[i] = Number.parseInt(h.slice(i * 2, i * 2 + 2), 16);
  }
  return out;
}

function viewOf(b: Uint8Array): DataView {
  return new DataView(b.buffer, b.byteOffset, b.byteLength);
}

function cString(b: Uint8Array): string {
  const z = b.indexOf(0);
  const slice = z >= 0 ? b.subarray(0, z) : b;
  return new TextDecoder("utf-8", { fatal: false }).decode(slice);
}

function hexDump(b: Uint8Array, max = 64, cols = 16): string {
  const n = Math.min(b.length, max);
  const lines: string[] = [];
  for (let i = 0; i < n; i += cols) {
    const end = Math.min(i + cols, n);
    const parts: string[] = [];
    for (let j = i; j < end; j += 1) {
      parts.push(b[j]!.toString(16).padStart(2, "0"));
    }
    lines.push(parts.join(" "));
  }
  if (b.length > max) {
    lines.push("…");
  }
  return lines.join("\n");
}

/** サイズが大きく、一覧に載せると溢れる値。 */
function isLongEntry(e: M5NvsEntry): boolean {
  return e.size > 24 || e.key.startsWith("mx") || e.key.startsWith("my") || e.key === "r";
}

function floatsLe(b: Uint8Array): number[] {
  const n = Math.floor(b.length / 4);
  const v = viewOf(b);
  const out: number[] = [];
  for (let i = 0; i < n; i += 1) {
    out.push(v.getFloat32(i * 4, true));
  }
  return out;
}

function intByType(e: M5NvsEntry, b: Uint8Array): string | null {
  const v = viewOf(b);
  try {
    if (e.type === 0x01 && b.length >= 1) return String(v.getUint8(0));
    if (e.type === 0x11 && b.length >= 1) return String(v.getInt8(0));
    if (e.type === 0x02 && b.length >= 2) return String(v.getUint16(0, true));
    if (e.type === 0x12 && b.length >= 2) return String(v.getInt16(0, true));
    if (e.type === 0x04 && b.length >= 4) return String(v.getUint32(0, true));
    if (e.type === 0x14 && b.length >= 4) return String(v.getInt32(0, true));
    if ((e.type === 0x08 || e.type === 0x18) && b.length >= 8) {
      return String(v.getBigUint64(0, true));
    }
  } catch {
    return null;
  }
  return null;
}

function fmtRouteBytes(b: Uint8Array, i: number): string {
  const o = i * 10;
  if (o + 10 > b.length) return `J${i} （短い）`;
  const v = viewOf(b.subarray(o, o + 10));
  const encHub = v.getUint8(0);
  const encCh = v.getInt8(1);
  const encAddr = v.getUint8(2);
  const actHub = v.getUint8(3);
  const actCh = v.getInt8(4);
  const actAddr = v.getUint8(5);
  const servo = v.getUint8(6);
  const inaHub = v.getUint8(7);
  const inaCh = v.getInt8(8);
  const inaAddr = v.getUint8(9);
  const enc = encAddr
    ? `enc ${encHub ? "0x" + encHub.toString(16) : "root"} CH${encCh} 0x${encAddr.toString(16)}`
    : "encなし";
  const ina = inaAddr ? ` ina 0x${inaHub.toString(16)} CH${inaCh}` : "";
  return `J${i}  servo ${servo} @ 0x${actAddr.toString(16)}${actHub ? " hub" : ""} CH${actCh} · ${enc}${ina}`;
}

function formatValue(e: M5NvsEntry): { summary: string; full: string } {
  const hex = e.data_hex ?? "";
  if (!hex) {
    return { summary: "値未受信（ファーム焼き直し）", full: "" };
  }
  const b = hexToBytes(hex);
  const hexAll = hexDump(b, b.length);
  const asInt = intByType(e, b);
  if (asInt != null) {
    if ((e.key.startsWith("mk") || e.key.startsWith("ok")) && e.ns === "cal") {
      return { summary: Number(asInt) ? "有効" : "無効", full: `生値 ${asInt}\n${hexAll}` };
    }
    return { summary: asInt, full: `hex\n${hexAll}` };
  }
  if (e.type === 0x21) {
    const s = cString(b);
    return { summary: s || "(空)", full: `${s}\n\n${hexAll}` };
  }
  if (e.ns === "jprof" && e.key === "r") {
    const lines = Array.from({ length: M5_JOINTS }, (_, i) => fmtRouteBytes(b, i));
    return { summary: `${Math.floor(b.length / 10)} 軸の経路`, full: `${lines.join("\n")}\n\n${hexAll}` };
  }
  if (e.ns === "jprof" && e.key === "foot" && b.length >= 3) {
    const hub = b[0]!;
    const ch = new DataView(b.buffer, b.byteOffset, b.byteLength).getInt8(1);
    const addr = b[2]!;
    const s = addr ? `0x${hub.toString(16)} CH${ch} / 0x${addr.toString(16)}` : "なし";
    return { summary: s, full: `${s}\n${hexAll}` };
  }
  if (e.ns === "cal" && (e.key.startsWith("mx") || e.key.startsWith("my"))) {
    const xs = floatsLe(b);
    if (!xs.length) return { summary: "空", full: "" };
    const lo = Math.min(...xs);
    const hi = Math.max(...xs);
    const numbered = xs.map((x, i) => `${String(i).padStart(3, " ")}  ${x.toFixed(4)}`).join("\n");
    return {
      summary: `${xs.length} 点  ${lo.toFixed(1)} … ${hi.toFixed(1)}`,
      full: `${numbered}\n\n${hexAll}`,
    };
  }
  if (e.ns === "phy" && e.key === "cal_mac" && b.length >= 6) {
    const mac = Array.from(b.subarray(0, 6))
      .map((x) => x.toString(16).padStart(2, "0"))
      .join(":");
    return { summary: mac, full: `${mac}\n${hexAll}` };
  }
  const text = cString(b);
  if (text.length >= 2 && /^[\x20-\x7e]+$/.test(text)) {
    return { summary: text, full: `${text}\n\n${hexAll}` };
  }
  return { summary: `${b.length} B`, full: hexAll };
}

export function NvsVault({
  nvs,
  canCmd,
  send,
}: {
  nvs: M5Nvs | null;
  canCmd: boolean;
  send: (cmd: M5Cmd) => void;
}) {
  const entries = nvs?.entries ?? [];
  // 既定はキー一覧のみ。値はスイッチで出す。
  const [showValues, setShowValues] = useState(false);
  const [popup, setPopup] = useState<M5NvsEntry | null>(null);
  const byNs = useMemo(() => {
    const m = new Map<string, M5NvsEntry[]>();
    for (const e of entries) {
      const list = m.get(e.ns) ?? [];
      list.push(e);
      m.set(e.ns, list);
    }
    return m;
  }, [entries]);

  useEffect(() => {
    if (!popup) {
      return;
    }
    const onKey = (ev: KeyboardEvent) => {
      if (ev.key === "Escape") {
        setPopup(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [popup]);

  const vaults = ["jprof", "cal", ...[...byNs.keys()].filter((k) => k !== "jprof" && k !== "cal")];
  const used = nvs?.bytes ?? 0;
  const nKeys = entries.length;

  const missing = (ns: string) =>
    expectedKeys().filter((k) => k.ns === ns && !entries.some((e) => e.ns === k.ns && e.key === k.key));

  return (
    <section className="nvs">
      <div className="nvs__chip">
        <div className="nvs__chip-meta">
          <span className="nvs__chip-mark">NVS</span>
          <div>
            <strong>0x9000</strong>
            <span>プログラム区画とは別。値は既定で隠し、長いデータはポップアップで全部見られます。</span>
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
        <button
          type="button"
          className={"m5__btn" + (showValues ? " m5__btn--on" : "")}
          onClick={() => setShowValues((v) => !v)}
        >
          {showValues ? "値を隠す" : "値を表示"}
        </button>
        <button type="button" className="m5__btn" disabled={!canCmd} onClick={() => send({ op: "nvs_list" })}>
          ボードから読む
        </button>
        <button type="button" className="m5__btn" disabled={!canCmd} onClick={() => send({ op: "prof_default" })}>
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
        <p className="nvs__hint">「ボードから読む」で実キーと値を取ります。値表示には新しいファームが必要です。</p>
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
                {keys.map((e) => {
                  const id = e.ns + "/" + e.key;
                  const shown = formatValue(e);
                  const long = isLongEntry(e);
                  return (
                    <li key={id} className="nvs__row">
                      <div className="nvs__row-btn">
                        <span className="nvs__key" title={e.key}>
                          {e.key}
                        </span>
                        <span className="nvs__type">{typeLabel(e.type)}</span>
                        <span className="nvs__size">{e.size} B</span>
                        <span className="nvs__bar">
                          <i style={{ width: `${Math.min(100, (e.size / 800) * 100)}%` }} />
                        </span>
                        {showValues ? <span className="nvs__hint-line">{shown.summary}</span> : null}
                        {showValues && long && shown.full ? (
                          <button
                            type="button"
                            className="nvs__full-btn"
                            onClick={() => setPopup(e)}
                          >
                            全部見る
                          </button>
                        ) : null}
                      </div>
                    </li>
                  );
                })}
                {ghost.map((g) => (
                  <li key={"miss-" + g.key} className="nvs__row nvs__row--ghost">
                    <span className="nvs__key" title={g.key}>
                      {g.key}
                    </span>
                    <span className="nvs__type">空</span>
                    <span className="nvs__size">—</span>
                    <span className="nvs__bar" />
                    <span className="nvs__hint-line">{g.hint}</span>
                  </li>
                ))}
              </ul>
            </article>
          );
        })}
      </div>

      {popup ? (
        <div className="nvs-pop" role="dialog" aria-modal="true" aria-labelledby="nvs-pop-title">
          <button type="button" className="nvs-pop__veil" aria-label="閉じる" onClick={() => setPopup(null)} />
          <div className="nvs-pop__sheet">
            <header className="nvs-pop__top">
              <div>
                <p className="nvs-pop__ns">{popup.ns}</p>
                <h2 id="nvs-pop-title">{popup.key}</h2>
                <p className="nvs-pop__meta">
                  {typeLabel(popup.type)} · {popup.size} B
                </p>
              </div>
              <button type="button" className="m5__btn" onClick={() => setPopup(null)}>
                閉じる
              </button>
            </header>
            <pre className="nvs-pop__body">{formatValue(popup).full || "（値なし）"}</pre>
          </div>
        </div>
      ) : null}
    </section>
  );
}
