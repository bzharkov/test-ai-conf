import { useEffect, useRef, useState } from "react";
import { explanationUrl } from "../api/client";
import { streamSSE } from "../api/sse";
import { Markdown } from "../lib/markdown";

export function Explanation({ buildId }: { buildId: number }) {
  const [text, setText] = useState("");
  const [state, setState] = useState<"loading" | "done" | "error">("loading");
  const ctl = useRef<AbortController | null>(null);

  useEffect(() => {
    const c = new AbortController();
    ctl.current = c;
    setText("");
    setState("loading");
    streamSSE(
      explanationUrl(buildId),
      {},
      (e) => {
        const d = e.data as { text?: string; message?: string };
        if (e.event === "token") setText((t) => t + (d.text ?? ""));
        else if (e.event === "replace" || e.event === "done") {
          setText(d.text ?? "");
          if (e.event === "done") setState("done");
        } else if (e.event === "error") setState("error");
      },
      c.signal,
    ).catch((err) => {
      if (!c.signal.aborted) {
        console.error(err);
        setState("error");
      }
    });
    return () => c.abort();
  }, [buildId]);

  return (
    <section className="panel p-4" aria-label="Объяснение выбора">
      <h2 className="label mb-2">Почему такая сборка</h2>
      {state === "loading" && !text && (
        <div className="space-y-2" aria-busy="true">
          <div className="skeleton h-3 w-3/4" />
          <div className="skeleton h-3 w-2/3" />
        </div>
      )}
      {text && <Markdown text={text} />}
      {state === "error" && !text && (
        <p className="text-sm text-warn">
          Объяснение сейчас недоступно, остальные данные актуальны.
        </p>
      )}
    </section>
  );
}
