from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


ProviderName = Literal["local", "deepseek"]
HealthStatus = Literal["green", "yellow", "red"]
CaptureStatus = Literal["success", "warning", "error"]
AlertSendStatus = Literal["sent", "failed", "skipped"]


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


class SignedPayload(BaseModel):
    timestamp: int | None = Field(default=None, description="Unix epoch milliseconds")
    nonce: str | None = None
    signature: str | None = None


class IngestRequest(SignedPayload):
    instance_id: str | None = Field(default=None, min_length=1)
    account_id: str | None = None
    account_name: str | None = None
    page_type: str | None = None
    page_url: str | None = None
    script_version: str | None = None
    captured_at: int = Field(..., description="Unix epoch milliseconds")
    metrics: dict[str, Any] = Field(default_factory=dict)
    raw_context: dict[str, Any] = Field(default_factory=dict)
    row_count: int | None = Field(default=None, ge=0)


class HeartbeatRequest(SignedPayload):
    instance_id: str | None = Field(default=None, min_length=1)
    script_version: str | None = None
    page_url: str | None = None
    page_type: str | None = None
    heartbeat_at: int = Field(..., description="Unix epoch milliseconds")
    browser_visible: bool | None = None
    capture_status: CaptureStatus = "success"
    last_capture_at: int | None = None
    row_count: int | None = Field(default=None, ge=0)
    error_message: str | None = None
    account_id: str | None = None
    account_name: str | None = None


class ErrorReportRequest(SignedPayload):
    instance_id: str | None = Field(default=None, min_length=1)
    occurred_at: int = Field(..., description="Unix epoch milliseconds")
    error_type: str = Field(..., min_length=1)
    error_message: str = Field(..., min_length=1)
    page_url: str | None = None
    script_version: str | None = None


class AlertRecordRequest(SignedPayload):
    instance_id: str | None = Field(default=None, min_length=1)
    account_id: str | None = None
    account_name: str | None = None
    page_type: str | None = None
    page_url: str | None = None
    script_version: str | None = None
    alert_kind: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    content_preview: str | None = None
    channel: str | None = None
    channel_option: str | None = None
    delivery_provider: str = Field(default="pushplus", min_length=1)
    send_status: AlertSendStatus
    provider_response: str | None = None
    severity: str | None = None
    anomaly_type: str | None = None
    triggered_at: int = Field(..., description="Unix epoch milliseconds")


class ApiAck(BaseModel):
    ok: bool = True
    message: str = "ok"
    server_time: int
    next_suggested_interval_sec: int | None = None


class AdminInstanceSummary(BaseModel):
    instance_id: str
    account_id: str | None = None
    account_name: str | None = None
    page_type: str | None = None
    page_url: str | None = None
    script_version: str | None = None
    health_status: HealthStatus
    last_seen_at: int | None = None
    last_heartbeat_at: int | None = None
    last_capture_at: int | None = None
    last_capture_status: str | None = None
    last_error: str | None = None
    consecutive_error_count: int = 0
    last_row_count: int | None = None
    last_analysis_at: int | None = None
    last_analysis_summary: str | None = None
    last_analysis_provider: str | None = None
    last_analysis_model: str | None = None
    last_anomaly_type: str | None = None
    last_anomaly_severity: str | None = None


class AdminSummary(BaseModel):
    total_instances: int
    green_instances: int
    yellow_instances: int
    red_instances: int
    latest_capture_at: int | None = None
    latest_heartbeat_at: int | None = None
    total_analyses: int = 0
    total_alerts: int = 0
    latest_alert_at: int | None = None


class AdminAlertRecord(BaseModel):
    id: int
    instance_id: str
    account_id: str | None = None
    account_name: str | None = None
    page_type: str | None = None
    page_url: str | None = None
    script_version: str | None = None
    alert_kind: str
    title: str
    content_preview: str | None = None
    channel: str | None = None
    channel_option: str | None = None
    delivery_provider: str
    send_status: AlertSendStatus
    provider_response: str | None = None
    severity: str | None = None
    anomaly_type: str | None = None
    triggered_at: int
    created_at: int


class AdminCaptureHistoryPoint(BaseModel):
    captured_at: int
    current_spend: float
    increase_amount: float = 0
    baseline_spend: float | None = None
    compare_interval_min: int | None = None
    notify_threshold: float | None = None
    row_count: int | None = None


class AdminErrorRecord(BaseModel):
    id: int
    error_type: str
    error_message: str
    occurred_at: int
    page_url: str | None = None
    script_version: str | None = None


class AdminAnalysisRecord(BaseModel):
    id: int
    provider: str
    model: str
    anomaly_type: str
    severity: str
    score: float
    summary: str
    raw_text: str
    created_at: int


class AdminInstanceDetail(AdminInstanceSummary):
    recent_errors: list[AdminErrorRecord] = Field(default_factory=list)
    recent_alerts: list[AdminAlertRecord] = Field(default_factory=list)
    recent_analyses: list[AdminAnalysisRecord] = Field(default_factory=list)
    capture_history: list[AdminCaptureHistoryPoint] = Field(default_factory=list)
