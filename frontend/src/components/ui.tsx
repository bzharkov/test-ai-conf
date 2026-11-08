import type { ReactNode } from "react";
import type { Warn } from "../api/types";

export function Warnings({ items }: { items: Warn[] }) {
  if (!items.length) return null;
  return (
    <ul className="space-y-2" aria-label="Предупреждения">
      {items.map((w) => (
        <li
          key={w.code + w.message_ru}
          className={`panel flex gap-2 border-l-4 px-3 py-2 text-sm ${
            w.code === "over_budget" || w.code === "no_build" ? "border-l-bad" : "border-l-warn"
          }`}
        >
          <span aria-hidden>⚠</span>
          <span>{w.message_ru}</span>
        </li>
      ))}
    </ul>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="panel border-l-4 border-l-bad p-4 text-sm">
      <p>{message}</p>
      {onRetry && (
        <button className="btn mt-3" onClick={onRetry}>
          Повторить
        </button>
      )}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="panel p-6 text-center text-sm text-mute">{children}</div>;
}

export function SkeletonCards({ n = 3 }: { n?: number }) {
  return (
    <div className="grid gap-4 md:grid-cols-3" aria-busy="true" aria-label="Загрузка">
      {Array.from({ length: n }, (_, i) => (
        <div key={i} className="panel space-y-3 p-4">
          <div className="skeleton h-4 w-1/2" />
          <div className="skeleton h-8 w-2/3" />
          <div className="skeleton h-3 w-full" />
          <div className="skeleton h-3 w-5/6" />
          <div className="skeleton h-3 w-4/6" />
        </div>
      ))}
    </div>
  );
}
