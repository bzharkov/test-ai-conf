import { afterEach, describe, expect, it, vi } from "vitest";
import { sseResponse } from "../test-utils";
import { parseSSE, streamSSE } from "./sse";

afterEach(() => vi.unstubAllGlobals());

describe("parseSSE", () => {
  it("parses complete blocks and keeps the tail", () => {
    const { events, rest } = parseSSE(
      'event: token\ndata: {"text":"Привет"}\n\nevent: done\ndata: {',
    );
    expect(events).toEqual([{ event: "token", data: { text: "Привет" } }]);
    expect(rest).toBe("event: done\ndata: {");
  });
  it("handles CRLF and non-JSON data", () => {
    const { events } = parseSSE("event: x\r\ndata: plain\r\n\r\n");
    expect(events).toEqual([{ event: "x", data: "plain" }]);
  });
});

describe("streamSSE", () => {
  it("reassembles events split across chunks", async () => {
    const frame = 'event: token\ndata: {"text":"Ответ"}\n\n';
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(sseResponse([frame.slice(0, 15), frame.slice(15)])),
    );
    const got: unknown[] = [];
    await streamSSE("/x", {}, (e) => got.push(e.data));
    expect(got).toEqual([{ text: "Ответ" }]);
  });
  it("throws API error message on non-2xx", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ error: { message: "Слишком много запросов" } }), {
          status: 429,
        }),
      ),
    );
    await expect(streamSSE("/x", {}, () => {})).rejects.toThrow("Слишком много запросов");
  });
});
