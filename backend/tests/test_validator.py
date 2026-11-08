import pytest
from conftest import pick

from app.llm.validator import (
    STATS,
    Vocabulary,
    drop_violating_sentences,
    extract_mentions,
    find_violations,
    validate_and_fix,
)


@pytest.fixture
def vocab(catalog, good_build):
    return Vocabulary(good_build.components(), catalog.components)


def test_extract_mentions_variants():
    m = extract_mentions(
        "RTX 4070 Ti SUPER, Ryzen 5 7600X, Core i5-12400F, Core Ultra 7 265K, RX 7800 XT и Arc B580"
    )
    assert m == [
        "rtx4070tisuper",
        "rx7800xt",
        "arcb580",
        "ryzen57600x",
        "coreultra7265k",
        "i512400f",
    ]


def test_allowed_models_pass(vocab):
    assert find_violations("Здесь Ryzen 5 7600 и RTX 4060 — отличная пара.", vocab) == []


def test_other_model_of_same_family_is_violation(vocab):
    assert find_violations("Лучше взять RTX 4060 Ti.", vocab) == ["rtx4060ti"]
    assert find_violations("Можно поставить Ryzen 7 7800X3D.", vocab) == ["ryzen77800x3d"]


def test_nonexistent_model_is_violation(vocab):
    assert find_violations("RTX 9090 справится.", vocab) == ["rtx9090"]


def test_catalog_token_outside_build_flagged(vocab):
    assert find_violations("Блок питания Corsair RM1000e подойдёт.", vocab)
    assert find_violations("Блок питания Corsair CX650 подойдёт.", vocab) == []


def test_drop_sentences():
    out = drop_violating_sentences(
        "Хорошая сборка. Возьмите RTX 4090 для запаса. Всё работает.", ["rtx4090"]
    )
    assert "4090" not in out and "Хорошая сборка." in out and "Всё работает." in out
    assert "удалена" in out


async def test_regenerate_then_ok(vocab):
    STATS.clear()

    async def regen(banned):
        assert "rtx4090" in banned
        return "Остаёмся на RTX 4060."

    text, bad = await validate_and_fix("Нужна RTX 4090.", vocab, regen)
    assert text == "Остаёмся на RTX 4060." and bad == ["rtx4090"]
    assert STATS["violations"] == 1 and STATS["regenerations"] == 1


async def test_regenerate_fails_then_drop(vocab):
    async def regen(banned):
        return "Всё равно RTX 4090."

    text, _ = await validate_and_fix("Нужна RTX 4090. Остальное хорошо.", vocab, regen)
    assert "4090" not in text and "Остальное хорошо." in text


async def test_clean_text_untouched(vocab, catalog):
    text, bad = await validate_and_fix("Всё совместимо.", vocab, None)
    assert text == "Всё совместимо." and bad == []
    _ = pick
