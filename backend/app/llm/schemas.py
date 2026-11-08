from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

UseCase = Literal[
    "gaming", "office", "video_editing", "3d_render", "programming", "study", "streaming", "ml"
]


class GamingReq(BaseModel):
    resolution: Literal["1080p", "1440p", "4k"] | None = None
    target_fps: int | None = None
    titles: list[str] = Field(default_factory=list)


class Preferences(BaseModel):
    cpu_brand: Literal["amd", "intel", "any"] = "any"
    gpu_brand: Literal["amd", "nvidia", "intel", "any"] = "any"
    form_factor: Literal["any", "compact", "mini_itx"] = "any"
    wifi_required: bool = False
    min_ram_gb: int | None = None
    min_storage_gb: int | None = None
    quiet: bool = False
    rgb: bool = False
    no_discrete_gpu: bool = False


class Requirements(BaseModel):
    use_cases: list[UseCase] = Field(default_factory=lambda: ["office"])  # type: ignore[arg-type,return-value]
    primary_use_case: str = "office"
    budget_rub: int | None = None
    budget_is_strict: bool = True
    gaming: GamingReq | None = None
    preferences: Preferences = Field(default_factory=Preferences)
    must_include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)
    notes: str | None = None
    confidence: float = 0.5
    budget_assumed: bool = False  # set by the pipeline when no budget was given
