import pytest
from conftest import mod, pick

from app.compat import check_build, has_errors
from app.compat.rules import (
    check_aio_radiator,
    check_cooler_height,
    check_cooler_socket,
    check_cooler_tdp,
    check_cpu_mb_socket,
    check_drive_bays,
    check_gpu_case_len,
    check_m2_slots,
    check_mb_case_ff,
    check_no_video,
    check_psu_case_ff,
    check_psu_power,
    check_ram_max,
    check_ram_mb_type,
    check_ram_slots,
)
from app.domain import Build


def codes(issues):
    return {i.code for i in issues}


def test_good_build_has_no_errors(good_build):
    issues = check_build(good_build)
    assert not has_errors(issues), issues


def test_cpu_mb_socket(good_build, catalog):
    assert check_cpu_mb_socket(good_build) == []
    bad = good_build.with_component(pick(catalog, "Core i5-12400F"))
    assert codes(check_cpu_mb_socket(bad)) == {"CPU_MB_SOCKET"}


def test_ram_type_against_motherboard_and_cpu(good_build, catalog):
    assert check_ram_mb_type(good_build) == []
    bad = good_build.with_component(pick(catalog, "FURY Beast 16GB (2x8GB) DDR4"))
    assert "RAM_MB_TYPE" in codes(check_ram_mb_type(bad))
    # CPU that does not support DDR5 on a (hypothetical) DDR5 board
    cpu = mod(good_build.cpu, memory_types=["DDR4"])
    assert "RAM_MB_TYPE" in codes(check_ram_mb_type(good_build.with_component(cpu)))


def test_ram_slots(good_build):
    assert check_ram_slots(good_build) == []
    bad = good_build.with_component(mod(good_build.ram, modules=8))
    assert codes(check_ram_slots(bad)) == {"RAM_SLOTS"}


def test_ram_max(good_build):
    assert check_ram_max(good_build) == []
    bad = good_build.with_component(mod(good_build.ram, capacity_gb_total=512))
    assert codes(check_ram_max(bad)) == {"RAM_MAX"}


def test_mb_case_form_factor(good_build, catalog):
    assert check_mb_case_ff(good_build) == []
    bad = good_build.with_component(pick(catalog, "NR200P"))  # Mini-ITX only
    assert codes(check_mb_case_ff(bad)) == {"MB_CASE_FF"}


def test_gpu_case_length(good_build):
    assert check_gpu_case_len(good_build) == []
    bad = good_build.with_component(mod(good_build.gpu, length_mm=500))
    assert codes(check_gpu_case_len(bad)) == {"GPU_CASE_LEN"}


def test_cooler_socket(good_build, catalog):
    assert check_cooler_socket(good_build) == []
    bad = good_build.with_component(mod(good_build.cpu_cooler, sockets=["LGA1700"]))
    assert codes(check_cooler_socket(bad)) == {"COOLER_SOCKET"}


def test_cooler_height_only_for_air(good_build, catalog):
    assert check_cooler_height(good_build) == []
    bad = good_build.with_component(mod(good_build.cpu_cooler, height_mm=200))
    assert codes(check_cooler_height(bad)) == {"COOLER_HEIGHT"}
    aio = good_build.with_component(pick(catalog, "Liquid Freezer III 240"))
    assert check_cooler_height(aio) == []


def test_aio_radiator(good_build, catalog):
    ok = good_build.with_component(pick(catalog, "Liquid Freezer III 240"))
    assert check_aio_radiator(ok) == []
    bad = good_build.with_component(pick(catalog, "Liquid Freezer III 360"))
    bad = bad.with_component(pick(catalog, "Q300L"))  # only 120 mm radiators
    assert codes(check_aio_radiator(bad)) == {"AIO_RADIATOR"}
    assert check_aio_radiator(good_build) == []  # air cooler: rule not applicable


def test_cooler_tdp_warning_and_unknown_rating(good_build, catalog):
    assert check_cooler_tdp(good_build) == []
    weak = good_build.with_component(mod(good_build.cpu_cooler, tdp_rating_w=40))
    issues = check_cooler_tdp(weak)
    assert codes(issues) == {"COOLER_TDP"} and issues[0].severity == "warning"
    unknown = good_build.with_component(mod(good_build.cpu_cooler, tdp_rating_w=None))
    assert check_cooler_tdp(unknown) == []


def test_psu_case_form_factor(good_build, catalog):
    assert check_psu_case_ff(good_build) == []
    sfx_in_atx = good_build.with_component(pick(catalog, "SF750"))
    assert check_psu_case_ff(sfx_in_atx) == []  # SFX in ATX case is allowed
    atx_in_sfx = good_build.with_component(pick(catalog, "NR200P"))
    assert codes(check_psu_case_ff(atx_in_sfx)) == {"PSU_CASE_FF"}


def test_psu_power(good_build, catalog):
    assert check_psu_power(good_build) == []
    big = good_build.with_component(pick(catalog, "RTX 4090")).with_component(
        pick(catalog, "Core i9-14900K")
    )
    big = big.with_component(pick(catalog, "CV450"))
    assert codes(check_psu_power(big)) == {"PSU_POWER"}


def test_no_video(good_build, catalog):
    assert check_no_video(good_build) == []  # has GPU
    igpu_ok = good_build.without("gpu")  # Ryzen 5 7600 has iGPU
    assert check_no_video(igpu_ok) == []
    no_igpu = igpu_ok.with_component(pick(catalog, "Ryzen 5 7500F"))
    assert codes(check_no_video(no_igpu)) == {"NO_VIDEO"}


def test_m2_slots(good_build, catalog):
    assert check_m2_slots(good_build) == []
    nv = pick(catalog, "NV2 1TB")
    bad = Build(**{**good_build.__dict__, "storage": [nv, nv, nv]})
    assert codes(check_m2_slots(bad)) == {"M2_SLOTS"}


def test_drive_bays_warning(good_build, catalog):
    assert check_drive_bays(good_build) == []
    hdd = pick(catalog, "BarraCuda")
    bad = Build(**{**good_build.__dict__, "storage": [hdd, hdd, hdd]})
    issues = check_drive_bays(bad)
    assert codes(issues) == {"DRIVE_BAYS"} and issues[0].severity == "warning"


def test_missing_data_is_a_warning_not_a_crash(good_build):
    cpu = mod(good_build.cpu, socket=None)
    issues = check_build(good_build.with_component(cpu))
    assert "MISSING_DATA" in codes(issues)
    assert all(i.severity == "warning" for i in issues if i.code == "MISSING_DATA")


def test_partial_build_skips_full_only_rules(catalog):
    b = Build(cpu=pick(catalog, "Ryzen 5 7500F"))  # no iGPU, no gpu yet
    assert "NO_VIDEO" in codes(check_build(b))
    assert "NO_VIDEO" not in codes(check_build(b, partial=True))


@pytest.mark.parametrize("fn", [check_cpu_mb_socket, check_ram_slots, check_psu_power])
def test_rules_ignore_empty_build(fn):
    assert fn(Build()) == []
