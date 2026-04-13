from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import app as gateway_app
from providers import ProviderResult


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
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
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
                    for path in ["/admin", "/admin/alerts", "/admin/settings", "/admin/instances/inst-1"]:
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

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
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
                    settings_response = client.get("/admin/settings")
                    detail_response = client.get("/admin/instances/inst-1")

                    self.assertEqual(admin_response.status_code, 200)
                    self.assertIn("dashboard-layout", admin_response.text)
                    self.assertNotIn("SPA READY", admin_response.text)

                    self.assertEqual(alerts_response.status_code, 200)
                    self.assertIn('action="/admin/alerts"', alerts_response.text)

                    self.assertEqual(settings_response.status_code, 200)
                    self.assertIn("PushPlus", settings_response.text)

                    self.assertEqual(detail_response.status_code, 200)
                    self.assertIn('data-instance-meta-form="inst-1"', detail_response.text)

    def test_settings_api_reads_and_updates_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            config_path.write_text(
                """
{
  "default_provider": "deepseek",
  "deepseek": {
    "base_url": "https://api.deepseek.com",
    "api_key": "old-deepseek-key",
    "model": "deepseek-chat"
  },
  "local": {
    "base_url": "http://127.0.0.1:11434/v1",
    "api_key": "EMPTY",
    "model": "qwen2.5:3b-instruct"
  },
  "alerts": {
    "enabled": true,
    "threshold_cooldown_minutes": 10,
    "offline_after_minutes": 10,
    "offline_cooldown_minutes": 60,
    "failure_cooldown_minutes": 30,
    "health_scan_interval_sec": 60,
    "failure_consecutive_count": 3,
    "pushplus": {
      "enabled": true,
      "token": "push-token-old",
      "channel": "mail",
      "option": ""
    }
  }
}
                """.strip(),
                encoding="utf-8",
            )

            with patch.object(gateway_app, "CONFIG_PATH", config_path), patch.object(
                gateway_app, "EXAMPLE_CONFIG_PATH", config_path
            ):
                with self._client() as client:
                    get_response = client.get("/admin/api/settings")
                    self.assertEqual(get_response.status_code, 200)
                    body = get_response.json()
                    self.assertTrue(body["pushplus"]["has_token"])
                    self.assertEqual(body["pushplus"]["token_preview"], "push...-old")
                    self.assertEqual(body["default_provider"], "deepseek")

                    post_response = client.post(
                        "/admin/api/settings",
                        json={
                            "default_provider": "local",
                            "deepseek": {
                                "base_url": "https://api.deepseek.com",
                                "model": "deepseek-chat",
                                "api_key": "",
                            },
                            "local": {
                                "base_url": "http://127.0.0.1:11434/v1",
                                "model": "qwen2.5:7b-instruct",
                                "api_key": "EMPTY",
                            },
                            "pushplus": {
                                "enabled": True,
                                "channel": "mail",
                                "channel_option": "receiver@example.com",
                                "token": "push-token-new",
                            },
                        },
                    )
                    self.assertEqual(post_response.status_code, 200)
                    updated = post_response.json()
                    self.assertEqual(updated["default_provider"], "local")
                    self.assertEqual(updated["local"]["model"], "qwen2.5:7b-instruct")
                    self.assertEqual(updated["pushplus"]["channel_option"], "receiver@example.com")
                    self.assertTrue(updated["pushplus"]["has_token"])

                    saved = gateway_app.load_config()
                    self.assertEqual(saved["default_provider"], "local")
                    self.assertEqual(saved["alerts"]["pushplus"]["token"], "push-token-new")
                    self.assertEqual(saved["local"]["model"], "qwen2.5:7b-instruct")

    def test_settings_test_endpoints_and_instance_chat(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            config_path = Path(tmp) / "config.json"
            db_path = Path(tmp) / "app.db"
            config_path.write_text(
                """
{
  "default_provider": "deepseek",
  "deepseek": {
    "base_url": "https://api.deepseek.com",
    "api_key": "deepseek-key",
    "model": "deepseek-chat"
  },
  "local": {
    "base_url": "http://127.0.0.1:11434/v1",
    "api_key": "EMPTY",
    "model": "qwen2.5:3b-instruct"
  },
  "alerts": {
    "enabled": true,
    "pushplus": {
      "enabled": true,
      "token": "push-token-old",
      "channel": "mail",
      "option": "receiver@example.com"
    }
  }
}
                """.strip(),
                encoding="utf-8",
            )
            gateway_app.ensure_database(db_path)
            gateway_app.save_ingest_event(
                db_path,
                {
                    "instance_id": "inst-chat",
                    "account_id": "acct-1",
                    "account_name": "测试账号",
                    "page_type": "financial",
                    "page_url": "https://example.test",
                    "script_version": "1.0.0",
                    "captured_at": 1_712_000_000_000,
                    "row_count": 3,
                    "metrics": {
                        "current_spend": 520.0,
                        "increase_amount": 42.0,
                        "compare_interval_min": 10,
                        "notify_threshold": 20.0,
                    },
                    "raw_context": {},
                },
            )

            async def fake_dispatch(*_args, **_kwargs):
                return {"ok": True, "provider_response": '{"code":200}'}

            async def fake_run_provider(_provider, prompt):
                if "连通性测试" in prompt:
                    return ProviderResult(provider="deepseek", model="deepseek-chat", text="连通成功")
                if "当前实例上下文" in prompt:
                    return ProviderResult(provider="deepseek", model="deepseek-chat", text=f"实例分析结果\n{prompt[:80]}")
                return ProviderResult(provider="deepseek", model="deepseek-chat", text="默认响应")

            with patch.object(gateway_app, "CONFIG_PATH", config_path), patch.object(
                gateway_app, "EXAMPLE_CONFIG_PATH", config_path
            ), patch.object(gateway_app, "DEFAULT_DB_PATH", db_path), patch.object(
                gateway_app, "dispatch_pushplus_alert", side_effect=fake_dispatch
            ), patch.object(gateway_app, "run_provider", side_effect=fake_run_provider):
                with self._client() as client:
                    push_response = client.post("/admin/api/settings/pushplus/test")
                    self.assertEqual(push_response.status_code, 200)
                    self.assertTrue(push_response.json()["ok"])

                    deepseek_response = client.post("/admin/api/settings/deepseek/test")
                    self.assertEqual(deepseek_response.status_code, 200)
                    self.assertEqual(deepseek_response.json()["provider"], "deepseek")
                    self.assertIn("连通成功", deepseek_response.json()["message"])

                    chat_response = client.post(
                        "/admin/api/instances/inst-chat/chat",
                        json={"message": "帮我分析一下当前异常是否需要暂停"},
                    )
                    self.assertEqual(chat_response.status_code, 200)
                    body = chat_response.json()
                    self.assertEqual(body["provider"], "deepseek")
                    self.assertIn("实例分析结果", body["reply"])
                    self.assertIn("当前实例上下文", body["context_preview"])


if __name__ == "__main__":
    unittest.main()
