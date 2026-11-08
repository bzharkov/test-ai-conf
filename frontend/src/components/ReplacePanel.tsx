import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { getAlternatives, replaceComponent } from "../api/client";
import type { Intent } from "../api/types";
import { AlternativeCard, type AltItem } from "./AlternativeCard";
import { Empty, ErrorBox } from "./ui";

const TABS: [Intent, string][] = [
  ["cheaper", "Дешевле"],
  ["similar", "Похожие"],
  ["better", "Мощнее"],
];

export function useApplyAlternative(buildId: number, category: string) {
  const nav = useNavigate();
  return useMutation({
    mutationFn: (alt: AltItem) =>
      replaceComponent(buildId, {
        category,
        component_id: alt.component_id,
        extra_component_id: alt.extra_component_id ?? null,
      }),
    onSuccess: (r) => nav(`/build/${r.build.id}`),
  });
}

export function ReplacePanel({ buildId, category }: { buildId: number; category: string }) {
  const [intent, setIntent] = useState<Intent>("cheaper");
  const q = useQuery({
    queryKey: ["alts", buildId, category, intent],
    queryFn: () => getAlternatives(buildId, category, intent),
  });
  const apply = useApplyAlternative(buildId, category);
  return (
    <div className="border-t border-line bg-bg/60 p-3" data-testid="replace-panel">
      <div className="mb-3 flex gap-2" role="tablist">
        {TABS.map(([k, label]) => (
          <button
            key={k}
            role="tab"
            aria-selected={intent === k}
            className={`chip ${intent === k ? "border-accent text-accent" : ""}`}
            onClick={() => setIntent(k)}
          >
            {label}
          </button>
        ))}
      </div>
      {q.isLoading && <div className="skeleton h-24 w-full" aria-busy="true" />}
      {q.isError && <ErrorBox message={q.error.message} onRetry={() => q.refetch()} />}
      {apply.isError && <ErrorBox message={apply.error.message} />}
      {q.data && q.data.length === 0 && (
        <Empty>Совместимых вариантов в этой категории не нашлось.</Empty>
      )}
      <div className="grid gap-3 sm:grid-cols-3">
        {q.data?.map((a) => (
          <AlternativeCard
            key={a.component_id}
            alt={a}
            disabled={apply.isPending}
            onApply={(alt) => apply.mutate(alt)}
          />
        ))}
      </div>
    </div>
  );
}
