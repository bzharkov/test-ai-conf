export interface SSEEvent {
  event: string;
  data: unknown;
}

/** Parse as many complete SSE blocks as possible; return the unconsumed tail. */
export function parseSSE(buffer: string): { events: SSEEvent[]; rest: string } {
  const normalized = buffer.replace(/\r\n/g, "\n");
  const parts = normalized.split("\n\n");
  const rest = parts.pop() ?? "";
  const events: SSEEvent[] = [];
  for (const block of parts) {
    let event = "message";
    const dataLines: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
    }
    if (!dataLines.length) continue;
    const raw = dataLines.join("\n");
    try {
      events.push({ event, data: JSON.parse(raw) });
    } catch {
      events.push({ event, data: raw });
    }
  }
  return { events, rest };
}

/** fetch + ReadableStream SSE reader (works for POST, unlike EventSource). */
export async function streamSSE(
  url: string,
  init: RequestInit,
  onEvent: (e: SSEEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const resp = await fetch(url, { ...init, signal });
  if (!resp.ok || !resp.body) {
    let message = `HTTP ${resp.status}`;
    try {
      const j = await resp.json();
      message = j?.error?.message ?? message;
    } catch {
      /* ignore */
    }
    throw new Error(message);
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const { events, rest } = parseSSE(buf);
    buf = rest;
    events.forEach(onEvent);
  }
  if (buf.trim()) parseSSE(buf + "\n\n").events.forEach(onEvent);
}
