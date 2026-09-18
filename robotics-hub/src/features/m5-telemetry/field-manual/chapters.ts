/**
 * ATOM 現場手帳の目次。本文は atom-rt/docs/field-manual が正本。
 * Hub は Vite の ?raw で文字列として取り込む（実行時にネットへ取りに行かない）。
 */
import mapMd from "../../../../../atom-rt/docs/field-manual/00-map.md?raw";
import boardsMd from "../../../../../atom-rt/docs/field-manual/01-boards.md?raw";
import firmwareMd from "../../../../../atom-rt/docs/field-manual/02-firmware.md?raw";
import usbMd from "../../../../../atom-rt/docs/field-manual/03-usb.md?raw";
import toolsMd from "../../../../../atom-rt/docs/field-manual/04-tools.md?raw";
import nvsMd from "../../../../../atom-rt/docs/field-manual/05-nvs.md?raw";
import layersMd from "../../../../../atom-rt/docs/field-manual/06-layers.md?raw";
import notesMd from "../../../../../atom-rt/docs/field-manual/07-notes.md?raw";
import type { ManualDiagramId } from "./Diagrams";

export interface ManualChapter {
  id: string;
  index: string;
  title: string;
  kicker: string;
  markdown: string;
  diagram: ManualDiagramId;
}

export const FIELD_MANUAL_CHAPTERS: ManualChapter[] = [
  {
    id: "map",
    index: "00",
    title: "地図",
    kicker: "何が何を握るか",
    markdown: mapMd,
    diagram: "stack",
  },
  {
    id: "boards",
    index: "01",
    title: "基板",
    kicker: "Lite / S3R / フラッシュ",
    markdown: boardsMd,
    diagram: "flash",
  },
  {
    id: "firmware",
    index: "02",
    title: "ファーム",
    kicker: "20 Hz とマスク",
    markdown: firmwareMd,
    diagram: "cores",
  },
  {
    id: "usb",
    index: "03",
    title: "USB",
    kicker: "ver=14 バイナリ",
    markdown: usbMd,
    diagram: "usb",
  },
  {
    id: "tools",
    index: "04",
    title: "道具",
    kicker: "PC と Hub",
    markdown: toolsMd,
    diagram: "stack",
  },
  {
    id: "nvs",
    index: "05",
    title: "有効と NVS",
    kicker: "経路は残す",
    markdown: nvsMd,
    diagram: "flash",
  },
  {
    id: "layers",
    index: "06",
    title: "層",
    kicker: "CDC とキャッシュ",
    markdown: layersMd,
    diagram: "layers",
  },
  {
    id: "notes",
    index: "07",
    title: "現場メモ",
    kicker: "ログの読み方",
    markdown: notesMd,
    diagram: "pipe",
  },
];

export const MANUAL_HASH_PREFIX = "#manual";

/** `#manual` または `#manual/usb` から章 id を取る。手帳でなければ null。 */
export function chapterIdFromHash(hash: string): string | null {
  if (hash === MANUAL_HASH_PREFIX || hash === MANUAL_HASH_PREFIX + "/") {
    return "map";
  }
  if (!hash.startsWith(MANUAL_HASH_PREFIX + "/")) {
    return null;
  }
  const id = hash.slice(MANUAL_HASH_PREFIX.length + 1).split("?")[0] ?? "";
  return FIELD_MANUAL_CHAPTERS.some((c) => c.id === id) ? id : "map";
}

export function hashForChapter(id: string): string {
  return `${MANUAL_HASH_PREFIX}/${id}`;
}
