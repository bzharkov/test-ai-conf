import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { configure } from "../api/client";
import type { ConfigureFilters, Requirements } from "../api/types";
import { BuildCard } from "../components/BuildCard";
import { HistoryList } from "../components/HistoryList";
import { ProgressSteps } from "../components/ProgressSteps";
import { RequirementsPanel } from "../components/RequirementsPanel";
import { Empty, ErrorBox, SkeletonCards, Warnings } from "../components/ui";
import { rub } from "../lib/format";
import {
  getSessionId,
  setLastResult,
  toggleCompare,
  useCompareIds,
  useLastResult,
} from "../lib/storage";

const EXAMPLES = [
  "Игры в 1440p до 120 000 ₽",
  "Офисный ПК до 40 000 ₽",
  "Монтаж 4K до 200 000 ₽",
  "Компактный ПК для учёбы и Dota 2",
];

export function Home() {
  const qc = useQueryClient();
  const last = useLastResult();
  const compare = useCompareIds();
  const [text, setText] = useState(last?.text ?? "");
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState<ConfigureFilters>({});

  const m = useMutation({
    mutationFn: (p: { text: string; requirements?: Requirements }) =>
      configure({
        text: p.text,
        session_id: getSessionId(),
        filters: p.requirements ? undefined : filters,
        requirements: p.requirements,
      }),
    onSuccess: (data, vars) => {
      setLastResult({ text: vars.text, data });
      qc.invalidateQueries({ queryKey: ["history"] });
    },
  });

  const submit = (t = text) => {
    if (t.trim().length < 3) return;
    m.mutate({ text: t.trim() });
  };
  const result = m.data ?? last?.data;
  const overBudget = result?.min_feasible_price != null;

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[minmax(0,1fr)_280px]">
      <div className="min-w-0 space-y-6">
        <section>
          <h1 className="text-2xl font-semibold sm:text-3xl">Подбор ПК под вашу задачу</h1>
          <p className="mt-1 text-sm text-mute">
            Опишите задачи и бюджет обычным текстом — получите 2–3 совместимые сборки.
          </p>
          <form
            className="mt-4 space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              submit();
            }}
          >
            <label className="sr-only" htmlFor="q">
              Опишите, какой ПК нужен
            </label>
            <textarea
              id="q"
              className="panel w-full resize-y p-3 text-base outline-none focus:border-accent"
              rows={3}
              maxLength={1500}
              placeholder="Например: ПК для игр в 1440p и монтажа до 120 000 ₽"
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
            <div className="flex flex-wrap gap-2">
              {EXAMPLES.map((ex) => (
                <button
                  type="button"
                  key={ex}
                  className="chip"
                  onClick={() => {
                    setText(ex);
                    submit(ex);
                  }}
                >
                  {ex}
                </button>
              ))}
            </div>
            <div>
              <button
                type="button"
                className="label hover:text-accent"
                aria-expanded={showFilters}
                onClick={() => setShowFilters(!showFilters)}
              >
                {showFilters ? "▾" : "▸"} Дополнительные фильтры
              </button>
              {showFilters && (
                <div className="panel mt-2 grid gap-3 p-3 sm:grid-cols-2">
                  <label className="text-sm">
                    <span className="label">Бюджет: {rub(filters.budget_rub ?? 100000)}</span>
                    <input
                      type="range"
                      min={30000}
                      max={400000}
                      step={5000}
                      className="mt-2 w-full accent-[rgb(var(--accent))]"
                      value={filters.budget_rub ?? 100000}
                      onChange={(e) =>
                        setFilters({ ...filters, budget_rub: Number(e.target.value) })
                      }
                    />
                  </label>
                  <label className="text-sm">
                    <span className="label">Процессор</span>
                    <select
                      className="mt-1 w-full rounded-sm border border-line bg-bg px-3 py-2"
                      value={filters.cpu_brand ?? ""}
                      onChange={(e) =>
                        setFilters({
                          ...filters,
                          cpu_brand: (e.target.value || undefined) as "amd" | "intel" | undefined,
                        })
                      }
                    >
                      <option value="">любой</option>
                      <option value="amd">AMD</option>
                      <option value="intel">Intel</option>
                    </select>
                  </label>
                  {(
                    [
                      ["wifi", "Нужен Wi-Fi"],
                      ["compact", "Маленький корпус"],
                      ["no_gpu", "Без видеокарты"],
                    ] as const
                  ).map(([key, label]) => (
                    <label key={key} className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={!!filters[key]}
                        onChange={(e) => setFilters({ ...filters, [key]: e.target.checked })}
                      />
                      {label}
                    </label>
                  ))}
                  {filters.budget_rub != null && (
                    <button
                      type="button"
                      className="label text-left hover:text-accent"
                      onClick={() => setFilters({ ...filters, budget_rub: undefined })}
                    >
                      Сбросить бюджет
                    </button>
                  )}
                </div>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-4">
              <button className="btn btn-primary" type="submit" disabled={m.isPending}>
                {m.isPending ? "Подбираю…" : "Подобрать"}
              </button>
              <ProgressSteps active={m.isPending} />
            </div>
          </form>
        </section>

        {m.isError && <ErrorBox message={m.error.message} onRetry={() => submit()} />}
        {m.isPending && <SkeletonCards />}

        {!m.isPending && result && (
          <section className="space-y-4" aria-label="Результат подбора">
            <Warnings items={result.warnings} />
            <RequirementsPanel
              requirements={result.requirements}
              busy={m.isPending}
              onRebuild={(r) => m.mutate({ text: last?.text ?? text, requirements: r })}
            />
            {result.builds.length === 0 ? (
              <Empty>Не удалось подобрать сборку. Попробуйте изменить запрос или бюджет.</Empty>
            ) : (
              <>
                {overBudget && (
                  <p className="text-sm text-bad">
                    Ближайшая возможная сборка стоит {rub(result.min_feasible_price)}.
                  </p>
                )}
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                  {result.builds.map((b) => (
                    <BuildCard
                      key={b.id}
                      build={b}
                      selected={compare.includes(b.id)}
                      onToggleCompare={toggleCompare}
                    />
                  ))}
                </div>
              </>
            )}
          </section>
        )}
      </div>
      <aside className="hidden lg:block">
        <h2 className="label mb-2">История</h2>
        <HistoryList compact />
      </aside>
    </div>
  );
}
