import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { chatUrl, getChatHistory } from "../api/client";
import { streamSSE } from "../api/sse";
import { Markdown } from "../lib/markdown";
import { getSessionId } from "../lib/storage";
import { AlternativeCard, type AltItem } from "./AlternativeCard";
import { useApplyAlternative } from "./ReplacePanel";

interface Msg {
  role: "user" | "assistant";
  content: string;
  alts?: { category: string; items: AltItem[] };
}

const SUGGESTIONS = ["Почему эта видеокарта?", "Можно дешевле?", "Чем заменить процессор?"];

function AltList({
  buildId,
  category,
  items,
}: {
  buildId: number;
  category: string;
  items: AltItem[];
}) {
  const apply = useApplyAlternative(buildId, category);
  return (
    <div className="mt-2 grid gap-2">
      {items.map((a) => (
        <AlternativeCard
          key={a.component_id}
          alt={a}
          disabled={apply.isPending}
          onApply={(x) => apply.mutate(x)}
        />
      ))}
      {apply.isError && <p className="text-xs text-bad">{apply.error.message}</p>}
    </div>
  );
}

export function ChatPanel({ buildId }: { buildId: number }) {
  const history = useQuery({ queryKey: ["chat", buildId], queryFn: () => getChatHistory(buildId) });
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (history.data)
      setMsgs(history.data.map((m) => ({ role: m.role as Msg["role"], content: m.content })));
  }, [history.data]);
  useEffect(() => {
    bottom.current?.scrollIntoView?.({ block: "nearest" });
  }, [msgs]);

  const send = async (message: string) => {
    if (!message.trim() || busy) return;
    setError(null);
    setBusy(true);
    setInput("");
    setMsgs((m) => [...m, { role: "user", content: message }, { role: "assistant", content: "" }]);
    const patch = (fn: (m: Msg) => Msg) =>
      setMsgs((all) => all.map((m, i) => (i === all.length - 1 ? fn(m) : m)));
    try {
      await streamSSE(
        chatUrl(buildId),
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ message, session_id: getSessionId() }),
        },
        (e) => {
          const d = e.data as Record<string, unknown>;
          if (e.event === "token")
            patch((m) => ({ ...m, content: m.content + String(d.text ?? "") }));
          else if (e.event === "replace" || e.event === "done")
            patch((m) => ({ ...m, content: String(d.text ?? m.content) }));
          else if (e.event === "alternatives")
            patch((m) => ({
              ...m,
              alts: { category: String(d.category), items: d.items as AltItem[] },
            }));
          else if (e.event === "error") setError(String(d.message ?? "Ошибка чата"));
        },
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка чата");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel flex h-[32rem] flex-col lg:h-[calc(100vh-8rem)]" aria-label="ИИ-чат">
      <h2 className="label border-b border-line p-3">ИИ-консультант по сборке</h2>
      <div className="flex-1 space-y-3 overflow-y-auto p-3" aria-live="polite">
        {msgs.length === 0 && !history.isLoading && (
          <div className="space-y-2 text-sm text-mute">
            <p>Спросите о сборке — отвечу и предложу совместимые замены из каталога.</p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <button key={s} className="chip" onClick={() => send(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {msgs.map((m, i) => (
          <div
            key={i}
            className={
              m.role === "user" ? "ml-8 rounded-sm bg-accent/15 p-2 text-sm" : "mr-2 text-sm"
            }
          >
            {m.role === "assistant" && !m.content && busy && i === msgs.length - 1 ? (
              <span className="text-mute">Печатаю…</span>
            ) : m.role === "assistant" ? (
              <Markdown text={m.content} />
            ) : (
              m.content
            )}
            {m.alts && m.alts.items.length > 0 && (
              <AltList buildId={buildId} category={m.alts.category} items={m.alts.items} />
            )}
          </div>
        ))}
        {error && (
          <p role="alert" className="text-sm text-bad">
            {error}
          </p>
        )}
        <div ref={bottom} />
      </div>
      <form
        className="flex gap-2 border-t border-line p-3"
        onSubmit={(e) => {
          e.preventDefault();
          void send(input);
        }}
      >
        <label className="sr-only" htmlFor="chat-input">
          Сообщение
        </label>
        <input
          id="chat-input"
          className="min-w-0 flex-1 rounded-sm border border-line bg-bg px-3 py-2 text-sm outline-none focus:border-accent"
          value={input}
          maxLength={1000}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Например: чем заменить видеокарту подешевле?"
        />
        <button className="btn btn-primary" disabled={busy || !input.trim()}>
          Отправить
        </button>
      </form>
    </section>
  );
}
