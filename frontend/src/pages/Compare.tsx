import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { compareBuilds } from "../api/client";
import { Empty, ErrorBox } from "../components/ui";
import { rub } from "../lib/format";
import { toggleCompare, useCompareIds } from "../lib/storage";

export function Compare() {
  const [params] = useSearchParams();
  const stored = useCompareIds();
  const fromUrl = (params.get("ids") ?? "")
    .split(",")
    .map(Number)
    .filter((n) => n > 0);
  const ids = fromUrl.length ? fromUrl : stored;
  const q = useQuery({
    queryKey: ["compare", ids],
    queryFn: () => compareBuilds(ids),
    enabled: ids.length >= 2 && ids.length <= 3,
  });

  if (ids.length < 2)
    return (
      <Empty>
        Выберите минимум две сборки кнопкой «Сравнить» на карточках.{" "}
        <Link to="/" className="text-accent underline">
          К подбору
        </Link>
      </Empty>
    );
  if (q.isLoading) return <div className="skeleton h-64 w-full" aria-busy="true" />;
  if (q.isError) return <ErrorBox message={q.error.message} onRetry={() => q.refetch()} />;
  const d = q.data!;
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Сравнение сборок</h1>
      <div className="panel overflow-x-auto">
        <table className="w-full min-w-[34rem] text-left text-sm">
          <thead>
            <tr className="border-b border-line">
              <th className="label p-3">Категория</th>
              {d.builds.map((b) => (
                <th key={b.id} className="p-3 align-top">
                  <Link to={`/build/${b.id}`} className="hover:text-accent">
                    {b.label}
                  </Link>
                  <button
                    className="label ml-2 hover:text-bad"
                    aria-label={`Убрать сборку ${b.label}`}
                    onClick={() => toggleCompare(b.id)}
                  >
                    ✕
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {d.rows.map((r) => (
              <tr key={r.category} className="border-b border-line/60 align-top">
                <th scope="row" className="label p-3">
                  {r.category_ru}
                </th>
                {r.cells.map((c, i) => (
                  <td
                    key={i}
                    className={`p-3 ${r.differs ? "bg-accent/10" : ""}`}
                    data-differs={r.differs}
                  >
                    <div className="break-words">{c.name ?? "—"}</div>
                    <div className="font-mono text-xs text-mute">{rub(c.price_rub)}</div>
                  </td>
                ))}
              </tr>
            ))}
            <tr className="border-b border-line/60">
              <th scope="row" className="label p-3">
                Итого
              </th>
              {d.totals.map((t, i) => (
                <td key={i} className="p-3 font-mono font-semibold">
                  {rub(t)}
                </td>
              ))}
            </tr>
            <tr>
              <th scope="row" className="label p-3">
                Потребление
              </th>
              {d.power_w.map((w, i) => (
                <td key={i} className="p-3 font-mono">
                  ~{w} Вт
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
      <p className="text-xs text-mute">Отличающиеся категории подсвечены.</p>
    </div>
  );
}
