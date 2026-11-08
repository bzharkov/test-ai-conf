import time

import pytest

from app.compat import check_build, has_errors
from app.llm.fallback_parser import parse_requirements_fallback
from app.llm.schemas import Requirements
from app.recommender.budget import allocate, build_profile
from app.recommender.service import _n_diff, recommend

QUERIES = [
    "Игры в 1440p до 120 000 ₽",
    "Офисный ПК до 40 000 ₽",
    "Монтаж 4K до 200 000 ₽",
    "Компактный ПК для учёбы и Dota 2 до 60000",
    "игры 1080p до 70к",
    "пк для программирования 90 тыс",
    "игры 4K 250к",
    "стрим и игры 130к",
]


@pytest.mark.parametrize("q", QUERIES)
def test_builds_are_compatible_and_within_budget(catalog, q):
    req = parse_requirements_fallback(q)
    res = recommend(catalog, req)
    assert res.recs, q
    for rec in res.recs:
        assert not has_errors(check_build(rec.build)), (q, rec.issues)
        assert rec.total <= res.budget + 1e-6, (q, rec.label, rec.total, res.budget)
        assert all(c.purchasable for c in rec.build.components())
        assert rec.power.psu_recommended_w <= rec.build.psu.spec("wattage_w")


def test_variants_differ_in_at_least_two_key_components(catalog):
    res = recommend(catalog, parse_requirements_fallback("Игры в 1440p до 120 000 ₽"))
    assert len(res.recs) >= 2
    for i, a in enumerate(res.recs):
        for b in res.recs[i + 1 :]:
            assert _n_diff(a.build, b.build) >= 2
    assert [r.label for r in res.recs][0] == "Оптимальная"


def test_gaming_build_has_strong_gpu_and_office_has_none(catalog):
    g = recommend(catalog, parse_requirements_fallback("игры в 1440p до 120 000 ₽")).recs[0]
    assert g.build.gpu is not None and g.build.gpu.perf_score >= 40
    o = recommend(catalog, parse_requirements_fallback("Офисный ПК до 40 000 ₽")).recs[0]
    assert o.build.gpu is None and o.build.cpu.spec("has_igpu")


def test_video_editing_prefers_cores_and_ram(catalog):
    r = recommend(catalog, parse_requirements_fallback("Монтаж 4K до 200 000 ₽")).recs[0].build
    assert r.cpu.spec("cores") >= 12 and r.ram.spec("capacity_gb_total") >= 32


def test_unreachable_budget_returns_cheapest_with_message(catalog):
    res = recommend(catalog, parse_requirements_fallback("4K-гейминг за 30 000 ₽"))
    codes = [w["code"] for w in res.warnings]
    assert "over_budget" in codes and res.recs[0].over_budget
    assert res.min_feasible_price and res.min_feasible_price > 30_000
    assert not has_errors(res.recs[0].issues)


def test_no_budget_uses_default_and_warns(catalog):
    res = recommend(catalog, parse_requirements_fallback("пк для работы"))
    assert res.budget == 100_000
    assert any(w["code"] == "budget_assumed" for w in res.warnings)
    assert res.requirements.budget_assumed


def test_must_include_model_is_used_or_reported(catalog):
    res = recommend(catalog, parse_requirements_fallback("игровой пк 150к с RTX 4070 SUPER"))
    assert "4070 SUPER" in res.recs[0].build.gpu.name
    res2 = recommend(
        catalog,
        Requirements(
            use_cases=["gaming"],
            primary_use_case="gaming",
            budget_rub=100_000,
            must_include=["RTX 9999"],
        ),
    )
    assert any(w["code"] == "must_include_not_found" for w in res2.warnings)
    assert res2.recs


def test_preferences_are_respected(catalog):
    res = recommend(
        catalog, parse_requirements_fallback("игры до 110000, только Intel, нужен wifi")
    )
    b = res.recs[0].build
    assert b.cpu.brand == "Intel" and b.motherboard.spec("wifi")


def test_compact_preference_gives_small_case(catalog):
    res = recommend(catalog, parse_requirements_fallback("компактный пк для игр 100к"))
    for r in res.recs:
        assert "ATX" not in r.build.case.spec("supported_mb_form_factors")


def test_deterministic(catalog):
    q = parse_requirements_fallback("игры в 1440p до 120 000 ₽")
    a = [[c.id for c in r.build.components()] for r in recommend(catalog, q).recs]
    b = [[c.id for c in r.build.components()] for r in recommend(catalog, q).recs]
    assert a == b


def test_speed_budget(catalog):
    t = time.monotonic()
    for q in QUERIES:
        recommend(catalog, parse_requirements_fallback(q))
    assert (time.monotonic() - t) / len(QUERIES) < 5


def test_budget_shares_sum_to_about_one():
    req = parse_requirements_fallback("игры 120к")
    shares = allocate(req, 100_000)
    assert 95_000 <= sum(shares.values()) <= 101_000
    assert shares["gpu"] == max(shares.values())


def test_mixed_profile_weights_normalised():
    req = parse_requirements_fallback("игры и монтаж 120к")
    prof = build_profile(req, 120_000)
    assert abs(sum(prof.weights.values()) - 1) < 1e-9
