from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime
from hashlib import sha1
from pathlib import Path


GREEN_HEARTBEAT_MS = 5 * 60 * 1000
GREEN_CAPTURE_MS = 10 * 60 * 1000
YELLOW_HEARTBEAT_MS = 10 * 60 * 1000
YELLOW_CAPTURE_MS = 15 * 60 * 1000
RED_CONSECUTIVE_ERRORS = 3
DEFAULT_METRICS = [
    {
        "metric_key": "spend",
        "display_name": "花费",
        "description": "账户流水花费，阶段一唯一可执行指标",
        "unit": "cny",
        "is_enabled": 1,
        "is_strategy_ready": 1,
    },
    {
        "metric_key": "impressions",
        "display_name": "曝光次数",
        "description": "预留指标",
        "unit": "count",
        "is_enabled": 1,
        "is_strategy_ready": 0,
    },
    {
        "metric_key": "clicks",
        "display_name": "点击次数",
        "description": "预留指标",
        "unit": "count",
        "is_enabled": 1,
        "is_strategy_ready": 0,
    },
    {
        "metric_key": "ctr",
        "display_name": "点击率",
        "description": "预留指标",
        "unit": "ratio",
        "is_enabled": 1,
        "is_strategy_ready": 0,
    },
    {
        "metric_key": "accelerated_spend",
        "display_name": "加速探索花费",
        "description": "预留指标",
        "unit": "cny",
        "is_enabled": 1,
        "is_strategy_ready": 0,
    },
    {
        "metric_key": "creative_boost_spend",
        "display_name": "素材追投花费",
        "description": "预留指标",
        "unit": "cny",
        "is_enabled": 1,
        "is_strategy_ready": 0,
    },
    {
        "metric_key": "video_3s",
        "display_name": "视频3秒播放次数",
        "description": "预留指标",
        "unit": "count",
        "is_enabled": 1,
        "is_strategy_ready": 0,
    },
    {
        "metric_key": "video_5s",
        "display_name": "视频5秒播放次数",
        "description": "预留指标",
        "unit": "count",
        "is_enabled": 1,
        "is_strategy_ready": 0,
    },
    {
        "metric_key": "video_complete",
        "display_name": "视频完播次数",
        "description": "预留指标",
        "unit": "count",
        "is_enabled": 1,
        "is_strategy_ready": 0,
    },
    {
        "metric_key": "yellow_cart_clicks",
        "display_name": "小黄车点击次数",
        "description": "预留指标",
        "unit": "count",
        "is_enabled": 1,
        "is_strategy_ready": 0,
    },
    {
        "metric_key": "product_card_clicks",
        "display_name": "商品卡点击次数",
        "description": "预留指标",
        "unit": "count",
        "is_enabled": 1,
        "is_strategy_ready": 0,
    },
    {
        "metric_key": "merchant_coupon_penetration",
        "display_name": "超级商家券订单渗透",
        "description": "预留指标",
        "unit": "ratio",
        "is_enabled": 1,
        "is_strategy_ready": 0,
    },
]
DEFAULT_STRATEGIES = [
    {
        "name": "默认花费阈值策略",
        "description": "阶段一默认策略：监控10分钟窗口花费增量阈值",
        "template_type": "window_threshold",
        "target_metric": "spend",
        "params_json": json.dumps(
            {
                "window_minutes": 10,
                "threshold_value": 20,
                "cooldown_minutes": 10,
                "severity": "high",
            },
            ensure_ascii=False,
        ),
        "enabled": 1,
        "is_default": 1,
        "auto_bind_new_instances": 1,
    },
    {
        "name": "默认历史基线策略",
        "description": "阶段一预置但默认不自动绑定的历史基线策略",
        "template_type": "historical_baseline",
        "target_metric": "spend",
        "params_json": json.dumps(
            {
                "window_minutes": 10,
                "lookback_days": 7,
                "zscore_threshold": 2.5,
                "min_samples": 3,
                "severity": "medium",
            },
            ensure_ascii=False,
        ),
        "enabled": 1,
        "is_default": 1,
        "auto_bind_new_instances": 0,
    },
]


def utc_now_ms() -> int:
    return int(time.time() * 1000)


def derive_instance_id(payload: dict) -> str:
    explicit = payload.get("instance_id")
    if explicit:
        return str(explicit)

    raw = "|".join(
        [
            str(payload.get("account_id") or ""),
            str(payload.get("account_name") or ""),
            str(payload.get("page_type") or ""),
            str(payload.get("page_url") or ""),
            str(payload.get("script_version") or ""),
        ]
    )
    return f"inst_{sha1(raw.encode('utf-8')).hexdigest()[:16]}"


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _seed_metric_registry(conn: sqlite3.Connection) -> None:
    now_ms = utc_now_ms()
    for item in DEFAULT_METRICS:
        conn.execute(
            """
            INSERT INTO metric_registry (
                metric_key, display_name, description, unit,
                is_enabled, is_strategy_ready, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(metric_key) DO UPDATE SET
                display_name = excluded.display_name,
                description = excluded.description,
                unit = excluded.unit,
                is_enabled = excluded.is_enabled,
                is_strategy_ready = excluded.is_strategy_ready,
                updated_at = excluded.updated_at
            """,
            (
                item["metric_key"],
                item["display_name"],
                item["description"],
                item["unit"],
                item["is_enabled"],
                item["is_strategy_ready"],
                now_ms,
                now_ms,
            ),
        )


def _seed_default_strategies(conn: sqlite3.Connection) -> None:
    now_ms = utc_now_ms()
    for item in DEFAULT_STRATEGIES:
        conn.execute(
            """
            INSERT INTO strategy_definitions (
                name, description, template_type, target_metric, params_json,
                enabled, is_default, auto_bind_new_instances, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                description = excluded.description,
                template_type = excluded.template_type,
                target_metric = excluded.target_metric,
                params_json = excluded.params_json,
                enabled = excluded.enabled,
                is_default = excluded.is_default,
                auto_bind_new_instances = excluded.auto_bind_new_instances,
                updated_at = excluded.updated_at
            """,
            (
                item["name"],
                item["description"],
                item["template_type"],
                item["target_metric"],
                item["params_json"],
                item["enabled"],
                item["is_default"],
                item["auto_bind_new_instances"],
                now_ms,
                now_ms,
            ),
        )


def _bind_default_strategies(conn: sqlite3.Connection, instance_id: str) -> None:
    now_ms = utc_now_ms()
    strategy_rows = conn.execute(
        """
        SELECT id
        FROM strategy_definitions
        WHERE enabled = 1 AND auto_bind_new_instances = 1
        """
    ).fetchall()
    for row in strategy_rows:
        conn.execute(
            """
            INSERT INTO instance_strategy_bindings (
                instance_id, strategy_id, enabled, priority, created_at, updated_at
            ) VALUES (?, ?, 1, 100, ?, ?)
            ON CONFLICT(instance_id, strategy_id) DO NOTHING
            """,
            (instance_id, row["id"], now_ms, now_ms),
        )


def ensure_database(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            PRAGMA journal_mode=WAL;

            CREATE TABLE IF NOT EXISTS script_instances (
                instance_id TEXT PRIMARY KEY,
                account_id TEXT,
                account_name TEXT,
                page_type TEXT,
                page_url TEXT,
                script_version TEXT,
                first_seen_at INTEGER NOT NULL,
                last_seen_at INTEGER NOT NULL,
                last_heartbeat_at INTEGER,
                last_capture_at INTEGER,
                last_capture_status TEXT,
                last_error TEXT,
                last_row_count INTEGER,
                consecutive_error_count INTEGER NOT NULL DEFAULT 0,
                health_status TEXT NOT NULL DEFAULT 'yellow',
                alias TEXT,
                remarks TEXT
            );

            CREATE TABLE IF NOT EXISTS script_heartbeats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instance_id TEXT NOT NULL,
                account_id TEXT,
                account_name TEXT,
                page_type TEXT,
                page_url TEXT,
                script_version TEXT,
                heartbeat_at INTEGER NOT NULL,
                browser_visible INTEGER,
                capture_status TEXT NOT NULL,
                last_capture_at INTEGER,
                row_count INTEGER,
                error_message TEXT,
                created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS capture_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instance_id TEXT NOT NULL,
                account_id TEXT,
                account_name TEXT,
                page_type TEXT,
                page_url TEXT,
                script_version TEXT,
                captured_at INTEGER NOT NULL,
                row_count INTEGER,
                metrics_json TEXT NOT NULL,
                raw_context_json TEXT NOT NULL,
                created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS error_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instance_id TEXT NOT NULL,
                page_url TEXT,
                script_version TEXT,
                error_type TEXT NOT NULL,
                error_message TEXT NOT NULL,
                occurred_at INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS analysis_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instance_id TEXT NOT NULL,
                account_id TEXT,
                account_name TEXT,
                page_type TEXT,
                page_url TEXT,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                anomaly_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                score REAL NOT NULL,
                summary TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS alert_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instance_id TEXT NOT NULL,
                account_id TEXT,
                account_name TEXT,
                page_type TEXT,
                page_url TEXT,
                script_version TEXT,
                alert_kind TEXT NOT NULL,
                title TEXT NOT NULL,
                content_preview TEXT,
                channel TEXT,
                channel_option TEXT,
                delivery_provider TEXT NOT NULL,
                send_status TEXT NOT NULL,
                provider_response TEXT,
                severity TEXT,
                anomaly_type TEXT,
                strategy_id INTEGER,
                strategy_hit_id INTEGER,
                capture_event_id INTEGER,
                strategy_name TEXT,
                target_metric TEXT,
                triggered_at INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS metric_registry (
                metric_key TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                description TEXT,
                unit TEXT,
                is_enabled INTEGER NOT NULL DEFAULT 1,
                is_strategy_ready INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS strategy_definitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                template_type TEXT NOT NULL,
                target_metric TEXT NOT NULL,
                params_json TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                is_default INTEGER NOT NULL DEFAULT 0,
                auto_bind_new_instances INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS instance_strategy_bindings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instance_id TEXT NOT NULL,
                strategy_id INTEGER NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                priority INTEGER NOT NULL DEFAULT 100,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                UNIQUE(instance_id, strategy_id)
            );

            CREATE TABLE IF NOT EXISTS strategy_hits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instance_id TEXT NOT NULL,
                strategy_id INTEGER NOT NULL,
                binding_id INTEGER,
                capture_event_id INTEGER,
                target_metric TEXT NOT NULL,
                strategy_name TEXT NOT NULL,
                template_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                score REAL NOT NULL,
                anomaly_type TEXT NOT NULL,
                evidence_json TEXT NOT NULL,
                snapshot_json TEXT NOT NULL,
                recommendation TEXT,
                triggered_at INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_heartbeats_instance_time
                ON script_heartbeats(instance_id, heartbeat_at DESC);

            CREATE INDEX IF NOT EXISTS idx_capture_events_instance_time
                ON capture_events(instance_id, captured_at DESC);

            CREATE INDEX IF NOT EXISTS idx_capture_events_account_time
                ON capture_events(account_id, captured_at DESC);

            CREATE INDEX IF NOT EXISTS idx_error_reports_instance_time
                ON error_reports(instance_id, occurred_at DESC);

            CREATE INDEX IF NOT EXISTS idx_analysis_summaries_instance_time
                ON analysis_summaries(instance_id, created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_alert_records_instance_time
                ON alert_records(instance_id, triggered_at DESC);

            CREATE INDEX IF NOT EXISTS idx_alert_records_created_time
                ON alert_records(created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_strategy_bindings_instance
                ON instance_strategy_bindings(instance_id, enabled, priority);

            CREATE INDEX IF NOT EXISTS idx_strategy_hits_instance_time
                ON strategy_hits(instance_id, triggered_at DESC);

            CREATE INDEX IF NOT EXISTS idx_strategy_hits_strategy_time
                ON strategy_hits(strategy_id, triggered_at DESC);
            """
        )
        _ensure_column(conn, "script_instances", "alias", "TEXT")
        _ensure_column(conn, "script_instances", "remarks", "TEXT")
        _ensure_column(conn, "alert_records", "strategy_id", "INTEGER")
        _ensure_column(conn, "alert_records", "strategy_hit_id", "INTEGER")
        _ensure_column(conn, "alert_records", "capture_event_id", "INTEGER")
        _ensure_column(conn, "alert_records", "strategy_name", "TEXT")
        _ensure_column(conn, "alert_records", "target_metric", "TEXT")
        _seed_metric_registry(conn)
        _seed_default_strategies(conn)


def open_connection(db_path: Path) -> sqlite3.Connection:
    ensure_database(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def compute_health_status(
    *,
    now_ms: int,
    last_heartbeat_at: int | None,
    last_capture_at: int | None,
    last_capture_status: str | None,
    consecutive_error_count: int,
) -> str:
    if not last_heartbeat_at or now_ms - last_heartbeat_at > YELLOW_HEARTBEAT_MS:
        return "red"

    if consecutive_error_count >= RED_CONSECUTIVE_ERRORS:
        return "red"

    if last_capture_status == "error":
        return "red"

    if (
        now_ms - last_heartbeat_at <= GREEN_HEARTBEAT_MS
        and last_capture_at
        and now_ms - last_capture_at <= GREEN_CAPTURE_MS
        and consecutive_error_count == 0
    ):
        return "green"

    if last_capture_at and now_ms - last_capture_at <= YELLOW_CAPTURE_MS:
        return "yellow"

    return "yellow"


def _upsert_instance_base(
    conn: sqlite3.Connection,
    *,
    instance_id: str,
    seen_at: int,
    account_id: str | None,
    account_name: str | None,
    page_type: str | None,
    page_url: str | None,
    script_version: str | None,
) -> None:
    conn.execute(
        """
        INSERT INTO script_instances (
            instance_id, account_id, account_name, page_type, page_url, script_version,
            first_seen_at, last_seen_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(instance_id) DO UPDATE SET
            account_id = COALESCE(excluded.account_id, script_instances.account_id),
            account_name = COALESCE(excluded.account_name, script_instances.account_name),
            page_type = COALESCE(excluded.page_type, script_instances.page_type),
            page_url = COALESCE(excluded.page_url, script_instances.page_url),
            script_version = COALESCE(excluded.script_version, script_instances.script_version),
            last_seen_at = excluded.last_seen_at
        """,
        (
            instance_id,
            account_id,
            account_name,
            page_type,
            page_url,
            script_version,
            seen_at,
            seen_at,
        ),
    )


def save_ingest_event(db_path: Path, payload: dict) -> str:
    now_ms = utc_now_ms()
    instance_id = derive_instance_id(payload)
    with open_connection(db_path) as conn:
        _upsert_instance_base(
            conn,
            instance_id=instance_id,
            seen_at=payload["captured_at"],
            account_id=payload.get("account_id"),
            account_name=payload.get("account_name"),
            page_type=payload.get("page_type"),
            page_url=payload.get("page_url"),
            script_version=payload.get("script_version"),
        )
        _bind_default_strategies(conn, instance_id)
        conn.execute(
            """
            INSERT INTO capture_events (
                instance_id, account_id, account_name, page_type, page_url, script_version,
                captured_at, row_count, metrics_json, raw_context_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                instance_id,
                payload.get("account_id"),
                payload.get("account_name"),
                payload.get("page_type"),
                payload.get("page_url"),
                payload.get("script_version"),
                payload["captured_at"],
                payload.get("row_count"),
                json.dumps(payload.get("metrics") or {}, ensure_ascii=False),
                json.dumps(payload.get("raw_context") or {}, ensure_ascii=False),
                now_ms,
            ),
        )

        current = conn.execute(
            """
            SELECT last_heartbeat_at, consecutive_error_count
            FROM script_instances
            WHERE instance_id = ?
            """,
            (instance_id,),
        ).fetchone()

        last_heartbeat_at = current["last_heartbeat_at"] if current else None
        health_status = compute_health_status(
            now_ms=now_ms,
            last_heartbeat_at=last_heartbeat_at or payload["captured_at"],
            last_capture_at=payload["captured_at"],
            last_capture_status="success",
            consecutive_error_count=0,
        )

        conn.execute(
            """
            UPDATE script_instances
            SET
                last_seen_at = ?,
                last_capture_at = ?,
                last_capture_status = 'success',
                last_error = NULL,
                last_row_count = COALESCE(?, last_row_count),
                consecutive_error_count = 0,
                health_status = ?,
                account_id = COALESCE(?, account_id),
                account_name = COALESCE(?, account_name),
                page_type = COALESCE(?, page_type),
                page_url = COALESCE(?, page_url),
                script_version = COALESCE(?, script_version)
            WHERE instance_id = ?
            """,
            (
                payload["captured_at"],
                payload["captured_at"],
                payload.get("row_count"),
                health_status,
                payload.get("account_id"),
                payload.get("account_name"),
                payload.get("page_type"),
                payload.get("page_url"),
                payload.get("script_version"),
                instance_id,
            ),
        )
    return instance_id


def save_heartbeat(db_path: Path, payload: dict) -> None:
    now_ms = utc_now_ms()
    instance_id = derive_instance_id(payload)
    with open_connection(db_path) as conn:
        _upsert_instance_base(
            conn,
            instance_id=instance_id,
            seen_at=payload["heartbeat_at"],
            account_id=payload.get("account_id"),
            account_name=payload.get("account_name"),
            page_type=payload.get("page_type"),
            page_url=payload.get("page_url"),
            script_version=payload.get("script_version"),
        )
        conn.execute(
            """
            INSERT INTO script_heartbeats (
                instance_id, account_id, account_name, page_type, page_url, script_version,
                heartbeat_at, browser_visible, capture_status, last_capture_at, row_count,
                error_message, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                instance_id,
                payload.get("account_id"),
                payload.get("account_name"),
                payload.get("page_type"),
                payload.get("page_url"),
                payload.get("script_version"),
                payload["heartbeat_at"],
                1 if payload.get("browser_visible") else 0 if payload.get("browser_visible") is not None else None,
                payload["capture_status"],
                payload.get("last_capture_at"),
                payload.get("row_count"),
                payload.get("error_message"),
                now_ms,
            ),
        )

        current = conn.execute(
            """
            SELECT last_capture_at, consecutive_error_count
            FROM script_instances
            WHERE instance_id = ?
            """,
            (instance_id,),
        ).fetchone()
        previous_errors = current["consecutive_error_count"] if current else 0
        last_capture_at = payload.get("last_capture_at") or (current["last_capture_at"] if current else None)
        error_count = previous_errors + 1 if payload["capture_status"] in {"warning", "error"} else 0
        health_status = compute_health_status(
            now_ms=now_ms,
            last_heartbeat_at=payload["heartbeat_at"],
            last_capture_at=last_capture_at,
            last_capture_status=payload["capture_status"],
            consecutive_error_count=error_count,
        )
        conn.execute(
            """
            UPDATE script_instances
            SET
                last_seen_at = ?,
                last_heartbeat_at = ?,
                last_capture_at = COALESCE(?, last_capture_at),
                last_capture_status = ?,
                last_error = CASE
                    WHEN ? IS NOT NULL AND ? <> '' THEN ?
                    ELSE last_error
                END,
                last_row_count = COALESCE(?, last_row_count),
                consecutive_error_count = ?,
                health_status = ?,
                account_id = COALESCE(?, account_id),
                account_name = COALESCE(?, account_name),
                page_type = COALESCE(?, page_type),
                page_url = COALESCE(?, page_url),
                script_version = COALESCE(?, script_version)
            WHERE instance_id = ?
            """,
            (
                payload["heartbeat_at"],
                payload["heartbeat_at"],
                payload.get("last_capture_at"),
                payload["capture_status"],
                payload.get("error_message"),
                payload.get("error_message"),
                payload.get("error_message"),
                payload.get("row_count"),
                error_count,
                health_status,
                payload.get("account_id"),
                payload.get("account_name"),
                payload.get("page_type"),
                payload.get("page_url"),
                payload.get("script_version"),
                instance_id,
            ),
        )


def save_error_report(db_path: Path, payload: dict) -> None:
    now_ms = utc_now_ms()
    instance_id = derive_instance_id(payload)
    with open_connection(db_path) as conn:
        _upsert_instance_base(
            conn,
            instance_id=instance_id,
            seen_at=payload["occurred_at"],
            account_id=None,
            account_name=None,
            page_type=None,
            page_url=payload.get("page_url"),
            script_version=payload.get("script_version"),
        )
        conn.execute(
            """
            INSERT INTO error_reports (
                instance_id, page_url, script_version, error_type, error_message, occurred_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                instance_id,
                payload.get("page_url"),
                payload.get("script_version"),
                payload["error_type"],
                payload["error_message"],
                payload["occurred_at"],
                now_ms,
            ),
        )
        current = conn.execute(
            """
            SELECT last_heartbeat_at, last_capture_at, consecutive_error_count
            FROM script_instances
            WHERE instance_id = ?
            """,
            (instance_id,),
        ).fetchone()
        next_error_count = (current["consecutive_error_count"] if current else 0) + 1
        health_status = compute_health_status(
            now_ms=now_ms,
            last_heartbeat_at=current["last_heartbeat_at"] if current else None,
            last_capture_at=current["last_capture_at"] if current else None,
            last_capture_status="error",
            consecutive_error_count=next_error_count,
        )
        conn.execute(
            """
            UPDATE script_instances
            SET
                last_seen_at = ?,
                last_capture_status = 'error',
                last_error = ?,
                consecutive_error_count = ?,
                health_status = ?,
                page_url = COALESCE(?, page_url),
                script_version = COALESCE(?, script_version)
            WHERE instance_id = ?
            """,
            (
                payload["occurred_at"],
                f'{payload["error_type"]}: {payload["error_message"]}',
                next_error_count,
                health_status,
                payload.get("page_url"),
                payload.get("script_version"),
                instance_id,
            ),
        )


def save_alert_record(db_path: Path, payload: dict) -> int:
    now_ms = utc_now_ms()
    instance_id = derive_instance_id(payload)
    with open_connection(db_path) as conn:
        _upsert_instance_base(
            conn,
            instance_id=instance_id,
            seen_at=payload["triggered_at"],
            account_id=payload.get("account_id"),
            account_name=payload.get("account_name"),
            page_type=payload.get("page_type"),
            page_url=payload.get("page_url"),
            script_version=payload.get("script_version"),
        )
        cursor = conn.execute(
            """
            INSERT INTO alert_records (
                instance_id, account_id, account_name, page_type, page_url, script_version,
                alert_kind, title, content_preview, channel, channel_option, delivery_provider,
                send_status, provider_response, severity, anomaly_type, strategy_id, strategy_hit_id,
                capture_event_id, strategy_name, target_metric, triggered_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                instance_id,
                payload.get("account_id"),
                payload.get("account_name"),
                payload.get("page_type"),
                payload.get("page_url"),
                payload.get("script_version"),
                payload["alert_kind"],
                payload["title"],
                payload.get("content_preview"),
                payload.get("channel"),
                payload.get("channel_option"),
                payload.get("delivery_provider") or "pushplus",
                payload["send_status"],
                payload.get("provider_response"),
                payload.get("severity"),
                payload.get("anomaly_type"),
                payload.get("strategy_id"),
                payload.get("strategy_hit_id"),
                payload.get("capture_event_id"),
                payload.get("strategy_name"),
                payload.get("target_metric"),
                payload["triggered_at"],
                now_ms,
            ),
        )
        conn.execute(
            """
            UPDATE script_instances
            SET
                last_seen_at = ?,
                account_id = COALESCE(?, account_id),
                account_name = COALESCE(?, account_name),
                page_type = COALESCE(?, page_type),
                page_url = COALESCE(?, page_url),
                script_version = COALESCE(?, script_version)
            WHERE instance_id = ?
            """,
            (
                payload["triggered_at"],
                payload.get("account_id"),
                payload.get("account_name"),
                payload.get("page_type"),
                payload.get("page_url"),
                payload.get("script_version"),
                instance_id,
            ),
        )
        return int(cursor.lastrowid)


def fetch_history_for_instance(db_path: Path, instance_id: str, limit: int = 60) -> list[dict]:
    with open_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT captured_at, metrics_json
            FROM capture_events
            WHERE instance_id = ?
            ORDER BY captured_at DESC
            LIMIT ?
            """,
            (instance_id, limit),
        ).fetchall()

    items: list[dict] = []
    for row in reversed(rows):
        try:
            metrics = json.loads(row["metrics_json"] or "{}")
        except json.JSONDecodeError:
            metrics = {}
        spend = metrics.get("current_spend")
        if spend is None:
            continue
        try:
            items.append({"timestamp": int(row["captured_at"]), "spend": float(spend)})
        except (TypeError, ValueError):
            continue
    return items


def fetch_capture_event_id(db_path: Path, instance_id: str, captured_at: int) -> int | None:
    with open_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT id
            FROM capture_events
            WHERE instance_id = ? AND captured_at = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (instance_id, captured_at),
        ).fetchone()
    return int(row["id"]) if row else None


def list_metric_registry(db_path: Path) -> list[dict]:
    with open_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT metric_key, display_name, description, unit, is_enabled, is_strategy_ready
            FROM metric_registry
            ORDER BY metric_key
            """
        ).fetchall()
    return [dict(row) for row in rows]


def fetch_strategy_definition(db_path: Path, strategy_id: int) -> dict | None:
    with open_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, name, description, template_type, target_metric, params_json, enabled,
                   is_default, auto_bind_new_instances, created_at, updated_at
            FROM strategy_definitions
            WHERE id = ?
            """,
            (strategy_id,),
        ).fetchone()
    if not row:
        return None
    item = dict(row)
    item["params"] = json.loads(item.pop("params_json") or "{}")
    item["enabled"] = bool(item["enabled"])
    item["is_default"] = bool(item["is_default"])
    item["auto_bind_new_instances"] = bool(item["auto_bind_new_instances"])
    return item


def fetch_strategy_by_name(db_path: Path, name: str) -> dict | None:
    with open_connection(db_path) as conn:
        row = conn.execute("SELECT id FROM strategy_definitions WHERE name = ?", (name,)).fetchone()
    return fetch_strategy_definition(db_path, int(row["id"])) if row else None


def fetch_admin_strategies(db_path: Path) -> list[dict]:
    with open_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                s.id,
                s.name,
                s.description,
                s.template_type,
                s.target_metric,
                s.params_json,
                s.enabled,
                s.is_default,
                s.auto_bind_new_instances,
                s.created_at,
                s.updated_at,
                COUNT(DISTINCT b.instance_id) AS binding_count,
                COUNT(h.id) AS hit_count
            FROM strategy_definitions s
            LEFT JOIN instance_strategy_bindings b ON b.strategy_id = s.id
            LEFT JOIN strategy_hits h ON h.strategy_id = s.id
            GROUP BY s.id
            ORDER BY s.updated_at DESC, s.id DESC
            """
        ).fetchall()

    items: list[dict] = []
    for row in rows:
        item = dict(row)
        item["params"] = json.loads(item.pop("params_json") or "{}")
        item["enabled"] = bool(item["enabled"])
        item["is_default"] = bool(item["is_default"])
        item["auto_bind_new_instances"] = bool(item["auto_bind_new_instances"])
        items.append(item)
    return items


def create_strategy_definition(
    db_path: Path,
    *,
    name: str,
    description: str | None,
    template_type: str,
    target_metric: str,
    params: dict,
    enabled: bool,
    is_default: bool,
    auto_bind_new_instances: bool,
) -> dict:
    now_ms = utc_now_ms()
    with open_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO strategy_definitions (
                name, description, template_type, target_metric, params_json,
                enabled, is_default, auto_bind_new_instances, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name.strip(),
                (description or "").strip() or None,
                template_type,
                target_metric,
                json.dumps(params, ensure_ascii=False),
                1 if enabled else 0,
                1 if is_default else 0,
                1 if auto_bind_new_instances else 0,
                now_ms,
                now_ms,
            ),
        )
    return fetch_strategy_definition(db_path, int(cursor.lastrowid))


def update_strategy_definition(
    db_path: Path,
    strategy_id: int,
    *,
    name: str,
    description: str | None,
    template_type: str,
    target_metric: str,
    params: dict,
    enabled: bool,
    is_default: bool,
    auto_bind_new_instances: bool,
) -> dict | None:
    now_ms = utc_now_ms()
    with open_connection(db_path) as conn:
        row = conn.execute("SELECT id FROM strategy_definitions WHERE id = ?", (strategy_id,)).fetchone()
        if not row:
            return None
        conn.execute(
            """
            UPDATE strategy_definitions
            SET
                name = ?,
                description = ?,
                template_type = ?,
                target_metric = ?,
                params_json = ?,
                enabled = ?,
                is_default = ?,
                auto_bind_new_instances = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                name.strip(),
                (description or "").strip() or None,
                template_type,
                target_metric,
                json.dumps(params, ensure_ascii=False),
                1 if enabled else 0,
                1 if is_default else 0,
                1 if auto_bind_new_instances else 0,
                now_ms,
                strategy_id,
            ),
        )
    return fetch_strategy_definition(db_path, strategy_id)


def delete_strategy_definition(db_path: Path, strategy_id: int) -> bool:
    with open_connection(db_path) as conn:
        row = conn.execute("SELECT id FROM strategy_definitions WHERE id = ?", (strategy_id,)).fetchone()
        if not row:
            return False
        conn.execute("DELETE FROM instance_strategy_bindings WHERE strategy_id = ?", (strategy_id,))
        conn.execute("DELETE FROM strategy_definitions WHERE id = ?", (strategy_id,))
    return True


def save_instance_strategy_binding(
    db_path: Path,
    instance_id: str,
    *,
    strategy_id: int,
    enabled: bool,
    priority: int,
) -> dict:
    now_ms = utc_now_ms()
    with open_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO instance_strategy_bindings (
                instance_id, strategy_id, enabled, priority, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(instance_id, strategy_id) DO UPDATE SET
                enabled = excluded.enabled,
                priority = excluded.priority,
                updated_at = excluded.updated_at
            """,
            (instance_id, strategy_id, 1 if enabled else 0, priority, now_ms, now_ms),
        )
    bindings = fetch_instance_strategy_bindings(db_path, instance_id)
    return next(item for item in bindings if item["strategy_id"] == strategy_id)


def delete_instance_strategy_binding(db_path: Path, instance_id: str, strategy_id: int) -> bool:
    with open_connection(db_path) as conn:
        row = conn.execute(
            "SELECT id FROM instance_strategy_bindings WHERE instance_id = ? AND strategy_id = ?",
            (instance_id, strategy_id),
        ).fetchone()
        if not row:
            return False
        conn.execute(
            "DELETE FROM instance_strategy_bindings WHERE instance_id = ? AND strategy_id = ?",
            (instance_id, strategy_id),
        )
    return True


def fetch_instance_strategy_bindings(db_path: Path, instance_id: str) -> list[dict]:
    with open_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                b.id,
                b.instance_id,
                b.strategy_id,
                b.enabled,
                b.priority,
                b.created_at,
                b.updated_at,
                s.name AS strategy_name,
                s.description,
                s.template_type,
                s.target_metric,
                s.params_json
            FROM instance_strategy_bindings b
            JOIN strategy_definitions s ON s.id = b.strategy_id
            WHERE b.instance_id = ?
            ORDER BY b.priority ASC, b.id ASC
            """,
            (instance_id,),
        ).fetchall()
    items: list[dict] = []
    for row in rows:
        item = dict(row)
        item["enabled"] = bool(item["enabled"])
        item["params"] = json.loads(item.pop("params_json") or "{}")
        items.append(item)
    return items


def fetch_active_instance_strategy_bindings(db_path: Path, instance_id: str) -> list[dict]:
    return [item for item in fetch_instance_strategy_bindings(db_path, instance_id) if item["enabled"]]


def save_strategy_hit(
    db_path: Path,
    *,
    instance_id: str,
    strategy_id: int,
    binding_id: int | None,
    capture_event_id: int | None,
    target_metric: str,
    strategy_name: str,
    template_type: str,
    severity: str,
    score: float,
    anomaly_type: str,
    evidence: list[str],
    snapshot: dict,
    recommendation: str | None,
    triggered_at: int,
) -> int:
    now_ms = utc_now_ms()
    with open_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO strategy_hits (
                instance_id, strategy_id, binding_id, capture_event_id, target_metric,
                strategy_name, template_type, severity, score, anomaly_type,
                evidence_json, snapshot_json, recommendation, triggered_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                instance_id,
                strategy_id,
                binding_id,
                capture_event_id,
                target_metric,
                strategy_name,
                template_type,
                severity,
                score,
                anomaly_type,
                json.dumps(evidence, ensure_ascii=False),
                json.dumps(snapshot, ensure_ascii=False),
                recommendation,
                triggered_at,
                now_ms,
            ),
        )
    return int(cursor.lastrowid)


def fetch_strategy_hits_for_instance(db_path: Path, instance_id: str, limit: int = 20) -> list[dict]:
    with open_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                instance_id,
                strategy_id,
                binding_id,
                capture_event_id,
                target_metric,
                strategy_name,
                template_type,
                severity,
                score,
                anomaly_type,
                evidence_json,
                snapshot_json,
                recommendation,
                triggered_at,
                created_at
            FROM strategy_hits
            WHERE instance_id = ?
            ORDER BY triggered_at DESC, id DESC
            LIMIT ?
            """,
            (instance_id, limit),
        ).fetchall()
    items: list[dict] = []
    for row in rows:
        item = dict(row)
        item["evidence"] = json.loads(item.pop("evidence_json") or "[]")
        item["snapshot"] = json.loads(item.pop("snapshot_json") or "{}")
        items.append(item)
    return items


def fetch_capture_history_for_instance(db_path: Path, instance_id: str, limit: int = 120) -> list[dict]:
    with open_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT captured_at, row_count, metrics_json
            FROM capture_events
            WHERE instance_id = ?
            ORDER BY captured_at DESC
            LIMIT ?
            """,
            (instance_id, limit),
        ).fetchall()

    items: list[dict] = []
    for row in reversed(rows):
        try:
            metrics = json.loads(row["metrics_json"] or "{}")
        except json.JSONDecodeError:
            metrics = {}
        current_spend = metrics.get("current_spend")
        if current_spend is None:
            continue
        try:
            items.append(
                {
                    "captured_at": int(row["captured_at"]),
                    "current_spend": float(current_spend),
                    "increase_amount": float(metrics.get("increase_amount") or 0),
                    "baseline_spend": (
                        float(metrics["baseline_spend"])
                        if metrics.get("baseline_spend") is not None
                        else None
                    ),
                    "compare_interval_min": (
                        int(metrics["compare_interval_min"])
                        if metrics.get("compare_interval_min") is not None
                        else None
                    ),
                    "notify_threshold": (
                        float(metrics["notify_threshold"])
                        if metrics.get("notify_threshold") is not None
                        else None
                    ),
                    "row_count": row["row_count"],
                }
            )
        except (TypeError, ValueError):
            continue

    if not items:
        return items

    all_increases = [float(item["increase_amount"]) for item in items]
    by_hour: dict[int, list[float]] = {}
    for item in items:
        hour = datetime.fromtimestamp(int(item["captured_at"]) / 1000).hour
        by_hour.setdefault(hour, []).append(float(item["increase_amount"]))

    fallback_baseline = sum(all_increases) / len(all_increases) if all_increases else 0.0
    for item in items:
        hour = datetime.fromtimestamp(int(item["captured_at"]) / 1000).hour
        baseline_pool = by_hour.get(hour) or all_increases
        baseline_value = sum(baseline_pool) / len(baseline_pool) if baseline_pool else fallback_baseline
        item["baseline_increase_amount"] = round(baseline_value, 2)

    return items


def save_analysis_summary(
    db_path: Path,
    *,
    instance_id: str,
    account_id: str | None,
    account_name: str | None,
    page_type: str | None,
    page_url: str | None,
    provider: str,
    model: str,
    anomaly_type: str,
    severity: str,
    score: float,
    summary: str,
    raw_text: str,
) -> None:
    now_ms = utc_now_ms()
    with open_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO analysis_summaries (
                instance_id, account_id, account_name, page_type, page_url,
                provider, model, anomaly_type, severity, score,
                summary, raw_text, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                instance_id,
                account_id,
                account_name,
                page_type,
                page_url,
                provider,
                model,
                anomaly_type,
                severity,
                score,
                summary,
                raw_text,
                now_ms,
            ),
        )


def fetch_latest_analysis_for_instance(db_path: Path, instance_id: str) -> dict | None:
    with open_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT
                created_at,
                summary,
                provider,
                model,
                anomaly_type,
                severity
            FROM analysis_summaries
            WHERE instance_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (instance_id,),
        ).fetchone()

    return dict(row) if row else None


def fetch_recent_analyses_for_instance(db_path: Path, instance_id: str, limit: int = 10) -> list[dict]:
    with open_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                provider,
                model,
                anomaly_type,
                severity,
                score,
                summary,
                raw_text,
                created_at
            FROM analysis_summaries
            WHERE instance_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (instance_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def fetch_recent_errors_for_instance(db_path: Path, instance_id: str, limit: int = 10) -> list[dict]:
    with open_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                error_type,
                error_message,
                occurred_at,
                page_url,
                script_version
            FROM error_reports
            WHERE instance_id = ?
            ORDER BY occurred_at DESC
            LIMIT ?
            """,
            (instance_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def fetch_admin_instances(db_path: Path) -> list[dict]:
    now_ms = utc_now_ms()
    with open_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                instance_id,
                alias,
                remarks,
                account_id,
                account_name,
                page_type,
                page_url,
                script_version,
                last_seen_at,
                last_heartbeat_at,
                last_capture_at,
                last_capture_status,
                last_error,
                consecutive_error_count,
                last_row_count
            FROM script_instances
            ORDER BY
                CASE health_status
                    WHEN 'red' THEN 0
                    WHEN 'yellow' THEN 1
                    ELSE 2
                END,
                COALESCE(last_heartbeat_at, last_seen_at, 0) DESC,
                COALESCE(last_capture_at, 0) DESC
            """
        ).fetchall()

    items: list[dict] = []
    for row in rows:
        item = dict(row)
        item["health_status"] = compute_health_status(
            now_ms=now_ms,
            last_heartbeat_at=item.get("last_heartbeat_at"),
            last_capture_at=item.get("last_capture_at"),
            last_capture_status=item.get("last_capture_status"),
            consecutive_error_count=item.get("consecutive_error_count") or 0,
        )
        latest_analysis = fetch_latest_analysis_for_instance(db_path, item["instance_id"])
        item["last_analysis_at"] = latest_analysis.get("created_at") if latest_analysis else None
        item["last_analysis_summary"] = latest_analysis.get("summary") if latest_analysis else None
        item["last_analysis_provider"] = latest_analysis.get("provider") if latest_analysis else None
        item["last_analysis_model"] = latest_analysis.get("model") if latest_analysis else None
        item["last_anomaly_type"] = latest_analysis.get("anomaly_type") if latest_analysis else None
        item["last_anomaly_severity"] = latest_analysis.get("severity") if latest_analysis else None
        items.append(item)
    return items


def fetch_admin_alerts(
    db_path: Path,
    limit: int = 20,
    *,
    account_keyword: str | None = None,
    send_status: str | None = None,
    alert_kind: str | None = None,
    strategy_id: int | None = None,
    template_type: str | None = None,
    target_metric: str | None = None,
    date_from_ms: int | None = None,
    date_to_ms: int | None = None,
) -> list[dict]:
    clauses: list[str] = []
    params: list[object] = []

    if account_keyword:
        clauses.append(
            "("
            "COALESCE(account_name, '') LIKE ? "
            "OR COALESCE(account_id, '') LIKE ? "
            "OR COALESCE(instance_id, '') LIKE ?"
            ")"
        )
        keyword = f"%{account_keyword}%"
        params.extend([keyword, keyword, keyword])
    if send_status:
        clauses.append("send_status = ?")
        params.append(send_status)
    if alert_kind:
        clauses.append("alert_kind = ?")
        params.append(alert_kind)
    if strategy_id is not None:
        clauses.append("a.strategy_id = ?")
        params.append(strategy_id)
    if template_type:
        clauses.append("COALESCE(s.template_type, '') = ?")
        params.append(template_type)
    if target_metric:
        clauses.append("COALESCE(a.target_metric, '') = ?")
        params.append(target_metric)
    if date_from_ms is not None:
        clauses.append("a.triggered_at >= ?")
        params.append(date_from_ms)
    if date_to_ms is not None:
        clauses.append("a.triggered_at <= ?")
        params.append(date_to_ms)

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with open_connection(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT
                a.id,
                a.instance_id,
                a.account_id,
                a.account_name,
                a.page_type,
                a.page_url,
                a.script_version,
                a.alert_kind,
                a.title,
                a.content_preview,
                a.channel,
                a.channel_option,
                a.delivery_provider,
                a.send_status,
                a.provider_response,
                a.severity,
                a.anomaly_type,
                a.strategy_id,
                a.strategy_hit_id,
                a.capture_event_id,
                a.strategy_name,
                a.target_metric,
                a.triggered_at,
                a.created_at,
                s.template_type
            FROM alert_records a
            LEFT JOIN strategy_definitions s ON s.id = a.strategy_id
            {where_sql}
            ORDER BY a.triggered_at DESC, a.id DESC
            LIMIT ?
            """,
            (*params, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def fetch_alerts_for_instance(db_path: Path, instance_id: str, limit: int = 20) -> list[dict]:
    with open_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                instance_id,
                account_id,
                account_name,
                page_type,
                page_url,
                script_version,
                alert_kind,
                title,
                content_preview,
                channel,
                channel_option,
                delivery_provider,
                send_status,
                provider_response,
                severity,
                anomaly_type,
                strategy_id,
                strategy_hit_id,
                capture_event_id,
                strategy_name,
                target_metric,
                triggered_at,
                created_at
            FROM alert_records
            WHERE instance_id = ?
            ORDER BY triggered_at DESC, id DESC
            LIMIT ?
            """,
            (instance_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def fetch_latest_alert_for_instance_kind(
    db_path: Path,
    instance_id: str,
    alert_kind: str,
) -> dict | None:
    with open_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT
                id,
                instance_id,
                account_id,
                account_name,
                page_type,
                page_url,
                script_version,
                alert_kind,
                title,
                content_preview,
                channel,
                channel_option,
                delivery_provider,
                send_status,
                provider_response,
                severity,
                anomaly_type,
                strategy_id,
                strategy_hit_id,
                capture_event_id,
                strategy_name,
                target_metric,
                triggered_at,
                created_at
            FROM alert_records
            WHERE instance_id = ? AND alert_kind = ?
            ORDER BY triggered_at DESC, id DESC
            LIMIT 1
            """,
            (instance_id, alert_kind),
        ).fetchone()
    return dict(row) if row else None


def fetch_instance_detail(db_path: Path, instance_id: str) -> dict | None:
    items = fetch_admin_instances(db_path)
    for item in items:
        if item["instance_id"] != instance_id:
            continue
        detail = dict(item)
        detail["recent_errors"] = fetch_recent_errors_for_instance(db_path, instance_id, limit=10)
        detail["recent_alerts"] = fetch_alerts_for_instance(db_path, instance_id, limit=10)
        detail["recent_analyses"] = fetch_recent_analyses_for_instance(db_path, instance_id, limit=10)
        detail["capture_history"] = fetch_capture_history_for_instance(db_path, instance_id, limit=120)
        detail["strategy_bindings"] = fetch_instance_strategy_bindings(db_path, instance_id)
        detail["recent_strategy_hits"] = fetch_strategy_hits_for_instance(db_path, instance_id, limit=10)
        latest_point = detail["capture_history"][-1] if detail["capture_history"] else None
        detail["latest_current_spend"] = (
            float(latest_point["current_spend"]) if latest_point else None
        )
        detail["latest_increase_amount"] = (
            float(latest_point["increase_amount"]) if latest_point else None
        )
        return detail
    return None


def update_instance_metadata(
    db_path: Path,
    instance_id: str,
    *,
    alias: str | None,
    remarks: str | None,
) -> dict | None:
    normalized_alias = (alias or "").strip() or None
    normalized_remarks = (remarks or "").strip() or None
    with open_connection(db_path) as conn:
        row = conn.execute(
            "SELECT instance_id FROM script_instances WHERE instance_id = ?",
            (instance_id,),
        ).fetchone()
        if not row:
            return None
        conn.execute(
            """
            UPDATE script_instances
            SET alias = ?, remarks = ?
            WHERE instance_id = ?
            """,
            (normalized_alias, normalized_remarks, instance_id),
        )
        updated = conn.execute(
            """
            SELECT instance_id, alias, remarks
            FROM script_instances
            WHERE instance_id = ?
            """,
            (instance_id,),
        ).fetchone()
    return dict(updated) if updated else None


def delete_instance_records(db_path: Path, instance_id: str) -> bool:
    with open_connection(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM script_instances WHERE instance_id = ?",
            (instance_id,),
        ).fetchone()
        if not row:
            return False
        for table in (
            "script_heartbeats",
            "capture_events",
            "error_reports",
            "analysis_summaries",
            "strategy_hits",
            "instance_strategy_bindings",
            "alert_records",
            "script_instances",
        ):
            conn.execute(f"DELETE FROM {table} WHERE instance_id = ?", (instance_id,))
    return True


def fetch_admin_summary(db_path: Path) -> dict:
    items = fetch_admin_instances(db_path)
    counts = {"green": 0, "yellow": 0, "red": 0}
    for item in items:
        counts[item["health_status"]] += 1

    latest_capture_at = max(
        (item["last_capture_at"] for item in items if item.get("last_capture_at")),
        default=None,
    )
    latest_heartbeat_at = max(
        (item["last_heartbeat_at"] for item in items if item.get("last_heartbeat_at")),
        default=None,
    )

    with open_connection(db_path) as conn:
        total_analyses = conn.execute("SELECT COUNT(*) FROM analysis_summaries").fetchone()[0]
        total_alerts = conn.execute("SELECT COUNT(*) FROM alert_records").fetchone()[0]
        latest_alert_at = conn.execute("SELECT MAX(triggered_at) FROM alert_records").fetchone()[0]

    return {
        "total_instances": len(items),
        "green_instances": counts["green"],
        "yellow_instances": counts["yellow"],
        "red_instances": counts["red"],
        "latest_capture_at": latest_capture_at,
        "latest_heartbeat_at": latest_heartbeat_at,
        "total_analyses": total_analyses,
        "total_alerts": total_alerts,
        "latest_alert_at": latest_alert_at,
    }
