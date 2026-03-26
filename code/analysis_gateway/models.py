from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


ProviderName = Literal["local", "deepseek"]


class HistoryPoint(BaseModel):
    timestamp: int = Field(..., description="Unix epoch milliseconds")
    spend: float = Field(..., ge=0)


class AnalysisEvent(BaseModel):
    current_spend: float = Field(..., ge=0)
    increase_amount: float
    compare_interval_min: int = Field(..., ge=1)
    threshold: float = Field(..., ge=0)
    baseline_time: int | None = None
    event_time: int | None = None
    extra_metrics: dict[str, Any] = Field(default_factory=dict)


class AnalysisRequest(BaseModel):
    provider_override: ProviderName | None = None
    event: AnalysisEvent
    history: list[HistoryPoint] = Field(default_factory=list)
    business_context: str | None = None


class DetectionSummary(BaseModel):
    anomaly_type: str
    severity: str
    score: float
    zscore: float | None = None
    evidence: list[str] = Field(default_factory=list)
    recommendation: str


class AnalysisResponse(BaseModel):
    provider: str
    model: str
    detection: DetectionSummary
    summary: str
    raw_text: str
