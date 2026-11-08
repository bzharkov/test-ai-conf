from conftest import pick

from app.compat import check_build, has_errors
from app.rag.alternatives import apply_replacement, find_alternatives, perf_value
from app.rag.embeddings import HashEmbedder, cosine


def test_hash_embedder_deterministic_and_similar():
    e = HashEmbedder()
    a, b, c = e.embed_passages(["GeForce RTX 4060 8 GB", "GeForce RTX 4060 Ti 8 GB", "PSU 650W"])
    assert a == e.embed_passages(["GeForce RTX 4060 8 GB"])[0]
    assert cosine(a, b) > cosine(a, c)


def test_cheaper_gpu_alternatives_are_compatible_and_cheaper(catalog, good_build):
    good_build = good_build.with_component(pick(catalog, "RTX 4070 SUPER"))
    alts = find_alternatives(catalog, good_build, "gpu", "cheaper", k=3, embedder=HashEmbedder())
    assert 1 <= len(alts) <= 3
    for a in alts:
        assert a.price_delta_rub < 0 and a.perf_delta_pct < 0
        nb = apply_replacement(catalog, good_build, a)
        assert not has_errors(check_build(nb))
        assert nb.gpu.id == a.component.id


def test_better_gpu_may_require_psu_upgrade(catalog, good_build):
    # CX650 + RTX 4060 build: a much stronger GPU needs a bigger PSU, offered as part of the swap
    alts = find_alternatives(catalog, good_build, "gpu", "better", k=3, embedder=HashEmbedder())
    assert alts
    for a in alts:
        assert a.perf_delta_pct > 0
        nb = apply_replacement(catalog, good_build, a)
        assert not has_errors(check_build(nb))
        if a.extra_component is not None:
            assert any("БП" in n for n in a.notes)
            assert a.total_delta_rub > a.price_delta_rub


def test_incompatible_candidates_are_dropped(catalog, good_build):
    # AM5 board: only AM5 CPUs may be offered as CPU alternatives
    alts = find_alternatives(catalog, good_build, "cpu", "similar", k=5, embedder=HashEmbedder())
    assert all(a.component.spec("socket") == "AM5" for a in alts)


def test_missing_slot_returns_empty(catalog, good_build):
    assert find_alternatives(catalog, good_build.without("gpu"), "gpu", "cheaper") == []


def test_perf_value_categories(catalog):
    assert perf_value(pick(catalog, "RTX 4090")) > perf_value(pick(catalog, "RTX 4060 VENTUS"))
    assert perf_value(pick(catalog, "AK400")) is None
