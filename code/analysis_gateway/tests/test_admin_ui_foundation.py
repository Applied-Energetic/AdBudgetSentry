from pathlib import Path
import unittest

from admin_ui import (
    build_admin_dashboard_html,
    build_alerts_page_html,
    build_instance_detail_html,
    render_badge,
    render_button,
    render_card,
    render_page_header,
)


class AdminUiFoundationTests(unittest.TestCase):
    def test_render_badge_uses_shared_badge_classes(self) -> None:
        badge = render_badge("Healthy", tone="success")

        self.assertIn('class="badge badge-success"', badge)
        self.assertIn(">Healthy<", badge)

    def test_render_button_supports_links_and_buttons(self) -> None:
        link = render_button("Open", href="/admin", variant="primary")
        button = render_button("Refresh", variant="secondary", attrs={"data-refresh-page": True})

        self.assertIn('<a class="button button-primary"', link)
        self.assertIn('href="/admin"', link)
        self.assertIn('<button type="button" class="button button-secondary"', button)
        self.assertIn("data-refresh-page", button)

    def test_render_card_wraps_content_with_shared_card_primitive(self) -> None:
        card = render_card("<p>Body</p>", title="Overview", subtitle="Stable")

        self.assertIn('class="card"', card)
        self.assertIn('class="card-header"', card)
        self.assertIn(">Overview<", card)
        self.assertIn(">Stable<", card)
        self.assertIn('class="card-body"', card)

    def test_render_page_header_uses_shared_page_header_structure(self) -> None:
        header = render_page_header(
            eyebrow="Monitor",
            title="Dashboard",
            description="Overview",
            meta_html="<span>Meta</span>",
            actions_html='<a href="/admin">Action</a>',
        )

        self.assertIn('class="page-header"', header)
        self.assertIn('class="page-header__eyebrow"', header)
        self.assertIn('class="page-header__title"', header)
        self.assertIn('class="page-header__meta"', header)
        self.assertIn('class="page-header__actions"', header)

    def test_dashboard_shell_includes_design_tokens_and_app_shell(self) -> None:
        html = build_admin_dashboard_html(
            {
                "total_instances": 1,
                "green_instances": 1,
                "yellow_instances": 0,
                "red_instances": 0,
                "total_analyses": 1,
                "total_alerts": 0,
                "latest_heartbeat_at": None,
                "latest_capture_at": None,
            },
            [],
            [],
            Path("app.db"),
        )

        self.assertIn("--color-bg-page", html)
        self.assertIn("--space-6", html)
        self.assertIn("--radius-lg", html)
        self.assertIn("--shadow-card", html)
        self.assertIn("--font-size-title-1", html)
        self.assertIn('class="app-shell"', html)

    def test_dashboard_uses_saas_admin_layout(self) -> None:
        html = build_admin_dashboard_html(
            {
                "total_instances": 3,
                "green_instances": 2,
                "yellow_instances": 1,
                "red_instances": 0,
                "total_analyses": 5,
                "total_alerts": 4,
                "latest_heartbeat_at": None,
                "latest_capture_at": None,
            },
            [
                {
                    "instance_id": "inst-1",
                    "alias": "Primary",
                    "remarks": "Important",
                    "account_name": "Account A",
                    "account_id": "A-1",
                    "health_status": "green",
                    "last_heartbeat_at": None,
                    "last_capture_at": None,
                    "last_capture_status": "ok",
                    "last_error": "",
                    "last_analysis_summary": "Stable",
                    "script_version": "1.0.0",
                }
            ],
            [
                {
                    "title": "Threshold Alert",
                    "account_name": "Account A",
                    "account_id": "A-1",
                    "send_status": "sent",
                    "triggered_at": None,
                    "channel": "mail",
                    "alert_kind": "threshold",
                    "content_preview": "Preview",
                }
            ],
            Path("app.db"),
        )

        self.assertIn('class="dashboard-layout"', html)
        self.assertIn('class="dashboard-sidebar"', html)
        self.assertIn('class="dashboard-toolbar"', html)
        self.assertIn('class="dashboard-kpi-grid"', html)
        self.assertIn('class="dashboard-chart-grid"', html)
        self.assertIn('class="dashboard-table-grid"', html)
        self.assertIn('class="dashboard-profile"', html)
        self.assertIn('class="dashboard-nav__icon"', html)
        self.assertIn("监控总览", html)
        self.assertIn("实例健康概览", html)
        self.assertIn("查看告警", html)

    def test_detail_and_alert_pages_do_not_render_replacement_characters(self) -> None:
        detail_html = build_instance_detail_html(
            {
                "instance_id": "inst-1",
                "alias": "主实例",
                "remarks": "负责人：小王",
                "account_name": "账号 A",
                "account_id": "A-1",
                "page_type": "campaign",
                "script_version": "1.0.0",
                "health_status": "green",
                "last_heartbeat_at": None,
                "last_capture_at": None,
                "last_error": "",
                "last_capture_status": "ok",
                "latest_current_spend": 123.45,
                "latest_increase_amount": 12.34,
                "capture_history": [],
                "recent_analyses": [],
                "recent_alerts": [],
                "recent_errors": [],
            },
            Path("app.db"),
        )
        alerts_html = build_alerts_page_html([], Path("app.db"))

        self.assertNotIn("\ufffd", detail_html)
        self.assertNotIn("\ufffd", alerts_html)
        self.assertIn("当前总消耗", detail_html)
        self.assertIn("填写负责人、用途和补充说明。", detail_html)
        self.assertIn("筛选条件", alerts_html)
        self.assertIn("按账号聚合", alerts_html)
        self.assertIn("已发送", alerts_html)


if __name__ == "__main__":
    unittest.main()
