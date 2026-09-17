/**
 * 実機テレメトリの上に載せる ATOM 現場手帳。
 * 正本は atom-rt/docs/field-manual。ハッシュ `#manual/usb` で直リンクできる。
 */
import { useEffect, useMemo, useState } from "react";
import { ManualDiagram } from "./Diagrams";
import {
  FIELD_MANUAL_CHAPTERS,
  chapterIdFromHash,
  hashForChapter,
} from "./chapters";
import { parseMarkdown, renderInline } from "./parseMarkdown";
import "./FieldManual.css";

function MarkdownBody({ src }: { src: string }) {
  const blocks = useMemo(() => parseMarkdown(src), [src]);
  return (
    <div className="m5-manual__md">
      {blocks.map((b, i) => {
        if (b.kind === "h") {
          if (b.level === 1) {
            return (
              <h2 key={i} className="m5-manual__h1">
                {renderInline(b.text)}
              </h2>
            );
          }
          if (b.level === 2) {
            return (
              <h3 key={i} className="m5-manual__h2">
                {renderInline(b.text)}
              </h3>
            );
          }
          return (
            <h4 key={i} className="m5-manual__h3">
              {renderInline(b.text)}
            </h4>
          );
        }
        if (b.kind === "p") {
          return <p key={i}>{renderInline(b.text)}</p>;
        }
        if (b.kind === "code") {
          return (
            <pre key={i} className="m5-manual__pre">
              <code>{b.text}</code>
            </pre>
          );
        }
        if (b.kind === "ul") {
          return (
            <ul key={i}>
              {b.items.map((item, j) => (
                <li key={j}>{renderInline(item)}</li>
              ))}
            </ul>
          );
        }
        if (b.kind === "ol") {
          return (
            <ol key={i}>
              {b.items.map((item, j) => (
                <li key={j}>{renderInline(item)}</li>
              ))}
            </ol>
          );
        }
        if (b.kind === "table") {
          return (
            <div key={i} className="m5-manual__table-wrap">
              <table>
                <thead>
                  <tr>
                    {b.heads.map((h) => (
                      <th key={h}>{renderInline(h)}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {b.rows.map((row, ri) => (
                    <tr key={ri}>
                      {row.map((cell, ci) => (
                        <td key={ci}>{renderInline(cell)}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }
        return <hr key={i} />;
      })}
    </div>
  );
}

export interface FieldManualProps {
  open: boolean;
  chapterId: string;
  onChapter: (id: string) => void;
  onClose: () => void;
}

export default function FieldManual({ open, chapterId, onChapter, onClose }: FieldManualProps) {
  const chapter =
    FIELD_MANUAL_CHAPTERS.find((c) => c.id === chapterId) ?? FIELD_MANUAL_CHAPTERS[0];

  useEffect(() => {
    if (!open) {
      return;
    }
    const onKey = (ev: KeyboardEvent) => {
      if (ev.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [open, onClose]);

  if (!open || !chapter) {
    return null;
  }

  return (
    <div className="m5-manual" role="dialog" aria-modal="true" aria-labelledby="m5-manual-title">
      <button type="button" className="m5-manual__veil" aria-label="手帳を閉じる" onClick={onClose} />
      <div className="m5-manual__sheet">
        <header className="m5-manual__top">
          <div className="m5-manual__brand">
            <span className="m5-manual__mark">ATOM</span>
            <div>
              <h2 id="m5-manual-title">Field Manual</h2>
              <p>ファームが運ぶ現場手帳 · USB ver=10</p>
            </div>
          </div>
          <button type="button" className="m5-manual__close" onClick={onClose}>
            閉じる
          </button>
        </header>

        <div className="m5-manual__body">
          <nav className="m5-manual__spine" aria-label="手帳の目次">
            {FIELD_MANUAL_CHAPTERS.map((c) => (
              <button
                key={c.id}
                type="button"
                className={"m5-manual__spine-btn" + (c.id === chapter.id ? " is-on" : "")}
                onClick={() => onChapter(c.id)}
              >
                <span className="m5-manual__spine-idx">{c.index}</span>
                <span className="m5-manual__spine-title">{c.title}</span>
                <span className="m5-manual__spine-kicker">{c.kicker}</span>
              </button>
            ))}
          </nav>

          <article className="m5-manual__page" key={chapter.id}>
            <p className="m5-manual__kicker">
              {chapter.index} · {chapter.kicker}
            </p>
            <h2 className="m5-manual__page-title">{chapter.title}</h2>
            <ManualDiagram id={chapter.diagram} />
            <MarkdownBody src={chapter.markdown} />
          </article>
        </div>
      </div>
    </div>
  );
}

/** ページ側の開閉とハッシュ `#manual/章` を同期する。 */
export function useFieldManual() {
  const [open, setOpen] = useState(() => chapterIdFromHash(window.location.hash) != null);
  const [chapterId, setChapterId] = useState(
    () => chapterIdFromHash(window.location.hash) ?? "map"
  );

  useEffect(() => {
    const apply = () => {
      const id = chapterIdFromHash(window.location.hash);
      if (id) {
        setOpen(true);
        setChapterId(id);
      } else {
        setOpen(false);
      }
    };
    window.addEventListener("hashchange", apply);
    return () => window.removeEventListener("hashchange", apply);
  }, []);

  const openTo = (id: string = "map") => {
    setChapterId(id);
    setOpen(true);
    const next = hashForChapter(id);
    if (window.location.hash !== next) {
      window.location.hash = next;
    }
  };

  const close = () => {
    setOpen(false);
    if (chapterIdFromHash(window.location.hash)) {
      history.replaceState(null, "", window.location.pathname + window.location.search);
    }
  };

  const selectChapter = (id: string) => {
    setChapterId(id);
    const next = hashForChapter(id);
    if (window.location.hash !== next) {
      window.location.hash = next;
    }
  };

  return { open, chapterId, openTo, close, selectChapter };
}
