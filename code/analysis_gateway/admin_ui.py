from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path


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
            <tr>
                <td>
                    <div class="cell-title">{html.escape(account_text)}</div>
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
                        {build_chip("HTTP", "blue")}
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
                    {build_chip("最近 20 条", "slate")}
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
    </body>
    </html>
    """
