import pytest

from app.llm.fallback_parser import parse_budget, parse_requirements_fallback


@pytest.mark.parametrize(
    "text,expected",
    [
        ("до 120к", 120_000),
        ("120 000 ₽", 120_000),
        ("бюджет 95000", 95_000),
        ("за 1.5 млн", 1_500_000),
        ("до 80 тыс", 80_000),
        ("игры 4K до 200 000 ₽", 200_000),
        ("4K-гейминг за 30 000 ₽", 30_000),
        ("32 ГБ озу", None),
        ("144 fps 1440p", None),
        ("пк за 60000 рублей", 60_000),
        ("RTX 4070 и Ryzen 7 7800X3D", None),
    ],
)
def test_budget(text, expected):
    assert parse_budget(text) == expected


def test_example_queries_from_tz():
    r = parse_requirements_fallback("ПК для игр в 1440p и монтажа до 120 000 ₽")
    assert r.use_cases[:2] == ["gaming", "video_editing"] and r.budget_rub == 120_000
    assert r.gaming and r.gaming.resolution == "1440p"
    r = parse_requirements_fallback("Компактный ПК для учёбы и Dota 2")
    assert "study" in r.use_cases and "gaming" in r.use_cases
    assert r.preferences.form_factor == "compact" and r.gaming.titles == ["Dota 2"]
    assert r.budget_rub is None


def test_preferences_and_models():
    r = parse_requirements_fallback(
        "игры 100к, Ryzen 5 7600, RTX 4060, Wi-Fi, 32 ГБ ОЗУ, 2 ТБ SSD, mini-itx, без видеокарты"
    )
    p = r.preferences
    assert p.cpu_brand == "amd" and p.wifi_required and p.min_ram_gb == 32
    assert p.min_storage_gb == 2000 and p.form_factor == "mini_itx" and p.no_discrete_gpu
    assert "Ryzen 5 7600" in r.must_include and "RTX 4060" in r.must_include


def test_empty_text_defaults_to_office_low_confidence():
    r = parse_requirements_fallback("нужен компьютер")
    assert r.use_cases == ["office"] and r.confidence < 0.6
