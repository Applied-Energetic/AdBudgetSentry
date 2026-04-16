from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app as gateway_app
from database import ensure_database, fetch_alerts_for_instance, save_ingest_event


class AnalysisAndAlertsTests(unittest.TestCase):
    def test_ingest_generates_strategy_hit_and_linked_alert_for_default_threshold_strategy(self) -> None:
        class FakeResponse:
            status_code = 200

            @staticmethod
            def json() -> dict:
                return {"code": 200}

        class FakeClient:
            def __init__(self, *args, **kwargs) -> None:
                self.kwargs = kwargs

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb) -> bool:
                return False

            async def post(self, *args, **kwargs):
                return FakeResponse()

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db_path = Path(tmp) / "app.db"
            ensure_database(db_path)

            with (
                patch.object(
                    gateway_app,
                    "load_config",
                    return_value={
                        "alerts": {
                            "enabled": True,
                            "pushplus": {
                                "enabled": True,
                                "token": "token-123",
                                "channel": "mail",
                                "option": "",
                            },
                        }
                    },
                ),
                patch.object(gateway_app.httpx, "AsyncClient", FakeClient),
            ):
                instance_id = save_ingest_event(
                    db_path,
                    {
                        "instance_id": "inst-strategy",
                        "account_id": "acct-1",
                        "account_name": "Threshold Shop",
                        "page_type": "financial",
                        "page_url": "https://example.test",
                        "script_version": "1.0.0",
                        "captured_at": 1_712_000_000_000,
                        "row_count": 3,
                        "metrics": {"current_spend": 100.0},
                        "raw_context": {},
                    },
                )
                save_ingest_event(
                    db_path,
                    {
                        "instance_id": instance_id,
                        "account_id": "acct-1",
                        "account_name": "Threshold Shop",
                        "page_type": "financial",
                        "page_url": "https://example.test",
                        "script_version": "1.0.0",
                        "captured_at": 1_712_000_600_000,
                        "row_count": 3,
                        "metrics": {"current_spend": 140.0},
                        "raw_context": {},
                    },
                )
                asyncio.run(
                    gateway_app.evaluate_ingest_strategies(
                        db_path,
                        {
                            "instance_id": instance_id,
                            "account_id": "acct-1",
                            "account_name": "Threshold Shop",
                            "page_type": "financial",
                            "page_url": "https://example.test",
                            "script_version": "1.0.0",
                            "captured_at": 1_712_000_600_000,
                            "row_count": 3,
                            "metrics": {"current_spend": 140.0},
                            "raw_context": {},
                        },
                    )
                )

            with gateway_app.open_connection(db_path) as conn:
                hit_row = conn.execute(
                    """
                    SELECT strategy_id, strategy_name, target_metric
                    FROM strategy_hits
                    WHERE instance_id = ?
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    ("inst-strategy",),
                ).fetchone()
                alert_row = conn.execute(
                    """
                    SELECT strategy_id, strategy_hit_id, strategy_name, target_metric, send_status
                    FROM alert_records
                    WHERE instance_id = ?
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    ("inst-strategy",),
                ).fetchone()

            self.assertIsNotNone(hit_row)
            self.assertEqual(hit_row["target_metric"], "spend")
            self.assertIsNotNone(alert_row)
            self.assertEqual(alert_row["target_metric"], "spend")
            self.assertIsNotNone(alert_row["strategy_id"])
            self.assertIsNotNone(alert_row["strategy_hit_id"])
            self.assertEqual(alert_row["send_status"], "sent")

    def test_build_threshold_alert_content_keeps_only_core_fields(self) -> None:
        title, preview = gateway_app.build_threshold_alert_content(
            {
                "account_name": "电旗店",
                "account_id": "acct-1",
                "captured_at": 1_712_000_000_000,
                "metrics": {
                    "current_spend": 746.04,
                    "compare_interval_min": 10,
                    "increase_amount": 48.52,
                    "notify_threshold": 20,
                },
            }
        )

        self.assertIn("电旗店", title)
        self.assertIn("账号名称：电旗店", preview)
        self.assertIn("当前总消耗：746.04 元", preview)
        self.assertIn("报警时间：", preview)
        self.assertIn("对比窗口：10 分钟", preview)
        self.assertIn("窗口增量：48.52 元", preview)
        self.assertIn("阈值：20.00 元", preview)
        self.assertNotIn("分析结果", preview)
        self.assertNotIn("实例", preview)
        self.assertNotIn("页面类型", preview)
        self.assertNotIn("基线", preview)

    def test_extract_summary_prefers_conclusion_line(self) -> None:
        raw_text = "\n".join(
            [
                "结论：10 分钟窗口消耗异常放大，建议立即关注投放计划。",
                "原因判断：1. 当前窗口增量显著高于分时段基线。",
                "建议：1. 继续观察后续 10 分钟趋势。",
            ]
        )

        summary = gateway_app.extract_analysis_summary(raw_text)

        self.assertEqual(summary, "10 分钟窗口消耗异常放大，建议立即关注投放计划。")

    def test_extract_summary_falls_back_to_first_non_empty_line(self) -> None:
        raw_text = "\n\n规则判断：threshold_breach\n建议：继续观察"

        summary = gateway_app.extract_analysis_summary(raw_text)

        self.assertEqual(summary, "规则判断：threshold_breach")

    def test_fetch_capture_history_adds_hourly_baseline(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db_path = Path(tmp) / "app.db"
            ensure_database(db_path)

            base_payload = {
                "instance_id": "inst-1",
                "account_id": "acct-1",
                "account_name": "电旗店",
                "page_type": "financial",
                "page_url": "https://example.test",
                "script_version": "1.0.0",
                "row_count": 3,
                "raw_context": {},
            }
            captured_times = [1_712_004_000_000, 1_712_004_600_000, 1_712_004_900_000]
            increases = [10.0, 20.0, 40.0]
            spends = [100.0, 120.0, 160.0]

            for captured_at, increase_amount, current_spend in zip(captured_times, increases, spends):
                save_ingest_event(
                    db_path,
                    {
                        **base_payload,
                        "captured_at": captured_at,
                        "metrics": {
                            "current_spend": current_spend,
                            "increase_amount": increase_amount,
                            "compare_interval_min": 10,
                            "notify_threshold": 20,
                        },
                    },
                )

            history = gateway_app.fetch_capture_history_for_instance(db_path, "inst-1", limit=10)

            self.assertEqual(len(history), 3)
            self.assertAlmostEqual(history[0]["baseline_increase_amount"], 23.33, places=2)
            self.assertAlmostEqual(history[1]["baseline_increase_amount"], 23.33, places=2)
            self.assertAlmostEqual(history[2]["baseline_increase_amount"], 23.33, places=2)

    def test_dispatch_pushplus_alert_disables_env_proxy(self) -> None:
        class FakeResponse:
            status_code = 200

            @staticmethod
            def json() -> dict:
                return {"code": 200}

        client_kwargs: dict[str, object] = {}

        class FakeClient:
            def __init__(self, *args, **kwargs) -> None:
                client_kwargs.update(kwargs)

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb) -> bool:
                return False

            async def post(self, *args, **kwargs):
                return FakeResponse()

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db_path = Path(tmp) / "app.db"
            ensure_database(db_path)

            with (
                patch.object(
                    gateway_app,
                    "load_config",
                    return_value={
                        "alerts": {
                            "enabled": True,
                            "pushplus": {
                                "enabled": True,
                                "token": "token-123",
                                "channel": "mail",
                                "option": "",
                            },
                        }
                    },
                ),
                patch.object(gateway_app, "fetch_latest_alert_for_instance_kind", return_value=None),
                patch.object(gateway_app.httpx, "AsyncClient", FakeClient),
            ):
                result = asyncio.run(
                    gateway_app.dispatch_pushplus_alert(
                        db_path,
                        instance_id="inst-1",
                        account_id="acct-1",
                        account_name="旗舰店",
                        page_type="finance",
                        page_url="https://example.test",
                        script_version="1.0.0",
                        alert_kind="threshold",
                        title="测试标题",
                        content_preview="测试内容",
                        content_html="<p>测试内容</p>",
                        severity="high",
                        anomaly_type="threshold_breach",
                        triggered_at=1_712_000_000_000,
                        cooldown_ms=0,
                    )
                )

            self.assertTrue(result["ok"])
            self.assertEqual(client_kwargs.get("trust_env"), False)
            saved_alerts = fetch_alerts_for_instance(db_path, "inst-1", limit=1)
            self.assertEqual(saved_alerts[0]["send_status"], "sent")


if __name__ == "__main__":
    unittest.main()
