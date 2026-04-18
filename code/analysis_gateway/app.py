from __future__ import annotations

import asyncio
import csv
import html
import mimetypes
import io
import json
import os
import time
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response

from admin_ui import build_admin_dashboard_html, build_alerts_page_html, build_instance_detail_html
from anomaly import detect_spend_anomaly
from database import (
    create_strategy_definition,
    delete_instance_records,
    delete_instance_strategy_binding,
    delete_strategy_definition,
    ensure_database,
    fetch_admin_alerts,
    fetch_admin_instance_strategies,
    fetch_admin_instances,
    fetch_admin_strategies,
    fetch_active_instance_strategy_bindings,
    fetch_capture_history_for_instance,
    fetch_capture_event_id,
    fetch_history_for_instance,
    fetch_instance_detail,
    fetch_latest_alert_for_instance_kind,
    fetch_latest_analysis_for_instance,
    fetch_instance_strategy_bindings,
    fetch_strategy_hits_for_instance,
    fetch_admin_summary,
    list_metric_registry,
    open_connection,
    save_alert_record,
    save_error_report,
    save_heartbeat,
    save_ingest_event,
    save_analysis_summary,
    save_instance_strategy_binding,
    save_strategy_hit,
    utc_now_ms,
    update_strategy_definition,
    update_instance_metadata,
)
from models import (
    AdminAlertRecord,
    AdminCaptureHistoryPoint,
    AdminInstanceDetail,
    AdminInstanceStrategyRecord,
    AdminInstanceSummary,
    AdminSystemSettings,
    AdminSummary,
    AnalysisRequest,
    AnalysisEvent,
    AnalysisResponse,
    AlertRecordRequest,
    ApiAck,
    CreateStrategyDefinitionRequest,
    ErrorReportRequest,
    HistoryPoint,
    HeartbeatRequest,
    InstanceMetadataResponse,
    InstanceChatRequest,
    InstanceChatResponse,
    InstanceStrategyBindingRequest,
    InstanceStrategyBindingResponse,
    IngestRequest,
    MetricRegistryItem,
    ProviderConnectivityResponse,
    ProviderSettings,
    PushplusSettings,
    StrategyDefinitionResponse,
    StrategyHitResponse,
    TestAlertRequest,
    UpdateAdminSystemSettingsRequest,
    UpdateStrategyDefinitionRequest,
    UpdateInstanceMetadataRequest,
)
from providers import OpenAICompatibleProvider, ProviderResult
from strategy_engine import execute_strategy


APP_DIR = Path(__file__).resolve().parent
ROOT_DIR = APP_DIR.parent.parent
DATA_DIR = ROOT_DIR / "data"
DEFAULT_DB_PATH = DATA_DIR / "app.db"
CONFIG_PATH = APP_DIR / "config.json"
EXAMPLE_CONFIG_PATH = APP_DIR / "config.example.json"
ADMIN_FRONTEND_DIR = APP_DIR / "admin_frontend"
ADMIN_FRONTEND_DIST_DIR = ADMIN_FRONTEND_DIR / "dist"

DEFAULT_CONTEXT = (
    "业务背景：快手磁力金牛在高客单价、目标成本偏高时，可能引入低质量流量，"
    "造成异常消耗和成本失控。请基于给定指标区分正常波动与异常放量风险，输出风险等级、证据和操作建议。"
)
MODEL_ANALYSIS_COOLDOWN_MS = int(os.getenv("ADBUDGET_ANALYSIS_COOLDOWN_MS", str(10 * 60 * 1000)))
DEFAULT_ALERTS_CONFIG = {
    "enabled": True,
    "threshold_cooldown_minutes": 10,
    "offline_after_minutes": 10,
    "offline_cooldown_minutes": 60,
    "failure_cooldown_minutes": 30,
    "health_scan_interval_sec": 60,
    "failure_consecutive_count": 3,
    "pushplus": {
        "enabled": True,
        "token": "",
        "channel": "mail",
        "option": "",
    },
}


def load_config() -> dict:
    path = CONFIG_PATH if CONFIG_PATH.exists() else EXAMPLE_CONFIG_PATH
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def get_db_path() -> Path:
    raw = os.getenv("ADBUDGET_DB_PATH")
    return Path(raw).expanduser().resolve() if raw else DEFAULT_DB_PATH


def get_alerts_config(config: dict | None = None) -> dict:
    config = config or load_config()
    alerts = dict(DEFAULT_ALERTS_CONFIG)
    alerts.update(config.get("alerts") or {})
    pushplus = dict(DEFAULT_ALERTS_CONFIG["pushplus"])
    pushplus.update(alerts.get("pushplus") or {})
    alerts["pushplus"] = pushplus
    return alerts


def get_pushplus_config(config: dict | None = None) -> dict:
    return get_alerts_config(config)["pushplus"]


def save_config(config: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def mask_token(token: str | None) -> str | None:
    raw = (token or "").strip()
    if not raw:
        return None
    if len(raw) <= 8:
        return "*" * len(raw)
    return f"{raw[:4]}...{raw[-4:]}"


def build_admin_settings(config: dict | None = None) -> AdminSystemSettings:
    config = config or load_config()
    pushplus = get_pushplus_config(config)
    deepseek = config.get("deepseek") or {}
    local = config.get("local") or {}
    token = str(pushplus.get("token") or "")

    return AdminSystemSettings(
        default_provider=config.get("default_provider", "deepseek"),
        deepseek=ProviderSettings(
            base_url=str(deepseek.get("base_url") or ""),
            model=str(deepseek.get("model") or ""),
            api_key="",
        ),
        local=ProviderSettings(
            base_url=str(local.get("base_url") or ""),
            model=str(local.get("model") or ""),
            api_key="",
        ),
        pushplus=PushplusSettings(
            enabled=bool(pushplus.get("enabled", True)),
            channel=str(pushplus.get("channel") or "mail"),
            channel_option=str(pushplus.get("option") or ""),
            has_token=bool(token),
            token_preview=mask_token(token),
            token="",
        ),
    )


def update_system_settings(request: UpdateAdminSystemSettingsRequest) -> AdminSystemSettings:
    existing = load_config()

    existing["default_provider"] = request.default_provider
    existing["deepseek"] = {
        **(existing.get("deepseek") or {}),
        "base_url": request.deepseek.base_url.strip(),
        "model": request.deepseek.model.strip(),
        "api_key": request.deepseek.api_key.strip() or (existing.get("deepseek") or {}).get("api_key", ""),
    }
    existing["local"] = {
        **(existing.get("local") or {}),
        "base_url": request.local.base_url.strip(),
        "model": request.local.model.strip(),
        "api_key": request.local.api_key.strip() or (existing.get("local") or {}).get("api_key", ""),
    }

    alerts = dict(existing.get("alerts") or {})
    pushplus = dict(alerts.get("pushplus") or {})
    pushplus.update(
        {
            "enabled": request.pushplus.enabled,
            "channel": request.pushplus.channel.strip() or "mail",
            "option": request.pushplus.channel_option.strip(),
        }
    )
    if request.pushplus.token.strip():
        pushplus["token"] = request.pushplus.token.strip()
    alerts["pushplus"] = pushplus
    existing["alerts"] = alerts

    save_config(existing)
    return build_admin_settings(existing)


def build_provider_test_prompt() -> str:
    return (
        "请执行一次连通性测试，并用一句中文短句回复当前模型可用。"
        "不要展开解释，不要使用 Markdown，只返回测试结果。"
    )


def build_instance_chat_context(detail: dict, history: list[dict]) -> str:
    latest_history = list(reversed(history[-12:]))
    history_lines = [
        f"- {format_time(item.get('captured_at'))} / 总花费 {item.get('current_spend') or 0:.2f} / "
        f"窗口增量 {item.get('increase_amount') or 0:.2f} / 阈值 {item.get('notify_threshold') or 0:.2f}"
        for item in latest_history
    ] or ["- 暂无最近采样"]
    recent_alerts = detail.get("recent_alerts", [])[:5]
    alert_lines = [
        f"- {format_time(item.get('triggered_at'))} / {item.get('alert_kind') or '-'} / {item.get('title') or '-'}"
        for item in recent_alerts
    ] or ["- 暂无最近告警"]
    recent_analyses = detail.get("recent_analyses", [])[:5]
    analysis_lines = [
        f"- {format_time(item.get('created_at'))} / {item.get('summary') or '-'}"
        for item in recent_analyses
    ] or ["- 暂无最近分析"]

    return "\n".join(
        [
            "当前实例上下文：",
            f"实例 ID：{detail.get('instance_id') or '-'}",
            f"账户：{format_account_identity(detail.get('account_name'), detail.get('account_id'))}",
            f"页面类型：{detail.get('page_type') or '-'}",
            f"健康状态：{detail.get('health_status') or '-'}",
            f"最新总花费：{detail.get('latest_current_spend') or 0:.2f}",
            f"最新窗口增量：{detail.get('latest_increase_amount') or 0:.2f}",
            "最近采样：",
            *history_lines,
            "最近告警：",
            *alert_lines,
            "最近分析：",
            *analysis_lines,
        ]
    )


def parse_date_start_ms(value: str) -> int | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        dt = datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None
    return int(dt.timestamp() * 1000)


def parse_date_end_ms(value: str) -> int | None:
    start_ms = parse_date_start_ms(value)
    if start_ms is None:
        return None
    return start_ms + (24 * 60 * 60 * 1000) - 1


def normalize_alert_kind(value: str | None) -> str:
    raw = (value or "").strip()
    if raw == "threshold_exceeded":
        return "threshold"
    return raw


def compute_cooldown_ms(minutes: int | float | None, fallback_minutes: int) -> int:
    try:
        value = int(minutes) if minutes is not None else fallback_minutes
    except (TypeError, ValueError):
        value = fallback_minutes
    return max(1, value) * 60 * 1000


def build_provider(config: dict, provider_name: str) -> OpenAICompatibleProvider:
    provider_config = config.get(provider_name)
    if not provider_config:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider_name}")

    return OpenAICompatibleProvider(
        provider_name=provider_name,
        base_url=provider_config["base_url"],
        api_key=provider_config.get("api_key", ""),
        model=provider_config["model"],
    )


def build_prompt(request: AnalysisRequest, detection_summary) -> str:
    event = request.event
    context = request.business_context or DEFAULT_CONTEXT
    metrics = json.dumps(event.extra_metrics, ensure_ascii=False)
    evidence_lines = "\n".join(f"- {item}" for item in detection_summary.evidence)

    return f"""
{context}

Current monitoring event:
- Current total spend: {event.current_spend:.2f}
- Window increase: {event.increase_amount:.2f}
- Compare window: {event.compare_interval_min} minutes
- Alert threshold: {event.threshold:.2f}
- Rule anomaly type: {detection_summary.anomaly_type}
- Rule severity: {detection_summary.severity}
- Rule score: {detection_summary.score}
- Extra metrics: {metrics}

Rule evidence:
{evidence_lines}

You are an ad-spend anomaly monitoring assistant. Base your answer only on the provided metrics and rule evidence. Do not invent data. Do not directly conclude fraud, fake orders,?? or intentional platform traffic manipulation.

Output exactly in this format:
缁撹锛歰ne concise sentence
鍘熷洜鍒ゆ柇锛?
1. ...
2. ...
寤鸿锛?
1. ...
2. ...

Requirements:
1. The conclusion must be clear and within one line.
2. Reasoning must only use the given inputs and rule evidence.
3. Suggestions must be concrete and executable for monitoring or troubleshooting.
4. No greetings, no extra headings, no repetition of raw inputs.
5. Keep the whole answer within 6 to 8 lines.
""".strip()


def fallback_text(detection_summary) -> str:
    evidence = "；".join(detection_summary.evidence[:2]) or "暂无额外规则证据"
    return "\n".join(
        [
            f"结论：规则检测命中 {detection_summary.anomaly_type}，严重度 {detection_summary.severity}。",
            "原因判断：",
            f"1. {evidence}",
            "建议：",
            f"1. {detection_summary.recommendation}",
        ]
    )


def extract_analysis_summary(raw_text: str) -> str:
    lines = [line.strip() for line in str(raw_text or "").splitlines() if line.strip()]
    if not lines:
        return ""

    for line in lines:
        if line.startswith("结论："):
            return line.removeprefix("结论：").strip()
        if line.startswith("结论:"):
            return line.removeprefix("结论:").strip()

    return lines[0]

def format_time(timestamp_ms: int | None) -> str:
    if not timestamp_ms:
        return "-"
    return datetime.fromtimestamp(timestamp_ms / 1000).strftime("%Y-%m-%d %H:%M:%S")


def compact_text(value: str | None, limit: int = 100) -> str:
    if not value:
        return "-"
    raw = " ".join(str(value).split())
    return raw if len(raw) <= limit else f"{raw[: limit - 3]}..."


def is_missing_account_id(value: str | None) -> bool:
    return value in {None, "", "未识别账户ID"}


def format_account_identity(account_name: str | None, account_id: str | None) -> str:
    name = (account_name or "").strip()
    account_id = None if is_missing_account_id(account_id) else (account_id or "").strip()
    if name and account_id:
        return f"{name} 路 {account_id}"
    if name:
        return name
    if account_id:
        return account_id
    return "未绑定账户"


def build_chip(label: str, tone: str) -> str:
    palette = {
        "teal": ("rgba(45, 212, 191, 0.16)", "#0f766e"),
        "green": ("rgba(134, 239, 172, 0.22)", "#166534"),
        "yellow": ("rgba(253, 224, 71, 0.24)", "#a16207"),
        "red": ("rgba(252, 165, 165, 0.24)", "#b91c1c"),
        "blue": ("rgba(147, 197, 253, 0.24)", "#1d4ed8"),
        "slate": ("rgba(203, 213, 225, 0.34)", "#334155"),
    }
    bg, fg = palette.get(tone, palette["slate"])
    return (
        f'<span class="chip" style="background:{bg};color:{fg};">'
        f"{html.escape(label)}</span>"
    )


def build_account_lines(account_name: str | None, account_id: str | None) -> list[str]:
    lines = [f"账户名称：{account_name or '未识别账户'}"]
    if not is_missing_account_id(account_id):
        lines.append(f"账户 ID：{account_id}")
    return lines


def build_alert_mail_html(title: str, lines: list[str]) -> str:
    escaped_rows = "".join(f"<p>{html.escape(line)}</p>" for line in lines)
    return (
        "<div style=\"font-family:sans-serif;padding:14px;border:1px solid #e5e7eb;border-radius:8px;\">"
        f"<h2 style=\"color:#0f172a;\">{html.escape(title)}</h2>"
        f"{escaped_rows}"
        "</div>"
    )


async def dispatch_pushplus_alert(
    db_path: Path,
    *,
    instance_id: str,
    account_id: str | None,
    account_name: str | None,
    page_type: str | None,
    page_url: str | None,
    script_version: str | None,
    alert_kind: str,
    title: str,
    content_preview: str,
    content_html: str,
    severity: str | None,
    anomaly_type: str | None,
    triggered_at: int,
    cooldown_ms: int,
    strategy_id: int | None = None,
    strategy_hit_id: int | None = None,
    capture_event_id: int | None = None,
    strategy_name: str | None = None,
    target_metric: str | None = None,
    force: bool = False,
) -> dict:
    latest_record = fetch_latest_alert_for_instance_kind(db_path, instance_id, alert_kind)
    if (
        not force
        and latest_record
        and latest_record.get("triggered_at")
        and triggered_at - int(latest_record["triggered_at"]) < cooldown_ms
    ):
        return {"ok": False, "skipped": True, "reason": "cooldown"}

    config = load_config()
    alerts_config = get_alerts_config(config)
    pushplus = get_pushplus_config(config)
    channel = pushplus.get("channel") or "mail"
    channel_option = pushplus.get("option") or ""

    record_payload = {
        "instance_id": instance_id,
        "account_id": account_id,
        "account_name": account_name,
        "page_type": page_type,
        "page_url": page_url,
        "script_version": script_version,
        "alert_kind": alert_kind,
        "title": title,
        "content_preview": content_preview,
        "channel": channel,
        "channel_option": channel_option,
        "delivery_provider": "pushplus",
        "severity": severity,
        "anomaly_type": anomaly_type,
        "strategy_id": strategy_id,
        "strategy_hit_id": strategy_hit_id,
        "capture_event_id": capture_event_id,
        "strategy_name": strategy_name,
        "target_metric": target_metric,
        "triggered_at": triggered_at,
    }

    if not alerts_config.get("enabled", True):
        save_alert_record(
            db_path,
            {
                **record_payload,
                "send_status": "skipped",
                "provider_response": "alerts.enabled=false",
            },
        )
        return {"ok": False, "skipped": True, "reason": "alerts_disabled"}

    if not pushplus.get("enabled", True) or not pushplus.get("token"):
        save_alert_record(
            db_path,
            {
                **record_payload,
                "send_status": "skipped",
                "provider_response": "鏈厤缃?PushPlus Token",
            },
        )
        return {"ok": False, "skipped": True, "reason": "missing_pushplus_token"}

    try:
        async with httpx.AsyncClient(timeout=20, trust_env=False) as client:
            response = await client.post(
                "https://www.pushplus.plus/send",
                json={
                    "token": pushplus["token"],
                    "title": title,
                    "content": content_html,
                    "template": "html",
                    "channel": channel,
                    "option": channel_option,
                },
            )
        try:
            body = response.json()
        except ValueError:
            body = {"raw": response.text}
        ok = response.status_code >= 200 and response.status_code < 300 and body.get("code", 200) == 200
        save_alert_record(
            db_path,
            {
                **record_payload,
                "send_status": "sent" if ok else "failed",
                "provider_response": json.dumps(body, ensure_ascii=False)[:500],
            },
        )
        return {"ok": ok, "body": body}
    except Exception as exc:  # noqa: BLE001
        save_alert_record(
            db_path,
            {
                **record_payload,
                "send_status": "failed",
                "provider_response": str(exc)[:500],
            },
        )
        return {"ok": False, "error": str(exc)}


def build_threshold_alert_content(payload: dict) -> tuple[str, str]:
    metrics = payload.get("metrics") or {}
    account_name = payload.get("account_name") or "-"
    preview_lines = [
        f"账号名称：{account_name}",
        f"当前总消耗：{float(metrics.get('current_spend') or 0):.2f} 元",
        f"报警时间：{format_time(int(payload.get('captured_at') or utc_now_ms()))}",
        f"对比窗口：{int(metrics.get('compare_interval_min') or 0)} 分钟",
        f"窗口增量：{float(metrics.get('increase_amount') or 0):.2f} 元",
        f"阈值：{float(metrics.get('notify_threshold') or metrics.get('threshold') or 0):.2f} 元",
    ]
    title = f"【磁力金牛告警】{format_account_identity(payload.get('account_name'), payload.get('account_id'))}"
    return title, "\n".join(preview_lines)

async def maybe_send_threshold_alert(
    db_path: Path,
    payload: dict,
    detection_summary,
    summary_text: str,
) -> None:
    metrics = payload.get("metrics") or {}
    threshold = float(metrics.get("notify_threshold") or metrics.get("threshold") or 0)
    increase_amount = float(metrics.get("increase_amount") or 0)
    if threshold <= 0 or increase_amount < threshold:
        return

    config = load_config()
    alerts_config = get_alerts_config(config)
    title, content_preview = build_threshold_alert_content(payload)
    await dispatch_pushplus_alert(
        db_path,
        instance_id=payload["instance_id"],
        account_id=payload.get("account_id"),
        account_name=payload.get("account_name"),
        page_type=payload.get("page_type"),
        page_url=payload.get("page_url"),
        script_version=payload.get("script_version"),
        alert_kind="threshold",
        title=title,
        content_preview=content_preview,
        content_html=build_alert_mail_html(title, content_preview.splitlines()),
        severity=detection_summary.severity,
        anomaly_type=detection_summary.anomaly_type,
        triggered_at=int(payload.get("captured_at") or utc_now_ms()),
        cooldown_ms=compute_cooldown_ms(alerts_config.get("threshold_cooldown_minutes"), 10),
    )


async def send_test_alert(db_path: Path, request: TestAlertRequest) -> dict:
    account_label = format_account_identity(request.account_name, request.account_id)
    title = f"【磁力金牛】【测试】{account_label}"
    preview_lines = [
        "测试报警",
        *build_account_lines(request.account_name, request.account_id),
        f"脚本实例：{request.instance_id or '-'}",
        f"页面类型：{request.page_type or '-'}",
        f"当前总花费：{request.current_spend:.2f} 元",
        f"{request.compare_interval_min} 分钟增量：{request.increase_amount:.2f} 元",
        f"分析结果：{request.analysis_text or '未提供'}",
    ]
    if request.baseline_spend is not None:
        preview_lines.insert(-1, f"基线花费：{request.baseline_spend:.2f} 元")
    if request.baseline_time:
        preview_lines.insert(-1, f"基线时间：{format_time(request.baseline_time)}")
    return await dispatch_pushplus_alert(
        db_path,
        instance_id=request.instance_id or "manual-test",
        account_id=request.account_id,
        account_name=request.account_name,
        page_type=request.page_type,
        page_url=request.page_url,
        script_version=request.script_version,
        alert_kind="test",
        title=title,
        content_preview="\n".join(preview_lines),
        content_html=build_alert_mail_html(title, preview_lines),
        severity="info",
        anomaly_type="test_alert",
        triggered_at=request.triggered_at,
        cooldown_ms=0,
        force=True,
    )


async def scan_and_alert_instance_health(db_path: Path) -> None:
    config = load_config()
    alerts_config = get_alerts_config(config)
    now_ms = utc_now_ms()
    offline_after_ms = compute_cooldown_ms(alerts_config.get("offline_after_minutes"), 10)
    offline_cooldown_ms = compute_cooldown_ms(alerts_config.get("offline_cooldown_minutes"), 60)
    failure_threshold = int(alerts_config.get("failure_consecutive_count") or 3)
    failure_cooldown_ms = compute_cooldown_ms(alerts_config.get("failure_cooldown_minutes"), 30)

    for item in fetch_admin_instances(db_path):
        instance_id = item["instance_id"]
        account_label = format_account_identity(item.get("account_name"), item.get("account_id"))
        last_heartbeat_at = item.get("last_heartbeat_at")
        if last_heartbeat_at and now_ms - int(last_heartbeat_at) >= offline_after_ms:
            title = f"【磁力金牛离线】{account_label}"
            lines = [
                "实例掉线提醒",
                *build_account_lines(item.get("account_name"), item.get("account_id")),
                f"脚本实例：{instance_id}",
                f"页面类型：{item.get('page_type') or '-'}",
                f"最近心跳：{format_time(last_heartbeat_at)}",
                f"最近采集：{format_time(item.get('last_capture_at'))}",
                "问题说明：超过配置窗口未收到心跳，请检查浏览器标签、网络和脚本运行状态。",
            ]
            await dispatch_pushplus_alert(
                db_path,
                instance_id=instance_id,
                account_id=item.get("account_id"),
                account_name=item.get("account_name"),
                page_type=item.get("page_type"),
                page_url=item.get("page_url"),
                script_version=item.get("script_version"),
                alert_kind="instance_offline",
                title=title,
                content_preview="\n".join(lines),
                content_html=build_alert_mail_html(title, lines),
                severity="high",
                anomaly_type="instance_offline",
                triggered_at=now_ms,
                cooldown_ms=offline_cooldown_ms,
            )

        if (item.get("consecutive_error_count") or 0) >= failure_threshold:
            title = f"【磁力金牛采集异常】{account_label}"
            lines = [
                "连续采集失败提醒",
                *build_account_lines(item.get("account_name"), item.get("account_id")),
                f"脚本实例：{instance_id}",
                f"页面类型：{item.get('page_type') or '-'}",
                f"连续失败次数：{item.get('consecutive_error_count') or 0}",
                f"最近采集状态：{item.get('last_capture_status') or '-'}",
                f"最近错误：{item.get('last_error') or '-'}",
                "问题说明：实例持续采集失败，请检查页面结构变化、登录状态或脚本报错。",
            ]
            await dispatch_pushplus_alert(
                db_path,
                instance_id=instance_id,
                account_id=item.get("account_id"),
                account_name=item.get("account_name"),
                page_type=item.get("page_type"),
                page_url=item.get("page_url"),
                script_version=item.get("script_version"),
                alert_kind="capture_failure",
                title=title,
                content_preview="\n".join(lines),
                content_html=build_alert_mail_html(title, lines),
                severity="high",
                anomaly_type="capture_failure",
                triggered_at=now_ms,
                cooldown_ms=failure_cooldown_ms,
            )


async def health_monitor_loop() -> None:
    db_path = get_db_path()
    while True:
        try:
            await scan_and_alert_instance_health(db_path)
        except Exception:
            pass
        config = load_config()
        interval = int(get_alerts_config(config).get("health_scan_interval_sec") or 60)
        await asyncio.sleep(max(15, interval))


def extract_current_spend(metrics: dict | None) -> float | None:
    metrics = metrics or {}
    current_spend = metrics.get("current_spend")
    if current_spend is None and isinstance(metrics.get("spend"), dict):
        current_spend = metrics["spend"].get("current")
    if current_spend is None:
        return None
    try:
        return float(current_spend)
    except (TypeError, ValueError):
        return None


def build_analysis_request_from_ingest(payload: dict, history: list[dict]) -> AnalysisRequest | None:
    metrics = payload.get("metrics") or {}
    current_spend = extract_current_spend(metrics)
    if current_spend is None:
        return None

    compare_interval_min = int(metrics.get("compare_interval_min") or 30)
    threshold = float(metrics.get("notify_threshold") or metrics.get("threshold") or 0)
    extra_metrics = {
        key: value
        for key, value in metrics.items()
        if key not in {"current_spend", "increase_amount", "compare_interval_min", "notify_threshold", "threshold"}
    }
    raw_context = payload.get("raw_context") or {}
    provider_override = raw_context.get("ai_provider")
    if provider_override not in {"local", "deepseek"}:
        provider_override = None

    return AnalysisRequest(
        provider_override=provider_override,
        event=AnalysisEvent(
            current_spend=float(current_spend),
            increase_amount=float(metrics.get("increase_amount") or 0),
            compare_interval_min=compare_interval_min,
            threshold=threshold,
            baseline_time=raw_context.get("baseline_time"),
            event_time=payload.get("captured_at"),
            extra_metrics=extra_metrics,
        ),
        history=[HistoryPoint(timestamp=item["timestamp"], spend=item["spend"]) for item in history],
        business_context=raw_context.get("business_context"),
    )


def build_strategy_alert_content(binding: dict, payload: dict, result) -> tuple[str, str, str]:
    strategy_name = binding.get("strategy_name") or "未命名策略"
    title = f"【策略告警】【{strategy_name}】{format_account_identity(payload.get('account_name'), payload.get('account_id'))}"
    lines = [
        f"策略名称：{strategy_name}",
        f"模板类型：{binding.get('template_type') or '-'}",
        f"目标指标：{binding.get('target_metric') or '-'}",
        f"实例 ID：{payload.get('instance_id') or '-'}",
        f"页面类型：{payload.get('page_type') or '-'}",
        f"触发时间：{format_time(int(payload.get('captured_at') or utc_now_ms()))}",
        f"指标值：{result.metric_value:.2f}",
    ]
    if result.baseline_value is not None:
        lines.append(f"基线值：{result.baseline_value:.2f}")
    lines.extend(result.evidence[:3])
    if result.recommendation:
        lines.append(f"建议：{result.recommendation}")
    preview = "`n".join(lines)
    return title, preview, build_alert_mail_html(title, lines)


async def evaluate_ingest_strategies(db_path: Path, payload: dict) -> None:
    instance_id = payload["instance_id"]
    captured_at = int(payload.get("captured_at") or utc_now_ms())
    current_spend = extract_current_spend(payload.get("metrics"))
    if current_spend is None:
        return

    history = fetch_history_for_instance(db_path, instance_id, limit=120)
    capture_event_id = fetch_capture_event_id(db_path, instance_id, captured_at)
    bindings = fetch_active_instance_strategy_bindings(db_path, instance_id)
    triggered_results: list[tuple[dict, object]] = []

    for binding in bindings:
        result = execute_strategy(
            binding["template_type"],
            history,
            captured_at,
            binding.get("params") or {},
        )
        if not result.triggered:
            continue

        hit_id = save_strategy_hit(
            db_path,
            instance_id=instance_id,
            strategy_id=binding["strategy_id"],
            binding_id=binding.get("id"),
            capture_event_id=capture_event_id,
            target_metric=binding["target_metric"],
            strategy_name=binding["strategy_name"],
            template_type=binding["template_type"],
            severity=result.severity,
            score=result.score,
            anomaly_type=result.anomaly_type,
            evidence=result.evidence,
            snapshot=result.snapshot,
            recommendation=result.recommendation,
            triggered_at=captured_at,
        )
        title, content_preview, content_html = build_strategy_alert_content(binding, payload, result)
        await dispatch_pushplus_alert(
            db_path,
            instance_id=instance_id,
            account_id=payload.get("account_id"),
            account_name=payload.get("account_name"),
            page_type=payload.get("page_type"),
            page_url=payload.get("page_url"),
            script_version=payload.get("script_version"),
            alert_kind=f"strategy:{binding['strategy_id']}",
            title=title,
            content_preview=content_preview,
            content_html=content_html,
            severity=result.severity,
            anomaly_type=result.anomaly_type,
            triggered_at=captured_at,
            cooldown_ms=compute_cooldown_ms((binding.get("params") or {}).get("cooldown_minutes"), 10),
            strategy_id=binding["strategy_id"],
            strategy_hit_id=hit_id,
            capture_event_id=capture_event_id,
            strategy_name=binding["strategy_name"],
            target_metric=binding["target_metric"],
        )
        triggered_results.append((binding, result))

    if triggered_results:
        binding, result = triggered_results[0]
        summary = f"{binding['strategy_name']} 命中，指标值 {result.metric_value:.2f}"
        raw_text = "`n".join(result.evidence + ([result.recommendation] if result.recommendation else []))
        save_analysis_summary(
            db_path,
            instance_id=instance_id,
            account_id=payload.get("account_id"),
            account_name=payload.get("account_name"),
            page_type=payload.get("page_type"),
            page_url=payload.get("page_url"),
            provider="rules",
            model="strategy-center",
            anomaly_type=result.anomaly_type,
            severity=result.severity,
            score=result.score,
            summary=summary,
            raw_text=raw_text,
        )
def build_admin_html(summary: dict, instances: list[dict], db_path: Path) -> str:
    cards = [
        ("瀹炰緥鎬绘暟", str(summary["total_instances"]), "#0f172a"),
        ("Green", str(summary["green_instances"]), "#166534"),
        ("Yellow", str(summary["yellow_instances"]), "#a16207"),
        ("Red", str(summary["red_instances"]), "#b91c1c"),
        ("鍒嗘瀽璁板綍", str(summary["total_analyses"]), "#1d4ed8"),
    ]
    rows = []
    for item in instances:
        color = {"green": "#dcfce7", "yellow": "#fef9c3", "red": "#fee2e2"}[item["health_status"]]
        text_color = {"green": "#166534", "yellow": "#854d0e", "red": "#991b1b"}[item["health_status"]]
        rows.append(
            f"""
            <tr>
                <td><code>{html.escape(item["instance_id"])}</code></td>
                <td>{html.escape(item.get("account_name") or "-")}</td>
                <td>{html.escape(item.get("page_type") or "-")}</td>
                <td><span style="padding:4px 8px;border-radius:999px;background:{color};color:{text_color};font-weight:700;">{item["health_status"]}</span></td>
                <td>{html.escape(item.get("script_version") or "-")}</td>
                <td>{format_time(item.get("last_heartbeat_at"))}</td>
                <td>{format_time(item.get("last_capture_at"))}</td>
                <td>{html.escape(item.get("last_capture_status") or "-")}</td>
                <td>{item.get("consecutive_error_count") or 0}</td>
                <td>{html.escape((item.get("last_error") or "-")[:80])}</td>
                <td>{html.escape(item.get("last_anomaly_type") or "-")}</td>
                <td>{html.escape(item.get("last_anomaly_severity") or "-")}</td>
                <td title="{html.escape(item.get("last_analysis_summary") or "-")}">{html.escape((item.get("last_analysis_summary") or "-")[:60])}</td>
            </tr>
            """
        )

    card_html = "".join(
        f"""
        <div class="card">
            <div class="card-label">{label}</div>
            <div class="card-value" style="color:{color};">{value}</div>
        </div>
        """
        for label, value, color in cards
    )

    rows_html = "".join(rows) or '<tr><td colspan="13">鏆傛棤瀹炰緥鏁版嵁</td></tr>'
    return f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>AdBudgetSentry 鎺у埗鍙?/title>
        <style>
            :root {{
                --bg: #f8fafc;
                --panel: #ffffff;
                --border: #e2e8f0;
                --ink: #0f172a;
                --muted: #64748b;
                --accent: #0f766e;
            }}
            body {{
                margin: 0;
                font-family: "Segoe UI", "PingFang SC", sans-serif;
                background:
                    radial-gradient(circle at top left, rgba(20, 184, 166, 0.10), transparent 30%),
                    linear-gradient(180deg, #f8fafc 0%, #eef6f7 100%);
                color: var(--ink);
            }}
            .wrap {{
                max-width: 1200px;
                margin: 0 auto;
                padding: 32px 20px 48px;
            }}
            .hero {{
                background: linear-gradient(135deg, #0f766e, #155e75);
                border-radius: 24px;
                color: white;
                padding: 28px;
                box-shadow: 0 24px 60px rgba(15, 118, 110, 0.18);
            }}
            .hero h1 {{
                margin: 0 0 8px;
                font-size: 28px;
            }}
            .hero p {{
                margin: 0;
                color: rgba(255,255,255,0.86);
            }}
            .meta {{
                margin-top: 14px;
                font-size: 13px;
                color: rgba(255,255,255,0.75);
            }}
            .cards {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                gap: 14px;
                margin: 22px 0;
            }}
            .card, .panel {{
                background: var(--panel);
                border: 1px solid var(--border);
                border-radius: 18px;
                padding: 18px;
                box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
            }}
            .card-label {{
                color: var(--muted);
                font-size: 13px;
                margin-bottom: 10px;
            }}
            .card-value {{
                font-size: 30px;
                font-weight: 800;
            }}
            .panel-head {{
                display: flex;
                justify-content: space-between;
                align-items: baseline;
                gap: 12px;
                margin-bottom: 12px;
            }}
            .panel-head h2 {{
                margin: 0;
                font-size: 20px;
            }}
            .panel-head span {{
                color: var(--muted);
                font-size: 13px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                font-size: 14px;
            }}
            th, td {{
                text-align: left;
                padding: 12px 10px;
                border-bottom: 1px solid var(--border);
                vertical-align: top;
            }}
            th {{
                color: var(--muted);
                font-weight: 600;
                font-size: 12px;
                text-transform: uppercase;
                letter-spacing: 0.04em;
            }}
            code {{
                font-size: 12px;
            }}
            .subgrid {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 14px;
                margin-top: 14px;
            }}
            .statline {{
                font-size: 14px;
                line-height: 1.7;
            }}
            .statline strong {{
                color: var(--ink);
            }}
            @media (max-width: 900px) {{
                .subgrid {{
                    grid-template-columns: 1fr;
                }}
                table {{
                    display: block;
                    overflow-x: auto;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="wrap">
            <section class="hero">
                <h1>AdBudgetSentry 鎺у埗鍙?/h1>
                <p>鏌ョ湅娌圭尨鑴氭湰鍦ㄧ嚎鐘舵€併€佹渶杩戦噰闆嗘椂闂村拰鍚庣鎺ュ叆鏄惁鍋ュ悍銆?/p>
                <div class="meta">
                    鏁版嵁搴擄細{html.escape(str(db_path))} |
                    鏈€杩戝績璺筹細{format_time(summary["latest_heartbeat_at"])} |
                    鏈€杩戦噰闆嗭細{format_time(summary["latest_capture_at"])}
                </div>
            </section>

            <section class="cards">
                {card_html}
            </section>

            <section class="subgrid">
                <div class="panel">
                    <div class="panel-head">
                        <h2>鐘舵€佽鏄?/h2>
                        <span>鎸夊疄渚嬭仛鍚?/span>
                    </div>
                    <div class="statline">
                        <strong>Green</strong>锛? 鍒嗛挓鍐呮湁蹇冭烦锛?0 鍒嗛挓鍐呮湁鎴愬姛閲囬泦锛屼笖鏃犺繛缁敊璇€?br />
                        <strong>Yellow</strong>锛氬績璺宠繕鍦紝浣嗛噰闆嗗彉鎱㈡垨鏈€杩戝瓨鍦ㄩ棿姝囨€ч敊璇€?br />
                        <strong>Red</strong>锛氳秴杩?10 鍒嗛挓鏃犲績璺筹紝鎴栬繛缁敊璇揪鍒伴槇鍊笺€?
                    </div>
                </div>
                <div class="panel">
                    <div class="panel-head">
                        <h2>璋冭瘯鎺ュ彛</h2>
                        <span>鏈湴鑱旇皟鐢?/span>
                    </div>
                    <div class="statline">
                        <strong>GET /healthz</strong><br />
                        <strong>GET /readyz</strong><br />
                        <strong>POST /ingest</strong><br />
                        <strong>POST /heartbeat</strong><br />
                        <strong>POST /error</strong><br />
                        <strong>GET /admin/summary</strong>
                    </div>
                </div>
            </section>

            <section class="panel" style="margin-top: 18px;">
                <div class="panel-head">
                    <h2>瀹炰緥鍋ュ悍鍒楄〃</h2>
                    <span>鎸夋渶杩戝績璺冲€掑簭</span>
                </div>
                <table>
                    <thead>
                        <tr>
                            <th>Instance</th>
                            <th>璐﹀彿</th>
                            <th>椤甸潰</th>
                            <th>鐘舵€?/th>
                            <th>鑴氭湰鐗堟湰</th>
                            <th>鏈€杩戝績璺?/th>
                            <th>鏈€杩戦噰闆?/th>
                            <th>閲囬泦鐘舵€?/th>
                            <th>杩炵画閿欒</th>
                            <th>鏈€杩戦敊璇?/th>
                            <th>寮傚父绫诲瀷</th>
                            <th>涓ラ噸搴?/th>
                            <th>鏈€杩戝垎鏋?/th>
                        </tr>
                    </thead>
                    <tbody>{rows_html}</tbody>
                </table>
            </section>
        </div>
    </body>
    </html>
    """


async def run_provider(provider: OpenAICompatibleProvider, prompt: str) -> ProviderResult:
    return await provider.complete(prompt)


def get_admin_frontend_dist_dir() -> Path:
    return ADMIN_FRONTEND_DIST_DIR


def get_admin_frontend_index_path() -> Path:
    return get_admin_frontend_dist_dir() / "index.html"


def render_admin_frontend_index() -> HTMLResponse | None:
    index_path = get_admin_frontend_index_path()
    if not index_path.is_file():
        return None
    return HTMLResponse(index_path.read_text(encoding="utf-8"))


app = FastAPI(title="AdBudgetSentry Analysis Gateway")


@app.on_event("startup")
async def startup() -> None:
    ensure_database(get_db_path())
    app.state.health_monitor_task = asyncio.create_task(health_monitor_loop())


@app.on_event("shutdown")
async def shutdown() -> None:
    task = getattr(app.state, "health_monitor_task", None)
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


@app.get("/health")
def health() -> dict:
    config = load_config()
    return {
        "status": "ok",
        "default_provider": config.get("default_provider", "deepseek"),
        "db_path": str(get_db_path()),
    }


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "server_time": utc_now_ms()}


@app.get("/readyz")
def readyz() -> dict:
    db_path = get_db_path()
    ensure_database(db_path)
    summary = fetch_admin_summary(db_path)
    return {
        "status": "ok",
        "db_path": str(db_path),
        "total_instances": summary["total_instances"],
        "server_time": utc_now_ms(),
    }


@app.post("/ingest", response_model=ApiAck)
async def ingest(request: IngestRequest) -> ApiAck:
    db_path = get_db_path()
    payload = request.model_dump()
    instance_id = save_ingest_event(db_path, payload)
    payload["instance_id"] = instance_id
    await evaluate_ingest_strategies(db_path, payload)
    return ApiAck(server_time=utc_now_ms(), next_suggested_interval_sec=120)


@app.post("/heartbeat", response_model=ApiAck)
def heartbeat(request: HeartbeatRequest) -> ApiAck:
    save_heartbeat(get_db_path(), request.model_dump())
    return ApiAck(server_time=utc_now_ms(), next_suggested_interval_sec=120)


@app.post("/error", response_model=ApiAck)
def report_error(request: ErrorReportRequest) -> ApiAck:
    save_error_report(get_db_path(), request.model_dump())
    return ApiAck(server_time=utc_now_ms(), next_suggested_interval_sec=60)


@app.post("/alert-record", response_model=ApiAck)
def report_alert_record(request: AlertRecordRequest) -> ApiAck:
    save_alert_record(get_db_path(), request.model_dump())
    return ApiAck(server_time=utc_now_ms(), next_suggested_interval_sec=60)


@app.post("/alerts/test", response_model=ApiAck)
async def trigger_test_alert(request: TestAlertRequest) -> ApiAck:
    result = await send_test_alert(get_db_path(), request)
    if result.get("ok"):
        return ApiAck(message="test alert sent", server_time=utc_now_ms(), next_suggested_interval_sec=60)
    if result.get("skipped"):
        return ApiAck(message=f"test alert skipped: {result.get('reason')}", server_time=utc_now_ms(), next_suggested_interval_sec=60)
    return ApiAck(ok=False, message=f"test alert failed: {result.get('error') or 'unknown'}", server_time=utc_now_ms(), next_suggested_interval_sec=60)


@app.get("/admin/summary", response_model=AdminSummary)
def admin_summary() -> AdminSummary:
    return AdminSummary(**fetch_admin_summary(get_db_path()))


@app.get("/admin/api/settings", response_model=AdminSystemSettings)
def admin_settings_api() -> AdminSystemSettings:
    return build_admin_settings()


@app.post("/admin/api/settings", response_model=AdminSystemSettings)
def admin_update_settings_api(request: UpdateAdminSystemSettingsRequest) -> AdminSystemSettings:
    return update_system_settings(request)


@app.post("/admin/api/settings/pushplus/test", response_model=ApiAck)
async def admin_test_pushplus() -> ApiAck:
    result = await dispatch_pushplus_alert(
        get_db_path(),
        instance_id="admin-settings",
        account_id="settings",
        account_name="系统设置页",
        page_type="admin",
        page_url="/admin/settings",
        script_version="admin",
        alert_kind="test",
        title="PushPlus 娴嬭瘯娑堟伅",
        content_preview="系统设置页 PushPlus 测试消息",
        content_html=build_alert_mail_html("PushPlus 测试消息", ["系统设置页 PushPlus 测试消息"]),
        severity="low",
        anomaly_type="manual_test",
        triggered_at=utc_now_ms(),
        cooldown_ms=0,
        force=True,
    )
    if result.get("ok"):
        return ApiAck(message="pushplus test sent", server_time=utc_now_ms())
    if result.get("skipped"):
        return ApiAck(ok=False, message=f"pushplus test skipped: {result.get('reason')}", server_time=utc_now_ms())
    return ApiAck(ok=False, message=f"pushplus test failed: {result.get('error') or 'unknown'}", server_time=utc_now_ms())


@app.post("/admin/api/settings/deepseek/test", response_model=ProviderConnectivityResponse)
async def admin_test_deepseek() -> ProviderConnectivityResponse:
    config = load_config()
    provider = build_provider(config, "deepseek")
    started = time.perf_counter()
    result = await run_provider(provider, build_provider_test_prompt())
    latency_ms = int((time.perf_counter() - started) * 1000)
    return ProviderConnectivityResponse(
        provider=result.provider,
        model=result.model,
        message=result.text,
        latency_ms=latency_ms,
    )


@app.get("/admin/api/metrics", response_model=list[MetricRegistryItem])
def admin_metrics_api() -> list[MetricRegistryItem]:
    return [MetricRegistryItem(**item) for item in list_metric_registry(get_db_path())]


@app.get("/admin/api/strategies", response_model=list[StrategyDefinitionResponse])
def admin_strategies_api() -> list[StrategyDefinitionResponse]:
    return [StrategyDefinitionResponse(**item) for item in fetch_admin_strategies(get_db_path())]


@app.get("/admin/api/instance-strategies", response_model=list[AdminInstanceStrategyRecord])
def admin_instance_strategies_api() -> list[AdminInstanceStrategyRecord]:
    return [AdminInstanceStrategyRecord(**item) for item in fetch_admin_instance_strategies(get_db_path())]


@app.post("/admin/api/strategies", response_model=StrategyDefinitionResponse)
def admin_create_strategy(request: CreateStrategyDefinitionRequest) -> StrategyDefinitionResponse:
    created = create_strategy_definition(
        get_db_path(),
        name=request.name,
        description=request.description,
        template_type=request.template_type,
        target_metric=request.target_metric,
        params=request.params,
        enabled=request.enabled,
        is_default=request.is_default,
        auto_bind_new_instances=request.auto_bind_new_instances,
    )
    return StrategyDefinitionResponse(**created)


@app.put("/admin/api/strategies/{strategy_id}", response_model=StrategyDefinitionResponse)
def admin_update_strategy(strategy_id: int, request: UpdateStrategyDefinitionRequest) -> StrategyDefinitionResponse:
    updated = update_strategy_definition(
        get_db_path(),
        strategy_id,
        name=request.name,
        description=request.description,
        template_type=request.template_type,
        target_metric=request.target_metric,
        params=request.params,
        enabled=request.enabled,
        is_default=request.is_default,
        auto_bind_new_instances=request.auto_bind_new_instances,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return StrategyDefinitionResponse(**updated)


@app.delete("/admin/api/strategies/{strategy_id}", response_model=ApiAck)
def admin_delete_strategy(strategy_id: int) -> ApiAck:
    if not delete_strategy_definition(get_db_path(), strategy_id):
        raise HTTPException(status_code=404, detail="Strategy not found")
    return ApiAck(message="deleted", server_time=utc_now_ms())


@app.get("/admin/instances", response_model=list[AdminInstanceSummary])
def admin_instances() -> list[AdminInstanceSummary]:
    return [AdminInstanceSummary(**item) for item in fetch_admin_instances(get_db_path())]


@app.get("/admin/api/alerts", response_model=list[AdminAlertRecord])
def admin_alerts_api(
    limit: int = 20,
    account_keyword: str = "",
    send_status: str = "",
    alert_kind: str = "",
    strategy_id: int | None = None,
    template_type: str = "",
    target_metric: str = "",
    date_from: str = "",
    date_to: str = "",
) -> list[AdminAlertRecord]:
    safe_limit = max(1, min(limit, 2000))
    normalized_alert_kind = normalize_alert_kind(alert_kind)
    return [
        AdminAlertRecord(**item)
        for item in fetch_admin_alerts(
            get_db_path(),
            limit=safe_limit,
            account_keyword=account_keyword,
            send_status=send_status,
            alert_kind=normalized_alert_kind,
            strategy_id=strategy_id,
            template_type=template_type,
            target_metric=target_metric,
            date_from_ms=parse_date_start_ms(date_from),
            date_to_ms=parse_date_end_ms(date_to),
        )
    ]


@app.get("/admin/alerts/export.csv")
def admin_alerts_export_csv(
    account_keyword: str = "",
    send_status: str = "",
    alert_kind: str = "",
    strategy_id: int | None = None,
    template_type: str = "",
    target_metric: str = "",
    date_from: str = "",
    date_to: str = "",
) -> Response:
    alerts = fetch_admin_alerts(
        get_db_path(),
        limit=5000,
        account_keyword=account_keyword,
        send_status=send_status,
        alert_kind=normalize_alert_kind(alert_kind),
        strategy_id=strategy_id,
        template_type=template_type,
        target_metric=target_metric,
        date_from_ms=parse_date_start_ms(date_from),
        date_to_ms=parse_date_end_ms(date_to),
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "id",
            "instance_id",
            "account_name",
            "account_id",
            "alert_kind",
            "send_status",
            "severity",
            "anomaly_type",
            "strategy_name",
            "template_type",
            "target_metric",
            "channel",
            "delivery_provider",
            "triggered_at",
            "title",
            "content_preview",
            "provider_response",
        ]
    )
    for item in alerts:
        writer.writerow(
            [
                item.get("id"),
                item.get("instance_id"),
                item.get("account_name"),
                item.get("account_id"),
                item.get("alert_kind"),
                item.get("send_status"),
                item.get("severity"),
                item.get("anomaly_type"),
                item.get("strategy_name"),
                item.get("template_type"),
                item.get("target_metric"),
                item.get("channel"),
                item.get("delivery_provider"),
                format_time(item.get("triggered_at")),
                item.get("title"),
                item.get("content_preview"),
                item.get("provider_response"),
            ]
        )
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=adbudget-alerts.csv"},
    )


@app.get("/admin/api/instances/{instance_id}", response_model=AdminInstanceDetail)
def admin_instance_detail_api(instance_id: str) -> AdminInstanceDetail:
    detail = fetch_instance_detail(get_db_path(), instance_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Instance not found")
    return AdminInstanceDetail(**detail)


@app.post("/admin/api/instances/{instance_id}/meta", response_model=InstanceMetadataResponse)
def admin_update_instance_metadata(
    instance_id: str,
    request: UpdateInstanceMetadataRequest,
) -> InstanceMetadataResponse:
    result = update_instance_metadata(
        get_db_path(),
        instance_id,
        alias=request.alias,
        remarks=request.remarks,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Instance not found")
    return InstanceMetadataResponse(**result)


@app.get("/admin/api/instances/{instance_id}/strategy-bindings", response_model=list[InstanceStrategyBindingResponse])
def admin_instance_strategy_bindings(instance_id: str) -> list[InstanceStrategyBindingResponse]:
    detail = fetch_instance_detail(get_db_path(), instance_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Instance not found")
    return [InstanceStrategyBindingResponse(**item) for item in fetch_instance_strategy_bindings(get_db_path(), instance_id)]


@app.post("/admin/api/instances/{instance_id}/strategy-bindings", response_model=InstanceStrategyBindingResponse)
def admin_upsert_instance_strategy_binding(
    instance_id: str,
    request: InstanceStrategyBindingRequest,
) -> InstanceStrategyBindingResponse:
    detail = fetch_instance_detail(get_db_path(), instance_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Instance not found")
    binding = save_instance_strategy_binding(
        get_db_path(),
        instance_id,
        strategy_id=request.strategy_id,
        enabled=request.enabled,
        priority=request.priority,
    )
    return InstanceStrategyBindingResponse(**binding)


@app.delete("/admin/api/instances/{instance_id}/strategy-bindings/{strategy_id}", response_model=ApiAck)
def admin_delete_instance_strategy_binding(instance_id: str, strategy_id: int) -> ApiAck:
    if not delete_instance_strategy_binding(get_db_path(), instance_id, strategy_id):
        raise HTTPException(status_code=404, detail="Binding not found")
    return ApiAck(message="deleted", server_time=utc_now_ms())


@app.delete("/admin/api/instances/{instance_id}", response_model=ApiAck)
def admin_delete_instance(instance_id: str) -> ApiAck:
    if not delete_instance_records(get_db_path(), instance_id):
        raise HTTPException(status_code=404, detail="Instance not found")
    return ApiAck(ok=True, message="deleted", server_time=utc_now_ms())


@app.get("/admin/api/instances/{instance_id}/history", response_model=list[AdminCaptureHistoryPoint])
def admin_instance_history_api(instance_id: str, limit: int = 120) -> list[AdminCaptureHistoryPoint]:
    safe_limit = max(1, min(limit, 500))
    detail = fetch_instance_detail(get_db_path(), instance_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Instance not found")
    history = fetch_capture_history_for_instance(get_db_path(), instance_id, limit=safe_limit)
    return [AdminCaptureHistoryPoint(**item) for item in history]


@app.post("/admin/api/instances/{instance_id}/chat", response_model=InstanceChatResponse)
async def admin_instance_chat_api(instance_id: str, request: InstanceChatRequest) -> InstanceChatResponse:
    db_path = get_db_path()
    detail = fetch_instance_detail(db_path, instance_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Instance not found")

    history = fetch_capture_history_for_instance(db_path, instance_id, limit=60)
    context = build_instance_chat_context(detail, history)
    config = load_config()
    provider_name = config.get("default_provider", "deepseek")
    provider = build_provider(config, provider_name)
    prompt = "\n\n".join(
        [
            context,
            "用户问题：",
            request.message.strip(),
            "请基于当前实例上下文回答，优先给出判断、原因和可执行建议，不要编造未提供的数据。",
        ]
    )
    result = await run_provider(provider, prompt)
    return InstanceChatResponse(
        provider=result.provider,
        model=result.model,
        reply=result.text,
        context_preview=context,
    )


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    db_path = get_db_path()
    summary = fetch_admin_summary(db_path)
    instances = fetch_admin_instances(db_path)
    alerts = fetch_admin_alerts(db_path, limit=20)
    return HTMLResponse(build_admin_dashboard_html(summary, instances, alerts, db_path))


@app.get("/admin", response_class=HTMLResponse)
def admin_home() -> HTMLResponse:
    spa_response = render_admin_frontend_index()
    if spa_response is not None:
        return spa_response

    db_path = get_db_path()
    summary = fetch_admin_summary(db_path)
    instances = fetch_admin_instances(db_path)
    alerts = fetch_admin_alerts(db_path, limit=20)
    return HTMLResponse(build_admin_dashboard_html(summary, instances, alerts, db_path))


@app.get("/admin/alerts", response_class=HTMLResponse)
def admin_alerts_page(
    account_keyword: str = "",
    send_status: str = "",
    alert_kind: str = "",
    date_from: str = "",
    date_to: str = "",
) -> HTMLResponse:
    spa_response = render_admin_frontend_index()
    if spa_response is not None:
        return spa_response

    db_path = get_db_path()
    normalized_alert_kind = normalize_alert_kind(alert_kind)
    alerts = fetch_admin_alerts(
        db_path,
        limit=500,
        account_keyword=account_keyword,
        send_status=send_status,
        alert_kind=normalized_alert_kind,
        date_from_ms=parse_date_start_ms(date_from),
        date_to_ms=parse_date_end_ms(date_to),
    )
    return HTMLResponse(
        build_alerts_page_html(
            alerts,
            db_path,
            account_keyword=account_keyword,
            send_status=send_status,
            alert_kind=alert_kind,
            date_from=date_from,
            date_to=date_to,
        )
    )


@app.get("/admin/settings", response_class=HTMLResponse)
def admin_settings_page() -> HTMLResponse:
    spa_response = render_admin_frontend_index()
    if spa_response is not None:
        return spa_response

    settings = build_admin_settings()
    provider_cards = []
    for label, provider in [("DeepSeek", settings.deepseek), ("本地模型", settings.local)]:
        provider_cards.append(
            "".join(
                [
                    '<div style="border:1px solid rgba(148,163,184,.24);border-radius:16px;padding:16px;background:#fff;">',
                    f'<div style="font-weight:700;font-size:16px;">{html.escape(label)}</div>',
                    f'<div style="margin-top:8px;color:#475569;">Base URL：{html.escape(provider.base_url)}</div>',
                    f'<div style="margin-top:6px;color:#475569;">Model：{html.escape(provider.model)}</div>',
                    "</div>",
                ]
            )
        )

    body = f"""
    <!doctype html>
    <html lang="zh-CN">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>绯荤粺璁剧疆 - AdBudgetSentry</title>
        <style>
          body {{ font-family: "Segoe UI","PingFang SC","Microsoft YaHei",sans-serif; margin: 0; background: #f8fafc; color: #0f172a; }}
          .page {{ max-width: 960px; margin: 0 auto; padding: 32px 20px 48px; }}
          .hero {{ background: linear-gradient(135deg,#0f766e,#1e293b); color: #fff; padding: 28px; border-radius: 24px; }}
          .card {{ margin-top: 20px; background: #fff; border: 1px solid rgba(148,163,184,.24); border-radius: 20px; padding: 24px; }}
          .grid {{ display: grid; gap: 16px; grid-template-columns: repeat(auto-fit,minmax(220px,1fr)); }}
          .row {{ margin-top: 10px; color: #475569; }}
          .token {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
          a {{ color: #0f766e; text-decoration: none; }}
        </style>
      </head>
      <body>
        <main class="page">
          <section class="hero">
            <div style="font-size:12px;letter-spacing:.16em;text-transform:uppercase;opacity:.82;">Settings</div>
            <h1 style="margin:10px 0 8px;">系统设置</h1>
            <div style="line-height:1.7;max-width:700px;">当前环境未找到 React 打包产物，因此暂时回退到后端渲染页。PushPlus 发送和模型调用都由 FastAPI 后端直接发起，保存配置后后续请求会自动读取新配置。</div>
            <div style="margin-top:14px;"><a href="/admin" style="color:#fff;">返回总览</a></div>
          </section>
          <section class="card">
            <h2 style="margin-top:0;">PushPlus</h2>
            <div class="row">启用状态：{"已启用" if settings.pushplus.enabled else "已关闭"}</div>
            <div class="row">发送通道：{html.escape(settings.pushplus.channel)}</div>
            <div class="row">通道参数：{html.escape(settings.pushplus.channel_option or "-")}</div>
            <div class="row">Token：<span class="token">{html.escape(settings.pushplus.token_preview or "未配置")}</span></div>
          </section>
          <section class="card">
            <h2 style="margin-top:0;">模型与提供方</h2>
            <div class="row">默认提供方：{html.escape(settings.default_provider)}</div>
            <div class="grid" style="margin-top:16px;">
              {''.join(provider_cards)}
            </div>
          </section>
        </main>
      </body>
    </html>
    """
    return HTMLResponse(body)


@app.get("/admin/strategies", response_class=HTMLResponse)
def admin_strategies_page() -> HTMLResponse:
    spa_response = render_admin_frontend_index()
    if spa_response is not None:
        return spa_response
    return HTMLResponse("<!doctype html><html><body><a href='/admin'>Back to admin</a></body></html>")


@app.get("/admin/instances/{instance_id}", response_class=HTMLResponse)
def admin_instance_detail_page(instance_id: str) -> HTMLResponse:
    spa_response = render_admin_frontend_index()
    if spa_response is not None:
        return spa_response

    db_path = get_db_path()
    detail = fetch_instance_detail(db_path, instance_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Instance not found")
    return HTMLResponse(build_instance_detail_html(detail, db_path))


@app.get("/{path:path}")
def admin_frontend_asset(path: str) -> Response:
    dist_dir = get_admin_frontend_dist_dir()
    if not dist_dir.is_dir():
        raise HTTPException(status_code=404, detail="Static assets not available")

    resolved_dist = dist_dir.resolve()
    candidate = (dist_dir / path).resolve()
    try:
        candidate.relative_to(resolved_dist)
    except ValueError:
        raise HTTPException(status_code=404, detail="Static asset not found")

    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="Static asset not found")

    media_type, _ = mimetypes.guess_type(candidate.name)
    return FileResponse(candidate, media_type=media_type or "application/octet-stream")


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze(request: AnalysisRequest) -> AnalysisResponse:
    config = load_config()
    provider_name = request.provider_override or config.get("default_provider", "deepseek")

    detection_summary = detect_spend_anomaly(
        history=request.history,
        increase_amount=request.event.increase_amount,
        compare_interval_min=request.event.compare_interval_min,
        threshold=request.event.threshold,
    )

    prompt = build_prompt(request, detection_summary)

    try:
        provider = build_provider(config, provider_name)
        result = await run_provider(provider, prompt)
        raw_text = result.text
    except Exception as exc:  # noqa: BLE001
        provider = build_provider(config, provider_name)
        raw_text = f"{fallback_text(detection_summary)}\n\n模型调用失败：{exc}"

    summary = extract_analysis_summary(raw_text) or fallback_text(detection_summary)

    return AnalysisResponse(
        provider=provider.provider_name,
        model=provider.model,
        detection=detection_summary,
        summary=summary,
        raw_text=raw_text,
    )


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("ADBUDGET_HOST", "127.0.0.1")
    port = int(os.getenv("ADBUDGET_PORT", "8787"))
    uvicorn.run("app:app", host=host, port=port, reload=False)
