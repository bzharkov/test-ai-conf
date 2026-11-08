import json

from app.core.cache import Cache
from app.llm.client import LLMResult, extract_json
from app.llm.parser import parse_requirements


class FakeLLM:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), 0

    async def complete(self, messages, **kw):
        self.calls += 1
        return LLMResult(self.replies.pop(0))

    async def stream(self, messages, **kw):
        yield ""


GOOD = json.dumps(
    {
        "use_cases": ["gaming"],
        "primary_use_case": "gaming",
        "budget_rub": 999,
        "preferences": {},
        "confidence": 0.9,
    }
)


async def test_llm_result_merged_with_regex_budget():
    llm = FakeLLM([GOOD])
    req, warns = await parse_requirements("игры до 120к", llm, Cache("redis://127.0.0.1:1/0"))
    assert req.budget_rub == 120_000 and warns == []  # regex number beats LLM hallucination


async def test_invalid_json_is_retried_then_ok():
    llm = FakeLLM(["не json", '{"use_cases": ["bad"]}', GOOD])
    req, warns = await parse_requirements("игры", llm, None)
    assert llm.calls == 3 and req.use_cases == ["gaming"] and not warns


async def test_falls_back_after_retries():
    llm = FakeLLM(["x", "y", "z"])
    req, warns = await parse_requirements("офис до 40000", llm, None)
    assert warns[0]["code"] == "llm_unavailable" and req.budget_rub == 40_000


async def test_no_llm_uses_fallback():
    req, warns = await parse_requirements("игры 1440p", None, None)
    assert warns[0]["code"] == "llm_unavailable" and req.gaming.resolution == "1440p"


async def test_cache_hit_skips_llm():
    cache = Cache("redis://127.0.0.1:1/0")
    llm = FakeLLM([GOOD])
    await parse_requirements("кэш тест", llm, cache)
    llm2 = FakeLLM([])
    req, _ = await parse_requirements("  Кэш   тест ", llm2, cache)
    assert llm2.calls == 0 and req.use_cases == ["gaming"]


async def test_filters_override():
    req, _ = await parse_requirements(
        "игры", None, None, {"budget_rub": 77000, "wifi": True, "cpu_brand": "amd"}
    )
    assert req.budget_rub == 77000 and req.preferences.wifi_required
    assert req.preferences.cpu_brand == "amd"


def test_extract_json_variants():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('вот: {"a": 2} готово') == {"a": 2}
