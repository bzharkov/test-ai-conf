from app.config import Settings
from app.power.calc import calculate_power, ceil_to_50


def test_ceil_to_50():
    assert ceil_to_50(401) == 450
    assert ceil_to_50(400) == 400


def test_power_breakdown_matches_formula(good_build):
    s = Settings(power_k_cpu=1.35, power_margin=1.3)
    r = calculate_power(good_build, s)
    expected = 65 * 1.35 + 115 + 50 + 5 * 2 + 5 + 15
    assert abs(r.estimated_power_w - expected) < 1e-6
    assert r.psu_recommended_w == max(ceil_to_50(expected * 1.3), 550)
    assert len(r.items) >= 6
    assert r.gpu_recommended_psu_w == 550


def test_gpu_recommended_psu_wins_when_higher(good_build, catalog):
    from conftest import mod

    b = good_build.with_component(mod(good_build.gpu, recommended_psu_w=1200))
    assert calculate_power(b).psu_recommended_w == 1200


def test_no_gpu(good_build):
    r = calculate_power(good_build.without("gpu"))
    assert r.gpu_recommended_psu_w == 0
    assert all("Видеокарта" not in label for label, _ in r.items)
