from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.llm.schemas import Requirements


class Warn(BaseModel):
    code: str
    message_ru: str


class ConfigureRequest(BaseModel):
    text: str = Field(min_length=3, max_length=1500)
    filters: dict[str, Any] | None = None
    requirements: Requirements | None = None  # edited "I understood" block: skips parsing
    session_id: str = Field(min_length=1, max_length=64)


class ComponentOut(BaseModel):
    id: int
    category: str
    category_ru: str
    brand: str
    model: str
    name: str
    specs: dict[str, Any]
    perf_score: float | None = None
    perf_multicore: float | None = None
    perf_estimated: bool = False
    price_rub: float | None = None
    in_stock: bool = False
    price_source: str | None = None
    price_updated_at: str | None = None
    price_is_demo: bool = False
    source: str


class KeyComponents(BaseModel):
    cpu: str | None = None
    gpu: str | None = None
    ram: str | None = None
    storage: str | None = None


class BuildSummary(BaseModel):
    id: int
    label: str
    total_price: float
    budget_rub: int | None
    budget_share: float | None
    over_budget: bool
    compat_ok: bool
    prices_are_demo: bool
    key_components: KeyComponents
    warnings: list[Warn]


class ConfigureResponse(BaseModel):
    request_id: int
    requirements: Requirements
    builds: list[BuildSummary]
    warnings: list[Warn]
    min_feasible_price: float | None = None


class PowerItem(BaseModel):
    label: str
    watts: int


class PowerOut(BaseModel):
    items: list[PowerItem]
    estimated_power_w: int
    margin: float
    gpu_recommended_psu_w: int
    psu_recommended_w: int
    installed_psu_w: int | None


class RuleStatus(BaseModel):
    code: str
    title: str
    status: Literal["ok", "warning", "error"]
    messages: list[str]


class IssueOut(BaseModel):
    code: str
    severity: Literal["error", "warning"]
    message_ru: str
    components: list[str]


class Compatibility(BaseModel):
    ok: bool
    rules: list[RuleStatus]
    issues: list[IssueOut]


class BuildOut(BuildSummary):
    request_id: int | None
    created_at: str
    items: list[ComponentOut]
    power: PowerOut
    compatibility: Compatibility
    explanation: str | None
    requirements: Requirements | None = None


class ReplaceRequest(BaseModel):
    category: str
    component_id: int
    extra_component_id: int | None = None  # e.g. PSU upgrade offered with an analog


class ReplaceResponse(BaseModel):
    build: BuildOut
    replaced: dict[str, Any]


class AlternativeOut(BaseModel):
    component_id: int
    name: str
    category: str
    price_rub: float | None
    price_delta_rub: float
    total_delta_rub: float
    perf_delta_pct: float | None
    compat_ok: bool
    notes: list[str]
    extra_component_id: int | None = None
    extra_component_name: str | None = None


class CompareRequest(BaseModel):
    build_ids: list[int] = Field(min_length=2, max_length=3)


class CompareCell(BaseModel):
    name: str | None
    price_rub: float | None


class CompareRow(BaseModel):
    category: str
    category_ru: str
    cells: list[CompareCell]
    differs: bool


class CompareResponse(BaseModel):
    builds: list[BuildSummary]
    rows: list[CompareRow]
    totals: list[float]
    power_w: list[int]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    session_id: str | None = None


class ChatMessageOut(BaseModel):
    role: str
    content: str
    created_at: str


class HistoryBuild(BaseModel):
    id: int
    label: str
    total_price: float


class HistoryItem(BaseModel):
    request_id: int
    text: str
    created_at: str
    builds: list[HistoryBuild]
