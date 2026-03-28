from __future__ import annotations

import asyncio
import csv
import html
import io
import json
import os
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response

from admin_ui import build_admin_dashboard_html, build_alerts_page_html, build_instance_detail_html
from anomaly import detect_spend_anomaly
from database import (
    ensure_database,
    fetch_admin_alerts,
    fetch_admin_instances,
    fetch_capture_history_for_instance,
    fetch_history_for_instance,
    fetch_instance_detail,
    fetch_latest_alert_for_instance_kind,
    fetch_latest_analysis_for_instance,
    fetch_admin_summary,
    save_alert_record,
    save_error_report,
    save_heartbeat,
    save_ingest_event,
    save_analysis_summary,
    utc_now_ms,
)
from models import (
    AdminAlertRecord,
    AdminCaptureHistoryPoint,
    AdminInstanceDetail,
    AdminInstanceSummary,
    AdminSummary,
    AnalysisRequest,
    AnalysisEvent,
    AnalysisResponse,
    AlertRecordRequest,
    ApiAck,
    ErrorReportRequest,
    HistoryPoint,
    HeartbeatRequest,
    IngestRequest,
    TestAlertRequest,
)
from providers import OpenAICompatibleProvider, ProviderResult


APP_DIR = Path(__file__).resolve().parent
ROOT_DIR = APP_DIR.parent.parent
DATA_DIR = ROOT_DIR / "data"
DEFAULT_DB_PATH = DATA_DIR / "app.db"
CONFIG_PATH = APP_DIR / "config.json"
EXAMPLE_CONFIG_PATH = APP_DIR / "config.example.json"

DEFAULT_CONTEXT = """业务背景：快手磁力金牛在高客单价、目标成本偏高时，可能引入低质量流量，造成虚假转化、疯狂消耗、成本失控。请区分正常爆量与低质流量嫌疑，输出风险等级、证据和操作建议。"""
MODEL_TRIGGER_TYPES = {"threshold_breach", "surge", "stalled"}
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

当前事件：
- 当前总消耗：{event.current_spend:.2f}
- 窗口增量：{event.increase_amount:.2f}
- 对比窗口：{event.compare_interval_min} 分钟
- 预警阈值：{event.threshold:.2f}
- 规则检测类型：{detection_summary.anomaly_type}
- 规则严重度：{detection_summary.severity}
- 规则分数：{detection_summary.score}
- 附加指标：{metrics}

规则证据：
{evidence_lines}

请输出：
请用纯文本输出，不要使用 Markdown、不要加粗、不要编号列表。
请按以下四行输出：
结论：这是正常爆量、低质流量嫌疑、还是暂时无法判断
依据：写 2 到 3 条核心依据，合并成一行
建议：继续观察 / 降预算 / 暂停计划 / 人工复核退款与场观
提示：一句话风险提示
""".strip()


def fallback_text(detection_summary) -> str:
    evidence = "；".join(detection_summary.evidence)
    return (
        f"规则判断为 {detection_summary.anomaly_type}，严重度 {detection_summary.severity}。"
        f"证据：{evidence}。建议：{detection_summary.recommendation}"
    )


def format_time(timestamp_ms: int | None) -> str:
    if not timestamp_ms:
        return "-"
    return datetime.fromtimestamp(timestamp_ms / 1000).strftime("%Y-%m-%d %H:%M:%S")


def compact_text(value: str | None, limit: int = 100) -> str:
    if not value:
        return "-"
    raw = " ".join(str(value).split())
    return raw if len(raw) <= limit else f"{raw[: limit - 1]}…"


def is_missing_account_id(value: str | None) -> bool:
    return value in {None, "", "未识别账号ID"}


def format_account_identity(account_name: str | None, account_id: str | None) -> str:
    name = (account_name or "").strip()
    account_id = None if is_missing_account_id(account_id) else (account_id or "").strip()
    if name and account_id:
        return f"{name} · {account_id}"
    if name:
        return name
    if account_id:
        return account_id
    return "未绑定账号"


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
    lines = [f"账号名称：{account_name or '未识别账号'}"]
    if not is_missing_account_id(account_id):
        lines.append(f"账号ID：{account_id}")
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
                "provider_response": "未配置 PushPlus Token",
            },
        )
        return {"ok": False, "skipped": True, "reason": "missing_pushplus_token"}

    try:
        async with httpx.AsyncClient(timeout=20) as client:
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


def build_threshold_alert_content(payload: dict, summary_text: str) -> tuple[str, str]:
    metrics = payload.get("metrics") or {}
    baseline_time = metrics.get("baseline_time") or payload.get("raw_context", {}).get("baseline_time")
    baseline_text = format_time(int(baseline_time)) if baseline_time else "-"
    preview_lines = [
        "消耗异常提醒",
        *build_account_lines(payload.get("account_name"), payload.get("account_id")),
        f"脚本实例：{payload.get('instance_id')}",
        f"页面类型：{payload.get('page_type') or '-'}",
        f"当前总消耗：{float(metrics.get('current_spend') or 0):.2f} 元",
        f"基线消耗：{float(metrics.get('baseline_spend') or 0):.2f} 元",
        f"基线时间：{baseline_text}",
        f"对比窗口：{int(metrics.get('compare_interval_min') or 0)} 分钟",
        f"窗口增量：{float(metrics.get('increase_amount') or 0):.2f} 元",
        f"阈值：{float(metrics.get('notify_threshold') or metrics.get('threshold') or 0):.2f} 元",
        f"分析结果：{summary_text or '暂无分析结果'}",
    ]
    title = f"【磁力金牛预警】{format_account_identity(payload.get('account_name'), payload.get('account_id'))}"
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
    title, content_preview = build_threshold_alert_content(payload, summary_text)
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
        f"当前总消耗：{request.current_spend:.2f} 元",
        f"{request.compare_interval_min} 分钟增量：{request.increase_amount:.2f} 元",
        f"分析结果：{request.analysis_text or '未提供'}",
    ]
    if request.baseline_spend is not None:
        preview_lines.insert(-1, f"基线消耗：{request.baseline_spend:.2f} 元")
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
                "问题说明：超过 10 分钟未收到心跳，请检查浏览器页签、网络和脚本运行状态。",
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


def build_analysis_request_from_ingest(payload: dict, history: list[dict]) -> AnalysisRequest | None:
    metrics = payload.get("metrics") or {}
    current_spend = metrics.get("current_spend")
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


async def analyze_ingest_payload(db_path: Path, payload: dict) -> None:
    instance_id = payload["instance_id"]
    history = fetch_history_for_instance(db_path, instance_id, limit=120)
    request = build_analysis_request_from_ingest(payload, history)
    if request is None:
        return

    raw_context = payload.get("raw_context") or {}
    ai_enabled = raw_context.get("ai_enabled", True)
    detection_summary = detect_spend_anomaly(
        history=request.history,
        increase_amount=request.event.increase_amount,
        compare_interval_min=request.event.compare_interval_min,
        threshold=request.event.threshold,
    )

    latest_analysis = fetch_latest_analysis_for_instance(db_path, instance_id)
    is_cooldown_active = bool(
        latest_analysis
        and latest_analysis.get("created_at")
        and utc_now_ms() - int(latest_analysis["created_at"]) < MODEL_ANALYSIS_COOLDOWN_MS
    )
    should_call_model = (
        ai_enabled
        and detection_summary.anomaly_type in MODEL_TRIGGER_TYPES
        and not is_cooldown_active
    )

    if should_call_model:
        config = load_config()
        provider_name = request.provider_override or config.get("default_provider", "deepseek")
        try:
            provider = build_provider(config, provider_name)
            raw_text = (await run_provider(provider, build_prompt(request, detection_summary))).text
            summary = raw_text.splitlines()[0].strip() if raw_text.strip() else fallback_text(detection_summary)
            provider_name_out = provider.provider_name
            model_out = provider.model
        except Exception as exc:  # noqa: BLE001
            raw_text = f"{fallback_text(detection_summary)}\n\n模型调用失败：{exc}"
            summary = fallback_text(detection_summary)
            provider_name_out = provider_name
            model_out = "fallback"
    else:
        raw_text = fallback_text(detection_summary)
        if ai_enabled and detection_summary.anomaly_type in MODEL_TRIGGER_TYPES and is_cooldown_active:
            raw_text = f"{raw_text}\n\n模型分析处于冷却期，本次跳过。"
        summary = raw_text
        provider_name_out = "rules"
        model_out = "fallback"

    save_analysis_summary(
        db_path,
        instance_id=instance_id,
        account_id=payload.get("account_id"),
        account_name=payload.get("account_name"),
        page_type=payload.get("page_type"),
        page_url=payload.get("page_url"),
        provider=provider_name_out,
        model=model_out,
        anomaly_type=detection_summary.anomaly_type,
        severity=detection_summary.severity,
        score=detection_summary.score,
        summary=summary,
        raw_text=raw_text,
    )
    await maybe_send_threshold_alert(db_path, payload, detection_summary, raw_text)


def build_admin_html(summary: dict, instances: list[dict], db_path: Path) -> str:
    cards = [
        ("实例总数", str(summary["total_instances"]), "#0f172a"),
        ("Green", str(summary["green_instances"]), "#166534"),
        ("Yellow", str(summary["yellow_instances"]), "#a16207"),
        ("Red", str(summary["red_instances"]), "#b91c1c"),
        ("分析记录", str(summary["total_analyses"]), "#1d4ed8"),
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

    rows_html = "".join(rows) or '<tr><td colspan="13">暂无实例数据</td></tr>'
    return f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>AdBudgetSentry 控制台</title>
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
                <h1>AdBudgetSentry 控制台</h1>
                <p>查看油猴脚本在线状态、最近采集时间和后端接入是否健康。</p>
                <div class="meta">
                    数据库：{html.escape(str(db_path))} |
                    最近心跳：{format_time(summary["latest_heartbeat_at"])} |
                    最近采集：{format_time(summary["latest_capture_at"])}
                </div>
            </section>

            <section class="cards">
                {card_html}
            </section>

            <section class="subgrid">
                <div class="panel">
                    <div class="panel-head">
                        <h2>状态说明</h2>
                        <span>按实例聚合</span>
                    </div>
                    <div class="statline">
                        <strong>Green</strong>：5 分钟内有心跳，10 分钟内有成功采集，且无连续错误。<br />
                        <strong>Yellow</strong>：心跳还在，但采集变慢或最近存在间歇性错误。<br />
                        <strong>Red</strong>：超过 10 分钟无心跳，或连续错误达到阈值。
                    </div>
                </div>
                <div class="panel">
                    <div class="panel-head">
                        <h2>调试接口</h2>
                        <span>本地联调用</span>
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
                    <h2>实例健康列表</h2>
                    <span>按最近心跳倒序</span>
                </div>
                <table>
                    <thead>
                        <tr>
                            <th>Instance</th>
                            <th>账号</th>
                            <th>页面</th>
                            <th>状态</th>
                            <th>脚本版本</th>
                            <th>最近心跳</th>
                            <th>最近采集</th>
                            <th>采集状态</th>
                            <th>连续错误</th>
                            <th>最近错误</th>
                            <th>异常类型</th>
                            <th>严重度</th>
                            <th>最近分析</th>
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
    await analyze_ingest_payload(db_path, payload)
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


@app.get("/admin/instances", response_model=list[AdminInstanceSummary])
def admin_instances() -> list[AdminInstanceSummary]:
    return [AdminInstanceSummary(**item) for item in fetch_admin_instances(get_db_path())]


@app.get("/admin/api/alerts", response_model=list[AdminAlertRecord])
def admin_alerts_api(
    limit: int = 20,
    account_keyword: str = "",
    send_status: str = "",
    alert_kind: str = "",
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
            date_from_ms=parse_date_start_ms(date_from),
            date_to_ms=parse_date_end_ms(date_to),
        )
    ]


@app.get("/admin/alerts/export.csv")
def admin_alerts_export_csv(
    account_keyword: str = "",
    send_status: str = "",
    alert_kind: str = "",
    date_from: str = "",
    date_to: str = "",
) -> Response:
    alerts = fetch_admin_alerts(
        get_db_path(),
        limit=5000,
        account_keyword=account_keyword,
        send_status=send_status,
        alert_kind=normalize_alert_kind(alert_kind),
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


@app.get("/admin/api/instances/{instance_id}/history", response_model=list[AdminCaptureHistoryPoint])
def admin_instance_history_api(instance_id: str, limit: int = 120) -> list[AdminCaptureHistoryPoint]:
    safe_limit = max(1, min(limit, 500))
    detail = fetch_instance_detail(get_db_path(), instance_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Instance not found")
    history = fetch_capture_history_for_instance(get_db_path(), instance_id, limit=safe_limit)
    return [AdminCaptureHistoryPoint(**item) for item in history]


@app.get("/", response_class=HTMLResponse)
@app.get("/admin", response_class=HTMLResponse)
def admin_home() -> HTMLResponse:
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


@app.get("/admin/instances/{instance_id}", response_class=HTMLResponse)
def admin_instance_detail_page(instance_id: str) -> HTMLResponse:
    db_path = get_db_path()
    detail = fetch_instance_detail(db_path, instance_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Instance not found")
    return HTMLResponse(build_instance_detail_html(detail, db_path))


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

    summary = raw_text.splitlines()[0].strip() if raw_text.strip() else fallback_text(detection_summary)

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
