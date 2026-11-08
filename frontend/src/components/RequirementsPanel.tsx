import { useState } from "react";
import type { Requirements, UseCase } from "../api/types";
import { rub, USE_CASE_RU } from "../lib/format";

export function describeRequirements(r: Requirements): string {
  const parts: string[] = [];
  const uc = r.use_cases.map((u) => USE_CASE_RU[u] ?? u);
  parts.push(uc.join(" + "));
  if (r.gaming?.resolution) parts.push(r.gaming.resolution);
  parts.push(r.budget_rub ? `бюджет ${rub(r.budget_rub)}` : "бюджет не указан");
  const p = r.preferences;
  parts.push(p.wifi_required ? "Wi-Fi нужен" : "Wi-Fi не обязателен");
  if (p.form_factor !== "any") parts.push(p.form_factor === "mini_itx" ? "Mini-ITX" : "компактный");
  if (p.cpu_brand !== "any") parts.push(`CPU ${p.cpu_brand.toUpperCase()}`);
  if (p.no_discrete_gpu) parts.push("без дискретной видеокарты");
  return parts.join(", ");
}

const ALL: UseCase[] = [
  "gaming",
  "office",
  "video_editing",
  "3d_render",
  "programming",
  "study",
  "streaming",
  "ml",
];

interface Props {
  requirements: Requirements;
  busy: boolean;
  onRebuild: (r: Requirements) => void;
}

export function RequirementsPanel({ requirements, busy, onRebuild }: Props) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Requirements>(requirements);

  const open = () => {
    setDraft(structuredClone(requirements));
    setEditing(true);
  };
  const toggleUc = (u: UseCase) => {
    const has = draft.use_cases.includes(u);
    const next = has ? draft.use_cases.filter((x) => x !== u) : [...draft.use_cases, u];
    if (!next.length) return;
    setDraft({ ...draft, use_cases: next, primary_use_case: next[0] });
  };

  return (
    <section className="panel p-4" aria-label="Распознанные требования">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="text-sm">
          <span className="label mr-2">Я понял</span>
          {describeRequirements(requirements)}
        </p>
        {!editing && (
          <button className="btn" onClick={open}>
            Поправить
          </button>
        )}
      </div>
      {requirements.budget_assumed && (
        <p className="mt-1 text-xs text-warn">
          Бюджет не указан — использован бюджет по умолчанию.
        </p>
      )}
      {editing && (
        <form
          className="mt-4 grid gap-4 sm:grid-cols-2"
          onSubmit={(e) => {
            e.preventDefault();
            setEditing(false);
            onRebuild(draft);
          }}
        >
          <fieldset className="sm:col-span-2">
            <legend className="label mb-2">Задачи</legend>
            <div className="flex flex-wrap gap-2">
              {ALL.map((u) => (
                <label
                  key={u}
                  className={`chip cursor-pointer ${draft.use_cases.includes(u) ? "border-accent text-accent" : ""}`}
                >
                  <input
                    type="checkbox"
                    className="sr-only"
                    checked={draft.use_cases.includes(u)}
                    onChange={() => toggleUc(u)}
                  />
                  {USE_CASE_RU[u]}
                </label>
              ))}
            </div>
          </fieldset>
          <label className="block text-sm">
            <span className="label">Бюджет, ₽</span>
            <input
              type="number"
              min={10000}
              step={1000}
              className="mt-1 w-full rounded-sm border border-line bg-bg px-3 py-2"
              value={draft.budget_rub ?? ""}
              onChange={(e) =>
                setDraft({ ...draft, budget_rub: e.target.value ? Number(e.target.value) : null })
              }
            />
          </label>
          <label className="block text-sm">
            <span className="label">Разрешение (игры)</span>
            <select
              className="mt-1 w-full rounded-sm border border-line bg-bg px-3 py-2"
              value={draft.gaming?.resolution ?? ""}
              onChange={(e) =>
                setDraft({
                  ...draft,
                  gaming: {
                    titles: draft.gaming?.titles ?? [],
                    resolution: (e.target.value || null) as "1080p" | "1440p" | "4k" | null,
                  },
                })
              }
            >
              <option value="">не важно</option>
              <option value="1080p">1080p</option>
              <option value="1440p">1440p</option>
              <option value="4k">4K</option>
            </select>
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={draft.preferences.wifi_required}
              onChange={(e) =>
                setDraft({
                  ...draft,
                  preferences: { ...draft.preferences, wifi_required: e.target.checked },
                })
              }
            />
            Нужен Wi-Fi
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={draft.preferences.no_discrete_gpu}
              onChange={(e) =>
                setDraft({
                  ...draft,
                  preferences: { ...draft.preferences, no_discrete_gpu: e.target.checked },
                })
              }
            />
            Без видеокарты
          </label>
          <div className="flex gap-2 sm:col-span-2">
            <button type="submit" className="btn btn-primary" disabled={busy}>
              Пересобрать
            </button>
            <button type="button" className="btn" onClick={() => setEditing(false)}>
              Отмена
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
