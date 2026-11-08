"""Compatibility rules (TZ section 6). Each rule is a pure function Build -> list[Issue]."""

from __future__ import annotations

from collections.abc import Callable

from app.domain import Build, Component, Issue
from app.power.calc import calculate_power

RuleFn = Callable[[Build], list[Issue]]


def _missing(code: str, *pairs: tuple[Component, str]) -> list[Issue]:
    gaps = [(c, f) for c, f in pairs if c.specs.get(f) is None]
    if not gaps:
        return []
    names = tuple(sorted({c.name for c, _ in gaps}))
    fields = ", ".join(sorted({f"{c.category}.{f}" for c, f in gaps}))
    return [
        Issue("MISSING_DATA", "warning", f"Не хватает данных для проверки {code}: {fields}.", names)
    ]


def _err(code: str, msg: str, *comps: Component) -> Issue:
    return Issue(code, "error", msg, tuple(c.name for c in comps))


def check_cpu_mb_socket(b: Build) -> list[Issue]:
    if not (b.cpu and b.motherboard):
        return []
    if m := _missing("CPU_MB_SOCKET", (b.cpu, "socket"), (b.motherboard, "socket")):
        return m
    if b.cpu.spec("socket") != b.motherboard.spec("socket"):
        return [
            _err(
                "CPU_MB_SOCKET",
                f"Сокет процессора ({b.cpu.spec('socket')}) не совпадает с сокетом "
                f"платы ({b.motherboard.spec('socket')}).",
                b.cpu,
                b.motherboard,
            )
        ]
    return []


def check_ram_mb_type(b: Build) -> list[Issue]:
    out: list[Issue] = []
    if b.ram and b.motherboard:
        if m := _missing("RAM_MB_TYPE", (b.ram, "type"), (b.motherboard, "memory_type")):
            out += m
        elif b.ram.spec("type") != b.motherboard.spec("memory_type"):
            out.append(
                _err(
                    "RAM_MB_TYPE",
                    f"Память {b.ram.spec('type')} не подходит к плате "
                    f"({b.motherboard.spec('memory_type')}).",
                    b.ram,
                    b.motherboard,
                )
            )
    if b.ram and b.cpu:
        if m := _missing("RAM_MB_TYPE", (b.ram, "type"), (b.cpu, "memory_types")):
            out += m
        elif b.ram.spec("type") not in b.cpu.spec("memory_types"):
            out.append(
                _err(
                    "RAM_MB_TYPE",
                    f"Процессор не поддерживает память {b.ram.spec('type')}.",
                    b.ram,
                    b.cpu,
                )
            )
    return out


def check_ram_slots(b: Build) -> list[Issue]:
    if not (b.ram and b.motherboard):
        return []
    if m := _missing("RAM_SLOTS", (b.ram, "modules"), (b.motherboard, "memory_slots")):
        return m
    if b.ram.spec("modules") > b.motherboard.spec("memory_slots"):
        return [
            _err("RAM_SLOTS", "Модулей памяти больше, чем слотов на плате.", b.ram, b.motherboard)
        ]
    return []


def check_ram_max(b: Build) -> list[Issue]:
    if not (b.ram and b.motherboard):
        return []
    if m := _missing("RAM_MAX", (b.ram, "capacity_gb_total"), (b.motherboard, "max_memory_gb")):
        return m
    if b.ram.spec("capacity_gb_total") > b.motherboard.spec("max_memory_gb"):
        return [
            _err(
                "RAM_MAX",
                "Объём памяти превышает максимум, поддерживаемый платой.",
                b.ram,
                b.motherboard,
            )
        ]
    return []


def check_mb_case_ff(b: Build) -> list[Issue]:
    if not (b.motherboard and b.case):
        return []
    if m := _missing(
        "MB_CASE_FF", (b.motherboard, "form_factor"), (b.case, "supported_mb_form_factors")
    ):
        return m
    if b.motherboard.spec("form_factor") not in b.case.spec("supported_mb_form_factors"):
        return [
            _err(
                "MB_CASE_FF",
                f"Плата формата {b.motherboard.spec('form_factor')} не помещается в корпус.",
                b.motherboard,
                b.case,
            )
        ]
    return []


def check_gpu_case_len(b: Build) -> list[Issue]:
    if not (b.gpu and b.case):
        return []
    if m := _missing("GPU_CASE_LEN", (b.gpu, "length_mm"), (b.case, "max_gpu_length_mm")):
        return m
    if b.gpu.spec("length_mm") > b.case.spec("max_gpu_length_mm"):
        return [
            _err(
                "GPU_CASE_LEN",
                f"Видеокарта ({b.gpu.spec('length_mm')} мм) длиннее допустимого для корпуса "
                f"({b.case.spec('max_gpu_length_mm')} мм).",
                b.gpu,
                b.case,
            )
        ]
    return []


def check_cooler_socket(b: Build) -> list[Issue]:
    if not (b.cpu and b.cpu_cooler):
        return []
    if m := _missing("COOLER_SOCKET", (b.cpu, "socket"), (b.cpu_cooler, "sockets")):
        return m
    if b.cpu.spec("socket") not in b.cpu_cooler.spec("sockets"):
        return [
            _err(
                "COOLER_SOCKET",
                f"Кулер не поддерживает сокет {b.cpu.spec('socket')}.",
                b.cpu,
                b.cpu_cooler,
            )
        ]
    return []


def check_cooler_height(b: Build) -> list[Issue]:
    if not (b.cpu_cooler and b.case) or b.cpu_cooler.spec("type") != "air":
        return []
    if m := _missing(
        "COOLER_HEIGHT", (b.cpu_cooler, "height_mm"), (b.case, "max_cooler_height_mm")
    ):
        return m
    if b.cpu_cooler.spec("height_mm") > b.case.spec("max_cooler_height_mm"):
        return [
            _err(
                "COOLER_HEIGHT", "Башенный кулер выше, чем допускает корпус.", b.cpu_cooler, b.case
            )
        ]
    return []


def check_aio_radiator(b: Build) -> list[Issue]:
    if not (b.cpu_cooler and b.case) or b.cpu_cooler.spec("type") != "aio":
        return []
    if m := _missing(
        "AIO_RADIATOR", (b.cpu_cooler, "radiator_mm"), (b.case, "radiator_support_mm")
    ):
        return m
    if b.cpu_cooler.spec("radiator_mm") not in b.case.spec("radiator_support_mm"):
        return [
            _err(
                "AIO_RADIATOR",
                f"Корпус не поддерживает радиатор {b.cpu_cooler.spec('radiator_mm')} мм.",
                b.cpu_cooler,
                b.case,
            )
        ]
    return []


def check_cooler_tdp(b: Build) -> list[Issue]:
    if not (b.cpu and b.cpu_cooler):
        return []
    rating, tdp = b.cpu_cooler.spec("tdp_rating_w"), b.cpu.spec("tdp_w")
    if rating is None or tdp is None:
        return []  # rating unknown: rule is skipped by definition
    if rating < tdp:
        return [
            Issue(
                "COOLER_TDP",
                "warning",
                f"Заявленный теплоотвод кулера ({rating} Вт) ниже TDP процессора ({tdp} Вт).",
                (b.cpu_cooler.name, b.cpu.name),
            )
        ]
    return []


def check_psu_case_ff(b: Build) -> list[Issue]:
    if not (b.psu and b.case):
        return []
    if m := _missing("PSU_CASE_FF", (b.psu, "form_factor"), (b.case, "psu_form_factor")):
        return m
    psu_ff, case_ff = b.psu.spec("form_factor"), b.case.spec("psu_form_factor")
    ok = psu_ff == case_ff or (psu_ff == "SFX" and case_ff == "ATX")
    if not ok:
        return [
            _err(
                "PSU_CASE_FF",
                f"БП формата {psu_ff} не подходит к корпусу ({case_ff}).",
                b.psu,
                b.case,
            )
        ]
    return []


def check_psu_power(b: Build) -> list[Issue]:
    if not (b.psu and b.cpu):
        return []
    if m := _missing("PSU_POWER", (b.psu, "wattage_w"), (b.cpu, "tdp_w")):
        return m
    rec = calculate_power(b).psu_recommended_w
    if b.psu.spec("wattage_w") < rec:
        return [
            _err(
                "PSU_POWER",
                f"Мощности БП ({b.psu.spec('wattage_w')} Вт) недостаточно, "
                f"рекомендуется от {rec} Вт.",
                b.psu,
            )
        ]
    return []


def check_no_video(b: Build) -> list[Issue]:
    if b.cpu is None or b.gpu is not None:
        return []
    if b.cpu.spec("has_igpu") is None:
        return _missing("NO_VIDEO", (b.cpu, "has_igpu"))
    if not b.cpu.spec("has_igpu"):
        return [_err("NO_VIDEO", "Нет видеокарты, а у процессора нет встроенной графики.", b.cpu)]
    return []


def check_m2_slots(b: Build) -> list[Issue]:
    if not b.motherboard:
        return []
    nvme = [d for d in b.storage if d.spec("type") == "nvme" or d.spec("form_factor") == "M.2"]
    if not nvme:
        return []
    if m := _missing("M2_SLOTS", (b.motherboard, "m2_slots")):
        return m
    if len(nvme) > b.motherboard.spec("m2_slots"):
        return [
            _err(
                "M2_SLOTS", "M.2-накопителей больше, чем M.2-слотов на плате.", b.motherboard, *nvme
            )
        ]
    return []


def check_drive_bays(b: Build) -> list[Issue]:
    if not b.case or not b.storage:
        return []
    bays25, bays35 = b.case.spec("bays_2_5"), b.case.spec("bays_3_5")
    out: list[Issue] = []
    n25 = sum(1 for d in b.storage if d.spec("form_factor") == "2.5")
    n35 = sum(1 for d in b.storage if d.spec("form_factor") == "3.5")
    if bays25 is not None and n25 > bays25:
        out.append(
            Issue("DRIVE_BAYS", "warning", "Не хватает отсеков 2.5″ в корпусе.", (b.case.name,))
        )
    if bays35 is not None and n35 > bays35:
        out.append(
            Issue("DRIVE_BAYS", "warning", "Не хватает отсеков 3.5″ в корпусе.", (b.case.name,))
        )
    return out


RULES: list[tuple[str, str, RuleFn]] = [
    ("CPU_MB_SOCKET", "Сокет процессора и платы", check_cpu_mb_socket),
    ("RAM_MB_TYPE", "Тип памяти (плата и процессор)", check_ram_mb_type),
    ("RAM_SLOTS", "Число модулей памяти и слотов", check_ram_slots),
    ("RAM_MAX", "Максимальный объём памяти", check_ram_max),
    ("MB_CASE_FF", "Форм-фактор платы и корпуса", check_mb_case_ff),
    ("GPU_CASE_LEN", "Длина видеокарты и корпус", check_gpu_case_len),
    ("COOLER_SOCKET", "Сокет кулера", check_cooler_socket),
    ("COOLER_HEIGHT", "Высота кулера и корпус", check_cooler_height),
    ("AIO_RADIATOR", "Радиатор СЖО и корпус", check_aio_radiator),
    ("COOLER_TDP", "Теплоотвод кулера и TDP процессора", check_cooler_tdp),
    ("PSU_CASE_FF", "Форм-фактор БП и корпуса", check_psu_case_ff),
    ("PSU_POWER", "Мощность блока питания", check_psu_power),
    ("NO_VIDEO", "Наличие видеовыхода", check_no_video),
    ("M2_SLOTS", "M.2-слоты платы", check_m2_slots),
    ("DRIVE_BAYS", "Отсеки для накопителей", check_drive_bays),
]
