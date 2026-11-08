"""Anti-hallucination validation of LLM texts (TZ 8.7)."""

from __future__ import annotations

import logging
import re
from collections import Counter
from collections.abc import Awaitable, Callable, Iterable

from app.domain import Component

log = logging.getLogger("validator")
STATS: Counter = Counter()  # violations / regenerations / dropped sentences (eval metrics)

MENTION_RES = [
    re.compile(r"RTX\s?\d{4}(?:\s?(?:Ti\s?SUPER|Ti|SUPER))?", re.I),
    re.compile(r"GTX\s?\d{3,4}(?:\s?Ti)?", re.I),
    re.compile(r"\bRX\s?\d{4}(?:\s?(?:XTX|XT|GRE))?", re.I),
    re.compile(r"\bArc\s?[AB]\d{3}", re.I),
    re.compile(r"Ryzen\s?(?:Threadripper\s?)?\d?\s?\d{4}[A-Z0-9]*", re.I),
    re.compile(r"Core\s?Ultra\s?\d\s?\d{3}[A-Z]*", re.I),
    re.compile(r"(?:Core\s?)?\bi[3579]-\d{4,5}[A-Z]{0,2}\b", re.I),
]
# generic "model-like" tokens (RM850e, NV2, AK400, B650M...) checked against the catalog
TOKEN_RE = re.compile(r"\b[A-Z]{1,4}-?\d{2,4}[A-Za-z]{0,3}\b")


def norm(s: str) -> str:
    s = re.sub(r"[\s\-]+", "", s.lower())
    return s[4:] if s.startswith("core") and not s.startswith("coreultra") else s


def extract_mentions(text: str) -> list[str]:
    found: list[str] = []
    for rx in MENTION_RES:
        for m in rx.finditer(text):
            n = norm(m.group(0))
            if n not in found:
                found.append(n)
    return found


def _tokens(text: str) -> set[str]:
    return {norm(m.group(0)) for m in TOKEN_RE.finditer(text)}


class Vocabulary:
    """Allowed mentions (from the build + analog context) and the whole-catalog token index."""

    def __init__(self, allowed: Iterable[Component], catalog: Iterable[Component]) -> None:
        self.allowed_mentions: set[str] = set()
        self.allowed_tokens: set[str] = set()
        for c in allowed:
            txt = f"{c.name} {c.model} {c.specs.get('chipset', '')}"
            self.allowed_mentions.update(extract_mentions(txt))
            self.allowed_tokens.update(_tokens(txt))
        self.catalog_mentions: set[str] = set()
        self.catalog_tokens: set[str] = set()
        for c in catalog:
            txt = f"{c.name} {c.model} {c.specs.get('chipset', '')}"
            self.catalog_mentions.update(extract_mentions(txt))
            self.catalog_tokens.update(_tokens(txt))


def find_violations(text: str, vocab: Vocabulary) -> list[str]:
    bad: list[str] = []
    for m in extract_mentions(text):
        if m not in vocab.allowed_mentions:
            bad.append(m)
    for t in _tokens(text):
        if (
            t in vocab.catalog_tokens
            and t not in vocab.allowed_tokens
            and not any(t in a for a in vocab.allowed_tokens | vocab.allowed_mentions)
            and t not in bad
        ):
            bad.append(t)
    return bad


def drop_violating_sentences(text: str, violations: list[str]) -> str:
    parts = re.split(r"(?<=[.!?\n])\s+", text)
    kept = []
    dropped = 0
    for p in parts:
        n = norm(p)
        if any(v in n for v in violations):
            dropped += 1
            continue
        kept.append(p)
    out = " ".join(kept).strip()
    if dropped:
        STATS["dropped_sentences"] += dropped
        out += "\n\n_Часть ответа удалена: в ней упоминались комплектующие вне подобранной сборки._"
    return out


async def validate_and_fix(
    text: str, vocab: Vocabulary, regenerate: Callable[[list[str]], Awaitable[str]] | None
) -> tuple[str, list[str]]:
    """Returns (final_text, violations_found_initially)."""
    bad = find_violations(text, vocab)
    if not bad:
        return text, []
    STATS["violations"] += len(bad)
    log.warning("llm output mentions out-of-context models: %s", bad)
    if regenerate is not None:
        STATS["regenerations"] += 1
        try:
            retry = await regenerate(bad)
        except Exception:
            retry = ""
        if retry and not find_violations(retry, vocab):
            return retry, bad
    return drop_violating_sentences(text, bad), bad
