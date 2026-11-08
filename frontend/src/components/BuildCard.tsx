import { Link } from "react-router-dom";
import type { BuildSummary } from "../api/types";
import { rub } from "../lib/format";

interface Props {
  build: BuildSummary;
  selected: boolean;
  onToggleCompare: (id: number) => void;
}

export function BuildCard({ build: b, selected, onToggleCompare }: Props) {
  const k = b.key_components;
  const rows: [string, string | null | undefined][] = [
    ["CPU", k.cpu],
    ["GPU", k.gpu ?? "встроенная графика"],
    ["RAM", k.ram],
    ["SSD", k.storage],
  ];
  return (
    <article className="panel flex flex-col p-4" data-testid="build-card">
      <div className="flex items-start justify-between gap-2">
        <h3 className="label">{b.label}</h3>
        {b.compat_ok ? (
          <span className="rounded-sm border border-accent/40 px-2 py-0.5 text-[11px] text-accent">
            Совместимость проверена ✓
          </span>
        ) : (
          <span className="rounded-sm border border-bad/40 px-2 py-0.5 text-[11px] text-bad">
            Есть несовместимость
          </span>
        )}
      </div>
      <p className="mt-2 font-mono text-2xl font-semibold">{rub(b.total_price)}</p>
      <p className="text-xs text-mute">
        {b.budget_share != null
          ? `${Math.round(b.budget_share * 100)}% от бюджета ${rub(b.budget_rub)}`
          : "бюджет не задан"}
        {b.prices_are_demo && " · цены ориентировочные (демо)"}
      </p>
      <dl className="mt-3 flex-1 space-y-1.5 text-sm">
        {rows.map(([name, value]) => (
          <div key={name} className="grid grid-cols-[3rem_1fr] gap-2">
            <dt className="font-mono text-xs text-mute">{name}</dt>
            <dd className="break-words">{value ?? "—"}</dd>
          </div>
        ))}
      </dl>
      {b.warnings.length > 0 && (
        <ul className="mt-3 space-y-1 text-xs text-warn">
          {b.warnings.slice(0, 2).map((w) => (
            <li key={w.code}>⚠ {w.message_ru}</li>
          ))}
        </ul>
      )}
      <div className="mt-4 flex gap-2">
        <Link to={`/build/${b.id}`} className="btn btn-primary flex-1">
          Подробнее
        </Link>
        <button
          className={`btn ${selected ? "border-accent text-accent" : ""}`}
          aria-pressed={selected}
          onClick={() => onToggleCompare(b.id)}
        >
          {selected ? "✓ В сравнении" : "Сравнить"}
        </button>
      </div>
    </article>
  );
}
