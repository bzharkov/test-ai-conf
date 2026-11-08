import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { HealthBadge } from "./HealthBadge";

afterEach(() => vi.restoreAllMocks());

it("shows unavailable when API fails", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 500 }));
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <HealthBadge />
    </QueryClientProvider>,
  );
  expect(await screen.findByText("Сервис недоступен")).toBeTruthy();
});
