from __future__ import annotations

import json
import sqlite3
import time
from hashlib import sha1
from pathlib import Path


GREEN_HEARTBEAT_MS = 5 * 60 * 1000
GREEN_CAPTURE_MS = 10 * 60 * 1000
YELLOW_HEARTBEAT_MS = 10 * 60 * 1000
YELLOW_CAPTURE_MS = 15 * 60 * 1000
RED_CONSECUTIVE_ERRORS = 3


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
            """
        )
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(script_instances)").fetchall()
        }
        if "alias" not in columns:
            conn.execute("ALTER TABLE script_instances ADD COLUMN alias TEXT")
        if "remarks" not in columns:
            conn.execute("ALTER TABLE script_instances ADD COLUMN remarks TEXT")


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
                send_status, provider_response, severity, anomaly_type, triggered_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
    if date_from_ms is not None:
        clauses.append("triggered_at >= ?")
        params.append(date_from_ms)
    if date_to_ms is not None:
        clauses.append("triggered_at <= ?")
        params.append(date_to_ms)

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with open_connection(db_path) as conn:
        rows = conn.execute(
            f"""
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
                triggered_at,
                created_at
            FROM alert_records
            {where_sql}
            ORDER BY triggered_at DESC, id DESC
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
