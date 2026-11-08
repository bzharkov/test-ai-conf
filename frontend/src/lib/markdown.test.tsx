import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { keySpecs, pct, rub, signedRub } from "./format";
import { Markdown } from "./markdown";

describe("Markdown", () => {
  it("renders headings, lists, bold", () => {
    render(<Markdown text={"### Заголовок\nТекст **важно**\n\n- один\n- два"} />);
    expect(screen.getByText("Заголовок")).toBeTruthy();
    expect(screen.getByText("важно").tagName).toBe("STRONG");
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });
  it("never injects HTML", () => {
    const { container } = render(
      <Markdown text={'<img src=x onerror="alert(1)"> <script>1</script>'} />,
    );
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("script")).toBeNull();
    expect(container.textContent).toContain("<script>");
  });
});

describe("format", () => {
  it("formats rubles and deltas", () => {
    expect(rub(120000).replace(/\s/g, " ")).toBe("120 000 ₽");
    expect(rub(null)).toBe("—");
    expect(signedRub(-5000).startsWith("−")).toBe(true);
    expect(pct(-12.4)).toBe("−12%");
    expect(pct(null)).toBe("нет данных");
  });
  it("lists key specs by category", () => {
    expect(keySpecs("gpu", { vram_gb: 8, tdp_w: 115, zzz: 1 })).toBe("VRAM, ГБ: 8 · TDP, Вт: 115");
  });
});
