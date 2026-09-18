/**
 * 関節プロファイル（経路）の既定値と文字列変換。
 *
 * 実機テレメトリと机上ラボの両方から使う。表記は lab_debug.py の
 * コンボボックス（"71 CH0  0x41" / "root  0x41" / "なし"）と揃える。
 */
import { M5_INA_DEFAULT_ASSIGNED, type M5FootRoute, type M5Route } from "./types";

/** 論理軸 i の既定経路。0〜5 は PaHub 0x70 の AS5600、INA は先頭 2 軸だけ */
export function emptyRoute(i: number): M5Route {
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
    enabled: true,
  };
}

/** 右足スレーブ（ATOM S3 Lite / DF9-40）の既定経路 */
export function emptyFoot(): M5FootRoute {
  return { hub: 0x71, ch: 2, addr: 0x28, enabled: true };
}

export function fmtFootRoute(r: M5FootRoute): string {
  if (!r.addr) return "なし";
  if (!r.hub) return `root  0x${r.addr.toString(16).toUpperCase().padStart(2, "0")}`;
  const hub = r.hub.toString(16).toUpperCase().padStart(2, "0");
  return `${hub} CH${r.ch}  0x${r.addr.toString(16).toUpperCase().padStart(2, "0")}`;
}

export function parseFootOption(text: string): M5FootRoute | null {
  const s = text.trim();
  if (s === "なし" || s === "" || s === "—") return { hub: 0, ch: -1, addr: 0, enabled: true };
  if (s.startsWith("root")) {
    const parts = s.split(/\s+/);
    const addr = Number.parseInt(parts[parts.length - 1] ?? "", 16);
    if (!Number.isFinite(addr)) return null;
    return { hub: 0, ch: -1, addr, enabled: true };
  }
  const bits = s.replace(/CH/i, " ").replace(/\s+/g, " ").trim().split(" ");
  const hub = Number.parseInt(bits[0] ?? "", 16);
  const ch = Number.parseInt(bits[1] ?? "", 10);
  const addr = Number.parseInt(bits[bits.length - 1] ?? "", 16);
  if (![hub, ch, addr].every(Number.isFinite)) return null;
  return { hub, ch, addr, enabled: true };
}

/** 経路テーブルの 1 セル。ch は 10 進、hub / addr は 16 進で見せる */
export function fmtRouteField(key: Exclude<keyof M5Route, "enabled">, n: number): string {
  if (key.endsWith("ch") || key === "servo_ch") return String(n);
  if (key.endsWith("hub") && n === 0) return "0";
  return `0x${n.toString(16).toUpperCase().padStart(2, "0")}`;
}

/** INA226 セレクトの表示値。未割当は「なし」 */
export function inaSelectValue(route: M5Route | undefined): string {
  if (!route || !route.ina_addr) return "なし";
  const addr = `0x${route.ina_addr.toString(16).toUpperCase().padStart(2, "0")}`;
  if (!route.ina_hub) return `root  ${addr}`;
  const hub = route.ina_hub.toString(16).toUpperCase().padStart(2, "0");
  return `${hub} CH${route.ina_ch}  ${addr}`;
}

export function parseInaOption(label: string): { hub: number; ch: number; addr: number } | null {
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
