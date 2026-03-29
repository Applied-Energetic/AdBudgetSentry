from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import app as gateway_app


class AdminSpaRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self._patchers = [
            patch.object(gateway_app, "ensure_database", lambda *_args, **_kwargs: None),
            patch.object(gateway_app, "health_monitor_loop", new=lambda: asyncio.sleep(0)),
        ]
        for patcher in self._patchers:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(self._patchers):
            patcher.stop()

    def _client(self) -> TestClient:
        return TestClient(gateway_app.app)

    def test_admin_routes_serve_spa_index_when_dist_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dist_dir = Path(tmp) / "dist"
            assets_dir = dist_dir / "assets"
            assets_dir.mkdir(parents=True)
            (dist_dir / "index.html").write_text(
                "<!doctype html><html><body>SPA READY</body></html>",
                encoding="utf-8",
            )
            (assets_dir / "main.js").write_text("console.log('spa');", encoding="utf-8")

            with patch.object(gateway_app, "get_admin_frontend_dist_dir", return_value=dist_dir), patch.object(
                gateway_app,
                "fetch_admin_summary",
                return_value={
                    "total_instances": 1,
                    "green_instances": 1,
                    "yellow_instances": 0,
                    "red_instances": 0,
                    "total_analyses": 1,
                    "total_alerts": 1,
                    "latest_heartbeat_at": None,
                    "latest_capture_at": None,
                },
            ), patch.object(gateway_app, "fetch_admin_instances", return_value=[]), patch.object(
                gateway_app,
                "fetch_admin_alerts",
                return_value=[],
            ):
                with self._client() as client:
                    for path in ["/admin", "/admin/alerts", "/admin/instances/inst-1"]:
                        response = client.get(path)
                        self.assertEqual(response.status_code, 200)
                        self.assertIn("SPA READY", response.text)
                        self.assertEqual(response.headers["content-type"].split(";")[0], "text/html")

                    asset_response = client.get("/assets/main.js")
                    self.assertEqual(asset_response.status_code, 200)
                    self.assertIn("console.log('spa');", asset_response.text)

                    api_response = client.get("/admin/api/alerts")
                    self.assertEqual(api_response.status_code, 200)
                    self.assertEqual(api_response.json(), [])

                    csv_response = client.get("/admin/alerts/export.csv")
                    self.assertEqual(csv_response.status_code, 200)
                    self.assertEqual(csv_response.headers["content-type"], "text/csv; charset=utf-8")
                    self.assertIn("adbudget-alerts.csv", csv_response.headers["content-disposition"])

    def test_admin_routes_fall_back_when_dist_is_missing(self) -> None:
        fallback_summary = {
            "total_instances": 1,
            "green_instances": 1,
            "yellow_instances": 0,
            "red_instances": 0,
            "total_analyses": 2,
            "total_alerts": 3,
            "latest_heartbeat_at": None,
            "latest_capture_at": None,
        }
        fallback_instances = [
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
        ]
        fallback_alerts = [
            {
                "id": 1,
                "instance_id": "inst-1",
                "account_name": "Account A",
                "account_id": "A-1",
                "alert_kind": "threshold",
                "send_status": "sent",
                "severity": "high",
                "anomaly_type": "threshold_breach",
                "channel": "mail",
                "delivery_provider": "pushplus",
                "triggered_at": None,
                "title": "Threshold Alert",
                "content_preview": "Preview",
                "provider_response": "{}",
            }
        ]
        fallback_detail = {
            "instance_id": "inst-1",
            "alias": "Primary",
            "remarks": "Important",
            "account_name": "Account A",
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
        }

        with tempfile.TemporaryDirectory() as tmp:
            dist_dir = Path(tmp) / "dist"
            dist_dir.mkdir(parents=True)

            with patch.object(gateway_app, "get_admin_frontend_dist_dir", return_value=dist_dir), patch.object(
                gateway_app,
                "fetch_admin_summary",
                return_value=fallback_summary,
            ), patch.object(gateway_app, "fetch_admin_instances", return_value=fallback_instances), patch.object(
                gateway_app,
                "fetch_admin_alerts",
                return_value=fallback_alerts,
            ), patch.object(gateway_app, "fetch_instance_detail", return_value=fallback_detail):
                with self._client() as client:
                    admin_response = client.get("/admin")
                    alerts_response = client.get("/admin/alerts")
                    detail_response = client.get("/admin/instances/inst-1")

                    self.assertEqual(admin_response.status_code, 200)
                    self.assertIn("dashboard-layout", admin_response.text)
                    self.assertNotIn("SPA READY", admin_response.text)

                    self.assertEqual(alerts_response.status_code, 200)
                    self.assertIn('action="/admin/alerts"', alerts_response.text)

                    self.assertEqual(detail_response.status_code, 200)
                    self.assertIn('data-instance-meta-form="inst-1"', detail_response.text)


if __name__ == "__main__":
    unittest.main()
