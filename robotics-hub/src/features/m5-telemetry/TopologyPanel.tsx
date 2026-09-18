/**
 * I2C トポロジ（配線確認・磁石状態）パネル。
 *
 * 実機テレメトリと机上ラボの両方で同じものを使う。SCAN で実際に応答した
 * ノードだけを木にするので、机上で挿抜しても表示が追従する。
 */
import { useState } from "react";
import { buildTopoTree, type TopoItem } from "./topoTree";
import { magColor } from "./m5Widgets";
import { KIND_META, M5_JOINTS, kindMeta, type M5Cmd, type M5Scan } from "./types";

export function TopologyPanel({
  scan,
  canCmd,
  send,
  compact = false,
}: {
  scan: M5Scan | null;
  canCmd: boolean;
  send: (cmd: M5Cmd) => void;
  /** どのタブでも横に置く常設パネル。木だけを残して操作を絞る */
  compact?: boolean;
}) {
  const [sel, setSel] = useState<number | null>(null);
  const [inaJoint, setInaJoint] = useState(0);
  const tree = buildTopoTree(scan?.nodes ?? []);
  const selected = sel != null ? scan?.nodes[sel] : undefined;

  if (compact) {
    return (
      <section className="m5__section m5-topo-mini">
        <header className="m5-topo-mini__head">
          <h2>トポロジ</h2>
          <span className="m5-topo-mini__count">{scan?.nodes?.length ?? 0} ノード</span>
        </header>
        <div className="m5-topo-mini__acts">
          <button type="button" className="m5__btn" disabled={!canCmd} onClick={() => send({ op: "scan" })}>
            スキャン
          </button>
          <button
            type="button"
            className="m5__btn"
            disabled={!canCmd || !selected}
            onClick={() => {
              if (!selected) return;
              send({ op: "probe", hub: selected.hub, ch: selected.ch, addr: selected.addr });
            }}
          >
            1回読む
          </button>
        </div>
        <div className="m5__legend m5-topo-mini__legend">
          {Object.entries(KIND_META).map(([k, meta]) => (
            <span key={k} className="m5__legend-item">
              <i style={{ background: meta.color }} />
              {meta.label}
            </span>
          ))}
        </div>
        <div className="m5__tree m5-topo-mini__tree">
          <div className="m5__tree-root">Grove I2C</div>
          {tree.map((item) => (
            <TopoNode
              key={`${item.kind}-${item.title}-${item.srcIndex}`}
              item={item}
              depth={0}
              selected={sel}
              onSelect={setSel}
            />
          ))}
          {!scan?.nodes?.length ? (
            <p className="m5__meta">スキャンすると、実際に応答した相手だけが出ます。</p>
          ) : null}
        </div>
      </section>
    );
  }

  return (
    <section className="m5__section">
      <div className="m5__toolbar">
        <button type="button" className="m5__btn" disabled={!canCmd} onClick={() => send({ op: "scan" })}>
          スキャン
        </button>
        <button
          type="button"
          className="m5__btn"
          disabled={!canCmd || !selected}
          onClick={() => {
            if (!selected) return;
            send({ op: "probe", hub: selected.hub, ch: selected.ch, addr: selected.addr });
          }}
        >
          1回読む
        </button>
        <label>
          INA→関節
          <select value={inaJoint} onChange={(e) => setInaJoint(Number(e.target.value))}>
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
          disabled={!canCmd || selected?.kind !== "ina226"}
          onClick={() => {
            if (!selected || selected.kind !== "ina226") return;
            const hub = selected.hub === "root" ? 0 : parseInt(String(selected.hub), 16) || 0;
            const addr = parseInt(String(selected.addr), 16) || 0;
            send({
              op: "ina_assign",
              ch: inaJoint,
              ina_hub: hub,
              ina_ch: selected.ch,
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
          onClick={() => send({ op: "ina_assign", ch: inaJoint, ina_hub: 0, ina_ch: -1, ina_addr: 0 })}
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
        {tree.map((item) => (
          <TopoNode
            key={`${item.kind}-${item.title}-${item.srcIndex}`}
            item={item}
            depth={0}
            selected={sel}
            onSelect={setSel}
          />
        ))}
      </div>
      {!scan?.nodes?.length ? <p className="m5__meta">スキャン結果がありません。</p> : null}
    </section>
  );
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
        {isHub ? <span className="m5__node-count">{item.children.length} ch</span> : null}
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
