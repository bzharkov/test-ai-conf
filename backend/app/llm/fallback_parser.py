"""Deterministic regex/dictionary parser (TZ 8.1). Used when the LLM is off and in tests."""

from __future__ import annotations

import re

from app.llm.schemas import GamingReq, Preferences, Requirements

_UNIT_AFTER = re.compile(r"^\s*(гб|gb|тб|tb|мб|mb|fps|фпс|гц|hz|вт|w\b|p\b|ядер|мгц|mhz)", re.I)
_NUM = re.compile(
    r"(\d{1,3}(?:[  ]\d{3})+|\d+(?:[.,]\d+)?)\s*(млн|тыс\.?|к\b|k\b|₽|руб\w*|р\b)?", re.I
)
_PREFIX = re.compile(r"(до|бюджет\w*|за|около|примерно|порядка|~|≈|в\s+пределах)\s*$", re.I)

USE_CASE_PATTERNS: dict[str, str] = {
    "gaming": r"игр|гейм|game|gaming|dota|дота|cs2|cs:go|кс\s?2|fortnite|cyberpunk|киберпанк|"
    r"warzone|minecraft|майнкрафт|gta|valorant|fps|шутер|геймер|танк",
    "video_editing": r"монтаж|видеомонтаж|premiere|davinci|after effects|видео\s*редакт|"
    r"обработк\w* видео",
    "3d_render": r"рендер|blender|блендер|3ds|maya|solidworks|autocad|\bcad\b|3d[- ]?(моделир|график)",
    "programming": r"программир|разработ|кодинг|docker|\bide\b|backend|frontend|девелоп",
    "study": r"учеб|учёб|студент|школ|универ|курсов|дипломн",
    "streaming": r"стрим|\bobs\b|twitch|трансляц",
    "ml": r"нейросет|машинн\w* обучен|\bml\b|deep learning|\bllm\b|pytorch|tensorflow|инференс",
    "office": r"офис|документ|excel|word|браузер|бухгалтер|домашн|интернет|сёрфинг|серфинг|для работы",
}

TITLES = {
    "Dota 2": r"dota|дота",
    "CS2": r"cs2|cs:go|кс\s?2",
    "Cyberpunk 2077": r"cyberpunk|киберпанк",
    "Fortnite": r"fortnite|фортнайт",
    "Minecraft": r"minecraft|майнкрафт",
    "GTA V": r"\bgta",
    "Valorant": r"valorant|валорант",
    "Warzone": r"warzone",
}

MODEL_MENTIONS = [
    r"RTX\s?\d{4}(?:\s?(?:Ti\s?SUPER|Ti|SUPER))?",
    r"GTX\s?\d{3,4}(?:\s?Ti)?",
    r"RX\s?\d{4}(?:\s?(?:XTX|XT|GRE))?",
    r"Arc\s?[AB]\d{3}",
    r"Ryzen\s?\d\s?\d{4}[A-Z0-9]*",
    r"Core\s?i\d-\d{4,5}[A-Z]{0,2}",
    r"Core\s?Ultra\s?\d\s?\d{3}[A-Z]*",
]


def parse_budget(text: str) -> int | None:
    cands: list[tuple[int, int, int]] = []  # (priority, pos, value)
    for m in _NUM.finditer(text):
        raw, unit = m.group(1), (m.group(2) or "").lower().rstrip(".")
        after = text[m.end() : m.end() + 8]
        if not unit and _UNIT_AFTER.match(after):
            continue
        try:
            n = float(raw.replace(" ", "").replace(" ", "").replace(",", "."))
        except ValueError:
            continue
        prefix_hit = bool(_PREFIX.search(text[max(0, m.start() - 14) : m.start()]))
        if unit in ("млн",):
            value = n * 1_000_000
        elif unit in ("к", "k", "тыс"):
            if n < 10:  # "4K" is a resolution, not 4 000 ₽
                continue
            value = n * 1000
        elif unit in ("₽",) or unit.startswith("руб") or unit == "р":
            value = n * 1000 if n < 1000 else n
        elif prefix_hit and n >= 10_000:
            value = n
        elif prefix_hit and 10 <= n < 1000 and not re.match(r"\s*(гб|gb|тб|tb)", after, re.I):
            value = n * 1000 if "." not in raw and "," not in raw and n >= 15 else n
            if value < 10_000:
                continue
        elif n >= 10_000 and re.search(r"\d[  ]\d{3}", raw):
            value = n
        else:
            continue
        if 5_000 <= value <= 5_000_000:
            cands.append((0 if prefix_hit else 1, m.start(), int(value)))
    if not cands:
        return None
    cands.sort()
    return cands[0][2]


def parse_resolution(text: str) -> str | None:
    t = text.lower()
    if re.search(r"\b4\s?[kк]\b|2160|\buhd\b", t):
        return "4k"
    if re.search(r"1440|\b2\s?[kк]\b|qhd|2560", t):
        return "1440p"
    if re.search(r"1080|full\s?hd|fhd", t):
        return "1080p"
    return None


def parse_use_cases(text: str) -> list[str]:
    t = text.lower()
    found: list[tuple[int, str]] = []
    for uc, pat in USE_CASE_PATTERNS.items():
        m = re.search(pat, t)
        if m:
            found.append((m.start(), uc))
    found.sort()
    return [uc for _, uc in found]


def parse_preferences(text: str) -> Preferences:
    t = text.lower()
    p = Preferences()
    amd_cpu = re.search(r"ryzen|райзен|амд|\bamd\b", t)
    intel = re.search(r"\bintel\b|интел|core\s?i\d", t)
    if amd_cpu and not intel:
        p.cpu_brand = "amd"
    elif intel and not amd_cpu:
        p.cpu_brand = "intel"
    if re.search(r"nvidia|нвидиа|geforce|\brtx\b", t):
        p.gpu_brand = "nvidia"
    elif re.search(r"radeon|\brx\s?\d", t) or re.search(r"всё на amd|все на amd", t):
        p.gpu_brand = "amd"
    elif re.search(r"\barc\b", t):
        p.gpu_brand = "intel"
    if re.search(r"mini[- ]?itx|\bitx\b|мини[- ]?итх", t):
        p.form_factor = "mini_itx"
    elif re.search(r"компакт|маленьк|небольш|малогабарит|мини[- ]?пк|\bsff\b", t):
        p.form_factor = "compact"
    if re.search(r"wi-?fi|вай-?фай|беспроводн", t) and not re.search(
        r"без\s+wi-?fi|без вай-?фай", t
    ):
        p.wifi_required = True
    if re.search(
        r"без\s+(дискретн\w+\s+)?(видеокарт|гпу|gpu)|встроенн\w+\s+(график|видео)|"
        r"интегрированн\w+\s+(график|видео)",
        t,
    ):
        p.no_discrete_gpu = True
    if re.search(r"тих|бесшум", t):
        p.quiet = True
    if re.search(r"rgb|подсветк", t):
        p.rgb = True
    m = re.search(r"(\d{1,3})\s*(?:гб|gb)\s*(?:озу|оператив\w*|ram|памят\w*)", t) or re.search(
        r"(?:озу|оператив\w*\s+памят\w*|ram)\s*(?:не менее|от|минимум)?\s*(\d{1,3})\s*(?:гб|gb)", t
    )
    if m:
        p.min_ram_gb = int(m.group(1))
    m = re.search(
        r"(\d+(?:[.,]\d+)?)\s*(тб|tb|гб|gb)\s*(?:ssd|nvme|накопител\w*|диск\w*|хранилищ\w*)", t
    )
    if m:
        v = float(m.group(1).replace(",", "."))
        p.min_storage_gb = int(v * 1000) if m.group(2) in ("тб", "tb") else int(v)
    return p


def parse_must_include(text: str) -> list[str]:
    out: list[str] = []
    for pat in MODEL_MENTIONS:
        for m in re.finditer(pat, text, re.I):
            v = re.sub(r"\s+", " ", m.group(0)).strip()
            if v.lower() not in {x.lower() for x in out}:
                out.append(v)
    return out


def parse_requirements_fallback(text: str) -> Requirements:
    ucs = parse_use_cases(text)
    gaming_in = "gaming" in ucs
    res = parse_resolution(text)
    budget = parse_budget(text)
    prefs = parse_preferences(text)
    titles = [t for t, pat in TITLES.items() if re.search(pat, text, re.I)]
    gaming = None
    if gaming_in or res and ucs == []:
        gaming = GamingReq(
            resolution=res or ("1080p" if gaming_in else None),  # type: ignore[arg-type]
            titles=titles,
        )
        fps = re.search(r"(\d{2,3})\s*(?:fps|фпс|кадр)", text, re.I)
        if fps:
            gaming.target_fps = int(fps.group(1))
    if not ucs:
        ucs = ["gaming"] if res else ["office"]
    strict = not re.search(r"около|примерно|порядка|~|≈|плюс-минус", text, re.I)
    known = sum([bool(ucs), budget is not None, res is not None]) / 3
    return Requirements(
        use_cases=ucs,  # type: ignore[arg-type]
        primary_use_case=ucs[0],
        budget_rub=budget,
        budget_is_strict=strict,
        gaming=gaming,
        preferences=prefs,
        must_include=parse_must_include(text),
        confidence=round(0.3 + 0.6 * known, 2),
    )
