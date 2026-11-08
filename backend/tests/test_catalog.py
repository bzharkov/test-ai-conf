import asyncio

from app.catalog.repository import build_seed_components
from app.domain import CATEGORIES
from app.pricing.providers import CsvPriceProvider, MockPriceProvider


def test_every_category_filled(catalog):
    for cat in CATEGORIES:
        assert len(catalog.by_category[cat]) >= 6, cat


def test_seed_components_have_no_missing_critical_fields(catalog):
    assert [c.name for c in catalog.components if c.missing_critical()] == []


def test_all_seed_prices_matched_and_sourced(catalog):
    assert all(c.purchasable and c.price_source and c.price_updated_at for c in catalog.components)


def test_perf_scores_from_table_not_estimated(catalog):
    gpus = catalog.by_category["gpu"]
    assert all(g.perf_score and not g.perf_estimated for g in gpus)
    cpus = catalog.by_category["cpu"]
    assert all(c.perf_score and c.perf_multicore for c in cpus)


def test_mock_provider_is_deterministic(catalog):
    p1 = asyncio.run(MockPriceProvider(catalog.components).get_prices([1, 2, 3]))
    p2 = asyncio.run(MockPriceProvider(catalog.components).get_prices([1, 2, 3]))
    assert p1 == p2 and "демо" in p1[1].source


def test_csv_provider_reports_unmatched(tmp_path, catalog):
    f = tmp_path / "p.csv"
    f.write_text(
        "sku_or_name,price_rub,in_stock,source,updated_at\n"
        "AMD Ryzen 5 5600,9000,true,x,2026-01-01\nNonexistent Foo 9000,1,true,x,y\n",
        encoding="utf-8",
    )
    p = CsvPriceProvider(f, catalog.components)
    assert p.unmatched == ["Nonexistent Foo 9000"]
    got = asyncio.run(p.get_prices([c.id for c in catalog.components]))
    assert len(got) == 1 and next(iter(got.values())).price_rub == 9000


def test_ids_are_stable_between_loads():
    a = build_seed_components("data/seed", "data/perf_scores.csv", "csv")
    b = build_seed_components("data/seed", "data/perf_scores.csv", "csv")
    assert [(c.id, c.name) for c in a] == [(c.id, c.name) for c in b]


def test_search(catalog):
    r = catalog.search("4060", "gpu")
    assert r and "4060" in r[0].name
