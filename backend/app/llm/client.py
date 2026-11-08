"""OpenRouter client (OpenAI-compatible). Local LLMs are intentionally unsupported."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.config import get_settings
from app.core.logging import log_event

log = logging.getLogger("llm")


@dataclass
class LLMResult:
    text: str
    usage: dict[str, int] = field(default_factory=dict)


class LLMClient(Protocol):
    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        json_schema: dict | None = None,
        max_tokens: int = 1200,
        temperature: float = 0.2,
    ) -> LLMResult: ...

    def stream(
        self, messages: list[dict[str, str]], *, max_tokens: int = 1200, temperature: float = 0.3
    ) -> AsyncIterator[str]: ...


def extract_json(text: str) -> Any:
    """Parse a JSON object from model text (handles ```json fences and surrounding prose)."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


class OpenRouterClient:
    def __init__(self) -> None:
        from openai import AsyncOpenAI

        s = get_settings()
        self._model = s.llm_model
        self._client = AsyncOpenAI(
            base_url=s.llm_base_url,
            api_key=s.openrouter_api_key,
            timeout=s.llm_timeout_s,
            max_retries=0,
        )

    async def complete(self, messages, *, json_schema=None, max_tokens=1200, temperature=0.2):
        kwargs: dict[str, Any] = dict(
            model=self._model, messages=messages, max_tokens=max_tokens, temperature=temperature
        )
        if json_schema is not None:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "requirements", "schema": json_schema, "strict": False},
            }
        try:
            resp = await self._client.chat.completions.create(**kwargs)
        except Exception as exc:
            # Model may not support json_schema: retry once as plain text with JSON-in-prompt.
            if (
                json_schema is None
                or "response_format" not in str(exc).lower()
                and getattr(exc, "status_code", None) != 400
            ):
                raise
            kwargs.pop("response_format")
            resp = await self._client.chat.completions.create(**kwargs)
        usage = {
            "prompt": getattr(resp.usage, "prompt_tokens", 0) or 0,
            "completion": getattr(resp.usage, "completion_tokens", 0) or 0,
        }
        log_event(
            log,
            "llm.complete",
            tokens_prompt=usage["prompt"],
            tokens_completion=usage["completion"],
        )
        return LLMResult(resp.choices[0].message.content or "", usage)

    async def stream(self, messages, *, max_tokens=1200, temperature=0.3):
        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        )
        async for chunk in resp:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


_llm: LLMClient | None = None
_llm_override = False


def set_llm(client: LLMClient | None) -> None:
    """Inject a client (tests). Passing None forces 'LLM unavailable'."""
    global _llm, _llm_override
    _llm, _llm_override = client, True


def reset_llm() -> None:
    global _llm, _llm_override
    _llm, _llm_override = None, False


def get_llm() -> LLMClient | None:
    global _llm
    if _llm_override:
        return _llm
    if _llm is None and get_settings().llm_available:
        _llm = OpenRouterClient()
    return _llm
