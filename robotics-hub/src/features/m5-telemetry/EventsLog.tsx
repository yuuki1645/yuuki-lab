/**
 * イベントログ表示。古い行が上、新しい行が下。
 *
 * 親の lines は時系列。毎回 join し直さず、先頭落ちと末尾追記だけ DOM を動かす。
 * seq が巻き戻った／件数が合わないときはスナップショットとして作り直す。
 */
import { useEffect, useRef, type MutableRefObject } from "react";

const EMPTY = "（イベントなし）";

type Props = {
  className?: string;
  lines: string[];
  /** lines[0] の seq。リングから落ちると増える */
  headSeq: number;
  /** 末尾の seq */
  tailSeq: number;
  /** 下端付近にいるときだけ追従。親と共有する */
  pinBottom: MutableRefObject<boolean>;
};

export function EventsLog({ className, lines, headSeq, tailSeq, pinBottom }: Props) {
  const preRef = useRef<HTMLPreElement>(null);
  const headRef = useRef(0);
  const tailRef = useRef(0);
  const nRef = useRef(0);

  const onScroll = () => {
    const el = preRef.current;
    if (!el) return;
    pinBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 32;
  };

  useEffect(() => {
    const el = preRef.current;
    if (!el) return;

    if (!lines.length) {
      el.textContent = EMPTY;
      headRef.current = 0;
      tailRef.current = 0;
      nRef.current = 0;
      return;
    }

    const prevHead = headRef.current;
    const prevTail = tailRef.current;
    const prevN = nRef.current;
    // 件数ベースで差分を取る。seq 欠落時に slice を取り過ぎない
    const dropped = Math.max(0, headSeq - prevHead);
    const remain = prevN - dropped;
    const addedN = lines.length - remain;
    const reset =
      prevN === 0 ||
      tailSeq < prevTail ||
      headSeq < prevHead ||
      remain < 0 ||
      addedN < 0;

    if (reset) {
      el.textContent = lines.join("\n");
    } else {
      if (dropped > 0) {
        let t = el.textContent || "";
        if (t === EMPTY) t = "";
        for (let i = 0; i < dropped; i += 1) {
          const nl = t.indexOf("\n");
          t = nl >= 0 ? t.slice(nl + 1) : "";
        }
        el.textContent = t;
      }
      if (addedN > 0) {
        const added = lines.slice(lines.length - addedN);
        const cur = el.textContent || "";
        const prefix = remain > 0 && cur && cur !== EMPTY ? "\n" : "";
        if (dropped > 0) {
          el.textContent = (cur && cur !== EMPTY ? cur : "") + prefix + added.join("\n");
        } else {
          el.appendChild(document.createTextNode(prefix + added.join("\n")));
        }
      }
    }

    headRef.current = headSeq;
    tailRef.current = tailSeq;
    nRef.current = lines.length;
    if (pinBottom.current) {
      el.scrollTop = el.scrollHeight;
    }
  }, [lines, headSeq, tailSeq, pinBottom]);

  return <pre ref={preRef} className={className} onScroll={onScroll} />;
}
