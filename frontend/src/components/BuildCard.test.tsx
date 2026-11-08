import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { BuildSummary } from "../api/types";
import { renderApp } from "../test-utils";
import { BuildCard } from "./BuildCard";

const build: BuildSummary = {
  id: 7,
  label: "Оптимальная",
  total_price: 118600,
  budget_rub: 120000,
  budget_share: 0.988,
  over_budget: false,
  compat_ok: true,
  prices_are_demo: true,
  key_components: { cpu: "AMD Ryzen 5 7600", gpu: null, ram: "32GB DDR5", storage: "NV2 1TB" },
  warnings: [{ code: "x", message_ru: "Что-то важное" }],
};

describe("BuildCard", () => {
  it("shows price, share, badge, demo note and links to details", () => {
    renderApp(<BuildCard build={build} selected={false} onToggleCompare={() => {}} />);
    expect(screen.getByText(/118\s?600/)).toBeTruthy();
    expect(screen.getByText(/99% от бюджета/)).toBeTruthy();
    expect(screen.getByText("Совместимость проверена ✓")).toBeTruthy();
    expect(screen.getByText(/ориентировочные \(демо\)/)).toBeTruthy();
    expect(screen.getByText("встроенная графика")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Подробнее" }).getAttribute("href")).toBe("/build/7");
    expect(screen.getByText(/Что-то важное/)).toBeTruthy();
  });
  it("toggles compare", () => {
    const fn = vi.fn();
    renderApp(<BuildCard build={build} selected={false} onToggleCompare={fn} />);
    fireEvent.click(screen.getByRole("button", { name: "Сравнить" }));
    expect(fn).toHaveBeenCalledWith(7);
  });
});
