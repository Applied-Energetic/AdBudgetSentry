from __future__ import annotations

import asyncio
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import app as gateway_app
from database import ensure_database, save_ingest_event


class StrategyAdminApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._health_patch = patch.object(gateway_app, "health_monitor_loop", new=lambda: asyncio.sleep(0))
        self._health_patch.start()

    def tearDown(self) -> None:
        self._health_patch.stop()

    def test_default_metric_registry_and_strategy_seed_exist(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db_path = Path(tmp) / "app.db"
            ensure_database(db_path)

            with sqlite3.connect(db_path) as conn:
                metric_rows = conn.execute(
                    "SELECT metric_key, is_strategy_ready FROM metric_registry ORDER BY metric_key"
                ).fetchall()
                strategy_rows = conn.execute(
                    "SELECT name, template_type, target_metric, auto_bind_new_instances FROM strategy_definitions ORDER BY id"
                ).fetchall()

            self.assertIn(("spend", 1), metric_rows)
            self.assertTrue(any(row[1] == "window_threshold" and row[2] == "spend" for row in strategy_rows))

    def test_admin_can_create_strategy_and_bind_it_to_instance(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db_path = Path(tmp) / "app.db"
            ensure_database(db_path)
            save_ingest_event(
                db_path,
                {
                    "instance_id": "inst-bind",
                    "account_id": "acct-1",
                    "account_name": "Binding Shop",
                    "page_type": "financial",
                    "page_url": "https://example.test",
                    "script_version": "1.0.0",
                    "captured_at": 1_712_000_000_000,
                    "row_count": 3,
                    "metrics": {"current_spend": 100.0},
                    "raw_context": {},
                },
            )

            with patch.object(gateway_app, "get_db_path", return_value=db_path):
                with TestClient(gateway_app.app) as client:
                    create_response = client.post(
                        "/admin/api/strategies",
                        json={
                            "name": "10分钟花费阈值",
                            "description": "phase-one threshold",
                            "template_type": "window_threshold",
                            "target_metric": "spend",
                            "enabled": True,
                            "is_default": False,
                            "auto_bind_new_instances": False,
                            "params": {
                                "window_minutes": 10,
                                "threshold_value": 20,
                                "cooldown_minutes": 10,
                                "severity": "high",
                            },
                        },
                    )
                    self.assertEqual(create_response.status_code, 200)
                    strategy_id = create_response.json()["id"]

                    bind_response = client.post(
                        "/admin/api/instances/inst-bind/strategy-bindings",
                        json={"strategy_id": strategy_id, "enabled": True, "priority": 50},
                    )
                    self.assertEqual(bind_response.status_code, 200)

                    detail_response = client.get("/admin/api/instances/inst-bind")
                    self.assertEqual(detail_response.status_code, 200)
                    detail = detail_response.json()

            self.assertTrue(any(item["strategy_id"] == strategy_id for item in detail["strategy_bindings"]))


if __name__ == "__main__":
    unittest.main()
