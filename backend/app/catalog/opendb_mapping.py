"""Mapping BuildCores OpenDB records -> our component schema (TZ 5.5).

Field names were taken from the real files in open-db/ (checked 2026-11):
CPU: socket, cores.{total,threads}, clocks.performance.{base,boost}, specifications.tdp,
     specifications.integratedGraphics.model, specifications.memory.types, metadata.releaseYear
Motherboard: socket, form_factor, chipset, memory.{max,ram_type,slots}, m2_slots[],
     storage_devices.{sata_6_gb_s,sata_3_gb_s}   (no Wi-Fi flag: inferred from the name)
RAM: ram_type, speed, modules.quantity, capacity (total GB)
GPU: chipset, memory (GB), length, tdp, total_slot_width     (no recommended PSU field)
Storage: capacity (GB), storage_type, nvme, form_factor, interface
CPUCooler: water_cooled, radiator_size, height, cpu_sockets[]
PSU: wattage, form_factor, efficiency_rating, modular
PCCase: supported_motherboard_form_factors[], supported_power_supply_form_factors[],
     max_video_card_length, max_cpu_cooler_height, internal_2_5_bays, internal_3_5_bays
     (no radiator-support field -> radiator_support_mm = None = unknown)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

DIRS = {
    "cpu": "CPU",
    "motherboard": "Motherboard",
    "ram": "RAM",
    "gpu": "GPU",
    "storage": "Storage",
    "cpu_cooler": "CPUCooler",
    "psu": "PSU",
    "case": "PCCase",
}
MIN_CPU_YEAR = 2020


class Rejected(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class Mapped:
    category: str
    brand: str
    model: str
    name: str
    specs: dict[str, Any]
    source_ref: str

    def as_row(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "brand": self.brand,
            "model": self.model,
            "name": self.name,
            "specs": self.specs,
            "source": "opendb",
            "source_ref": self.source_ref,
        }


def norm_socket(s: str | None) -> str | None:
    if not s:
        return None
    s = re.sub(r"^socket\s*", "", s.strip(), flags=re.I)
    return re.sub(r"\s+", "", s).upper().replace("LGA", "LGA")


_MB_FF = {
    "atx": "ATX",
    "micro atx": "mATX",
    "matx": "mATX",
    "mini-itx": "Mini-ITX",
    "mini itx": "Mini-ITX",
    "eatx": "E-ATX",
    "e-atx": "E-ATX",
    "extended atx": "E-ATX",
}


def norm_ff(s: str | None) -> str | None:
    return _MB_FF.get((s or "").strip().lower())


def _meta(d: dict) -> tuple[str, str, str]:
    m = d.get("metadata") or {}
    name = (m.get("name") or "").strip()
    brand = (m.get("manufacturer") or "").strip()
    if not name or not brand:
        raise Rejected("no_name_or_brand")
    model = re.sub(rf"^{re.escape(brand)}\s+", "", name, flags=re.I).strip() or name
    return brand, model, name


def _pos(v: Any) -> float | None:
    return float(v) if isinstance(v, (int, float)) and v > 0 else None


def map_cpu(d: dict) -> Mapped:
    brand, model, name = _meta(d)
    year = (d.get("metadata") or {}).get("releaseYear")
    if not year or year < MIN_CPU_YEAR:
        raise Rejected("too_old_or_no_year")
    sock = norm_socket(d.get("socket"))
    cores = d.get("cores") or {}
    perf = (d.get("clocks") or {}).get("performance") or {}
    sp = d.get("specifications") or {}
    tdp = _pos(sp.get("tdp"))
    types = (sp.get("memory") or {}).get("types") or []
    if not sock or not _pos(cores.get("total")) or not tdp or not types:
        raise Rejected("missing_critical_fields")
    igpu = (sp.get("integratedGraphics") or {}).get("model")
    return Mapped(
        "cpu",
        brand,
        model,
        name,
        {
            "socket": sock,
            "cores": int(cores["total"]),
            "threads": int(cores.get("threads") or cores["total"]),
            "base_clock_ghz": _pos(perf.get("base")),
            "boost_clock_ghz": _pos(perf.get("boost")),
            "tdp_w": tdp,
            "has_igpu": bool(igpu) and str(igpu).lower() != "none",
            "memory_types": list(types),
        },
        d["opendb_id"],
    )


def map_motherboard(d: dict) -> Mapped:
    brand, model, name = _meta(d)
    ff = norm_ff(d.get("form_factor"))
    mem = d.get("memory") or {}
    sock = norm_socket(d.get("socket"))
    if mem.get("ram_type") not in ("DDR4", "DDR5"):
        raise Rejected("old_memory_type")
    if not ff:
        raise Rejected("unsupported_form_factor")
    if not sock or not _pos(mem.get("slots")) or not _pos(mem.get("max")):
        raise Rejected("missing_critical_fields")
    sd = d.get("storage_devices") or {}
    return Mapped(
        "motherboard",
        brand,
        model,
        name,
        {
            "socket": sock,
            "chipset": d.get("chipset"),
            "form_factor": ff,
            "memory_type": mem["ram_type"],
            "memory_slots": int(mem["slots"]),
            "max_memory_gb": int(mem["max"]),
            "m2_slots": len(d.get("m2_slots") or []),
            "sata_ports": int(sd.get("sata_6_gb_s") or 0) + int(sd.get("sata_3_gb_s") or 0),
            "wifi": bool(re.search(r"wi-?fi|wireless|\bax\b", name, re.I)),
            "wifi_inferred": True,
        },
        d["opendb_id"],
    )


def map_ram(d: dict) -> Mapped:
    brand, model, name = _meta(d)
    t = d.get("ram_type")
    mods = d.get("modules") or {}
    if t not in ("DDR4", "DDR5"):
        raise Rejected("old_memory_type")
    if not _pos(d.get("capacity")) or not _pos(mods.get("quantity")):
        raise Rejected("missing_critical_fields")
    if d.get("ecc") not in (None, "Non-ECC") or d.get("registered") not in (None, "Unbuffered"):
        raise Rejected("server_memory")
    return Mapped(
        "ram",
        brand,
        model,
        name,
        {
            "type": t,
            "capacity_gb_total": int(d["capacity"]),
            "modules": int(mods["quantity"]),
            "speed_mhz": d.get("speed"),
        },
        d["opendb_id"],
    )


_MODERN_GPU = re.compile(r"(RTX\s*[2-5]0\d0|GTX\s*16\d0|RX\s*[5-9]\d{3}|Arc\s*[AB]\d{3})", re.I)


def map_gpu(d: dict) -> Mapped:
    brand, model, name = _meta(d)
    chipset = d.get("chipset") or ""
    if not _MODERN_GPU.search(chipset):
        raise Rejected("old_or_unsupported_chipset")
    if not _pos(d.get("length")) or not _pos(d.get("tdp")) or not _pos(d.get("memory")):
        raise Rejected("missing_critical_fields")
    return Mapped(
        "gpu",
        brand,
        model,
        name,
        {
            "chipset": chipset,
            "vram_gb": d["memory"],
            "length_mm": d["length"],
            "tdp_w": d["tdp"],
            "slots": d.get("total_slot_width"),
            "recommended_psu_w": None,
        },
        d["opendb_id"],
    )


def map_storage(d: dict) -> Mapped:
    brand, model, name = _meta(d)
    ff_raw = d.get("form_factor") or ""
    if ff_raw.startswith("M.2"):
        ff = "M.2"
    elif ff_raw.startswith("2.5"):
        ff = "2.5"
    elif ff_raw.startswith("3.5"):
        ff = "3.5"
    else:
        raise Rejected("unsupported_form_factor")
    itf = d.get("interface") or ""
    if itf.startswith("SAS"):
        raise Rejected("sas_drive")
    st = d.get("storage_type")
    if st in ("HDD", "SSHD"):
        typ = "hdd"
    elif d.get("nvme"):
        typ = "nvme"
    elif st == "SSD":
        typ = "sata_ssd"
    else:
        raise Rejected("unknown_storage_type")
    cap = _pos(d.get("capacity"))
    if not cap:
        raise Rejected("missing_critical_fields")
    return Mapped(
        "storage",
        brand,
        model,
        name,
        {"type": typ, "interface": itf, "form_factor": ff, "capacity_gb": int(cap)},
        d["opendb_id"],
    )


def map_cooler(d: dict) -> Mapped:
    brand, model, name = _meta(d)
    socks = sorted({s for s in (norm_socket(x) for x in d.get("cpu_sockets") or []) if s})
    if not socks:
        raise Rejected("missing_critical_fields")
    if d.get("water_cooled"):
        rad = _pos(d.get("radiator_size"))
        if not rad:
            raise Rejected("missing_critical_fields")
        typ, height, radiator = "aio", None, int(rad)
    else:
        h = _pos(d.get("height"))
        if not h:
            raise Rejected("missing_critical_fields")
        typ, height, radiator = "air", h, None
    return Mapped(
        "cpu_cooler",
        brand,
        model,
        name,
        {
            "type": typ,
            "sockets": socks,
            "height_mm": height,
            "radiator_mm": radiator,
            "tdp_rating_w": None,
        },
        d["opendb_id"],
    )


def map_psu(d: dict) -> Mapped:
    brand, model, name = _meta(d)
    ff = d.get("form_factor")
    if ff not in ("ATX", "SFX"):
        raise Rejected("unsupported_form_factor")
    if not _pos(d.get("wattage")):
        raise Rejected("missing_critical_fields")
    return Mapped(
        "psu",
        brand,
        model,
        name,
        {
            "wattage_w": int(d["wattage"]),
            "form_factor": ff,
            "efficiency": d.get("efficiency_rating"),
            "modular": d.get("modular") not in (None, "Non-Modular"),
        },
        d["opendb_id"],
    )


def map_case(d: dict) -> Mapped:
    brand, model, name = _meta(d)
    ffs = sorted(
        {f for f in (norm_ff(x) for x in d.get("supported_motherboard_form_factors") or []) if f}
    )
    psus = d.get("supported_power_supply_form_factors") or []
    psu_ff = "ATX" if "ATX" in psus else ("SFX" if "SFX" in psus else None)
    if (
        not ffs
        or not psu_ff
        or not _pos(d.get("max_video_card_length"))
        or not _pos(d.get("max_cpu_cooler_height"))
    ):
        raise Rejected("missing_critical_fields")
    return Mapped(
        "case",
        brand,
        model,
        name,
        {
            "supported_mb_form_factors": ffs,
            "max_gpu_length_mm": d["max_video_card_length"],
            "max_cooler_height_mm": d["max_cpu_cooler_height"],
            "psu_form_factor": psu_ff,
            "radiator_support_mm": None,
            "bays_2_5": d.get("internal_2_5_bays"),
            "bays_3_5": d.get("internal_3_5_bays"),
        },
        d["opendb_id"],
    )


MAPPERS = {
    "cpu": map_cpu,
    "motherboard": map_motherboard,
    "ram": map_ram,
    "gpu": map_gpu,
    "storage": map_storage,
    "cpu_cooler": map_cooler,
    "psu": map_psu,
    "case": map_case,
}
