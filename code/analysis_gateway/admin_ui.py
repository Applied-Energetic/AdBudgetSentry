from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path
from urllib.parse import quote


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


def build_trend_chart(history: list[dict]) -> str:
    if len(history) < 2:
        return '<div class="empty-panel">最近采样点不足，暂时无法绘制趋势图。</div>'

    width = 920
    height = 260
    padding_left = 48
    padding_right = 16
    padding_top = 16
    padding_bottom = 34
    inner_width = width - padding_left - padding_right
    inner_height = height - padding_top - padding_bottom

    spend_values = [float(item.get("current_spend") or 0) for item in history]
    delta_values = [float(item.get("increase_amount") or 0) for item in history]
    max_value = max(spend_values + delta_values + [1.0])

    def to_x(index: int) -> float:
        if len(history) == 1:
            return padding_left + inner_width / 2
        return padding_left + (inner_width * index / (len(history) - 1))

    def to_y(value: float) -> float:
        return padding_top + inner_height - (value / max_value) * inner_height

    spend_points = " ".join(f"{to_x(i):.1f},{to_y(v):.1f}" for i, v in enumerate(spend_values))
    delta_points = " ".join(f"{to_x(i):.1f},{to_y(v):.1f}" for i, v in enumerate(delta_values))

    guide_lines = []
    for ratio in (0.25, 0.5, 0.75, 1):
        y = padding_top + inner_height - inner_height * ratio
        label = max_value * ratio
        guide_lines.append(
            f'<line x1="{padding_left}" y1="{y:.1f}" x2="{width - padding_right}" y2="{y:.1f}" '
            'stroke="rgba(148, 163, 184, 0.25)" stroke-dasharray="4 6" />'
            f'<text x="8" y="{y + 4:.1f}" fill="#64748b" font-size="11">{label:.0f}</text>'
        )

    x_labels = []
    step = max(1, len(history) // 6)
    for actual_index in range(0, len(history), step):
        item = history[actual_index]
        x = to_x(actual_index)
        label = datetime.fromtimestamp(item["captured_at"] / 1000).strftime("%H:%M")
        x_labels.append(
            f'<text x="{x:.1f}" y="{height - 8}" fill="#64748b" font-size="11" text-anchor="middle">{html.escape(label)}</text>'
        )

    return f"""
    <div class="chart-wrap">
        <svg viewBox="0 0 {width} {height}" class="trend-chart" role="img" aria-label="实例采样趋势图">
            <rect x="0" y="0" width="{width}" height="{height}" rx="20" fill="rgba(248,250,252,0.96)"></rect>
            {''.join(guide_lines)}
            <polyline points="{spend_points}" fill="none" stroke="#0f766e" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></polyline>
            <polyline points="{delta_points}" fill="none" stroke="#1d4ed8" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></polyline>
            {''.join(x_labels)}
        </svg>
        <div class="chart-legend">
            <span><i class="dot dot-teal"></i>当前总消耗</span>
            <span><i class="dot dot-blue"></i>窗口增量</span>
        </div>
    </div>
    """


def build_admin_dashboard_html(summary: dict, instances: list[dict], alerts: list[dict], db_path: Path) -> str:
    cards = [
        ("在线实例", str(summary["total_instances"]), "teal"),
        ("Green", str(summary["green_instances"]), "green"),
        ("Yellow", str(summary["yellow_instances"]), "yellow"),
        ("Red", str(summary["red_instances"]), "red"),
        ("分析记录", str(summary["total_analyses"]), "blue"),
        ("告警记录", str(summary["total_alerts"]), "slate"),
    ]
    tone_map = {
        "teal": "#0f766e",
        "green": "#166534",
        "yellow": "#a16207",
        "red": "#b91c1c",
        "blue": "#1d4ed8",
        "slate": "#334155",
    }
    card_html = "".join(
        f"""
        <article class="metric-card">
            <div class="metric-label">{html.escape(label)}</div>
            <div class="metric-value" style="color:{tone_map[tone]};">{html.escape(value)}</div>
        </article>
        """
        for label, value, tone in cards
    )

    status_chip_tone = {"green": "green", "yellow": "yellow", "red": "red"}
    instance_rows: list[str] = []
    for item in instances:
        account_text = format_account_identity(item.get("account_name"), item.get("account_id"))
        preview = item.get("last_analysis_summary") or "-"
        last_error = compact_text(item.get("last_error"), limit=90)
        instance_rows.append(
            f"""
            <tr class="click-row" data-href="/admin/instances/{quote(item.get("instance_id") or "", safe="")}">
                <td>
                        <div class="cell-title"><a class="detail-link" href="/admin/instances/{quote(item.get("instance_id") or "", safe="")}">{html.escape(account_text)}</a></div>
                        <div class="cell-sub">{html.escape(item.get("instance_id") or "-")}</div>
                </td>
                <td>
                    <div class="cell-title">{html.escape(item.get("page_type") or "-")}</div>
                    <div class="cell-sub">{html.escape(compact_text(item.get("page_url"), 52))}</div>
                </td>
                <td>{build_chip(item["health_status"].upper(), status_chip_tone[item["health_status"]])}</td>
                <td>
                    <div class="cell-title">{html.escape(item.get("script_version") or "-")}</div>
                    <div class="cell-sub">连续错误 {item.get("consecutive_error_count") or 0}</div>
                </td>
                <td>
                    <div class="cell-title">{format_time(item.get("last_heartbeat_at"))}</div>
                    <div class="cell-sub">采集 {format_time(item.get("last_capture_at"))}</div>
                </td>
                <td>
                    <div class="cell-title">{html.escape(item.get("last_capture_status") or "-")}</div>
                    <div class="cell-sub">{html.escape(last_error)}</div>
                </td>
                <td>
                    <div class="cell-title">{html.escape(item.get("last_anomaly_type") or "-")}</div>
                    <div class="cell-sub">{html.escape(item.get("last_anomaly_severity") or "-")}</div>
                </td>
                <td title="{html.escape(preview)}">
                    <div class="analysis-preview">{html.escape(compact_text(preview, 120))}</div>
                </td>
            </tr>
            """
        )
    instance_rows_html = "".join(instance_rows) or '<tr><td colspan="8" class="empty-state">暂无实例数据</td></tr>'

    alert_rows: list[str] = []
    for alert in alerts:
        alert_status_tone = {"sent": "green", "failed": "red", "skipped": "yellow"}.get(
            alert.get("send_status") or "",
            "slate",
        )
        meta_bits = [
            f"时间 {format_time(alert.get('triggered_at'))}",
            f"渠道 {(alert.get('channel') or '-')}",
            f"类型 {(alert.get('alert_kind') or '-')}",
        ]
        if alert.get("anomaly_type"):
            meta_bits.append(f"异常 {alert['anomaly_type']}")
        if alert.get("severity"):
            meta_bits.append(f"严重度 {alert['severity']}")
        alert_rows.append(
            f"""
            <article class="alert-card alert-{html.escape(alert.get("send_status") or "unknown")}">
                <div class="alert-top">
                    <div>
                        <div class="cell-title">{html.escape(alert.get("title") or "-")}</div>
                        <div class="cell-sub">{html.escape(format_account_identity(alert.get("account_name"), alert.get("account_id")))}</div>
                    </div>
                    {build_chip((alert.get("send_status") or "unknown").upper(), alert_status_tone)}
                </div>
                <div class="alert-meta">{html.escape(" · ".join(meta_bits))}</div>
                <div class="alert-preview">{html.escape(compact_text(alert.get("content_preview"), 220))}</div>
                <div class="alert-foot">
                    <span>实例 {html.escape(alert.get("instance_id") or "-")}</span>
                    <span>{html.escape(alert.get("delivery_provider") or "pushplus")}</span>
                </div>
            </article>
            """
        )
    alerts_html = "".join(alert_rows) or '<div class="empty-panel">最近还没有告警记录。</div>'
    latest_alert_text = format_time(summary.get("latest_alert_at"))

    return f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>AdBudgetSentry 控制台</title>
        <style>
            :root {{
                --bg-top: #f3fbfa;
                --bg-bottom: #eef2ff;
                --panel: rgba(255, 255, 255, 0.86);
                --panel-strong: #ffffff;
                --border: rgba(148, 163, 184, 0.20);
                --ink: #0f172a;
                --muted: #5b6b82;
                --teal-deep: #115e59;
                --shadow: 0 18px 44px rgba(15, 23, 42, 0.10);
                --radius-xl: 28px;
                --radius-lg: 22px;
            }}
            * {{ box-sizing: border-box; }}
            body {{
                margin: 0;
                color: var(--ink);
                font-family: "Avenir Next", "PingFang SC", "Microsoft YaHei", sans-serif;
                background:
                    radial-gradient(circle at 0% 0%, rgba(45, 212, 191, 0.18), transparent 28%),
                    radial-gradient(circle at 100% 20%, rgba(96, 165, 250, 0.16), transparent 22%),
                    linear-gradient(180deg, var(--bg-top) 0%, var(--bg-bottom) 100%);
            }}
            .shell {{ max-width: 1380px; margin: 0 auto; padding: 28px 20px 44px; }}
            .hero {{
                position: relative; overflow: hidden; border-radius: var(--radius-xl); padding: 30px; color: #fff;
                background: linear-gradient(135deg, rgba(15, 118, 110, 0.96), rgba(15, 23, 42, 0.92));
                box-shadow: 0 26px 64px rgba(15, 118, 110, 0.26);
            }}
            .hero::after {{
                content: ""; position: absolute; inset: auto -10% -30% auto; width: 380px; height: 380px;
                border-radius: 999px; background: radial-gradient(circle, rgba(255,255,255,0.20), transparent 62%);
            }}
            .hero-grid {{ position: relative; z-index: 1; display: grid; grid-template-columns: minmax(0, 1.3fr) minmax(320px, 0.7fr); gap: 18px; align-items: end; }}
            .eyebrow {{ font-size: 12px; letter-spacing: 0.16em; text-transform: uppercase; color: rgba(255,255,255,0.74); }}
            .hero h1 {{ margin: 10px 0 10px; font-size: clamp(30px, 4vw, 44px); line-height: 1.02; }}
            .hero p {{ margin: 0; max-width: 760px; font-size: 15px; line-height: 1.7; color: rgba(255,255,255,0.84); }}
            .hero-meta {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 16px; }}
            .hero-badge {{
                padding: 10px 14px; border-radius: 999px; font-size: 13px; color: rgba(255,255,255,0.92);
                background: rgba(255,255,255,0.10); border: 1px solid rgba(255,255,255,0.14); backdrop-filter: blur(10px);
            }}
            .hero-side {{ display: grid; gap: 12px; }}
            .hero-side-card {{
                border-radius: 20px; padding: 18px 18px 16px; background: rgba(255,255,255,0.10);
                border: 1px solid rgba(255,255,255,0.14); backdrop-filter: blur(10px);
            }}
            .hero-side-card strong {{ display: block; margin-bottom: 8px; font-size: 12px; letter-spacing: 0.10em; text-transform: uppercase; color: rgba(255,255,255,0.74); }}
            .hero-side-card .big {{ font-size: 24px; font-weight: 800; line-height: 1.15; }}
            .hero-side-card .sub {{ margin-top: 6px; font-size: 13px; color: rgba(255,255,255,0.76); }}
            .metric-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 14px; margin: 20px 0; }}
            .metric-card, .panel {{
                background: var(--panel); backdrop-filter: blur(20px); border: 1px solid var(--border);
                border-radius: var(--radius-lg); box-shadow: var(--shadow);
            }}
            a {{ color: inherit; text-decoration: none; }}
            .top-link {{
                display: inline-flex; align-items: center; justify-content: center; gap: 8px; padding: 10px 14px;
                border-radius: 999px; background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.16);
                color: rgba(255,255,255,0.92); font-size: 13px; font-weight: 700;
            }}
            .top-link:hover {{ background: rgba(255,255,255,0.18); }}
            .detail-link {{
                color: #0f172a;
                border-bottom: 1px solid transparent;
            }}
            .detail-link:hover {{
                color: #0f766e;
                border-bottom-color: rgba(15, 118, 110, 0.35);
            }}
            .click-row {{ cursor: pointer; }}
            .click-row:hover {{ background: rgba(240, 253, 250, 0.92); }}
            .metric-card {{ padding: 18px 18px 20px; }}
            .metric-label {{ font-size: 13px; color: var(--muted); margin-bottom: 10px; }}
            .metric-value {{ font-size: 32px; font-weight: 800; line-height: 1; }}
            .panel {{ padding: 22px; }}
            .panel-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: flex-end; margin-bottom: 16px; }}
            .panel-title {{ margin: 0; font-size: 20px; line-height: 1.2; }}
            .panel-subtitle {{ margin-top: 6px; color: var(--muted); font-size: 13px; }}
            .chip {{
                display: inline-flex; align-items: center; justify-content: center; padding: 6px 10px; border-radius: 999px;
                font-size: 12px; font-weight: 700; letter-spacing: 0.04em; white-space: nowrap;
            }}
            .top-grid {{ display: grid; grid-template-columns: minmax(0, 2fr) minmax(320px, 1fr); gap: 16px; align-items: start; }}
            .guide-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }}
            .guide-box {{ border-radius: 18px; padding: 16px; background: #ffffff; border: 1px solid rgba(148, 163, 184, 0.16); }}
            .guide-box strong {{ display: block; font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); margin-bottom: 10px; }}
            .guide-line {{ font-size: 14px; line-height: 1.75; color: var(--ink); }}
            .guide-line b {{ color: var(--teal-deep); }}
            .stack-list {{ display: grid; gap: 10px; }}
            .api-row {{
                display: flex; justify-content: space-between; gap: 12px; padding: 10px 12px; border-radius: 14px;
                background: rgba(248, 250, 252, 0.88); border: 1px solid rgba(226, 232, 240, 0.86); font-size: 13px;
            }}
            .api-row code {{ font-size: 12px; color: var(--ink); }}
            .alert-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 14px; }}
            .alert-card {{
                padding: 18px; border-radius: 18px; background: #ffffff; border: 1px solid rgba(226, 232, 240, 0.88);
                box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
            }}
            .alert-sent {{ border-left: 6px solid rgba(22, 101, 52, 0.72); }}
            .alert-failed {{ border-left: 6px solid rgba(185, 28, 28, 0.72); }}
            .alert-skipped {{ border-left: 6px solid rgba(161, 98, 7, 0.72); }}
            .alert-top {{ display: flex; gap: 10px; align-items: flex-start; justify-content: space-between; }}
            .cell-title {{ font-size: 14px; font-weight: 700; line-height: 1.45; color: var(--ink); }}
            .cell-sub {{ margin-top: 4px; font-size: 12px; line-height: 1.5; color: var(--muted); word-break: break-all; }}
            .alert-meta {{ margin: 12px 0 10px; font-size: 12px; line-height: 1.6; color: var(--muted); }}
            .alert-preview {{ font-size: 13px; line-height: 1.7; color: #1e293b; white-space: pre-wrap; min-height: 68px; }}
            .alert-foot {{ margin-top: 14px; display: flex; justify-content: space-between; gap: 10px; font-size: 12px; color: var(--muted); }}
            .table-shell {{ overflow: hidden; border-radius: 20px; border: 1px solid rgba(226, 232, 240, 0.88); background: #ffffff; }}
            table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
            th, td {{ padding: 14px 14px; border-bottom: 1px solid rgba(226, 232, 240, 0.84); text-align: left; vertical-align: top; }}
            th {{ font-size: 12px; letter-spacing: 0.06em; text-transform: uppercase; color: var(--muted); background: rgba(248, 250, 252, 0.94); }}
            tbody tr:hover {{ background: rgba(248, 250, 252, 0.86); }}
            .analysis-preview {{ line-height: 1.7; color: #1e293b; max-width: 360px; }}
            .empty-panel, .empty-state {{ padding: 28px 16px; text-align: center; color: var(--muted); }}
            .footer-note {{ margin-top: 16px; font-size: 12px; color: var(--muted); text-align: right; }}
            @media (max-width: 1120px) {{ .hero-grid, .top-grid {{ grid-template-columns: 1fr; }} }}
            @media (max-width: 860px) {{
                .shell {{ padding: 18px 14px 28px; }}
                .hero {{ padding: 22px; }}
                .guide-grid {{ grid-template-columns: 1fr; }}
                .table-shell {{ overflow-x: auto; }}
                table {{ min-width: 1040px; }}
            }}
        </style>
    </head>
    <body>
        <main class="shell">
            <section class="hero">
                <div class="hero-grid">
                    <div>
                        <div class="eyebrow">AdBudgetSentry Monitor</div>
                        <h1>油猴监控、分析摘要和告警回执都在这里</h1>
                        <p>这套后台现在同时聚合脚本实例健康、最近采集、规则与模型分析，以及 PushPlus 告警发送结果，方便你从一个页面确认整条监控链路是否还活着。</p>
                        <div class="hero-meta">
                            <div class="hero-badge">数据库 {html.escape(str(db_path))}</div>
                            <div class="hero-badge">最近心跳 {format_time(summary["latest_heartbeat_at"])}</div>
                            <div class="hero-badge">最近采集 {format_time(summary["latest_capture_at"])}</div>
                            <div class="hero-badge">最近告警 {latest_alert_text}</div>
                        </div>
                    </div>
                    <div class="hero-side">
                        <div class="hero-side-card">
                            <strong>当前总览</strong>
                            <div class="big">{summary["green_instances"]} 个实例健康</div>
                            <div class="sub">Yellow {summary["yellow_instances"]} · Red {summary["red_instances"]}</div>
                        </div>
                        <div class="hero-side-card">
                            <strong>分析与告警</strong>
                            <div class="big">{summary["total_analyses"]} 条分析</div>
                            <div class="sub">{summary["total_alerts"]} 条告警回执已落库</div>
                        </div>
                    </div>
                </div>
            </section>
            <section class="metric-grid">{card_html}</section>
            <section class="top-grid">
                <section class="panel">
                    <div class="panel-head">
                        <div>
                            <h2 class="panel-title">运行规则</h2>
                            <div class="panel-subtitle">先看这个区域，能快速判断脚本是慢了、挂了，还是只是暂时没有异常。</div>
                        </div>
                        {build_chip("实时聚合", "teal")}
                    </div>
                    <div class="guide-grid">
                        <div class="guide-box">
                            <strong>健康判定</strong>
                            <div class="guide-line"><b>Green</b>：5 分钟内有心跳，10 分钟内有成功采集，且无连续错误。</div>
                            <div class="guide-line"><b>Yellow</b>：心跳还在，但采集变慢或最近有间歇性错误。</div>
                            <div class="guide-line"><b>Red</b>：超过 10 分钟无心跳，或连续错误达到阈值。</div>
                        </div>
                        <div class="guide-box">
                            <strong>当前链路</strong>
                            <div class="guide-line">油猴负责采集与上报。</div>
                            <div class="guide-line">后端负责落库、规则分析、模型摘要和后台展示。</div>
                            <div class="guide-line">告警发送后会写入最近告警记录，方便回查发送结果。</div>
                        </div>
                    </div>
                </section>
                <section class="panel">
                    <div class="panel-head">
                        <div>
                            <h2 class="panel-title">调试接口</h2>
                            <div class="panel-subtitle">本地联调和穿透后的外部检查都可以直接用这些接口。</div>
                        </div>
                    <a class="top-link" href="/admin/alerts">查看告警中心</a>
                    </div>
                    <div class="stack-list">
                        <div class="api-row"><code>GET /healthz</code><span>存活检查</span></div>
                        <div class="api-row"><code>GET /readyz</code><span>数据库就绪检查</span></div>
                        <div class="api-row"><code>POST /ingest</code><span>采集落库</span></div>
                        <div class="api-row"><code>POST /heartbeat</code><span>实例心跳</span></div>
                        <div class="api-row"><code>POST /error</code><span>错误上报</span></div>
                        <div class="api-row"><code>POST /alert-record</code><span>告警回执落库</span></div>
                        <div class="api-row"><code>GET /admin/alerts</code><span>最近告警记录</span></div>
                        <div class="api-row"><code>GET /admin/summary</code><span>总览聚合</span></div>
                    </div>
                </section>
            </section>
            <section class="panel" style="margin-top: 18px;">
                <div class="panel-head">
                    <div>
                        <h2 class="panel-title">最近告警记录</h2>
                        <div class="panel-subtitle">这里展示 PushPlus 发送结果和对应实例，方便确认邮件是否真的发出，以及是哪一个账号触发。</div>
                    </div>
                    <a class="top-link" style="color:#0f172a;background:#fff;border-color:rgba(148,163,184,0.18);" href="/admin/alerts">查看全部历史</a>
                </div>
                <div class="alert-grid">{alerts_html}</div>
            </section>
            <section class="panel" style="margin-top: 18px;">
                <div class="panel-head">
                    <div>
                        <h2 class="panel-title">实例健康列表</h2>
                        <div class="panel-subtitle">按最近心跳倒序。这里重点看账号归属、采集状态、最近异常类型和最新分析结论。</div>
                    </div>
                    {build_chip("按实例聚合", "teal")}
                </div>
                <div class="table-shell">
                    <table>
                        <thead>
                            <tr>
                                <th>账号 / 实例</th>
                                <th>页面</th>
                                <th>状态</th>
                                <th>脚本</th>
                                <th>时间</th>
                                <th>采集</th>
                                <th>异常</th>
                                <th>最近分析</th>
                            </tr>
                        </thead>
                        <tbody>{instance_rows_html}</tbody>
                    </table>
                </div>
                <div class="footer-note">页面刷新即可看到最新告警与实例状态，无需手动清缓存。</div>
            </section>
        </main>
        <script>
            document.querySelectorAll('.click-row[data-href]').forEach(function (row) {{
                row.addEventListener('click', function (event) {{
                    if (event.target.closest('a, button, input, select, textarea, label')) {{
                        return;
                    }}
                    var href = row.getAttribute('data-href');
                    if (href) {{
                        window.location.href = href;
                    }}
                }});
            }});
        </script>
    </body>
    </html>
    """


def build_instance_detail_html(detail: dict, db_path: Path) -> str:
    history = detail.get("capture_history") or []
    chart_html = build_trend_chart(history)
    health_tone = {"green": "green", "yellow": "yellow", "red": "red"}.get(detail.get("health_status"), "slate")

    info_cards = [
        ("账号", format_account_identity(detail.get("account_name"), detail.get("account_id"))),
        ("实例 ID", detail.get("instance_id") or "-"),
        ("页面类型", detail.get("page_type") or "-"),
        ("脚本版本", detail.get("script_version") or "-"),
        ("最近心跳", format_time(detail.get("last_heartbeat_at"))),
        ("最近采集", format_time(detail.get("last_capture_at"))),
        ("最近错误", compact_text(detail.get("last_error"), 90)),
        ("采集状态", detail.get("last_capture_status") or "-"),
    ]
    info_cards_html = "".join(
        f"""
        <div class="detail-card">
            <div class="detail-label">{html.escape(label)}</div>
            <div class="detail-value">{html.escape(value)}</div>
        </div>
        """
        for label, value in info_cards
    )

    history_rows = "".join(
        f"""
        <tr>
            <td>{format_time(item.get("captured_at"))}</td>
            <td>{float(item.get("current_spend") or 0):.2f}</td>
            <td>{float(item.get("increase_amount") or 0):.2f}</td>
            <td>{'-' if item.get('baseline_spend') is None else f"{float(item.get('baseline_spend') or 0):.2f}"}</td>
            <td>{item.get("compare_interval_min") or '-'}</td>
            <td>{item.get("row_count") or '-'}</td>
        </tr>
        """
        for item in reversed(history[-20:])
    ) or '<tr><td colspan="6" class="empty-state">暂无采样记录</td></tr>'

    analysis_cards = "".join(
        f"""
        <article class="stack-card">
            <div class="stack-top">
                <div class="cell-title">{html.escape(item.get("summary") or "-")}</div>
                {build_chip((item.get("severity") or "-").upper(), {"low": "teal", "medium": "yellow", "high": "red"}.get(item.get("severity") or "", "slate"))}
            </div>
            <div class="cell-sub">{format_time(item.get("created_at"))} · {html.escape(item.get("provider") or "-")} / {html.escape(item.get("model") or "-")} · {html.escape(item.get("anomaly_type") or "-")}</div>
            <div class="stack-preview">{html.escape(compact_text(item.get("raw_text"), 260))}</div>
        </article>
        """
        for item in detail.get("recent_analyses", [])
    ) or '<div class="empty-panel">最近还没有分析记录。</div>'

    error_cards = "".join(
        f"""
        <article class="stack-card">
            <div class="stack-top">
                <div class="cell-title">{html.escape(item.get("error_type") or "-")}</div>
                {build_chip("ERROR", "red")}
            </div>
            <div class="cell-sub">{format_time(item.get("occurred_at"))}</div>
            <div class="stack-preview">{html.escape(item.get("error_message") or "-")}</div>
        </article>
        """
        for item in detail.get("recent_errors", [])
    ) or '<div class="empty-panel">最近没有错误记录。</div>'

    alert_cards = "".join(
        f"""
        <article class="stack-card">
            <div class="stack-top">
                <div class="cell-title">{html.escape(item.get("title") or "-")}</div>
                {build_chip((item.get("send_status") or "-").upper(), {"sent": "green", "failed": "red", "skipped": "yellow"}.get(item.get("send_status") or "", "slate"))}
            </div>
            <div class="cell-sub">{format_time(item.get("triggered_at"))} · {html.escape(item.get("channel") or "-")} · {html.escape(item.get("alert_kind") or "-")}</div>
            <div class="stack-preview">{html.escape(compact_text(item.get("content_preview"), 220))}</div>
        </article>
        """
        for item in detail.get("recent_alerts", [])
    ) or '<div class="empty-panel">最近没有告警记录。</div>'

    return f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>实例详情 - AdBudgetSentry</title>
        <style>
            :root {{
                --bg-top: #f3fbfa;
                --bg-bottom: #eef2ff;
                --panel: rgba(255,255,255,0.92);
                --border: rgba(148,163,184,0.20);
                --ink: #0f172a;
                --muted: #5b6b82;
                --shadow: 0 18px 44px rgba(15,23,42,0.10);
            }}
            * {{ box-sizing: border-box; }}
            body {{
                margin: 0;
                color: var(--ink);
                font-family: "Avenir Next", "PingFang SC", "Microsoft YaHei", sans-serif;
                background:
                    radial-gradient(circle at 0% 0%, rgba(45, 212, 191, 0.18), transparent 28%),
                    radial-gradient(circle at 100% 20%, rgba(96, 165, 250, 0.16), transparent 22%),
                    linear-gradient(180deg, var(--bg-top) 0%, var(--bg-bottom) 100%);
            }}
            .shell {{ max-width: 1380px; margin: 0 auto; padding: 28px 20px 44px; }}
            .hero {{
                border-radius: 28px;
                padding: 28px;
                background: linear-gradient(135deg, rgba(15, 118, 110, 0.96), rgba(15, 23, 42, 0.92));
                color: #fff;
                box-shadow: 0 26px 64px rgba(15, 118, 110, 0.26);
            }}
            .hero-top {{ display:flex; justify-content:space-between; gap:16px; align-items:flex-start; }}
            .hero h1 {{ margin: 8px 0 8px; font-size: clamp(28px, 4vw, 42px); line-height: 1.05; }}
            .hero p {{ margin: 0; color: rgba(255,255,255,0.84); font-size: 15px; line-height: 1.7; max-width: 780px; }}
            .hero-meta {{ display:flex; flex-wrap:wrap; gap:10px; margin-top:16px; }}
            .hero-badge {{
                padding: 10px 14px; border-radius: 999px; font-size: 13px; color: rgba(255,255,255,0.92);
                background: rgba(255,255,255,0.10); border: 1px solid rgba(255,255,255,0.14);
            }}
            .back-link {{
                display:inline-flex; align-items:center; gap:8px; color:#fff; text-decoration:none;
                padding:10px 14px; border-radius:999px; background:rgba(255,255,255,0.12); border:1px solid rgba(255,255,255,0.16);
            }}
            .chip {{
                display: inline-flex; align-items:center; justify-content:center; padding: 6px 10px; border-radius:999px;
                font-size:12px; font-weight:700; letter-spacing:0.04em; white-space:nowrap;
            }}
            .grid {{ display:grid; gap:16px; margin-top:20px; }}
            .summary-grid {{ grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }}
            .panel {{
                background: var(--panel);
                border: 1px solid var(--border);
                border-radius: 22px;
                padding: 22px;
                box-shadow: var(--shadow);
            }}
            .panel-head {{ display:flex; justify-content:space-between; gap:12px; align-items:flex-end; margin-bottom:16px; }}
            .panel-title {{ margin:0; font-size:20px; }}
            .panel-subtitle {{ margin-top:6px; font-size:13px; color:var(--muted); }}
            .detail-card {{
                border-radius: 18px;
                padding: 16px;
                background: #fff;
                border: 1px solid rgba(226,232,240,0.86);
            }}
            .detail-label {{ font-size:12px; text-transform:uppercase; letter-spacing:0.08em; color:var(--muted); margin-bottom:8px; }}
            .detail-value {{ font-size:14px; line-height:1.6; word-break:break-all; }}
            .two-col {{ display:grid; grid-template-columns: minmax(0, 1.25fr) minmax(320px, 0.75fr); gap:16px; margin-top:20px; }}
            .trend-chart {{ width:100%; height:auto; display:block; }}
            .chart-wrap {{ display:grid; gap:12px; }}
            .chart-legend {{ display:flex; gap:18px; flex-wrap:wrap; font-size:13px; color:var(--muted); }}
            .dot {{ width:10px; height:10px; border-radius:999px; display:inline-block; margin-right:8px; }}
            .dot-teal {{ background:#0f766e; }}
            .dot-blue {{ background:#1d4ed8; }}
            .stack-list {{ display:grid; gap:12px; }}
            .stack-card {{ padding:16px; border-radius:18px; background:#fff; border:1px solid rgba(226,232,240,0.86); }}
            .stack-top {{ display:flex; justify-content:space-between; gap:10px; align-items:flex-start; }}
            .cell-title {{ font-size:14px; font-weight:700; line-height:1.5; }}
            .cell-sub {{ margin-top:4px; font-size:12px; line-height:1.6; color:var(--muted); word-break:break-all; }}
            .stack-preview {{ margin-top:10px; font-size:13px; line-height:1.75; color:#1e293b; white-space:pre-wrap; }}
            .table-shell {{ overflow:hidden; border-radius:20px; border:1px solid rgba(226,232,240,0.88); background:#fff; }}
            table {{ width:100%; border-collapse:collapse; font-size:13px; }}
            th, td {{ padding:14px; border-bottom:1px solid rgba(226,232,240,0.84); text-align:left; vertical-align:top; }}
            th {{ font-size:12px; letter-spacing:0.06em; text-transform:uppercase; color:var(--muted); background:rgba(248,250,252,0.94); }}
            .empty-panel, .empty-state {{ padding:28px 16px; text-align:center; color:var(--muted); }}
            .footer-note {{ margin-top:16px; font-size:12px; color:var(--muted); }}
            @media (max-width: 980px) {{
                .hero-top, .two-col {{ grid-template-columns:1fr; display:grid; }}
            }}
            @media (max-width: 860px) {{
                .shell {{ padding:18px 14px 28px; }}
                .table-shell {{ overflow-x:auto; }}
                table {{ min-width:760px; }}
            }}
        </style>
    </head>
    <body>
        <main class="shell">
            <section class="hero">
                <div class="hero-top">
                    <div>
                        <a class="back-link" href="/admin">返回总览</a>
                        <h1>{html.escape(format_account_identity(detail.get("account_name"), detail.get("account_id")))}</h1>
                        <p>实例详情页用于排障。这里会集中展示该脚本实例的最近采样、最新分析、最近告警和最近错误，方便快速判断问题是采样异常、阈值命中还是发送链路异常。</p>
                        <div class="hero-meta">
                            <div class="hero-badge">数据库 {html.escape(str(db_path))}</div>
                            <div class="hero-badge">实例 {html.escape(detail.get("instance_id") or "-")}</div>
                            <div class="hero-badge">状态 {detail.get("health_status", "-").upper()}</div>
                            <div class="hero-badge">最近采集 {format_time(detail.get("last_capture_at"))}</div>
                        </div>
                    </div>
                    <div>{build_chip(detail.get("health_status", "-").upper(), health_tone)}</div>
                </div>
            </section>

            <section class="grid summary-grid">
                {info_cards_html}
            </section>

            <section class="two-col">
                <section class="panel">
                    <div class="panel-head">
                        <div>
                            <h2 class="panel-title">最近采样趋势</h2>
                            <div class="panel-subtitle">绿色线是当前总消耗，蓝色线是窗口增量。用于快速判断上涨节奏和异常触发前后的变化。</div>
                        </div>
                        {build_chip(f"{len(history)} 个采样点", "blue")}
                    </div>
                    {chart_html}
                </section>
                <section class="panel">
                    <div class="panel-head">
                        <div>
                            <h2 class="panel-title">最近分析</h2>
                            <div class="panel-subtitle">优先看这里判断模型和规则最近给出的结论。</div>
                        </div>
                        {build_chip(f"{len(detail.get('recent_analyses', []))} 条", "teal")}
                    </div>
                    <div class="stack-list">{analysis_cards}</div>
                </section>
            </section>

            <section class="panel" style="margin-top:20px;">
                <div class="panel-head">
                    <div>
                        <h2 class="panel-title">最近采样历史</h2>
                        <div class="panel-subtitle">这里列出最近 20 条采样的核心数值，方便和趋势图交叉验证。</div>
                    </div>
                    {build_chip("最近 20 条", "slate")}
                </div>
                <div class="table-shell">
                    <table>
                        <thead>
                            <tr>
                                <th>采样时间</th>
                                <th>当前总消耗</th>
                                <th>窗口增量</th>
                                <th>基线消耗</th>
                                <th>比较窗口</th>
                                <th>行数</th>
                            </tr>
                        </thead>
                        <tbody>{history_rows}</tbody>
                    </table>
                </div>
            </section>

            <section class="two-col">
                <section class="panel">
                    <div class="panel-head">
                        <div>
                            <h2 class="panel-title">最近告警记录</h2>
                            <div class="panel-subtitle">确认该实例是否真的触发并发出了告警。</div>
                        </div>
                        {build_chip(f"{len(detail.get('recent_alerts', []))} 条", "yellow")}
                    </div>
                    <div class="stack-list">{alert_cards}</div>
                </section>
                <section class="panel">
                    <div class="panel-head">
                        <div>
                            <h2 class="panel-title">最近错误记录</h2>
                            <div class="panel-subtitle">如果这里出现连续错误，优先排查页面结构变化和采集选择器。</div>
                        </div>
                        {build_chip(f"{len(detail.get('recent_errors', []))} 条", "red")}
                    </div>
                    <div class="stack-list">{error_cards}</div>
                </section>
            </section>

            <div class="footer-note">趋势图和采样历史来自后端保存的 capture_events，不依赖浏览器当前页重新抓取。</div>
        </main>
    </body>
    </html>
    """


def build_alerts_page_html(
    alerts: list[dict],
    db_path: Path,
    *,
    account_keyword: str = "",
    send_status: str = "",
    alert_kind: str = "",
    date_from: str = "",
    date_to: str = "",
) -> str:
    alert_cards: list[str] = []
    for alert in alerts:
        status = alert.get("send_status") or "unknown"
        tone = {"sent": "green", "failed": "red", "skipped": "yellow"}.get(status, "slate")
        account_text = format_account_identity(alert.get("account_name"), alert.get("account_id"))
        meta_bits = [
            f"触发时间 {format_time(alert.get('triggered_at'))}",
            f"渠道 {alert.get('channel') or '-'}",
            f"类型 {alert.get('alert_kind') or '-'}",
            f"提供方 {alert.get('delivery_provider') or 'pushplus'}",
        ]
        if alert.get("anomaly_type"):
            meta_bits.append(f"异常 {alert['anomaly_type']}")
        if alert.get("severity"):
            meta_bits.append(f"严重度 {alert['severity']}")
        alert_cards.append(
            f"""
            <article class="alert-card alert-{html.escape(status)}">
                <div class="alert-top">
                    <div>
                        <div class="cell-title">{html.escape(alert.get("title") or "-")}</div>
                        <div class="cell-sub">{html.escape(account_text)}</div>
                    </div>
                    {build_chip(status.upper(), tone)}
                </div>
                <div class="alert-meta">{html.escape(" · ".join(meta_bits))}</div>
                <div class="alert-preview">{html.escape(alert.get("content_preview") or "-")}</div>
                <div class="alert-foot">
                    <span>实例 {html.escape(alert.get("instance_id") or "-")}</span>
                    <span>{html.escape(alert.get("page_type") or "-")}</span>
                </div>
            </article>
            """
        )
    alerts_html = "".join(alert_cards) or '<div class="empty-panel">当前筛选条件下没有告警记录。</div>'

    filter_count = sum(1 for value in [account_keyword, send_status, alert_kind, date_from, date_to] if value)

    return f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>AdBudgetSentry 告警中心</title>
        <style>
            :root {{
                --bg-top: #f3fbfa;
                --bg-bottom: #eef2ff;
                --panel: rgba(255, 255, 255, 0.88);
                --border: rgba(148, 163, 184, 0.18);
                --ink: #0f172a;
                --muted: #64748b;
                --shadow: 0 18px 44px rgba(15, 23, 42, 0.10);
            }}
            * {{ box-sizing: border-box; }}
            body {{
                margin: 0;
                color: var(--ink);
                font-family: "Avenir Next", "PingFang SC", "Microsoft YaHei", sans-serif;
                background:
                    radial-gradient(circle at 0% 0%, rgba(45, 212, 191, 0.18), transparent 28%),
                    radial-gradient(circle at 100% 20%, rgba(96, 165, 250, 0.16), transparent 22%),
                    linear-gradient(180deg, var(--bg-top) 0%, var(--bg-bottom) 100%);
            }}
            .shell {{ max-width: 1380px; margin: 0 auto; padding: 28px 20px 44px; }}
            .hero {{
                border-radius: 28px; padding: 28px 30px; color: #fff;
                background: linear-gradient(135deg, rgba(15, 118, 110, 0.96), rgba(15, 23, 42, 0.92));
                box-shadow: 0 26px 64px rgba(15, 118, 110, 0.26);
            }}
            .eyebrow {{ font-size: 12px; letter-spacing: 0.16em; text-transform: uppercase; color: rgba(255,255,255,0.74); }}
            .hero h1 {{ margin: 10px 0 10px; font-size: clamp(30px, 4vw, 42px); line-height: 1.02; }}
            .hero p {{ margin: 0; max-width: 860px; font-size: 15px; line-height: 1.7; color: rgba(255,255,255,0.84); }}
            .hero-meta {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 16px; }}
            .hero-badge, .top-link {{
                display: inline-flex; align-items: center; justify-content: center; gap: 8px; padding: 10px 14px;
                border-radius: 999px; font-size: 13px; font-weight: 700;
                background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.16); color: rgba(255,255,255,0.92);
            }}
            .top-link {{ text-decoration: none; }}
            .panel {{
                margin-top: 18px; padding: 22px; border-radius: 22px; background: var(--panel);
                border: 1px solid var(--border); box-shadow: var(--shadow); backdrop-filter: blur(20px);
            }}
            .panel-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: flex-end; margin-bottom: 16px; }}
            .panel-title {{ margin: 0; font-size: 20px; line-height: 1.2; }}
            .panel-subtitle {{ margin-top: 6px; color: var(--muted); font-size: 13px; }}
            .chip {{
                display: inline-flex; align-items: center; justify-content: center; padding: 6px 10px; border-radius: 999px;
                font-size: 12px; font-weight: 700; letter-spacing: 0.04em; white-space: nowrap;
            }}
            .filter-grid {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; }}
            .field {{ display: grid; gap: 8px; }}
            .field label {{ font-size: 12px; font-weight: 700; letter-spacing: 0.04em; color: var(--muted); }}
            .field input, .field select {{
                width: 100%; border: 1px solid rgba(148, 163, 184, 0.26); border-radius: 14px; background: #fff;
                padding: 12px 14px; font-size: 14px; color: var(--ink); outline: none;
            }}
            .field input:focus, .field select:focus {{ border-color: rgba(15, 118, 110, 0.54); box-shadow: 0 0 0 4px rgba(45, 212, 191, 0.12); }}
            .filter-actions {{ display: flex; gap: 10px; margin-top: 14px; flex-wrap: wrap; }}
            .btn {{
                display: inline-flex; align-items: center; justify-content: center; padding: 11px 16px; border-radius: 14px;
                border: 1px solid rgba(15, 118, 110, 0.18); background: #0f766e; color: #fff; font-size: 14px; font-weight: 700; text-decoration: none;
            }}
            .btn.secondary {{ background: #fff; color: var(--ink); border-color: rgba(148, 163, 184, 0.24); }}
            .summary-row {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px; }}
            .summary-pill {{
                display: inline-flex; align-items: center; padding: 8px 12px; border-radius: 999px; background: rgba(248, 250, 252, 0.96);
                border: 1px solid rgba(226, 232, 240, 0.9); color: var(--muted); font-size: 13px;
            }}
            .alert-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 14px; }}
            .alert-card {{
                padding: 18px; border-radius: 18px; background: #ffffff; border: 1px solid rgba(226, 232, 240, 0.88);
                box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
            }}
            .alert-sent {{ border-left: 6px solid rgba(22, 101, 52, 0.72); }}
            .alert-failed {{ border-left: 6px solid rgba(185, 28, 28, 0.72); }}
            .alert-skipped {{ border-left: 6px solid rgba(161, 98, 7, 0.72); }}
            .alert-top {{ display: flex; gap: 10px; align-items: flex-start; justify-content: space-between; }}
            .cell-title {{ font-size: 14px; font-weight: 700; line-height: 1.45; color: var(--ink); }}
            .cell-sub {{ margin-top: 4px; font-size: 12px; line-height: 1.5; color: var(--muted); word-break: break-all; }}
            .alert-meta {{ margin: 12px 0 10px; font-size: 12px; line-height: 1.6; color: var(--muted); }}
            .alert-preview {{ font-size: 13px; line-height: 1.7; color: #1e293b; white-space: pre-wrap; min-height: 72px; }}
            .alert-foot {{ margin-top: 14px; display: flex; justify-content: space-between; gap: 10px; font-size: 12px; color: var(--muted); }}
            .empty-panel {{ padding: 34px 16px; text-align: center; color: var(--muted); border-radius: 18px; background: rgba(255,255,255,0.72); }}
            @media (max-width: 1120px) {{ .filter-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
            @media (max-width: 720px) {{
                .shell {{ padding: 18px 14px 28px; }}
                .hero {{ padding: 22px; }}
                .filter-grid {{ grid-template-columns: 1fr; }}
            }}
        </style>
    </head>
    <body>
        <main class="shell">
            <section class="hero">
                <div class="eyebrow">Alert Center</div>
                <h1>告警历史、筛选结果和发送回执统一查看</h1>
                <p>这里保留完整告警历史，支持按账号、发送状态、告警类型和日期范围过滤。总览页只看最近记录，查历史和排障都在这个页面完成。</p>
                <div class="hero-meta">
                    <div class="hero-badge">数据库 {html.escape(str(db_path))}</div>
                    <div class="hero-badge">当前结果 {len(alerts)} 条</div>
                    <div class="hero-badge">已启用筛选 {filter_count} 项</div>
                    <a class="top-link" href="/admin">返回总览</a>
                </div>
            </section>

            <section class="panel">
                <div class="panel-head">
                    <div>
                        <h2 class="panel-title">筛选条件</h2>
                        <div class="panel-subtitle">支持账号关键字、日期范围、发送状态和告警类型组合过滤。</div>
                    </div>
                    {build_chip("历史查询", "teal")}
                </div>
                <form method="get" action="/admin/alerts">
                    <div class="filter-grid">
                        <div class="field">
                            <label for="account_keyword">账号 / 账号ID / 实例ID</label>
                            <input id="account_keyword" name="account_keyword" value="{html.escape(account_keyword)}" placeholder="输入账号名、账号ID或实例ID" />
                        </div>
                        <div class="field">
                            <label for="send_status">发送状态</label>
                            <select id="send_status" name="send_status">
                                <option value=""{" selected" if not send_status else ""}>全部</option>
                                <option value="sent"{" selected" if send_status == "sent" else ""}>已发送</option>
                                <option value="failed"{" selected" if send_status == "failed" else ""}>发送失败</option>
                                <option value="skipped"{" selected" if send_status == "skipped" else ""}>跳过</option>
                            </select>
                        </div>
                        <div class="field">
                            <label for="alert_kind">告警类型</label>
                            <select id="alert_kind" name="alert_kind">
                                <option value=""{" selected" if not alert_kind else ""}>全部</option>
                                <option value="threshold_exceeded"{" selected" if alert_kind == "threshold_exceeded" else ""}>阈值超限</option>
                                <option value="analysis_summary"{" selected" if alert_kind == "analysis_summary" else ""}>分析摘要</option>
                                <option value="test"{" selected" if alert_kind == "test" else ""}>测试告警</option>
                            </select>
                        </div>
                        <div class="field">
                            <label for="date_from">开始日期</label>
                            <input id="date_from" name="date_from" type="date" value="{html.escape(date_from)}" />
                        </div>
                        <div class="field">
                            <label for="date_to">结束日期</label>
                            <input id="date_to" name="date_to" type="date" value="{html.escape(date_to)}" />
                        </div>
                    </div>
                    <div class="filter-actions">
                        <button class="btn" type="submit">查询记录</button>
                        <a class="btn secondary" href="/admin/alerts">清空筛选</a>
                    </div>
                </form>
                <div class="summary-row">
                    <div class="summary-pill">结果条数 {len(alerts)}</div>
                    <div class="summary-pill">账号关键字 {html.escape(account_keyword or "全部")}</div>
                    <div class="summary-pill">发送状态 {html.escape(send_status or "全部")}</div>
                    <div class="summary-pill">告警类型 {html.escape(alert_kind or "全部")}</div>
                    <div class="summary-pill">日期范围 {html.escape((date_from or "-") + " ~ " + (date_to or "-"))}</div>
                </div>
            </section>

            <section class="panel">
                <div class="panel-head">
                    <div>
                        <h2 class="panel-title">告警历史</h2>
                        <div class="panel-subtitle">默认展示最近 500 条，点击实例可回到详情页交叉查看采样、错误和分析。</div>
                    </div>
                    {build_chip(f"{len(alerts)} 条结果", "blue")}
                </div>
                <div class="alert-grid">{alerts_html}</div>
            </section>
        </main>
        <script>
            document.querySelectorAll('.click-row[data-href]').forEach(function (row) {{
                row.addEventListener('click', function (event) {{
                    if (event.target.closest('a, button, input, select, textarea, label')) {{
                        return;
                    }}
                    var href = row.getAttribute('data-href');
                    if (href) {{
                        window.location.href = href;
                    }}
                }});
            }});
        </script>
    </body>
    </html>
    """
