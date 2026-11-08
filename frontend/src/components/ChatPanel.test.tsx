import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { json, renderApp, sseResponse } from "../test-utils";
import { ChatPanel } from "./ChatPanel";

afterEach(() => vi.unstubAllGlobals());

const alt = {
  component_id: 66,
  name: "Intel Arc B580 Limited Edition",
  category: "gpu",
  price_rub: 26000,
  price_delta_rub: -26000,
  total_delta_rub: -26000,
  perf_delta_pct: -39.5,
  compat_ok: true,
  notes: [],
  extra_component_id: null,
  extra_component_name: null,
};

describe("ChatPanel", () => {
  it("streams tokens and renders alternative cards with Apply", async () => {
    const calls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        calls.push(`${init?.method ?? "GET"} ${url}`);
        if (url.endsWith("/chat") && init?.method === "POST")
          return sseResponse([
            `event: alternatives\ndata: ${JSON.stringify({ category: "gpu", intent: "cheaper", items: [alt] })}\n\n`,
            'event: token\ndata: {"text":"Вот "}\n\n',
            'event: token\ndata: {"text":"варианты"}\n\n',
            'event: done\ndata: {"text":"Вот варианты замены.","source":"llm"}\n\n',
          ]);
        if (url.includes("/replace")) return json({ build: { id: 99 }, replaced: {} });
        return json([]);
      }),
    );
    renderApp(<ChatPanel buildId={5} />);
    fireEvent.change(screen.getByLabelText("Сообщение"), {
      target: { value: "чем заменить видеокарту подешевле?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Отправить" }));
    expect(await screen.findByText("Вот варианты замены.")).toBeTruthy();
    expect(screen.getByText("Intel Arc B580 Limited Edition")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Применить" }));
    await waitFor(() =>
      expect(calls.some((c) => c.startsWith("POST") && c.includes("/replace"))).toBe(true),
    );
  });

  it("replaces the streamed text when the server sends a corrected version", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) =>
        init?.method === "POST"
          ? sseResponse([
              'event: token\ndata: {"text":"Возьмите RTX 5090"}\n\n',
              'event: replace\ndata: {"text":"Остаёмся на текущей."}\n\n',
              'event: done\ndata: {"text":"Остаёмся на текущей.","source":"llm"}\n\n',
            ])
          : json([]),
      ),
    );
    renderApp(<ChatPanel buildId={5} />);
    fireEvent.change(screen.getByLabelText("Сообщение"), { target: { value: "привет" } });
    fireEvent.click(screen.getByRole("button", { name: "Отправить" }));
    expect(await screen.findByText("Остаёмся на текущей.")).toBeTruthy();
    expect(screen.queryByText(/5090/)).toBeNull();
  });

  it("shows an error when the stream fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_u: string, init?: RequestInit) =>
        init?.method === "POST"
          ? new Response(JSON.stringify({ error: { message: "Слишком много запросов" } }), {
              status: 429,
            })
          : json([]),
      ),
    );
    renderApp(<ChatPanel buildId={5} />);
    fireEvent.change(screen.getByLabelText("Сообщение"), { target: { value: "привет" } });
    fireEvent.click(screen.getByRole("button", { name: "Отправить" }));
    expect(await screen.findByRole("alert")).toBeTruthy();
  });
});
