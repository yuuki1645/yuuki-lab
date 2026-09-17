/**
 * 現場手帳用のごく薄い Markdown。
 * 依存を増やさず、見出し・表・コード・リストだけを React にする。
 */
import type { ReactNode } from "react";

export type MdBlock =
  | { kind: "h"; level: 1 | 2 | 3; text: string }
  | { kind: "p"; text: string }
  | { kind: "code"; lang: string; text: string }
  | { kind: "ul"; items: string[] }
  | { kind: "ol"; items: string[] }
  | { kind: "table"; heads: string[]; rows: string[][] }
  | { kind: "hr" };

/** `**bold**` と `` `code` `` だけインライン変換する。 */
export function renderInline(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0;
  let key = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text))) {
    if (m.index > last) {
      out.push(text.slice(last, m.index));
    }
    const tok = m[0];
    if (tok.startsWith("**")) {
      out.push(<strong key={key}>{tok.slice(2, -2)}</strong>);
    } else {
      out.push(<code key={key}>{tok.slice(1, -1)}</code>);
    }
    key += 1;
    last = m.index + tok.length;
  }
  if (last < text.length) {
    out.push(text.slice(last));
  }
  return out;
}

function splitRow(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((c) => c.trim());
}

function isFence(line: string): boolean {
  return line.trimStart().startsWith("```");
}

function isHr(line: string): boolean {
  return /^---+$/.test(line.trim());
}

function isTableSep(line: string): boolean {
  return /^\|?\s*:?-{3,}/.test(line.trim());
}

/** 現場手帳の Markdown をブロック列にする。 */
export function parseMarkdown(src: string): MdBlock[] {
  const lines = src.replace(/\r\n/g, "\n").split("\n");
  const blocks: MdBlock[] = [];
  let i = 0;

  const flushPara = (buf: string[]) => {
    const text = buf.join(" ").trim();
    if (text) {
      blocks.push({ kind: "p", text });
    }
    buf.length = 0;
  };

  while (i < lines.length) {
    const line = lines[i] ?? "";
    const trimmed = line.trim();

    if (trimmed === "") {
      i += 1;
      continue;
    }

    if (isHr(trimmed) && !trimmed.startsWith("|")) {
      blocks.push({ kind: "hr" });
      i += 1;
      continue;
    }

    if (isFence(trimmed)) {
      const lang = trimmed.replace(/```/, "").trim();
      i += 1;
      const body: string[] = [];
      while (i < lines.length && !isFence(lines[i] ?? "")) {
        body.push(lines[i] ?? "");
        i += 1;
      }
      if (i < lines.length) {
        i += 1;
      }
      blocks.push({ kind: "code", lang, text: body.join("\n") });
      continue;
    }

    const heading = /^(#{1,3})\s+(.+)$/.exec(trimmed);
    if (heading) {
      const level = heading[1]!.length as 1 | 2 | 3;
      blocks.push({ kind: "h", level, text: heading[2] ?? "" });
      i += 1;
      continue;
    }

    if (trimmed.startsWith("|") && i + 1 < lines.length && isTableSep(lines[i + 1] ?? "")) {
      const heads = splitRow(trimmed);
      i += 2;
      const rows: string[][] = [];
      while (i < lines.length && (lines[i] ?? "").trim().startsWith("|")) {
        rows.push(splitRow(lines[i] ?? ""));
        i += 1;
      }
      blocks.push({ kind: "table", heads, rows });
      continue;
    }

    if (/^[-*]\s+/.test(trimmed)) {
      const items: string[] = [];
      while (i < lines.length && /^[-*]\s+/.test((lines[i] ?? "").trim())) {
        items.push((lines[i] ?? "").trim().replace(/^[-*]\s+/, ""));
        i += 1;
      }
      blocks.push({ kind: "ul", items });
      continue;
    }

    if (/^\d+\.\s+/.test(trimmed)) {
      const items: string[] = [];
      while (i < lines.length && /^\d+\.\s+/.test((lines[i] ?? "").trim())) {
        items.push((lines[i] ?? "").trim().replace(/^\d+\.\s+/, ""));
        i += 1;
      }
      blocks.push({ kind: "ol", items });
      continue;
    }

    const para: string[] = [trimmed];
    i += 1;
    while (
      i < lines.length &&
      (lines[i] ?? "").trim() !== "" &&
      !isFence(lines[i] ?? "") &&
      !/^(#{1,3})\s+/.test((lines[i] ?? "").trim()) &&
      !/^[-*]\s+/.test((lines[i] ?? "").trim()) &&
      !/^\d+\.\s+/.test((lines[i] ?? "").trim()) &&
      !(lines[i] ?? "").trim().startsWith("|")
    ) {
      para.push((lines[i] ?? "").trim());
      i += 1;
    }
    flushPara(para);
  }

  return blocks;
}
