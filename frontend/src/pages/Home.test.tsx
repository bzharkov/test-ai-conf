import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, renderApp } from "../test-utils";
import { Home } from "./Home";

const requirements = {
  use_cases: ["gaming"],
  primary_use_case: "gaming",
  budget_rub: 120000,
  budget_is_strict: true,
  gaming: { resolution: "1440p", titles: [] },
  preferences: {
    cpu_brand: "any",
    gpu_brand: "any",
    form_factor: "any",
    wifi_required: false,
    quiet: false,
    rgb: false,
    no_discrete_gpu: false,
  },
  must_include: [],
  exclude: [],
  confidence: 0.9,
  budget_assumed: false,
};
const mk = (id: number, label: string, price: number) => ({
  id,
  label,
  total_price: price,
  budget_rub: 120000,
  budget_share: price / 120000,
  over_budget: false,
  compat_ok: true,
  prices_are_demo: true,
  key_components: { cpu: "CPU " + id, gpu: "GPU " + id, ram: "RAM", storage: "SSD" },
  warnings: [],
});

beforeEach(() => sessionStorage.clear());
afterEach(() => vi.unstubAllGlobals());

describe("Home", () => {
  it("runs a query from an example chip and shows requirements + 3 cards", async () => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.includes("/history")) return json([]);
      expect(url).toContain("/configure");
      expect(JSON.parse(String(init?.body)).text).toBe("Игры в 1440p до 120 000 ₽");
      return json({
        request_id: 1,
        requirements,
        warnings: [{ code: "llm_unavailable", message_ru: "ИИ-разбор недоступен" }],
        builds: [
          mk(1, "Оптимальная", 118000),
          mk(2, "Экономичная", 80000),
          mk(3, "Максимум за бюджет", 119000),
        ],
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    renderApp(<Home />);
    fireEvent.click(screen.getByRole("button", { name: "Игры в 1440p до 120 000 ₽" }));
    await waitFor(() => expect(screen.getAllByTestId("build-card")).toHaveLength(3));
    expect(screen.getByText(/ИИ-разбор недоступен/)).toBeTruthy();
    expect(screen.getByText(/игры, 1440p, бюджет/)).toBeTruthy();
    expect(screen.getByText("Максимум за бюджет")).toBeTruthy();
  });

  it("shows an error box with retry when the API fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) =>
        url.includes("/history")
          ? json([])
          : json({ error: { code: "rate_limited", message: "Слишком много запросов" } }, 429),
      ),
    );
    renderApp(<Home />);
    fireEvent.change(screen.getByLabelText("Опишите, какой ПК нужен"), {
      target: { value: "офисный пк до 40000" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Подобрать" }));
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByText("Слишком много запросов")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Повторить" })).toBeTruthy();
  });

  it("does not submit text shorter than 3 chars", () => {
    const f = vi.fn();
    vi.stubGlobal("fetch", f);
    renderApp(<Home />);
    fireEvent.change(screen.getByLabelText("Опишите, какой ПК нужен"), { target: { value: "а" } });
    fireEvent.click(screen.getByRole("button", { name: "Подобрать" }));
    expect(f.mock.calls.filter((c) => String(c[0]).includes("configure"))).toHaveLength(0);
  });
});
