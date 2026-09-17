/**
 * M5 系ページの小物。実機テレメトリと机上ラボで共有する。
 */
import { useState } from "react";

/** 配列の安全な添字アクセス（欠測は undefined） */
export function at<T>(xs: T[] | undefined, i: number): T | undefined {
  return xs && i >= 0 && i < xs.length ? xs[i] : undefined;
}

/** 数値 + 単位。桁を揃えるため整数部を左スペース埋めする */
export function fmt(v: number | null | undefined, unit: string): string {
  if (typeof v !== "number" || !Number.isFinite(v)) return `— ${unit}`;
  return `${v.toFixed(2).padStart(8, " ")} ${unit}`;
}

/** µs を ms 表示に */
export function fmtMs(us: number | undefined): string {
  if (typeof us !== "number" || !Number.isFinite(us)) return "— ms";
  return `${(us / 1000).toFixed(1).padStart(6, " ")} ms`;
}

/** AS5600 の磁石コード色。0=OK、1/4=致命、2/3=注意 */
export function magColor(code: number): string {
  if (code === 0) return "#10ac84";
  if (code === 1 || code === 4) return "#ee5253";
  if (code === 2 || code === 3) return "#feca57";
  return "#8b9bb0";
}

export function Metric({
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

/** フォーカス中だけローカル編集し、blur で 1 回だけ送る数値入力 */
export function NumField({
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
