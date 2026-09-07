import { MAG_LABEL, type M5ScanNode } from "./types";

export type TopoItem = {
  /** 元の scan.nodes 添字。合成ノード（Grove 根）は null */
  srcIndex: number | null;
  kind: string;
  /** 見出し（PaHub 0x70 / CH3 0x36 など） */
  title: string;
  detail: string;
  magLabel: string;
  magCode: number;
  children: TopoItem[];
};

function normHub(s: string): string {
  return s.replace(/^0x/i, "").toUpperCase();
}

/**
 * フラットなスキャン結果を Grove → PaHub → CH の木にする。
 * 同じ (hub, ch, addr, kind) が二度来たら後勝ち（再スキャンの重複対策）。
 */
export function buildTopoTree(nodes: M5ScanNode[]): TopoItem[] {
  const uniq = new Map<string, { node: M5ScanNode; index: number }>();
  nodes.forEach((node, index) => {
    uniq.set(`${node.hub}|${node.ch}|${node.addr}|${node.kind}`, { node, index });
  });
  const list = [...uniq.values()];

  const hubs = new Map<string, TopoItem>();
  const grove: TopoItem[] = [];

  for (const { node, index } of list) {
    if (node.hub !== "root" || node.kind !== "pahub") continue;
    const key = normHub(node.addr);
    hubs.set(key, {
      srcIndex: index,
      kind: "pahub",
      title: `PaHub ${node.addr}`,
      detail: "Grove 直結",
      magLabel: "",
      magCode: 255,
      children: [],
    });
  }

  // Grove 直下はスキャン順（サーボ → PaHub など）を保つ
  for (const { node, index } of list) {
    if (node.hub !== "root") continue;
    if (node.kind === "pahub") {
      const item = hubs.get(normHub(node.addr));
      if (item && !grove.includes(item)) grove.push(item);
      continue;
    }
    grove.push({
      srcIndex: index,
      kind: node.kind,
      title: node.addr,
      detail: "Grove 直結",
      magLabel: node.kind === "as5600" ? (MAG_LABEL[node.mag] ?? String(node.mag)) : "",
      magCode: node.mag,
      children: [],
    });
  }

  for (const { node, index } of list) {
    if (node.hub === "root") continue;
    const magLabel = node.kind === "as5600" ? (MAG_LABEL[node.mag] ?? String(node.mag)) : "";
    const child: TopoItem = {
      srcIndex: index,
      kind: node.kind,
      title: `CH${node.ch}  ${node.addr}`,
      detail: `Hub 0x${normHub(node.hub)}`,
      magLabel,
      magCode: node.mag,
      children: [],
    };
    const parent = hubs.get(normHub(node.hub));
    if (parent) parent.children.push(child);
    else grove.push(child);
  }

  grove.forEach((h) => {
    if (h.kind !== "pahub") return;
    h.children.sort((a, b) => a.title.localeCompare(b.title, "en"));
  });

  return grove;
}
