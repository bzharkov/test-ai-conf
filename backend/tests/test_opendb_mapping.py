import json

import pytest

from app.catalog.opendb_mapping import (
    Rejected,
    map_case,
    map_cooler,
    map_cpu,
    map_gpu,
    map_motherboard,
    map_psu,
    map_ram,
    map_storage,
    norm_ff,
    norm_socket,
)

M = {"manufacturer": "AMD", "name": "AMD Ryzen 5 7600"}


def test_normalizers():
    assert norm_socket("LGA 1700") == "LGA1700" and norm_socket("Socket AM5") == "AM5"
    assert norm_ff("Micro ATX") == "mATX" and norm_ff("EATX") == "E-ATX"
    assert norm_ff("SSI EEB") is None


def cpu(**kw):
    d = {
        "opendb_id": "x",
        "socket": "AM5",
        "cores": {"total": 6, "threads": 12},
        "clocks": {"performance": {"base": 3.8, "boost": 5.1}},
        "specifications": {
            "tdp": 65,
            "integratedGraphics": {"model": "Radeon"},
            "memory": {"types": ["DDR5"]},
        },
        "metadata": {**M, "releaseYear": 2023},
    }
    d.update(kw)
    return d


def test_cpu_ok_and_rejections():
    m = map_cpu(cpu())
    assert m.model == "Ryzen 5 7600" and m.brand == "AMD"
    assert m.specs["socket"] == "AM5" and m.specs["has_igpu"] is True and m.specs["tdp_w"] == 65
    with pytest.raises(Rejected, match="too_old"):
        map_cpu(cpu(metadata={**M, "releaseYear": 2016}))
    with pytest.raises(Rejected, match="missing_critical"):
        map_cpu(cpu(specifications={"tdp": 0, "memory": {"types": ["DDR5"]}}))
    none_igpu = cpu()
    none_igpu["specifications"]["integratedGraphics"] = {"model": "None"}
    assert map_cpu(none_igpu).specs["has_igpu"] is False


def test_motherboard_wifi_inferred_and_old_memory_rejected():
    d = {
        "opendb_id": "m",
        "socket": "AM5",
        "form_factor": "Micro ATX",
        "chipset": "AMD B650",
        "memory": {"max": 192, "ram_type": "DDR5", "slots": 4},
        "m2_slots": [{"size": "2280", "key": "M", "interface": "PCIe 4.0 x4"}] * 2,
        "storage_devices": {"sata_6_gb_s": 4, "sata_3_gb_s": 0, "u2": 0},
        "metadata": {"manufacturer": "MSI", "name": "MSI PRO B650M-A WIFI"},
    }
    m = map_motherboard(d)
    assert m.specs["form_factor"] == "mATX" and m.specs["m2_slots"] == 2 and m.specs["wifi"]
    assert m.specs["wifi_inferred"] is True
    with pytest.raises(Rejected, match="old_memory"):
        map_motherboard({**d, "memory": {"max": 32, "ram_type": "DDR3", "slots": 4}})


def test_ram_gpu_storage_psu_cooler_case():
    ram = map_ram(
        {
            "opendb_id": "r",
            "ram_type": "DDR5",
            "speed": 6000,
            "capacity": 32,
            "modules": {"quantity": 2, "capacity_gb": 16},
            "ecc": "Non-ECC",
            "registered": "Unbuffered",
            "metadata": {"manufacturer": "Corsair", "name": "Corsair Vengeance 32GB"},
        }
    )
    assert ram.specs["capacity_gb_total"] == 32 and ram.specs["modules"] == 2
    gpu = map_gpu(
        {
            "opendb_id": "g",
            "chipset": "GeForce RTX 4060",
            "memory": 8,
            "tdp": 115,
            "length": 199,
            "total_slot_width": 2,
            "metadata": {"manufacturer": "MSI", "name": "MSI RTX 4060 VENTUS"},
        }
    )
    assert gpu.specs["recommended_psu_w"] is None
    with pytest.raises(Rejected, match="old_or_unsupported"):
        map_gpu(
            {
                "opendb_id": "g",
                "chipset": "GeForce GTX 970",
                "memory": 4,
                "tdp": 145,
                "length": 250,
                "metadata": {"manufacturer": "MSI", "name": "MSI GTX 970"},
            }
        )
    nvme = map_storage(
        {
            "opendb_id": "s",
            "capacity": 1000,
            "storage_type": "SSD",
            "nvme": True,
            "form_factor": "M.2-2280",
            "interface": "M.2 PCIe 4.0 x4",
            "metadata": {"manufacturer": "WD", "name": "WD SN580 1TB"},
        }
    )
    assert nvme.specs["type"] == "nvme" and nvme.specs["form_factor"] == "M.2"
    with pytest.raises(Rejected, match="sas"):
        map_storage(
            {
                "opendb_id": "s",
                "capacity": 1000,
                "storage_type": "HDD",
                "nvme": False,
                "form_factor": '3.5"',
                "interface": "SAS 12.0 Gb/s",
                "metadata": {"manufacturer": "X", "name": "X SAS"},
            }
        )
    psu = map_psu(
        {
            "opendb_id": "p",
            "wattage": 650,
            "form_factor": "ATX",
            "efficiency_rating": "80+ Gold",
            "modular": "Semi-Modular",
            "metadata": {"manufacturer": "Y", "name": "Y 650W"},
        }
    )
    assert psu.specs["modular"] is True
    aio = map_cooler(
        {
            "opendb_id": "c",
            "water_cooled": True,
            "radiator_size": 240,
            "height": None,
            "cpu_sockets": ["AM5", "LGA 1700"],
            "metadata": {"manufacturer": "Z", "name": "Z AIO 240"},
        }
    )
    assert aio.specs["type"] == "aio" and aio.specs["sockets"] == ["AM5", "LGA1700"]
    case = map_case(
        {
            "opendb_id": "k",
            "supported_motherboard_form_factors": ["ATX", "Micro ATX"],
            "supported_power_supply_form_factors": ["ATX"],
            "max_video_card_length": 392,
            "max_cpu_cooler_height": 180.5,
            "internal_2_5_bays": 6,
            "internal_3_5_bays": 2,
            "metadata": {"manufacturer": "Lian Li", "name": "Lian Li LANCOOL 216"},
        }
    )
    assert case.specs["radiator_support_mm"] is None  # unknown, never invented
    assert case.specs["supported_mb_form_factors"] == ["ATX", "mATX"]
    assert json.dumps(case.as_row())  # serialisable for upsert
