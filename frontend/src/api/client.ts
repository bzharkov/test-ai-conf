import type {
  AlternativeOut,
  BuildOut,
  ChatMessageOut,
  CompareResponse,
  ConfigureFilters,
  ConfigureResponse,
  HistoryItem,
  Intent,
  ReplaceResponse,
  Requirements,
} from "./types";

const BASE = "/api/v1";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(BASE + path, {
    headers: { "content-type": "application/json" },
    ...init,
  });
  if (!resp.ok) {
    let code = "http_error";
    let message = `Ошибка ${resp.status}`;
    try {
      const j = await resp.json();
      code = j?.error?.code ?? code;
      message = j?.error?.message ?? message;
    } catch {
      /* non-JSON error */
    }
    throw new ApiError(resp.status, code, message);
  }
  return resp.json() as Promise<T>;
}

export interface Health {
  status: "ok" | "degraded";
  db: { ok: boolean };
  redis: { ok: boolean };
  llm: { ok: boolean };
  catalog_size: number | null;
}

export const getHealth = () => request<Health>("/health");

export const configure = (p: {
  text: string;
  session_id: string;
  filters?: ConfigureFilters;
  requirements?: Requirements;
}) => request<ConfigureResponse>("/configure", { method: "POST", body: JSON.stringify(p) });

export const getBuild = (id: number) => request<BuildOut>(`/builds/${id}`);

export const getAlternatives = (id: number, category: string, intent: Intent) =>
  request<AlternativeOut[]>(`/builds/${id}/alternatives?category=${category}&intent=${intent}`);

export const replaceComponent = (
  id: number,
  p: { category: string; component_id: number; extra_component_id?: number | null },
) => request<ReplaceResponse>(`/builds/${id}/replace`, { method: "POST", body: JSON.stringify(p) });

export const compareBuilds = (ids: number[]) =>
  request<CompareResponse>("/compare", {
    method: "POST",
    body: JSON.stringify({ build_ids: ids }),
  });

export const getHistory = (sessionId: string) =>
  request<HistoryItem[]>(`/history?session_id=${encodeURIComponent(sessionId)}`);

export const getChatHistory = (id: number) => request<ChatMessageOut[]>(`/builds/${id}/chat`);

export const explanationUrl = (id: number) => `${BASE}/builds/${id}/explanation/stream`;
export const chatUrl = (id: number) => `${BASE}/builds/${id}/chat`;
