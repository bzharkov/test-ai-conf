import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getBuild } from "../api/client";
import type { BuildOut } from "../api/types";
import { ChatPanel } from "../components/ChatPanel";
import { Explanation } from "../components/Explanation";
import { ReplacePanel } from "../components/ReplacePanel";
import { ErrorBox, Warnings } from "../components/ui";
import { keySpecs, rub } from "../lib/format";
import { toggleCompare, useCompareIds } from "../lib/storage";

function PowerBlock({ b }: { b: BuildOut }) {
  const p = b.power;
  return (
    <section className="panel p-4" aria-label="Питание">
      <h2 className="label mb-3">Питание</h2>
      <table className="w-full text-sm">
        <tbody>
          {p.items.map((i) => (
            <tr key={i.label} className="border-b border-line/50">
              <td className="py-1 pr-2">{i.label}</td>
              <td className="py-1 text-right font-mono">{i.watts} Вт</td>
            </tr>
          ))}
          <tr>
            <td className="pt-2 font-medium">Оценка нагрузки</td>
            <td className="pt-2 text-right font-mono">{p.estimated_power_w} Вт</td>
          </tr>
          <tr>
            <td className="py-1 text-mute">× запас {p.margin}, округление до 50 Вт</td>
            <td className="py-1 text-right font-mono">{p.psu_recommended_w} Вт</td>
          </tr>
          {p.gpu_recommended_psu_w > 0 && (
            <tr>
              <td className="py-1 text-mute">Рекомендация производителя GPU</td>
              <td className="py-1 text-right font-mono">{p.gpu_recommended_psu_w} Вт</td>
            </tr>
          )}
        </tbody>
      </table>
      <p className="mt-2 text-sm">
        Установлен БП: <b className="font-mono">{p.installed_psu_w} Вт</b>
        {p.installed_psu_w != null && p.installed_psu_w >= p.psu_recommended_w ? " ✓" : " ⚠"}
      </p>
    </section>
  );
}

function CompatBlock({ b }: { b: BuildOut }) {
  return (
    <section className="panel p-4" aria-label="Проверки совместимости">
      <h2 className="label mb-3">Проверки совместимости</h2>
      <ul className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
        {b.compatibility.rules.map((r) => (
          <li key={r.code} title={r.messages.join("; ")} className="flex gap-2">
            <span
              className={
                r.status === "ok"
                  ? "text-accent"
                  : r.status === "warning"
                    ? "text-warn"
                    : "text-bad"
              }
              aria-label={r.status}
            >
              {r.status === "ok" ? "✓" : r.status === "warning" ? "⚠" : "✕"}
            </span>
            <span>
              {r.title}
              {r.messages.map((m) => (
                <span key={m} className="block text-xs text-mute">
                  {m}
                </span>
              ))}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function Build() {
  const id = Number(useParams().id);
  const q = useQuery({ queryKey: ["build", id], queryFn: () => getBuild(id), enabled: id > 0 });
  const [open, setOpen] = useState<string | null>(null);
  const compare = useCompareIds();

  if (q.isLoading)
    return (
      <div className="space-y-3" aria-busy="true">
        <div className="skeleton h-8 w-1/2" />
        <div className="skeleton h-64 w-full" />
      </div>
    );
  if (q.isError)
    return (
      <div className="space-y-3">
        <ErrorBox message={q.error.message} onRetry={() => q.refetch()} />
        <Link to="/" className="text-accent underline">
          К подбору
        </Link>
      </div>
    );
  const b = q.data!;

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[minmax(0,1fr)_400px]">
      <div className="min-w-0 space-y-6">
        <header className="space-y-2">
          <Link to="/" className="label hover:text-accent">
            ← К подбору
          </Link>
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="label">{b.label}</p>
              <p className="font-mono text-3xl font-semibold">{rub(b.total_price)}</p>
              <p className="text-xs text-mute">
                {b.budget_share != null
                  ? `${Math.round(b.budget_share * 100)}% от бюджета ${rub(b.budget_rub)}`
                  : "бюджет не задан"}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={`rounded-sm border px-2 py-1 text-xs ${
                  b.compat_ok ? "border-accent/40 text-accent" : "border-bad/40 text-bad"
                }`}
              >
                {b.compat_ok ? "Совместимость проверена ✓" : "Есть несовместимость"}
              </span>
              <button
                className="btn"
                aria-pressed={compare.includes(b.id)}
                onClick={() => toggleCompare(b.id)}
              >
                {compare.includes(b.id) ? "✓ В сравнении" : "Сравнить"}
              </button>
            </div>
          </div>
          <Warnings items={b.warnings} />
        </header>

        <Explanation buildId={b.id} />

        <section className="panel" aria-label="Комплектующие">
          <h2 className="label border-b border-line p-3">Комплектующие</h2>
          <ul>
            {b.items.map((c) => (
              <li key={c.id} className="border-b border-line/60 last:border-b-0">
                <div className="grid gap-x-4 gap-y-1 p-3 sm:grid-cols-[8rem_1fr_auto]">
                  <p className="label sm:pt-1">{c.category_ru}</p>
                  <div className="min-w-0">
                    <p className="break-words font-medium">{c.name}</p>
                    <p className="break-words text-xs text-mute">{keySpecs(c.category, c.specs)}</p>
                    {c.perf_estimated && (
                      <p className="text-xs text-warn">оценка производительности приблизительная</p>
                    )}
                  </div>
                  <div className="flex items-center justify-between gap-3 sm:flex-col sm:items-end sm:justify-start">
                    <div className="text-right">
                      <p className="font-mono">{rub(c.price_rub)}</p>
                      <p className="text-[11px] text-mute">
                        {c.price_is_demo ? "ориентировочно (демо)" : c.price_source}
                        {c.price_updated_at ? ` · ${c.price_updated_at}` : ""}
                      </p>
                    </div>
                    <button
                      className="btn !min-h-[32px] !py-1"
                      aria-expanded={open === c.category}
                      onClick={() => setOpen(open === c.category ? null : c.category)}
                    >
                      Заменить
                    </button>
                  </div>
                </div>
                {open === c.category && <ReplacePanel buildId={b.id} category={c.category} />}
              </li>
            ))}
          </ul>
        </section>

        <div className="grid grid-cols-[minmax(0,1fr)] gap-6 xl:grid-cols-2">
          <PowerBlock b={b} />
          <CompatBlock b={b} />
        </div>
      </div>
      <div className="lg:sticky lg:top-4 lg:self-start">
        <ChatPanel buildId={b.id} />
      </div>
    </div>
  );
}
