import type { ReactNode } from "react";

function inline(text: string, keyBase: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`|(?<![*\w])\*[^*\n]+\*(?!\*)|_[^_\n]+_)/g;
  let last = 0;
  let i = 0;
  for (const m of text.matchAll(re)) {
    const idx = m.index ?? 0;
    if (idx > last) out.push(text.slice(last, idx));
    const tok = m[0];
    const k = `${keyBase}-${i++}`;
    if (tok.startsWith("**")) out.push(<strong key={k}>{tok.slice(2, -2)}</strong>);
    else if (tok.startsWith("`")) out.push(<code key={k}>{tok.slice(1, -1)}</code>);
    else out.push(<em key={k}>{tok.slice(1, -1)}</em>);
    last = idx + tok.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

/** Minimal, XSS-safe Markdown (headings, lists, bold/italic/code). Never uses innerHTML. */
export function Markdown({ text }: { text: string }) {
  const blocks: ReactNode[] = [];
  let list: string[] = [];
  let para: string[] = [];
  const flushList = () => {
    if (!list.length) return;
    const items = list;
    blocks.push(
      <ul key={`ul${blocks.length}`} className="ml-5 list-disc space-y-1">
        {items.map((t, i) => (
          <li key={i}>{inline(t, `li${blocks.length}-${i}`)}</li>
        ))}
      </ul>,
    );
    list = [];
  };
  const flushPara = () => {
    if (!para.length) return;
    blocks.push(<p key={`p${blocks.length}`}>{inline(para.join(" "), `p${blocks.length}`)}</p>);
    para = [];
  };
  for (const line of text.split("\n")) {
    const h = /^(#{1,4})\s+(.*)$/.exec(line);
    const li = /^\s*[-*]\s+(.*)$/.exec(line);
    if (h) {
      flushList();
      flushPara();
      blocks.push(
        <h4
          key={`h${blocks.length}`}
          className="mt-3 font-mono text-xs uppercase tracking-wider text-accent"
        >
          {inline(h[2], `h${blocks.length}`)}
        </h4>,
      );
    } else if (li) {
      flushPara();
      list.push(li[1]);
    } else if (!line.trim()) {
      flushList();
      flushPara();
    } else {
      flushList();
      para.push(line.trim());
    }
  }
  flushList();
  flushPara();
  return <div className="space-y-2 text-sm leading-relaxed">{blocks}</div>;
}
