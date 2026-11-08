from __future__ import annotations

from app.domain import CATEGORY_RU, Component

_KEYS = {
    "cpu": ["socket", "cores", "threads", "boost_clock_ghz", "tdp_w", "has_igpu"],
    "motherboard": ["socket", "chipset", "form_factor", "memory_type", "m2_slots", "wifi"],
    "ram": ["type", "capacity_gb_total", "modules", "speed_mhz"],
    "gpu": ["chipset", "vram_gb", "length_mm", "tdp_w"],
    "storage": ["type", "interface", "capacity_gb"],
    "cpu_cooler": ["type", "height_mm", "radiator_mm", "tdp_rating_w"],
    "psu": ["wattage_w", "form_factor", "efficiency", "modular"],
    "case": ["supported_mb_form_factors", "max_gpu_length_mm", "max_cooler_height_mm"],
}


def make_search_text(category: str, brand: str, model: str, specs: dict) -> str:
    parts = [f"{CATEGORY_RU.get(category, category)} {brand} {model}"]
    for k in _KEYS.get(category, []):
        if specs.get(k) is not None:
            parts.append(f"{k}: {specs[k]}")
    return "; ".join(parts)


def component_search_text(c: Component) -> str:
    return make_search_text(c.category, c.brand, c.model, c.specs)
