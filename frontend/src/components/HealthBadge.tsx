import { useQuery } from "@tanstack/react-query";
import { getHealth } from "../api/client";

export function HealthBadge() {
  const { data, isError, isLoading } = useQuery({ queryKey: ["health"], queryFn: getHealth });
  if (isLoading) return <span>Проверяю сервис…</span>;
  if (isError || !data) return <span role="status">Сервис недоступен</span>;
  return (
    <span role="status">
      {data.status === "ok" ? "Сервис работает" : "Сервис работает частично"}
    </span>
  );
}
