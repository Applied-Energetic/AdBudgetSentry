from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path
from urllib.parse import quote


THEME_KEY = "adbudget-theme"
BADGE_TONE_MAP = {
    "teal": "accent",
    "green": "success",
    "yellow": "warning",
    "red": "danger",
    "blue": "info",
    "slate": "neutral",
}

FOUNDATION_CSS = """
:root{--space-1:4px;--space-2:8px;--space-3:12px;--space-4:16px;--space-5:20px;--space-6:24px;--space-7:28px;--space-8:32px;--radius-sm:12px;--radius-md:16px;--radius-lg:20px;--radius-xl:28px;--border-width-thin:1px;--shadow-soft:0 8px 24px rgba(15,23,42,.06);--shadow-card:0 20px 48px rgba(15,23,42,.10);--shadow-hero:0 26px 60px rgba(15,23,42,.20);--font-family-base:"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;--font-size-label:12px;--font-size-body-sm:13px;--font-size-body-md:14px;--font-size-title-3:18px;--font-size-title-2:20px;--font-size-title-1:clamp(28px,4vw,42px);--font-size-metric:30px;--line-height-tight:1.2;--line-height-body:1.7;--button-height:38px;--touch-target-min:38px;--color-accent:#0f766e;--color-info:#1d4ed8;--color-danger:#b91c1c;--color-success:#166534;--color-warning:#a16207;--color-neutral:#334155;--color-chart-1:#0f766e;--color-chart-2:#1d4ed8}
:root[data-theme="light"]{--color-bg-page:#f4f7fb;--color-bg-page-alt:#edf3fb;--color-bg-surface:rgba(255,255,255,.92);--color-bg-elevated:#ffffff;--color-text-primary:#142033;--color-text-secondary:#617085;--color-text-inverse:#ffffff;--color-text-inverse-muted:rgba(255,255,255,.84);--color-text-inverse-soft:rgba(255,255,255,.72);--color-border-subtle:rgba(148,163,184,.22);--color-hero:linear-gradient(135deg,rgba(16,76,103,.94),rgba(16,24,40,.94));--color-chart-bg:rgba(248,250,252,.96);--color-axis:#64748b;--color-badge-accent-bg:rgba(45,212,191,.16);--color-badge-accent-fg:#0f766e;--color-badge-success-bg:rgba(134,239,172,.22);--color-badge-success-fg:#166534;--color-badge-warning-bg:rgba(253,224,71,.24);--color-badge-warning-fg:#a16207;--color-badge-danger-bg:rgba(252,165,165,.24);--color-badge-danger-fg:#b91c1c;--color-badge-info-bg:rgba(147,197,253,.24);--color-badge-info-fg:#1d4ed8;--color-badge-neutral-bg:rgba(203,213,225,.34);--color-badge-neutral-fg:#334155}
:root[data-theme="dark"]{--color-bg-page:#09111d;--color-bg-page-alt:#111b2b;--color-bg-surface:rgba(15,23,42,.86);--color-bg-elevated:#111827;--color-text-primary:#e6eef9;--color-text-secondary:#94a3b8;--color-text-inverse:#ffffff;--color-text-inverse-muted:rgba(255,255,255,.84);--color-text-inverse-soft:rgba(255,255,255,.72);--color-border-subtle:rgba(148,163,184,.18);--color-hero:linear-gradient(135deg,rgba(14,56,79,.96),rgba(7,12,24,.98));--color-chart-bg:rgba(15,23,42,.96);--color-axis:#94a3b8;--color-badge-accent-bg:rgba(45,212,191,.18);--color-badge-accent-fg:#7ce6da;--color-badge-success-bg:rgba(134,239,172,.18);--color-badge-success-fg:#9ee8b0;--color-badge-warning-bg:rgba(253,224,71,.18);--color-badge-warning-fg:#f5d66f;--color-badge-danger-bg:rgba(252,165,165,.18);--color-badge-danger-fg:#f3a6a6;--color-badge-info-bg:rgba(147,197,253,.18);--color-badge-info-fg:#9fc7ff;--color-badge-neutral-bg:rgba(148,163,184,.22);--color-badge-neutral-fg:#d7e0ef}
*{box-sizing:border-box}
body{margin:0;color:var(--color-text-primary);font-family:var(--font-family-base);background:radial-gradient(circle at 0% 0%,rgba(94,234,212,.10),transparent 26%),radial-gradient(circle at 100% 0%,rgba(96,165,250,.10),transparent 22%),linear-gradient(180deg,var(--color-bg-page) 0%,var(--color-bg-page-alt) 100%)}
a{color:inherit;text-decoration:none}
.app-shell{display:contents}
.shell{max-width:1380px;margin:0 auto;padding:var(--space-6) var(--space-5) 40px}
.page-header,.hero{border-radius:var(--radius-xl);padding:var(--space-7);color:var(--color-text-inverse);background:var(--color-hero);box-shadow:var(--shadow-hero)}
.page-header__layout,.hero-grid,.split{display:grid;gap:var(--space-4);grid-template-columns:minmax(0,1.15fr) minmax(300px,.85fr)}
.page-header__content{display:grid;gap:var(--space-3);align-content:start}
.page-header__eyebrow,.eyebrow,.metric .label,.meta-label{font-size:var(--font-size-label);letter-spacing:.06em;text-transform:uppercase}
.page-header__eyebrow,.eyebrow{color:var(--color-text-inverse-soft);letter-spacing:.16em}
.page-header__title,.hero h1{margin:0;font-size:var(--font-size-title-1);line-height:1.06}
.page-header__description,.hero p{margin:0;max-width:760px;line-height:var(--line-height-body);color:var(--color-text-inverse-muted);font-size:15px}
.page-header__meta,.page-header__actions,.hero-meta,.hero-actions,.metrics,.cards,.actions,.legend,.summary-row{display:flex;flex-wrap:wrap;gap:var(--space-3)}
.page-header__meta,.hero-meta{margin-top:var(--space-1)}
.page-header__aside{display:grid;align-content:start}
.card,.panel,.metric,.summary-box,.stack,.alert,.spotlight{background:var(--color-bg-surface);border:1px solid var(--color-border-subtle);border-radius:var(--radius-lg);box-shadow:var(--shadow-card)}
.card{padding:var(--space-4)}
.card-muted{background:rgba(255,255,255,.10);border-color:rgba(255,255,255,.18);color:var(--color-text-inverse)}
.card-header,.head{display:flex;justify-content:space-between;gap:var(--space-3);align-items:end;margin-bottom:var(--space-4)}
.card-title-group{display:grid;gap:6px}
.card-title,.title{margin:0;font-size:var(--font-size-title-2);line-height:var(--line-height-tight)}
.card-subtitle,.subtitle{margin:0;color:var(--color-text-secondary);font-size:var(--font-size-body-sm);line-height:1.6}
.card-muted .card-subtitle{color:var(--color-text-inverse-muted)}
.card-body{display:block}
.panel{padding:22px}
.metrics{margin:20px 0}
.metric{padding:18px;flex:1 1 150px}
.metric .label,.meta-label{color:var(--color-text-secondary)}
.metric .value{margin-top:var(--space-2);font-size:var(--font-size-metric);font-weight:800}
.badge,.chip{display:inline-flex;align-items:center;justify-content:center;padding:6px 10px;border-radius:999px;font-size:var(--font-size-label);font-weight:700;letter-spacing:.04em;white-space:nowrap;border:1px solid transparent}
.badge-accent{background:var(--color-badge-accent-bg);color:var(--color-badge-accent-fg)}
.badge-success{background:var(--color-badge-success-bg);color:var(--color-badge-success-fg)}
.badge-warning{background:var(--color-badge-warning-bg);color:var(--color-badge-warning-fg)}
.badge-danger{background:var(--color-badge-danger-bg);color:var(--color-badge-danger-fg)}
.badge-info{background:var(--color-badge-info-bg);color:var(--color-badge-info-fg)}
.badge-neutral{background:var(--color-badge-neutral-bg);color:var(--color-badge-neutral-fg)}
.button,.btn,.btn-light,.btn-danger{display:inline-flex;align-items:center;justify-content:center;min-height:var(--button-height);padding:0 14px;border-radius:999px;border:1px solid var(--color-border-subtle);cursor:pointer;font:inherit;transition:background-color .18s ease,border-color .18s ease,color .18s ease,transform .18s ease}
.button:hover,.btn:hover,.btn-light:hover,.btn-danger:hover{transform:translateY(-1px)}
.button-secondary,.btn{background:var(--color-bg-surface);color:var(--color-text-primary)}
.button-primary{background:var(--color-info);border-color:transparent;color:#fff}
.button-danger,.btn-danger{color:var(--color-danger);background:rgba(185,28,28,.08);border-color:transparent}
.button-inverted,.btn-light{background:rgba(255,255,255,.12);color:#fff;border-color:rgba(255,255,255,.18)}
.theme-toggle{display:inline-flex;flex-wrap:wrap;gap:var(--space-2)}
.theme-toggle button{min-height:36px;padding:0 12px;border-radius:999px;border:1px solid var(--color-border-subtle);background:var(--color-bg-surface);color:var(--color-text-primary);cursor:pointer}
.theme-toggle button.active{outline:2px solid rgba(94,234,212,.24)}
.cards{display:grid;gap:14px}
.card-link{display:block}
.row{display:flex;justify-content:space-between;gap:var(--space-3);align-items:flex-start}
.name{font-size:15px;font-weight:700;line-height:1.45}
.sub{margin-top:4px;font-size:var(--font-size-label);line-height:1.6;color:var(--color-text-secondary);word-break:break-word}
.stats{display:grid;gap:10px;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));margin-top:14px}
.stat{padding:12px;border-radius:14px;background:var(--color-bg-elevated);border:1px solid var(--color-border-subtle)}
.stat strong{display:block;font-size:var(--font-size-label);color:var(--color-text-secondary);margin-bottom:6px}
.actions{margin-top:14px}
.actions .button,.actions .btn,.actions .btn-danger,.actions .button-danger{flex:1 1 0}
.chart{display:grid;gap:12px}
.trend{width:100%;height:auto;display:block}
.dot{width:10px;height:10px;border-radius:999px;display:inline-block;margin-right:8px}
.dot.teal{background:var(--color-chart-1)}
.dot.blue{background:var(--color-chart-2)}
.detail-grid,.spotlights{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));margin-top:20px}
.detail,.spotlight{padding:18px}
.spotlight .value{margin-top:10px;font-size:clamp(28px,4vw,36px);font-weight:800}
.stack-list,.alerts{display:grid;gap:14px}
.stack,.alert{padding:16px}
.preview{margin-top:10px;font-size:var(--font-size-body-sm);line-height:1.75;white-space:pre-wrap}
.table-wrap{overflow:auto;border-radius:var(--radius-lg);border:1px solid var(--color-border-subtle);background:var(--color-bg-elevated)}
table{width:100%;border-collapse:collapse;font-size:var(--font-size-body-sm)}
th,td{padding:14px;text-align:left;border-bottom:1px solid var(--color-border-subtle);vertical-align:top}
th{font-size:var(--font-size-label);text-transform:uppercase;letter-spacing:.06em;color:var(--color-text-secondary);background:rgba(148,163,184,.08)}
.filters{display:grid;gap:12px;grid-template-columns:repeat(5,minmax(0,1fr))}
.field{display:grid;gap:6px}
.field label{font-size:var(--font-size-label);color:var(--color-text-secondary)}
input,select,textarea{width:100%;border-radius:14px;border:1px solid var(--color-border-subtle);background:var(--color-bg-elevated);color:var(--color-text-primary);font:inherit;padding:12px 14px}
textarea{min-height:112px;resize:vertical}
.summary-box{padding:18px}
.summary-box h3{margin:0 0 12px;font-size:15px}
.pill{display:inline-flex;align-items:center;padding:8px 12px;border-radius:999px;background:var(--color-bg-elevated);border:1px solid var(--color-border-subtle);font-size:var(--font-size-label)}
.empty,.note,.status{color:var(--color-text-secondary);font-size:var(--font-size-label);line-height:1.7}
.empty{padding:24px 12px;text-align:center}
@media (max-width:1120px){.page-header__layout,.hero-grid,.split,.filters{grid-template-columns:1fr}}
@media (max-width:860px){.shell{padding:16px 14px 28px}.page-header,.hero{padding:20px}.card-header,.head,.row{flex-direction:column;align-items:stretch}.actions{display:grid;grid-template-columns:1fr 1fr}.button,.btn,.btn-light,.btn-danger,.theme-toggle button{width:100%}}
@media (max-width:640px){.metrics,.detail-grid,.spotlights,.stats,.cards,.alerts{display:grid;grid-template-columns:1fr}.actions{grid-template-columns:1fr}}
"""

DASHBOARD_CSS = """
.dashboard-layout{display:grid;grid-template-columns:216px minmax(0,1fr);min-height:100vh;background:#f3f5f7}
.dashboard-sidebar{padding:18px 14px;border-right:1px solid rgba(15,23,42,.06);background:#f6f7f8}
.dashboard-sidebar__inner{position:sticky;top:0;display:grid;gap:18px;padding-top:10px}
.dashboard-brand{display:grid;gap:6px}
.dashboard-brand__eyebrow{font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:#8a94a6}
.dashboard-brand__title{font-size:18px;font-weight:700;line-height:1.15;color:#18212f}
.dashboard-brand__copy{font-size:12px;line-height:1.6;color:#7c8798}
.dashboard-nav{display:grid;gap:6px}
.dashboard-nav__label{margin-bottom:2px;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#98a2b3}
.dashboard-nav__link{display:flex;align-items:center;justify-content:space-between;padding:9px 10px;border-radius:12px;font-size:13px;color:#667085;border:1px solid transparent}
.dashboard-nav__link-main{display:flex;align-items:center;gap:10px}
.dashboard-nav__icon{display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:8px;background:rgba(15,23,42,.04);color:#6b7280;font-size:11px;font-weight:700}
.dashboard-nav__link:hover{background:#ffffff;color:#18212f;border-color:rgba(15,23,42,.06)}
.dashboard-nav__link.is-active{background:#ffffff;color:#18212f;border-color:rgba(15,23,42,.06);box-shadow:0 1px 2px rgba(15,23,42,.03)}
.dashboard-sidebar .card{background:#ffffff;border:1px solid rgba(15,23,42,.06);border-radius:12px;box-shadow:0 1px 2px rgba(15,23,42,.03)}
.dashboard-main{min-width:0;padding:20px}
.dashboard-toolbar{display:flex;align-items:center;justify-content:space-between;gap:var(--space-4);margin-bottom:20px}
.dashboard-toolbar__intro{display:grid;gap:6px}
.dashboard-toolbar__eyebrow{font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:#8a94a6}
.dashboard-toolbar__title{font-size:28px;font-weight:700;line-height:1.1;color:#18212f}
.dashboard-toolbar__copy{font-size:13px;line-height:1.6;color:#667085}
.dashboard-toolbar__actions{display:flex;align-items:center;gap:var(--space-3);flex-wrap:wrap;justify-content:flex-end}
.dashboard-search{min-width:260px;height:40px;padding:0 14px;border-radius:12px;border:1px solid rgba(15,23,42,.08);background:#ffffff;color:#18212f;font:inherit;box-shadow:0 1px 2px rgba(15,23,42,.02)}
.dashboard-search::placeholder{color:#98a2b3}
.dashboard-toolbar__icon-btn{width:40px;min-width:40px;height:40px;padding:0;border-radius:12px;border:1px solid rgba(15,23,42,.08);background:#ffffff;color:#667085;box-shadow:0 1px 2px rgba(15,23,42,.02)}
.dashboard-profile{display:flex;align-items:center;gap:10px;padding:6px 8px 6px 6px;border:1px solid rgba(15,23,42,.08);border-radius:14px;background:#ffffff;box-shadow:0 1px 2px rgba(15,23,42,.02)}
.dashboard-profile__avatar{display:inline-flex;align-items:center;justify-content:center;width:30px;height:30px;border-radius:10px;background:#ecf5f3;color:#0f766e;font-size:12px;font-weight:700}
.dashboard-profile__meta{display:grid;gap:2px}
.dashboard-profile__name{font-size:13px;font-weight:600;color:#18212f}
.dashboard-profile__role{font-size:11px;color:#98a2b3}
.dashboard-toolbar .theme-toggle{gap:8px}
.dashboard-toolbar .theme-toggle button{min-height:40px;padding:0 10px;border-radius:12px;border-color:rgba(15,23,42,.08);background:#ffffff;color:#98a2b3;box-shadow:0 1px 2px rgba(15,23,42,.02)}
.dashboard-toolbar .theme-toggle button.active{outline:none;border-color:rgba(15,118,110,.18);color:#0f766e;background:#ecf5f3}
.dashboard-content{display:grid;gap:20px}
.dashboard-kpi-grid{display:grid;gap:16px;grid-template-columns:repeat(4,minmax(0,1fr))}
.dashboard-kpi,.dashboard-chart-card,.dashboard-table-card{background:#ffffff;border:1px solid rgba(15,23,42,.06);border-radius:12px;box-shadow:0 1px 2px rgba(15,23,42,.03)}
.dashboard-kpi .card-body{display:grid;gap:10px}
.dashboard-kpi__top{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}
.dashboard-kpi__label{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#98a2b3}
.dashboard-kpi__icon{display:inline-flex;align-items:center;justify-content:center;width:32px;height:32px;border-radius:10px;font-size:11px;font-weight:700}
.dashboard-kpi__value{font-size:32px;font-weight:700;line-height:1;color:#18212f}
.dashboard-kpi__meta{font-size:12px;line-height:1.5;color:#667085}
.dashboard-chart-grid,.dashboard-table-grid{display:grid;gap:var(--space-4);grid-template-columns:repeat(2,minmax(0,1fr))}
.dashboard-chart{display:grid;gap:var(--space-3)}
.dashboard-chart__legend{display:flex;flex-wrap:wrap;gap:10px}
.dashboard-chart__legend-item{display:inline-flex;align-items:center;gap:8px;font-size:12px;color:#667085}
.dashboard-chart__legend-swatch{width:10px;height:10px;border-radius:999px}
.dashboard-mini-note{font-size:12px;line-height:1.6;color:#667085}
.dashboard-chart-card .card-header,.dashboard-table-card .card-header{margin-bottom:14px}
.dashboard-chart-card .card-title,.dashboard-table-card .card-title{font-size:16px}
.dashboard-chart-card .card-subtitle,.dashboard-table-card .card-subtitle{font-size:12px;color:#98a2b3}
.dashboard-table{width:100%;border-collapse:collapse}
.dashboard-table th,.dashboard-table td{padding:12px 10px;text-align:left;border-bottom:1px solid rgba(15,23,42,.06);vertical-align:middle}
.dashboard-table th{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#98a2b3;background:transparent}
.dashboard-table td{font-size:13px;color:#344054}
.dashboard-table__primary{font-weight:600;color:#18212f}
.dashboard-table__secondary{margin-top:4px;font-size:11px;color:#98a2b3}
.dashboard-table__link{font-weight:600;color:#0f766e}
.dashboard-sidebar-footer{font-size:11px;line-height:1.7;color:#98a2b3}
@media (max-width:1200px){.dashboard-kpi-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:1024px){.dashboard-layout{grid-template-columns:1fr}.dashboard-sidebar{border-right:0;border-bottom:1px solid rgba(15,23,42,.06)}.dashboard-sidebar__inner{position:static}}
@media (max-width:860px){.dashboard-main{padding:16px 14px 28px}.dashboard-toolbar{flex-direction:column;align-items:stretch}.dashboard-toolbar__actions{justify-content:stretch}.dashboard-search{min-width:0;width:100%}.dashboard-chart-grid,.dashboard-table-grid,.dashboard-kpi-grid{grid-template-columns:1fr}.dashboard-profile{justify-content:space-between}}
"""


def _join_classes(*parts: str | None) -> str:
    return " ".join(part.strip() for part in parts if part and part.strip())


def _render_attrs(attrs: dict[str, object] | None = None) -> str:
    if not attrs:
        return ""
    rendered: list[str] = []
    for key, value in attrs.items():
        if value is None or value is False:
            continue
        if value is True:
            rendered.append(key)
            continue
        rendered.append(f'{key}="{html.escape(str(value), quote=True)}"')
    return f" {' '.join(rendered)}" if rendered else ""


def format_time(timestamp_ms: int | None) -> str:
    if not timestamp_ms:
        return "-"
    return datetime.fromtimestamp(timestamp_ms / 1000).strftime("%Y-%m-%d %H:%M:%S")


def compact_text(value: str | None, limit: int = 100) -> str:
    if not value:
        return "-"
    raw = " ".join(str(value).split())
    return raw if len(raw) <= limit else f"{raw[: limit - 1]}..."


def format_money(value: float | int | None) -> str:
    if value is None:
        return "-"
    return f"{float(value):.2f}"


def is_missing_account_id(value: str | None) -> bool:
    return value in {None, "", "未识别账户ID"}


def format_account_identity(account_name: str | None, account_id: str | None) -> str:
    name = (account_name or "").strip()
    account_id = None if is_missing_account_id(account_id) else (account_id or "").strip()
    if name and account_id:
        return f"{name} / {account_id}"
    if name:
        return name
    if account_id:
        return account_id
    return "未知账户"


def localize_health_status(status: str | None) -> str:
    return {
        "green": "健康",
        "yellow": "关注",
        "red": "风险",
    }.get((status or "").lower(), status or "-")


def localize_alert_status(status: str | None) -> str:
    return {
        "sent": "已发送",
        "failed": "发送失败",
        "skipped": "已跳过",
    }.get((status or "").lower(), status or "-")


def localize_severity(severity: str | None) -> str:
    return {
        "low": "低",
        "medium": "中",
        "high": "高",
    }.get((severity or "").lower(), severity or "-")


def localize_capture_status(status: str | None) -> str:
    return {
        "ok": "正常",
        "success": "成功",
        "failed": "失败",
        "error": "错误",
    }.get((status or "").lower(), status or "-")


def render_badge(
    label: str,
    *,
    tone: str = "neutral",
    class_name: str = "",
    attrs: dict[str, object] | None = None,
) -> str:
    classes = _join_classes("badge", f"badge-{tone}", class_name)
    return f'<span class="{classes}"{_render_attrs(attrs)}>{html.escape(label)}</span>'


def render_button(
    label: str,
    *,
    href: str | None = None,
    variant: str = "secondary",
    button_type: str = "button",
    class_name: str = "",
    attrs: dict[str, object] | None = None,
) -> str:
    classes = _join_classes("button", f"button-{variant}", class_name)
    if href is not None:
        merged_attrs = {"href": href}
        if attrs:
            merged_attrs.update(attrs)
        return f'<a class="{classes}"{_render_attrs(merged_attrs)}>{html.escape(label)}</a>'
    merged_attrs = {}
    if attrs:
        merged_attrs.update(attrs)
    return f'<button type="{html.escape(button_type, quote=True)}" class="{classes}"{_render_attrs(merged_attrs)}>{html.escape(label)}</button>'


def render_card(
    content: str,
    *,
    title: str | None = None,
    subtitle: str | None = None,
    header_actions_html: str = "",
    tag: str = "section",
    class_name: str = "",
    body_class_name: str = "",
    attrs: dict[str, object] | None = None,
) -> str:
    header_html = ""
    if title or subtitle or header_actions_html:
        title_markup = f'<h2 class="card-title">{html.escape(title)}</h2>' if title else ""
        subtitle_markup = f'<p class="card-subtitle">{html.escape(subtitle)}</p>' if subtitle else ""
        title_html = (
            '<div class="card-title-group">'
            f"{title_markup}"
            f"{subtitle_markup}"
            "</div>"
        )
        header_html = f'<div class="card-header">{title_html}{header_actions_html}</div>'
    classes = _join_classes("card", class_name)
    body_classes = _join_classes("card-body", body_class_name)
    return f"<{tag} class=\"{classes}\"{_render_attrs(attrs)}>{header_html}<div class=\"{body_classes}\">{content}</div></{tag}>"


def render_page_header(
    *,
    eyebrow: str,
    title: str,
    description: str,
    meta_html: str = "",
    actions_html: str = "",
    aside_html: str = "",
) -> str:
    meta_block = f'<div class="page-header__meta">{meta_html}</div>' if meta_html else ""
    actions_block = f'<div class="page-header__actions">{actions_html}</div>' if actions_html else ""
    aside_block = f'<div class="page-header__aside">{aside_html}</div>' if aside_html else ""
    return f"""
    <section class="page-header">
      <div class="page-header__layout">
        <div class="page-header__content">
          <div class="page-header__eyebrow">{html.escape(eyebrow)}</div>
          <h1 class="page-header__title">{html.escape(title)}</h1>
          <p class="page-header__description">{html.escape(description)}</p>
          {meta_block}
          {actions_block}
        </div>
        {aside_block}
      </div>
    </section>
    """


def render_app_shell(content: str) -> str:
    return f'<main class="app-shell">{content}</main>'


def build_chip(label: str, tone: str) -> str:
    badge_tone = BADGE_TONE_MAP.get(tone, "neutral")
    return render_badge(label, tone=badge_tone, class_name="chip")


def build_trend_chart(history: list[dict]) -> str:
    if len(history) < 2:
        return '<div class="empty">采样点不足，暂时无法生成趋势图。</div>'

    width, height = 920, 260
    left, right, top, bottom = 48, 18, 16, 34
    inner_w = width - left - right
    inner_h = height - top - bottom
    spend_values = [float(item.get("current_spend") or 0) for item in history]
    delta_values = [float(item.get("increase_amount") or 0) for item in history]
    max_value = max(spend_values + delta_values + [1.0])

    def to_x(index: int) -> float:
        return left + (inner_w * index / max(1, len(history) - 1))

    def to_y(value: float) -> float:
        return top + inner_h - (value / max_value) * inner_h

    spend_points = " ".join(f"{to_x(i):.1f},{to_y(v):.1f}" for i, v in enumerate(spend_values))
    delta_points = " ".join(f"{to_x(i):.1f},{to_y(v):.1f}" for i, v in enumerate(delta_values))
    labels = []
    step = max(1, len(history) // 6)
    for index in range(0, len(history), step):
        x = to_x(index)
        label = datetime.fromtimestamp(history[index]["captured_at"] / 1000).strftime("%H:%M")
        labels.append(f'<text x="{x:.1f}" y="{height - 8}" fill="var(--color-axis)" font-size="11" text-anchor="middle">{html.escape(label)}</text>')
    return f"""
    <div class="chart">
      <svg viewBox="0 0 {width} {height}" class="trend" role="img" aria-label="实例趋势图">
        <rect x="0" y="0" width="{width}" height="{height}" rx="20" fill="var(--color-chart-bg)"></rect>
        <polyline points="{spend_points}" fill="none" stroke="var(--color-chart-1)" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"></polyline>
        <polyline points="{delta_points}" fill="none" stroke="var(--color-chart-2)" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"></polyline>
        {''.join(labels)}
      </svg>
      <div class="legend"><span><i class="dot teal"></i>当前总消耗</span><span><i class="dot blue"></i>窗口增量</span></div>
    </div>
    """


def build_dashboard_bar_chart(items: list[tuple[str, int | float, str]], aria_label: str) -> str:
    if not items:
        return '<div class="empty">暂无可用数据。</div>'

    width, height = 460, 220
    left, right, top, bottom = 28, 18, 18, 34
    inner_w = width - left - right
    inner_h = height - top - bottom
    max_value = max(float(value) for _, value, _ in items) or 1.0
    slot = inner_w / max(len(items), 1)
    bar_w = min(54, slot * 0.56)
    rects: list[str] = []
    labels: list[str] = []
    values: list[str] = []

    for index, (label, value, color) in enumerate(items):
        x = left + index * slot + (slot - bar_w) / 2
        scaled_h = 6 if float(value) <= 0 else max(14.0, inner_h * (float(value) / max_value))
        y = top + inner_h - scaled_h
        rects.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{scaled_h:.1f}" rx="12" fill="{color}"></rect>'
        )
        values.append(
            f'<text x="{x + bar_w / 2:.1f}" y="{max(y - 8, top):.1f}" fill="var(--color-text-primary)" font-size="12" text-anchor="middle">{html.escape(str(int(value) if float(value).is_integer() else value))}</text>'
        )
        labels.append(
            f'<text x="{x + bar_w / 2:.1f}" y="{height - 10}" fill="var(--color-text-secondary)" font-size="11" text-anchor="middle">{html.escape(compact_text(label, 12))}</text>'
        )

    return f"""
    <div class="dashboard-chart">
      <svg viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(aria_label)}" class="trend">
        <rect x="0" y="0" width="{width}" height="{height}" rx="18" fill="var(--color-bg-elevated)"></rect>
        {''.join(rects)}
        {''.join(values)}
        {''.join(labels)}
      </svg>
    </div>
    """


def build_shell(title: str, body: str, *, include_filter_restore: bool = False) -> str:
    filter_restore = (
        """
      var form = document.querySelector('form[action="/admin/alerts"]');
      if (form && !(window.location.search && window.location.search.length > 1)) {
        try {
          var saved = JSON.parse(localStorage.getItem("adbudget-alert-filters") || "{}");
          ["account_keyword","send_status","alert_kind","date_from","date_to"].forEach(function(name){
            var field = form.querySelector('[name="' + name + '"]');
            if (field && saved[name]) field.value = saved[name];
          });
        } catch (_error) {}
        form.addEventListener("submit", function(){
          var payload = {};
          ["account_keyword","send_status","alert_kind","date_from","date_to"].forEach(function(name){
            var field = form.querySelector('[name="' + name + '"]');
            payload[name] = field ? field.value : "";
          });
          localStorage.setItem("adbudget-alert-filters", JSON.stringify(payload));
        });
      }
    """
        if include_filter_restore
        else ""
    )
    return f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
      <meta charset="UTF-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1.0" />
      <title>{html.escape(title)}</title>
      <script>
      (function(){{
        var setting = localStorage.getItem("{THEME_KEY}") || "system";
        var theme = setting === "system" ? (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light") : setting;
        document.documentElement.dataset.themeSetting = setting;
        document.documentElement.dataset.theme = theme;
      }})();
      </script>
      <style>{FOUNDATION_CSS}</style>
    </head>
    <body><div class="app-shell">{body}</div>
      <script>
      (function(){{
        function setTheme(setting){{
          var theme = setting === "system" ? (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light") : setting;
          document.documentElement.dataset.themeSetting = setting;
          document.documentElement.dataset.theme = theme;
          document.querySelectorAll("[data-theme-choice]").forEach(function(btn){{btn.classList.toggle("active", btn.getAttribute("data-theme-choice") === setting);}});
        }}
        setTheme(localStorage.getItem("{THEME_KEY}") || "system");
        document.addEventListener("click", function(event){{
          var themeBtn = event.target.closest("[data-theme-choice]");
          if (themeBtn) {{
            var setting = themeBtn.getAttribute("data-theme-choice") || "system";
            localStorage.setItem("{THEME_KEY}", setting);
            setTheme(setting);
            return;
          }}
          var refreshBtn = event.target.closest("[data-refresh-page]");
          if (refreshBtn) {{ window.location.reload(); return; }}
          var deleteBtn = event.target.closest("[data-delete-instance]");
          if (deleteBtn) {{
            event.preventDefault(); event.stopPropagation();
            var instanceId = deleteBtn.getAttribute("data-delete-instance");
            if (!instanceId || !window.confirm("删除后如果脚本再次上报，该实例会重新出现。确认删除该实例？")) return;
            fetch("/admin/api/instances/" + encodeURIComponent(instanceId), {{method:"DELETE"}}).then(function(resp){{ if (!resp.ok) throw new Error("delete"); window.location.href="/admin"; }}).catch(function(){{ window.alert("删除实例失败，请稍后重试。"); }});
            return;
          }}
          var editBtn = event.target.closest("[data-edit-instance]");
          if (editBtn) {{
            event.preventDefault(); event.stopPropagation();
            var instanceId = editBtn.getAttribute("data-edit-instance");
            var currentAlias = editBtn.getAttribute("data-current-alias") || "";
            var currentRemarks = editBtn.getAttribute("data-current-remarks") || "";
            var alias = window.prompt("设置实例别名", currentAlias);
            if (alias === null) return;
            var remarks = window.prompt("设置实例备注", currentRemarks);
            if (remarks === null) return;
            fetch("/admin/api/instances/" + encodeURIComponent(instanceId) + "/meta", {{method:"POST", headers:{{"Content-Type":"application/json"}}, body:JSON.stringify({{alias:alias, remarks:remarks}})}}).then(function(resp){{ if (!resp.ok) throw new Error("meta"); window.location.reload(); }}).catch(function(){{ window.alert("保存备注失败，请稍后重试。"); }});
            return;
          }}
        }});
        var form = document.querySelector("[data-instance-meta-form]");
        if (form) {{
          form.addEventListener("submit", function(event){{
            event.preventDefault();
            var status = form.querySelector("[data-form-status]");
            fetch("/admin/api/instances/" + encodeURIComponent(form.getAttribute("data-instance-meta-form")) + "/meta", {{method:"POST", headers:{{"Content-Type":"application/json"}}, body:JSON.stringify({{alias:form.elements.alias.value, remarks:form.elements.remarks.value}})}}).then(function(resp){{ if (!resp.ok) throw new Error("meta"); if (status) status.textContent = "备注已保存。"; }}).catch(function(){{ if (status) status.textContent = "备注保存失败，请稍后重试。"; }});
          }});
        }}
        {filter_restore}
      }})();
      </script>
    </body>
    </html>
    """
def build_admin_dashboard_html(summary: dict, instances: list[dict], alerts: list[dict], db_path: Path) -> str:
    status_tone = {"green": "green", "yellow": "yellow", "red": "red"}
    summary_cards = [
        ("在线实例", str(summary["total_instances"]), "已接入的浏览器会话", "var(--color-accent)", "实例", "rgba(15,118,110,.10)"),
        ("健康实例", str(summary["green_instances"]), f"{summary['yellow_instances']} 个需要关注", "var(--color-success)", "健康", "rgba(22,101,52,.10)"),
        ("分析记录", str(summary["total_analyses"]), "已存储的模型或规则摘要", "var(--color-warning)", "分析", "rgba(234,88,12,.10)"),
        ("告警记录", str(summary["total_alerts"]), "最近的通知投递记录", "#c026d3", "告警", "rgba(192,38,211,.10)"),
    ]
    kpi_html = "".join(
        render_card(
            (
                f'<div class="dashboard-kpi__top"><div class="dashboard-kpi__label">{html.escape(label)}</div><span class="dashboard-kpi__icon" style="background:{icon_bg};color:{color};">{html.escape(icon)}</span></div>'
                f'<div class="dashboard-kpi__value" style="color:{color};">{html.escape(value)}</div>'
                f'<div class="dashboard-kpi__meta">{html.escape(meta)}</div>'
            ),
            class_name="dashboard-kpi",
        )
        for label, value, meta, color, icon, icon_bg in summary_cards
    )

    health_chart = build_dashboard_bar_chart(
        [
            ("健康", int(summary.get("green_instances") or 0), "var(--color-success)"),
            ("关注", int(summary.get("yellow_instances") or 0), "var(--color-warning)"),
            ("风险", int(summary.get("red_instances") or 0), "var(--color-danger)"),
        ],
        "实例健康分布",
    )

    status_counts = {"sent": 0, "failed": 0, "skipped": 0}
    for alert in alerts:
        key = (alert.get("send_status") or "").lower()
        if key in status_counts:
            status_counts[key] += 1

    alert_chart = build_dashboard_bar_chart(
        [
            ("已发送", status_counts["sent"], "var(--color-success)"),
            ("发送失败", status_counts["failed"], "var(--color-danger)"),
            ("已跳过", status_counts["skipped"], "var(--color-warning)"),
        ],
        "告警发送状态",
    )

    charts_html = "".join(
        [
            render_card(
                health_chart
                + (
                    '<div class="dashboard-chart__legend">'
                    '<span class="dashboard-chart__legend-item"><span class="dashboard-chart__legend-swatch" style="background:var(--color-success)"></span>健康</span>'
                    '<span class="dashboard-chart__legend-item"><span class="dashboard-chart__legend-swatch" style="background:var(--color-warning)"></span>关注</span>'
                    '<span class="dashboard-chart__legend-item"><span class="dashboard-chart__legend-swatch" style="background:var(--color-danger)"></span>风险</span>'
                    '</div>'
                ),
                title="实例健康概览",
                subtitle="当前实例状态分布",
                class_name="dashboard-chart-card",
            ),
            render_card(
                alert_chart + '<div class="dashboard-mini-note">投递状态基于网关中已存储的最近告警记录。</div>',
                title="告警投递概览",
                subtitle="最近通知结果",
                class_name="dashboard-chart-card",
            ),
        ]
    )

    instance_rows = []
    for item in instances[:8]:
        instance_id = item.get("instance_id") or ""
        primary = item.get("alias") or format_account_identity(item.get("account_name"), item.get("account_id"))
        secondary = item.get("remarks") or format_account_identity(item.get("account_name"), item.get("account_id"))
        health = localize_health_status(item.get("health_status"))
        health_chip = build_chip(health, status_tone.get(item.get("health_status"), "slate"))
        instance_rows.append(
            f"""
            <tr>
              <td>
                <div class="dashboard-table__primary">{html.escape(primary)}</div>
                <div class="dashboard-table__secondary">{html.escape(compact_text(secondary, 52))}</div>
              </td>
              <td>{health_chip}</td>
              <td>{html.escape(format_time(item.get("last_heartbeat_at")))}</td>
              <td>{html.escape(localize_capture_status(item.get("last_capture_status")))}</td>
              <td><a class="dashboard-table__link" href="/admin/instances/{quote(instance_id, safe='')}">查看</a></td>
            </tr>
            """
        )
    instance_table_html = "".join(instance_rows) or '<tr><td colspan="5" class="empty">暂时还没有实例上报。</td></tr>'

    alert_rows = []
    for alert in alerts[:8]:
        tone = {"sent": "green", "failed": "red", "skipped": "yellow"}.get(alert.get("send_status") or "", "slate")
        alert_rows.append(
            f"""
            <tr>
              <td>
                <div class="dashboard-table__primary">{html.escape(alert.get("title") or "-")}</div>
                <div class="dashboard-table__secondary">{html.escape(format_account_identity(alert.get("account_name"), alert.get("account_id")))}</div>
              </td>
              <td>{build_chip(localize_alert_status(alert.get("send_status")), tone)}</td>
              <td>{html.escape(alert.get("alert_kind") or "-")}</td>
              <td>{html.escape(format_time(alert.get("triggered_at")))}</td>
            </tr>
            """
        )
    alert_table_html = "".join(alert_rows) or '<tr><td colspan="4" class="empty">暂时还没有告警记录。</td></tr>'

    tables_html = "".join(
        [
            render_card(
                '<div class="table-wrap"><table class="dashboard-table"><thead><tr><th>实例</th><th>状态</th><th>最近心跳</th><th>采样状态</th><th>操作</th></tr></thead><tbody>'
                + instance_table_html
                + '</tbody></table></div>',
                title="实例列表",
                subtitle="按健康状态优先排序的监控目标",
                class_name="dashboard-table-card",
                header_actions_html=render_badge("按健康度排序", tone="accent"),
            ),
            render_card(
                '<div class="table-wrap"><table class="dashboard-table"><thead><tr><th>告警</th><th>发送状态</th><th>类型</th><th>触发时间</th></tr></thead><tbody>'
                + alert_table_html
                + '</tbody></table></div>',
                title="告警列表",
                subtitle="最近的网关投递记录",
                class_name="dashboard-table-card",
                header_actions_html=render_button("查看告警", href="/admin/alerts"),
            ),
        ]
    )

    latest_heartbeat = format_time(summary.get("latest_heartbeat_at"))
    latest_capture = format_time(summary.get("latest_capture_at"))
    sidebar_meta = render_card(
        (
            f'<div class="dashboard-mini-note">数据库：{html.escape(str(db_path))}</div>'
            f'<div class="dashboard-mini-note">最近心跳：{html.escape(latest_heartbeat)}</div>'
            f'<div class="dashboard-mini-note">最近采样：{html.escape(latest_capture)}</div>'
        ),
        title="系统状态",
        subtitle="网关快照",
        class_name="dashboard-sidebar-card",
    )
    toolbar_actions = (
        '<input class="dashboard-search" type="search" placeholder="搜索实例、告警、账号" aria-label="搜索总览" />'
        + '<button type="button" class="dashboard-toolbar__icon-btn" data-refresh-page aria-label="刷新总览">刷新</button>'
        + '<a href="/admin/alerts" class="dashboard-toolbar__icon-btn" aria-label="打开告警页">告警</a>'
        + '<div class="dashboard-profile"><span class="dashboard-profile__avatar">管理</span><span class="dashboard-profile__meta"><span class="dashboard-profile__name">管理员</span><span class="dashboard-profile__role">监控负责人</span></span></div>'
    )
    body = f"""
    <style>{DASHBOARD_CSS}</style>
    <div class="dashboard-layout">
      <aside class="dashboard-sidebar">
        <div class="dashboard-sidebar__inner">
          <div class="dashboard-brand">
            <div class="dashboard-brand__eyebrow">AdBudgetSentry</div>
            <div class="dashboard-brand__title">管理后台</div>
            <div class="dashboard-brand__copy">实例、告警和分析结果的统一监控入口。</div>
          </div>
          <nav class="dashboard-nav">
            <div class="dashboard-nav__label">导航</div>
            <a class="dashboard-nav__link is-active" href="/admin"><span class="dashboard-nav__link-main"><span class="dashboard-nav__icon">总览</span><span>总览</span></span>{render_badge("在线", tone="success")}</a>
            <a class="dashboard-nav__link" href="/admin/alerts"><span class="dashboard-nav__link-main"><span class="dashboard-nav__icon">告警</span><span>告警</span></span>{render_badge(f"{len(alerts)} 条", tone="neutral")}</a>
          </nav>
          {sidebar_meta}
          <div class="dashboard-sidebar-footer">先在总览页判断健康状态，再进入告警页或单个实例页继续排查。</div>
        </div>
      </aside>
      <div class="dashboard-main">
        <header class="dashboard-toolbar">
          <div class="dashboard-toolbar__intro">
            <div class="dashboard-toolbar__eyebrow">总览</div>
            <div class="dashboard-toolbar__title">监控总览</div>
            <div class="dashboard-toolbar__copy">以实例健康、告警投递和待处理项目为中心的监控面板。</div>
          </div>
          <div class="dashboard-toolbar__actions">
            {toolbar_actions}
            <div class="theme-toggle" aria-label="主题模式">
              <button type="button" data-theme-choice="system">跟随系统</button>
              <button type="button" data-theme-choice="light">日间</button>
              <button type="button" data-theme-choice="dark">夜间</button>
            </div>
          </div>
        </header>
        <main class="dashboard-content">
          <section class="dashboard-kpi-grid">{kpi_html}</section>
          <section class="dashboard-chart-grid">{charts_html}</section>
          <section class="dashboard-table-grid">{tables_html}</section>
        </main>
      </div>
    </div>
    """
    return build_shell("监控总览 - AdBudgetSentry", body)
def build_instance_detail_html(detail: dict, db_path: Path) -> str:
    history = detail.get("capture_history") or []
    chart_html = build_trend_chart(history)
    health_tone = {"green": "green", "yellow": "yellow", "red": "red"}.get(detail.get("health_status"), "slate")
    spotlight = "".join(
        [
            f'<article class="spotlight"><div class="meta-label">当前总消耗</div><div class="value" style="color:#0f766e;">{html.escape(format_money(detail.get("latest_current_spend")))}</div></article>',
            f'<article class="spotlight"><div class="meta-label">窗口增量</div><div class="value" style="color:#1d4ed8;">{html.escape(format_money(detail.get("latest_increase_amount")))}</div></article>',
        ]
    )
    info_cards = [
        ("账户", format_account_identity(detail.get("account_name"), detail.get("account_id"))),
        ("实例 ID", detail.get("instance_id") or "-"),
        ("页面类型", detail.get("page_type") or "-"),
        ("脚本版本", detail.get("script_version") or "-"),
        ("最近心跳", format_time(detail.get("last_heartbeat_at"))),
        ("最近采样", format_time(detail.get("last_capture_at"))),
        ("最近错误", compact_text(detail.get("last_error"), 90)),
        ("采样状态", localize_capture_status(detail.get("last_capture_status"))),
    ]
    info_html = "".join(
        f'<div class="detail"><div class="meta-label">{html.escape(label)}</div><div style="margin-top:8px;line-height:1.65;word-break:break-word;">{html.escape(value)}</div></div>'
        for label, value in info_cards
    )
    history_rows = "".join(
        f"<tr><td>{html.escape(format_time(item.get('captured_at')))}</td><td>{html.escape(format_money(item.get('current_spend')))}</td><td>{html.escape(format_money(item.get('increase_amount')))}</td><td>{html.escape(format_money(item.get('baseline_spend')))}</td><td>{html.escape(str(item.get('compare_interval_min') or '-'))}</td><td>{html.escape(str(item.get('row_count') or '-'))}</td></tr>"
        for item in reversed(history[-20:])
    ) or '<tr><td colspan="6" class="empty">暂无采样历史。</td></tr>'
    analysis_html = "".join(
        f'<article class="stack"><div class="row"><div><div class="name">{html.escape(item.get("summary") or "-")}</div><div class="sub">{html.escape(format_time(item.get("created_at")))} / {html.escape(item.get("provider") or "-")} / {html.escape(item.get("model") or "-")}</div></div>{build_chip(localize_severity(item.get("severity")), {"low":"teal","medium":"yellow","high":"red"}.get(item.get("severity") or "", "slate"))}</div><div class="preview">{html.escape(compact_text(item.get("raw_text"), 260))}</div></article>'
        for item in detail.get("recent_analyses", [])
    ) or '<div class="empty">最近还没有分析记录。</div>'
    alerts_html = "".join(
        f'<article class="stack"><div class="row"><div><div class="name">{html.escape(item.get("title") or "-")}</div><div class="sub">{html.escape(format_time(item.get("triggered_at")))} / {html.escape(item.get("channel") or "-")} / {html.escape(item.get("alert_kind") or "-")}</div></div>{build_chip(localize_alert_status(item.get("send_status")), {"sent":"green","failed":"red","skipped":"yellow"}.get(item.get("send_status") or "", "slate"))}</div><div class="preview">{html.escape(compact_text(item.get("content_preview"), 220))}</div></article>'
        for item in detail.get("recent_alerts", [])
    ) or '<div class="empty">最近没有告警记录。</div>'
    errors_html = "".join(
        f'<article class="stack"><div class="row"><div><div class="name">{html.escape(item.get("error_type") or "-")}</div><div class="sub">{html.escape(format_time(item.get("occurred_at")))}</div></div>{build_chip("错误", "red")}</div><div class="preview">{html.escape(item.get("error_message") or "-")}</div></article>'
        for item in detail.get("recent_errors", [])
    ) or '<div class="empty">最近没有错误记录。</div>'
    body = f"""
    <main class="shell">
      <section class="hero">
        <div class="hero-grid">
          <div>
            <div class="eyebrow">实例详情</div>
            <h1>{html.escape(detail.get("alias") or format_account_identity(detail.get("account_name"), detail.get("account_id")))}</h1>
            <p>实例详情页优先展示当前关键指标，其次再展开趋势、分析、告警和错误，便于快速判断问题是在采样、分析还是通知链路。</p>
            <div class="hero-meta">
              <div class="chip" style="background:rgba(255,255,255,.14);color:#fff;">实例 {html.escape(detail.get("instance_id") or "-")}</div>
              <div class="chip" style="background:rgba(255,255,255,.14);color:#fff;">状态 {html.escape(localize_health_status(detail.get("health_status")))}</div>
              <div class="chip" style="background:rgba(255,255,255,.14);color:#fff;">数据库 {html.escape(str(db_path))}</div>
            </div>
          </div>
          <div class="stack">
            <div class="hero-actions"><a class="btn-light" href="/admin">返回总览</a><button type="button" class="btn-light" data-refresh-page>刷新页面</button></div>
            <div class="hero-actions" style="margin-top:10px;"><div class="theme-toggle"><button type="button" data-theme-choice="system">跟随系统</button><button type="button" data-theme-choice="light">日间</button><button type="button" data-theme-choice="dark">夜间</button></div><button type="button" class="btn-danger" data-delete-instance="{html.escape(detail.get('instance_id') or '')}">删除实例</button></div>
            <div class="status" style="margin-top:10px;">{build_chip(localize_health_status(detail.get("health_status")), health_tone)} 最近采样 {html.escape(format_time(detail.get("last_capture_at")))}</div>
          </div>
        </div>
      </section>
      <section class="spotlights">{spotlight}</section>
      <section class="detail-grid">{info_html}</section>
      <section class="panel">
        <div class="head"><div><h2 class="title">实例备注</h2><div class="subtitle">别名和备注只在后台监控系统中维护，不会同步到油猴脚本。</div></div></div>
        <form data-instance-meta-form="{html.escape(detail.get('instance_id') or '')}">
          <div class="field"><label for="alias">实例别名</label><input id="alias" name="alias" value="{html.escape(detail.get('alias') or '')}" placeholder="例如：投流主账号 01" /></div>
          <div class="field" style="margin-top:12px;"><label for="remarks">实例备注</label><textarea id="remarks" name="remarks" placeholder="填写负责人、用途和补充说明。">{html.escape(detail.get('remarks') or '')}</textarea></div>
          <div class="hero-actions" style="margin-top:12px;"><button type="submit" class="btn">保存备注</button><div class="status" data-form-status>删除实例只清理后台记录，不会阻止新的上报重新生成实例。</div></div>
        </form>
      </section>
      <section class="split">
        <section class="panel"><div class="head"><div><h2 class="title">最近采样趋势</h2><div class="subtitle">绿色曲线表示当前总消耗，蓝色曲线表示窗口增量。</div></div>{build_chip(f"{len(history)} 个点", "blue")}</div>{chart_html}</section>
        <section class="panel"><div class="head"><div><h2 class="title">最近分析</h2><div class="subtitle">优先看模型或规则最近给出的摘要和严重等级。</div></div>{build_chip(f"{len(detail.get('recent_analyses', []))} 条", "teal")}</div><div class="stack-list">{analysis_html}</div></section>
      </section>
      <section class="panel">
        <div class="head"><div><h2 class="title">最近采样明细</h2><div class="subtitle">保留最近 20 条采样结果，用于和趋势图交叉核对。</div></div>{build_chip("最近 20 条", "slate")}</div>
        <div class="table-wrap"><table><thead><tr><th>采样时间</th><th>当前总消耗</th><th>窗口增量</th><th>基线消耗</th><th>比较窗口</th><th>行数</th></tr></thead><tbody>{history_rows}</tbody></table></div>
      </section>
      <section class="split">
        <section class="panel"><div class="head"><div><h2 class="title">最近告警</h2><div class="subtitle">确认该实例是否真正触发并发出了通知。</div></div>{build_chip(f"{len(detail.get('recent_alerts', []))} 条", "yellow")}</div><div class="stack-list">{alerts_html}</div></section>
        <section class="panel"><div class="head"><div><h2 class="title">最近错误</h2><div class="subtitle">如果这里连续报错，优先检查页面结构变化和采样选择器。</div></div>{build_chip(f"{len(detail.get('recent_errors', []))} 条", "red")}</div><div class="stack-list">{errors_html}</div></section>
      </section>
    </main>
    """
    return build_shell("实例详情页 - AdBudgetSentry", body)


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
    account_counts: dict[str, int] = {}
    kind_counts: dict[str, int] = {}
    for alert in alerts:
        label = format_account_identity(alert.get("account_name"), alert.get("account_id"))
        account_counts[label] = account_counts.get(label, 0) + 1
        kind = alert.get("alert_kind") or "unknown"
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
    top_accounts_html = "".join(f'<div class="pill">{html.escape(label)} {count} 条</div>' for label, count in sorted(account_counts.items(), key=lambda item: item[1], reverse=True)[:6]) or '<div class="pill">暂无账户统计</div>'
    kind_html = "".join(f'<div class="pill">{html.escape(label)} {count} 条</div>' for label, count in sorted(kind_counts.items(), key=lambda item: item[1], reverse=True)[:6]) or '<div class="pill">暂无类型统计</div>'
    query_parts = [f"{key}={quote(str(value), safe='')}" for key, value in [("account_keyword", account_keyword), ("send_status", send_status), ("alert_kind", alert_kind), ("date_from", date_from), ("date_to", date_to)] if value]
    export_href = "/admin/alerts/export.csv" + (f"?{'&'.join(query_parts)}" if query_parts else "")
    alert_cards = []
    for alert in alerts:
        tone = {"sent": "green", "failed": "red", "skipped": "yellow"}.get(alert.get("send_status") or "", "slate")
        meta = [f"触发时间 {format_time(alert.get('triggered_at'))}", f"渠道 {alert.get('channel') or '-'}", f"类型 {alert.get('alert_kind') or '-'}"]
        alert_cards.append(f'<article class="alert"><div class="row"><div><div class="name">{html.escape(alert.get("title") or "-")}</div><div class="sub">{html.escape(format_account_identity(alert.get("account_name"), alert.get("account_id")))}</div></div>{build_chip(localize_alert_status(alert.get("send_status")), tone)}</div><div class="sub">{html.escape(" / ".join(meta))}</div><div class="preview">{html.escape(alert.get("content_preview") or "-")}</div></article>')
    alerts_html = "".join(alert_cards) or '<div class="empty">当前筛选条件下没有告警记录。</div>'
    body = f"""
    <main class="shell">
      <section class="hero">
        <div class="hero-grid">
          <div>
            <div class="eyebrow">告警中心</div>
            <h1>按实例、账号、类型和时间回看告警链路</h1>
            <p>这个页面承接历史告警的筛选、回查和导出。主题行为与后台其他页面保持一致，手机端同样优先保证可读性。</p>
            <div class="hero-meta"><div class="chip" style="background:rgba(255,255,255,.14);color:#fff;">数据库 {html.escape(str(db_path))}</div><div class="chip" style="background:rgba(255,255,255,.14);color:#fff;">当前结果 {len(alerts)} 条</div></div>
          </div>
          <div class="stack">
            <div class="hero-actions"><a class="btn-light" href="/admin">返回总览</a><a class="btn-light" href="{html.escape(export_href)}">导出 CSV</a></div>
            <div class="hero-actions" style="margin-top:10px;"><div class="theme-toggle"><button type="button" data-theme-choice="system">跟随系统</button><button type="button" data-theme-choice="light">日间</button><button type="button" data-theme-choice="dark">夜间</button></div><button type="button" class="btn-light" data-refresh-page>刷新页面</button></div>
          </div>
        </div>
      </section>
      <section class="panel">
        <div class="head"><div><h2 class="title">筛选条件</h2><div class="subtitle">支持账号关键词、发送状态、告警类型和日期范围筛选。</div></div></div>
        <form action="/admin/alerts" method="get">
          <div class="filters">
            <div class="field"><label for="account_keyword">账号关键词</label><input id="account_keyword" name="account_keyword" value="{html.escape(account_keyword)}" placeholder="账号名、账号 ID、实例 ID" /></div>
            <div class="field"><label for="send_status">发送状态</label><select id="send_status" name="send_status"><option value="">全部</option><option value="sent" {"selected" if send_status == "sent" else ""}>已发送</option><option value="failed" {"selected" if send_status == "failed" else ""}>发送失败</option><option value="skipped" {"selected" if send_status == "skipped" else ""}>已跳过</option></select></div>
            <div class="field"><label for="alert_kind">告警类型</label><input id="alert_kind" name="alert_kind" value="{html.escape(alert_kind)}" placeholder="例如：threshold / offline" /></div>
            <div class="field"><label for="date_from">开始日期</label><input id="date_from" type="date" name="date_from" value="{html.escape(date_from)}" /></div>
            <div class="field"><label for="date_to">结束日期</label><input id="date_to" type="date" name="date_to" value="{html.escape(date_to)}" /></div>
          </div>
          <div class="hero-actions" style="margin-top:14px;"><button type="submit" class="btn">应用筛选</button><a class="btn" href="/admin/alerts">重置</a></div>
        </form>
      </section>
      <section class="metrics"><article class="summary-box"><h3>按账号聚合</h3><div class="summary-row">{top_accounts_html}</div></article><article class="summary-box"><h3>按告警类型聚合</h3><div class="summary-row">{kind_html}</div></article></section>
      <section class="panel"><div class="head"><div><h2 class="title">告警历史</h2><div class="subtitle">默认展示最近 500 条结果，方便在一个页面内完成回看与导出。</div></div>{build_chip(f"{len(alerts)} 条", "blue")}</div><div class="alerts">{alerts_html}</div></section>
    </main>
    """
    return build_shell("告警中心 - AdBudgetSentry", body, include_filter_restore=True)
