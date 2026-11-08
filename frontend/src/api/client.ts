export interface Health {
  status: "ok" | "degraded";
  db: { ok: boolean };
  redis: { ok: boolean };
  llm: { ok: boolean };
  catalog_size: number | null;
}

export async function getHealth(): Promise<Health> {
  const r = await fetch("/api/v1/health");
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}
