import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Requirements } from "../api/types";
import { renderApp } from "../test-utils";
import { RequirementsPanel, describeRequirements } from "./RequirementsPanel";

const req = {
  use_cases: ["gaming"],
  primary_use_case: "gaming",
  budget_rub: null,
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
  confidence: 0.5,
  budget_assumed: true,
} as Requirements;

describe("RequirementsPanel", () => {
  it("describes requirements incl. missing budget", () => {
    expect(describeRequirements(req)).toContain("бюджет не указан");
    expect(describeRequirements(req)).toContain("Wi-Fi не обязателен");
  });
  it("lets the user edit and rebuild", () => {
    const onRebuild = vi.fn();
    renderApp(<RequirementsPanel requirements={req} busy={false} onRebuild={onRebuild} />);
    fireEvent.click(screen.getByRole("button", { name: "Поправить" }));
    fireEvent.change(screen.getByLabelText("Бюджет, ₽"), { target: { value: "90000" } });
    fireEvent.click(screen.getByLabelText("Нужен Wi-Fi"));
    fireEvent.click(screen.getByRole("button", { name: "Пересобрать" }));
    const sent = onRebuild.mock.calls[0][0] as Requirements;
    expect(sent.budget_rub).toBe(90000);
    expect(sent.preferences.wifi_required).toBe(true);
  });
});
