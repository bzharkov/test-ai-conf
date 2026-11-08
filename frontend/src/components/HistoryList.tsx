import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { getHistory } from "../api/client";
import { rub } from "../lib/format";
import { getSessionId } from "../lib/storage";
import { Empty, ErrorBox } from "./ui";

export function HistoryList({ compact = false }: { compact?: boolean }) {
  const sid = getSessionId();
  const q = useQuery({ queryKey: ["history", sid], queryFn: () => getHistory(sid) });
  if (q.isLoading) return <div className="skeleton h-24 w-full" aria-busy="true" />;
  if (q.isError)
    return <ErrorBox message="Не удалось загрузить историю" onRetry={() => q.refetch()} />;
  if (!q.data?.length) return <Empty>Пока нет запросов. Опишите задачу на главной странице.</Empty>;
  return (
    <ul className="space-y-2">
      {q.data.slice(0, compact ? 6 : 50).map((h) => (
        <li key={h.request_id} className="panel p-3 text-sm">
          <p className="line-clamp-2 break-words">{h.text}</p>
          <p className="label mt-1">{new Date(h.created_at).toLocaleString("ru-RU")}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {h.builds.map((b) => (
              <Link key={b.id} to={`/build/${b.id}`} className="chip">
                {b.label} · {rub(b.total_price)}
              </Link>
            ))}
          </div>
        </li>
      ))}
    </ul>
  );
}
