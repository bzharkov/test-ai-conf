import dataclasses

import pytest

from app.catalog.repository import Catalog, build_seed_components, set_catalog
from app.domain import Build, Component


@pytest.fixture(scope="session")
def catalog() -> Catalog:
    comps = build_seed_components("data/seed", "data/perf_scores.csv", "csv")
    cat = Catalog(comps)
    set_catalog(cat)
    return cat


@pytest.fixture(autouse=True)
def _use_seed_catalog(catalog):
    set_catalog(catalog)
    yield


def pick(catalog: Catalog, name_part: str) -> Component:
    hits = [c for c in catalog.components if name_part.lower() in c.name.lower()]
    assert hits, name_part
    return hits[0]


def mod(c: Component, **specs) -> Component:
    return dataclasses.replace(c, specs={**c.specs, **specs})


@pytest.fixture
def good_build(catalog) -> Build:
    """AM5 + DDR5 + RTX 4060, fully compatible."""
    return Build(
        cpu=pick(catalog, "Ryzen 5 7600"),
        motherboard=pick(catalog, "PRO B650M-A"),
        ram=pick(catalog, "FURY Beast 32GB (2x16GB) DDR5"),
        gpu=pick(catalog, "RTX 4060 VENTUS"),
        cpu_cooler=pick(catalog, "AK400"),
        psu=pick(catalog, "Corsair CX650"),
        case=pick(catalog, "4000D"),
        storage=[pick(catalog, "NV2 1TB")],
    )
