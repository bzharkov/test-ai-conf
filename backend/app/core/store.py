"""Persistence for requests / builds / chat. PgStore in production, MemoryStore when the DB is
unreachable (and in tests). Both keep the same dict-shaped records."""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from typing import Any, Protocol

from sqlalchemy import select, update

from app.db.models import BuildRow, ChatMessageRow, RequestRow
from app.db.session import get_session_maker


class Store(Protocol):
    async def save_request(self, session_id: str, raw_text: str, parsed: dict) -> int: ...
    async def get_request(self, request_id: int) -> dict | None: ...
    async def save_build(self, data: dict) -> int: ...
    async def get_build(self, build_id: int) -> dict | None: ...
    async def set_explanation(self, build_id: int, text: str) -> None: ...
    async def history(self, session_id: str, limit: int = 20) -> list[dict]: ...
    async def add_chat(self, build_id: int, role: str, content: str) -> None: ...
    async def get_chat(self, build_id: int, limit: int | None = None) -> list[dict]: ...


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class MemoryStore:
    def __init__(self) -> None:
        self.requests: dict[int, dict] = {}
        self.builds: dict[int, dict] = {}
        self.chat: dict[int, list[dict]] = {}

    async def save_request(self, session_id, raw_text, parsed):
        rid = len(self.requests) + 1
        self.requests[rid] = {
            "id": rid,
            "session_id": session_id,
            "raw_text": raw_text,
            "parsed_requirements": parsed,
            "created_at": _now(),
        }
        return rid

    async def get_request(self, request_id):
        return copy.deepcopy(self.requests.get(request_id))

    async def save_build(self, data):
        bid = len(self.builds) + 1
        self.builds[bid] = {**copy.deepcopy(data), "id": bid, "created_at": _now()}
        return bid

    async def get_build(self, build_id):
        return copy.deepcopy(self.builds.get(build_id))

    async def set_explanation(self, build_id, text):
        if build_id in self.builds:
            self.builds[build_id]["explanation"] = text

    async def history(self, session_id, limit=20):
        out = []
        for r in sorted(self.requests.values(), key=lambda r: -r["id"]):
            if r["session_id"] != session_id:
                continue
            bs = [b for b in self.builds.values() if b.get("request_id") == r["id"]]
            out.append(
                {
                    "request_id": r["id"],
                    "text": r["raw_text"],
                    "created_at": r["created_at"],
                    "builds": [
                        {"id": b["id"], "label": b["label"], "total_price": b["total_price"]}
                        for b in bs
                    ],
                }
            )
        return out[:limit]

    async def add_chat(self, build_id, role, content):
        self.chat.setdefault(build_id, []).append(
            {"role": role, "content": content, "created_at": _now()}
        )

    async def get_chat(self, build_id, limit=None):
        msgs = self.chat.get(build_id, [])
        return copy.deepcopy(msgs[-limit:] if limit else msgs)


class PgStore:
    async def save_request(self, session_id, raw_text, parsed):
        async with get_session_maker()() as s:
            row = RequestRow(session_id=session_id, raw_text=raw_text, parsed_requirements=parsed)
            s.add(row)
            await s.commit()
            return row.id

    async def get_request(self, request_id):
        async with get_session_maker()() as s:
            r = await s.get(RequestRow, request_id)
            if r is None:
                return None
            return {
                "id": r.id,
                "session_id": r.session_id,
                "raw_text": r.raw_text,
                "parsed_requirements": r.parsed_requirements,
                "created_at": r.created_at.isoformat(),
            }

    @staticmethod
    def _build_dict(b: BuildRow) -> dict[str, Any]:
        return {
            "id": b.id,
            "request_id": b.request_id,
            "label": b.label,
            "items": b.items,
            "total_price": float(b.total_price),
            "estimated_power_w": b.estimated_power_w,
            "psu_recommended_w": b.psu_recommended_w,
            "score": b.score,
            "explanation": b.explanation,
            "warnings": b.warnings,
            "extra": b.extra or {},
            "created_at": b.created_at.isoformat(),
        }

    async def save_build(self, data):
        async with get_session_maker()() as s:
            row = BuildRow(
                request_id=data.get("request_id"),
                label=data["label"],
                items=data["items"],
                total_price=data["total_price"],
                estimated_power_w=data["estimated_power_w"],
                psu_recommended_w=data["psu_recommended_w"],
                score=data["score"],
                explanation=data.get("explanation"),
                warnings=data["warnings"],
                extra=data.get("extra", {}),
            )
            s.add(row)
            await s.commit()
            return row.id

    async def get_build(self, build_id):
        async with get_session_maker()() as s:
            b = await s.get(BuildRow, build_id)
            return self._build_dict(b) if b else None

    async def set_explanation(self, build_id, text):
        async with get_session_maker()() as s:
            await s.execute(
                update(BuildRow).where(BuildRow.id == build_id).values(explanation=text)
            )
            await s.commit()

    async def history(self, session_id, limit=20):
        async with get_session_maker()() as s:
            reqs = (
                (
                    await s.execute(
                        select(RequestRow)
                        .where(RequestRow.session_id == session_id)
                        .order_by(RequestRow.id.desc())
                        .limit(limit)
                    )
                )
                .scalars()
                .all()
            )
            out = []
            for r in reqs:
                bs = (
                    (
                        await s.execute(
                            select(BuildRow)
                            .where(BuildRow.request_id == r.id)
                            .order_by(BuildRow.id)
                        )
                    )
                    .scalars()
                    .all()
                )
                out.append(
                    {
                        "request_id": r.id,
                        "text": r.raw_text,
                        "created_at": r.created_at.isoformat(),
                        "builds": [
                            {"id": b.id, "label": b.label, "total_price": float(b.total_price)}
                            for b in bs
                        ],
                    }
                )
            return out

    async def add_chat(self, build_id, role, content):
        async with get_session_maker()() as s:
            s.add(ChatMessageRow(build_id=build_id, role=role, content=content))
            await s.commit()

    async def get_chat(self, build_id, limit=None):
        async with get_session_maker()() as s:
            rows = (
                (
                    await s.execute(
                        select(ChatMessageRow)
                        .where(ChatMessageRow.build_id == build_id)
                        .order_by(ChatMessageRow.id)
                    )
                )
                .scalars()
                .all()
            )
            msgs = [
                {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
                for m in rows
            ]
            return msgs[-limit:] if limit else msgs


_store: Store | None = None


def set_store(s: Store | None) -> None:
    global _store
    _store = s


def get_store() -> Store:
    global _store
    if _store is None:
        _store = MemoryStore()
    return _store
