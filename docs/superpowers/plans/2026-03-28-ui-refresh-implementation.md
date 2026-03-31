# UI Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the backend monitoring UI and userscript panel for responsive desktop/mobile use, add light/dark theme support, prioritize the instance health list, and add backend-only instance alias/remarks editing plus instance deletion.

**Architecture:** Keep the existing FastAPI plus server-rendered HTML approach for the backend and the single-file floating panel approach for the userscript. Add additive schema fields and JSON endpoints in the backend, then layer focused UI updates and small client-side enhancements on top of the current rendering model.

**Tech Stack:** Python, FastAPI, SQLite, inline HTML/CSS/JavaScript in `admin_ui.py`, Tampermonkey userscript with jQuery and GM storage APIs

---

### Task 1: Extend backend schema and models for instance metadata and detail metrics

**Files:**
- Modify: `code/analysis_gateway/database.py`
- Modify: `code/analysis_gateway/models.py`
- Test: `code/analysis_gateway/database.py`

- [ ] **Step 1: Add additive schema migration for alias and remarks**

Update `ensure_database()` so `script_instances` supports nullable `alias` and `remarks`, using additive `ALTER TABLE` guards after `CREATE TABLE IF NOT EXISTS`.

```python
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
```

- [ ] **Step 2: Add helper to ensure missing columns exist for old databases**

Inside `ensure_database()`, inspect `PRAGMA table_info(script_instances)` and add missing columns.

```python
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(script_instances)").fetchall()
        }
        if "alias" not in columns:
            conn.execute("ALTER TABLE script_instances ADD COLUMN alias TEXT")
        if "remarks" not in columns:
            conn.execute("ALTER TABLE script_instances ADD COLUMN remarks TEXT")
```

- [ ] **Step 3: Extend admin models with metadata and derived metrics**

Update `AdminInstanceSummary` and `AdminInstanceDetail` in `models.py`.

```python
class AdminInstanceSummary(BaseModel):
    instance_id: str
    alias: str | None = None
    remarks: str | None = None
    account_id: str | None = None
    account_name: str | None = None
    ...


class AdminInstanceDetail(AdminInstanceSummary):
    latest_current_spend: float | None = None
    latest_increase_amount: float | None = None
    recent_errors: list[AdminErrorRecord] = Field(default_factory=list)
    ...
```

- [ ] **Step 4: Run a syntax check for backend modules**

Run: `python -m py_compile code/analysis_gateway/database.py code/analysis_gateway/models.py`

Expected: command exits with no output.

- [ ] **Step 5: Commit**

```bash
git add code/analysis_gateway/database.py code/analysis_gateway/models.py
git commit -m "feat: add instance metadata fields"
```

### Task 2: Add backend queries for metadata update, deletion, sorting, and derived metrics

**Files:**
- Modify: `code/analysis_gateway/database.py`
- Test: `code/analysis_gateway/database.py`

- [ ] **Step 1: Update instance summary query to include alias and remarks**

Extend `fetch_admin_instances()` to select metadata and sort by health priority then latest heartbeat descending.

```python
        instances = conn.execute(
            """
            SELECT
                instance_id, alias, remarks, account_id, account_name, page_type, page_url,
                script_version, first_seen_at, last_seen_at, last_heartbeat_at, last_capture_at,
                last_capture_status, last_error, last_row_count, consecutive_error_count, health_status
            FROM script_instances
            ORDER BY
                CASE health_status
                    WHEN 'red' THEN 0
                    WHEN 'yellow' THEN 1
                    ELSE 2
                END,
                COALESCE(last_heartbeat_at, 0) DESC,
                COALESCE(last_capture_at, 0) DESC
            """
        ).fetchall()
```

- [ ] **Step 2: Update instance detail fetch to include metadata and latest metrics**

Extend `fetch_instance_detail()` so it returns `alias`, `remarks`, `latest_current_spend`, and `latest_increase_amount`.

```python
    latest_point = capture_history[-1] if capture_history else None
    detail["latest_current_spend"] = (
        float(latest_point["current_spend"]) if latest_point else None
    )
    detail["latest_increase_amount"] = (
        float(latest_point["increase_amount"]) if latest_point else None
    )
```

- [ ] **Step 3: Add metadata update query helper**

Add a function that updates alias and remarks for one `instance_id`.

```python
def update_instance_metadata(db_path: Path, instance_id: str, *, alias: str | None, remarks: str | None) -> dict | None:
    normalized_alias = (alias or "").strip() or None
    normalized_remarks = (remarks or "").strip() or None
    with open_connection(db_path) as conn:
        conn.execute(
            """
            UPDATE script_instances
            SET alias = ?, remarks = ?
            WHERE instance_id = ?
            """,
            (normalized_alias, normalized_remarks, instance_id),
        )
        if conn.total_changes == 0:
            return None
        row = conn.execute(
            "SELECT instance_id, alias, remarks FROM script_instances WHERE instance_id = ?",
            (instance_id,),
        ).fetchone()
        return dict(row) if row else None
```

- [ ] **Step 4: Add instance deletion helper across related tables**

Add a delete helper that removes one instance and all related records in one transaction.

```python
def delete_instance_records(db_path: Path, instance_id: str) -> bool:
    with open_connection(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM script_instances WHERE instance_id = ?",
            (instance_id,),
        ).fetchone()
        if not row:
            return False
        for table in [
            "script_heartbeats",
            "capture_events",
            "error_reports",
            "analysis_summaries",
            "alert_records",
            "script_instances",
        ]:
            conn.execute(f"DELETE FROM {table} WHERE instance_id = ?", (instance_id,))
        return True
```

- [ ] **Step 5: Run a syntax check**

Run: `python -m py_compile code/analysis_gateway/database.py`

Expected: command exits with no output.

- [ ] **Step 6: Commit**

```bash
git add code/analysis_gateway/database.py
git commit -m "feat: add backend instance metadata operations"
```

### Task 3: Expose metadata and deletion APIs in FastAPI

**Files:**
- Modify: `code/analysis_gateway/app.py`
- Modify: `code/analysis_gateway/models.py`
- Test: `code/analysis_gateway/app.py`

- [ ] **Step 1: Add request and response models for metadata editing**

Extend `models.py` with small API models.

```python
class UpdateInstanceMetadataRequest(BaseModel):
    alias: str | None = None
    remarks: str | None = None


class InstanceMetadataResponse(BaseModel):
    instance_id: str
    alias: str | None = None
    remarks: str | None = None
```

- [ ] **Step 2: Import the new database helpers and models in `app.py`**

Update imports.

```python
from database import (
    ...
    delete_instance_records,
    update_instance_metadata,
)
from models import (
    ...
    InstanceMetadataResponse,
    UpdateInstanceMetadataRequest,
)
```

- [ ] **Step 3: Add metadata update endpoint**

Create a JSON endpoint for alias and remarks updates.

```python
@app.post("/admin/api/instances/{instance_id}/meta", response_model=InstanceMetadataResponse)
def admin_update_instance_metadata(instance_id: str, payload: UpdateInstanceMetadataRequest):
    result = update_instance_metadata(
        get_db_path(),
        instance_id,
        alias=payload.alias,
        remarks=payload.remarks,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Instance not found")
    return result
```

- [ ] **Step 4: Add delete endpoint**

Create a JSON delete endpoint.

```python
@app.delete("/admin/api/instances/{instance_id}", response_model=ApiAck)
def admin_delete_instance(instance_id: str):
    deleted = delete_instance_records(get_db_path(), instance_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Instance not found")
    return ApiAck(ok=True, message="deleted", server_time=utc_now_ms())
```

- [ ] **Step 5: Run a syntax check**

Run: `python -m py_compile code/analysis_gateway/app.py code/analysis_gateway/models.py`

Expected: command exits with no output.

- [ ] **Step 6: Commit**

```bash
git add code/analysis_gateway/app.py code/analysis_gateway/models.py
git commit -m "feat: add admin instance management APIs"
```

### Task 4: Refactor shared admin theme and layout helpers

**Files:**
- Modify: `code/analysis_gateway/admin_ui.py`
- Test: `code/analysis_gateway/admin_ui.py`

- [ ] **Step 1: Add shared theme and page-shell helper functions near the top of `admin_ui.py`**

Introduce helpers for theme tokens, theme toggle script, and reusable top actions.

```python
def build_theme_bootstrap(theme_key: str = "adbudget-theme") -> str:
    return """
    <script>
    (function () {
        const key = %s;
        const stored = localStorage.getItem(key);
        const theme = stored || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
        document.documentElement.dataset.theme = theme;
    })();
    </script>
    """ % json.dumps(theme_key)
```

- [ ] **Step 2: Add shared CSS token block used by dashboard, detail, and alerts pages**

Create a helper that returns a shared `<style>` fragment with light/dark variables and common controls.

```python
def build_shared_admin_style() -> str:
    return """
    <style>
    :root {
        --font-sans: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    }
    :root[data-theme="light"] {
        --bg: #f4f7fb;
        --panel: rgba(255,255,255,0.92);
        --panel-strong: #ffffff;
        --ink: #142033;
        --muted: #607089;
        --border: rgba(148,163,184,0.22);
        --accent: #0f766e;
    }
    :root[data-theme="dark"] {
        --bg: #0f1722;
        --panel: rgba(17,24,39,0.86);
        --panel-strong: #111827;
        --ink: #e5eef9;
        --muted: #9aa8bc;
        --border: rgba(148,163,184,0.18);
        --accent: #5eead4;
    }
    </style>
    """
```

- [ ] **Step 3: Add a small shared script for manual theme override**

Provide buttons for `light`, `dark`, and `system`.

```python
def build_theme_toggle_controls() -> str:
    return """
    <div class="theme-toggle" data-theme-toggle>
        <button type="button" data-theme-choice="system">跟随系统</button>
        <button type="button" data-theme-choice="light">日间</button>
        <button type="button" data-theme-choice="dark">夜间</button>
    </div>
    """
```

- [ ] **Step 4: Run a syntax check**

Run: `python -m py_compile code/analysis_gateway/admin_ui.py`

Expected: command exits with no output.

- [ ] **Step 5: Commit**

```bash
git add code/analysis_gateway/admin_ui.py
git commit -m "refactor: add shared admin theme helpers"
```

### Task 5: Rebuild the backend dashboard with a top-priority health list and mobile-safe actions

**Files:**
- Modify: `code/analysis_gateway/admin_ui.py`
- Test: `code/analysis_gateway/admin_ui.py`

- [ ] **Step 1: Replace the current instance table section with a top health list section**

Update `build_admin_dashboard_html()` so the health list appears before alerts and uses cards that still scan well on desktop.

```python
    health_cards_html = "".join(
        f"""
        <article class="instance-card" data-instance-card data-instance-id="{html.escape(item['instance_id'])}">
            <a class="instance-card-link" href="/admin/instances/{quote(item['instance_id'], safe='')}">
                <div class="instance-card-top">
                    <div>
                        <div class="instance-title">{html.escape(item.get('alias') or format_account_identity(item.get('account_name'), item.get('account_id')))}</div>
                        <div class="instance-subtitle">{html.escape(item.get('remarks') or item.get('instance_id') or '-')}</div>
                    </div>
                    {build_chip(item["health_status"].upper(), status_chip_tone[item["health_status"]])}
                </div>
            </a>
            <div class="instance-card-actions">
                <button type="button" data-edit-instance="{html.escape(item['instance_id'])}">编辑</button>
                <button type="button" data-delete-instance="{html.escape(item['instance_id'])}" class="danger">删除</button>
            </div>
        </article>
        """
        for item in instances
    )
```

- [ ] **Step 2: Add refresh action and inline status area**

Add a refresh button in the health section header and an inline status message area.

```python
                <div class="section-actions">
                    <button type="button" class="ghost-btn" data-refresh-instances>手动刷新</button>
                </div>
...
            <div class="inline-status" data-instance-refresh-status></div>
```

- [ ] **Step 3: Add dashboard enhancement script for refresh, edit, delete, and touch-safe navigation**

Inject JS at the bottom of the page to:

- fetch `/admin/instances`
- avoid action-button navigation conflicts
- open detail pages from the card body only
- post metadata updates
- delete instances after confirmation

```javascript
document.addEventListener("click", async function (event) {
    const refreshBtn = event.target.closest("[data-refresh-instances]");
    if (refreshBtn) {
        event.preventDefault();
        await refreshInstances();
        return;
    }
    const deleteBtn = event.target.closest("[data-delete-instance]");
    if (deleteBtn) {
        event.preventDefault();
        event.stopPropagation();
        const instanceId = deleteBtn.getAttribute("data-delete-instance");
        if (!window.confirm("删除后如果脚本再次上报，该实例会重新出现。确认删除？")) {
            return;
        }
        await deleteInstance(instanceId);
    }
});
```

- [ ] **Step 4: Add responsive CSS for stacked mobile cards**

Ensure there is no reliance on horizontal table scrolling for the primary health list.

```css
@media (max-width: 860px) {
    .instance-list {
        grid-template-columns: 1fr;
    }
    .instance-card {
        padding: 16px;
    }
    .instance-card-actions {
        grid-template-columns: 1fr 1fr;
    }
}
```

- [ ] **Step 5: Run a syntax check**

Run: `python -m py_compile code/analysis_gateway/admin_ui.py`

Expected: command exits with no output.

- [ ] **Step 6: Commit**

```bash
git add code/analysis_gateway/admin_ui.py
git commit -m "feat: redesign admin dashboard health list"
```

### Task 6: Upgrade the instance detail page with top metric cards and metadata editing

**Files:**
- Modify: `code/analysis_gateway/admin_ui.py`
- Test: `code/analysis_gateway/admin_ui.py`

- [ ] **Step 1: Add two top metric cards for latest spend and delta**

Update `build_instance_detail_html()` to show the newest spend metrics immediately under the hero.

```python
    spotlight_cards = [
        ("当前总消耗", "-" if detail.get("latest_current_spend") is None else f"{float(detail['latest_current_spend']):.2f}"),
        ("窗口增量", "-" if detail.get("latest_increase_amount") is None else f"{float(detail['latest_increase_amount']):.2f}"),
    ]
```

- [ ] **Step 2: Add metadata editor panel near the top**

Render a small form for alias and remarks.

```python
            <section class="panel">
                <div class="panel-head">
                    <div>
                        <h2 class="panel-title">实例备注</h2>
                        <div class="panel-subtitle">只在后台监控系统中生效，不会同步到油猴脚本。</div>
                    </div>
                </div>
                <form class="meta-form" data-instance-meta-form data-instance-id="{html.escape(detail.get('instance_id') or '')}">
                    <input name="alias" value="{html.escape(detail.get('alias') or '')}" />
                    <textarea name="remarks">{html.escape(detail.get('remarks') or '')}</textarea>
                    <button type="submit">保存备注</button>
                </form>
            </section>
```

- [ ] **Step 3: Add delete action to detail page**

Place a guarded delete button in the hero action area.

```python
                    <div class="hero-actions">
                        <a class="back-link" href="/admin">返回总览</a>
                        <button type="button" class="danger-btn" data-delete-instance="{html.escape(detail.get('instance_id') or '')}">删除实例</button>
                    </div>
```

- [ ] **Step 4: Add detail-page script for save and delete**

Use fetch for metadata updates and deletion.

```javascript
const form = document.querySelector("[data-instance-meta-form]");
if (form) {
    form.addEventListener("submit", async function (event) {
        event.preventDefault();
        const instanceId = form.getAttribute("data-instance-id");
        const payload = {
            alias: form.elements.alias.value,
            remarks: form.elements.remarks.value,
        };
        await fetch(`/admin/api/instances/${encodeURIComponent(instanceId)}/meta`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
    });
}
```

- [ ] **Step 5: Run a syntax check**

Run: `python -m py_compile code/analysis_gateway/admin_ui.py`

Expected: command exits with no output.

- [ ] **Step 6: Commit**

```bash
git add code/analysis_gateway/admin_ui.py
git commit -m "feat: enhance instance detail experience"
```

### Task 7: Align the alerts page to the new theme system

**Files:**
- Modify: `code/analysis_gateway/admin_ui.py`
- Test: `code/analysis_gateway/admin_ui.py`

- [ ] **Step 1: Reuse shared theme helpers in `build_alerts_page_html()`**

Replace duplicated fixed light-theme tokens with the shared theme token block.

```python
    return f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        {build_theme_bootstrap()}
        {build_shared_admin_style()}
```

- [ ] **Step 2: Add theme controls to the alerts page header**

```python
                        {build_theme_toggle_controls()}
```

- [ ] **Step 3: Verify responsive filter layout still works with dark mode**

Run: `python -m py_compile code/analysis_gateway/admin_ui.py`

Expected: command exits with no output.

- [ ] **Step 4: Commit**

```bash
git add code/analysis_gateway/admin_ui.py
git commit -m "feat: unify alerts page theme behavior"
```

### Task 8: Redesign the userscript panel for theme support and narrow-screen usability

**Files:**
- Modify: `code/userscripts/磁力金牛财务报警助手.user.js`
- Test: `code/userscripts/磁力金牛财务报警助手.user.js`

- [ ] **Step 1: Add theme state persisted in GM storage**

Extend `state.config` with a theme mode.

```javascript
        config: {
            accountIdOverride: GM_getValue("account_id_override", ""),
            accountNameOverride: GM_getValue("account_name_override", ""),
            refreshIntervalMin: GM_getValue("refresh_interval_min", 5),
            compareIntervalMin: GM_getValue("compare_interval_min", 30),
            notifyThreshold: GM_getValue("notify_threshold", 1000),
            aiEnabled: GM_getValue("ai_enabled", true),
            aiProvider: GM_getValue("ai_provider", "deepseek"),
            themeMode: GM_getValue("theme_mode", "system"),
            backendBaseUrl: normalizeBackendBaseUrl(...),
        },
```

- [ ] **Step 2: Refactor styles to use CSS variables and light/dark panel themes**

Rework `addStyles()` to declare panel variables and a theme attribute.

```css
#ad-budget-sentry-panel {
    --panel-bg: rgba(255,255,255,0.94);
    --panel-ink: #142033;
    --panel-muted: #617085;
    --panel-border: rgba(148,163,184,0.28);
}
#ad-budget-sentry-panel[data-theme="dark"] {
    --panel-bg: rgba(17,24,39,0.96);
    --panel-ink: #e6edf7;
    --panel-muted: #97a7bc;
    --panel-border: rgba(148,163,184,0.18);
}
```

- [ ] **Step 3: Add theme selector control in the config area**

Provide `system`, `light`, and `dark` options.

```javascript
                        <div class="field-group">
                            <label for="theme-mode">界面主题</label>
                            <select id="theme-mode">
                                <option value="system">跟随系统</option>
                                <option value="light">日间模式</option>
                                <option value="dark">夜间模式</option>
                            </select>
                        </div>
```

- [ ] **Step 4: Add runtime theme resolution and apply it during render**

Add helper functions that resolve the final theme from system plus override.

```javascript
    function resolveThemeMode() {
        if (state.config.themeMode === "light" || state.config.themeMode === "dark") {
            return state.config.themeMode;
        }
        return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }

    function applyPanelTheme() {
        const panel = document.getElementById(CONFIG.panelId);
        if (!panel) return;
        panel.setAttribute("data-theme", resolveThemeMode());
    }
```

- [ ] **Step 5: Improve narrow-screen layout and touch targets**

Add media rules and button sizing.

```css
@media (max-width: 640px) {
    #ad-budget-sentry-panel {
        width: min(92vw, 360px);
        top: 10px;
        right: 10px;
        max-height: 82vh;
    }
    #ad-budget-sentry-panel .button-row {
        grid-template-columns: 1fr;
    }
    #ad-budget-sentry-panel button,
    #ad-budget-sentry-panel select,
    #ad-budget-sentry-panel input {
        min-height: 36px;
    }
}
```

- [ ] **Step 6: Run a syntax check**

Run: `node -e "new Function(require('fs').readFileSync('code/userscripts/磁力金牛财务报警助手.user.js','utf8'))"`

Expected: command exits with no output.

- [ ] **Step 7: Commit**

```bash
git add code/userscripts/磁力金牛财务报警助手.user.js
git commit -m "feat: refresh userscript panel theme and layout"
```

### Task 9: Verify end-to-end rendering and regression safety

**Files:**
- Modify: `code/analysis_gateway/admin_ui.py`
- Modify: `code/analysis_gateway/app.py`
- Modify: `code/analysis_gateway/database.py`
- Modify: `code/analysis_gateway/models.py`
- Modify: `code/userscripts/磁力金牛财务报警助手.user.js`

- [ ] **Step 1: Run backend syntax verification**

Run: `python -m py_compile code/analysis_gateway/admin_ui.py code/analysis_gateway/app.py code/analysis_gateway/database.py code/analysis_gateway/models.py`

Expected: command exits with no output.

- [ ] **Step 2: Run userscript syntax verification**

Run: `node -e "new Function(require('fs').readFileSync('code/userscripts/磁力金牛财务报警助手.user.js','utf8'))"`

Expected: command exits with no output.

- [ ] **Step 3: Run a quick app import smoke test**

Run: `python -c "import sys; sys.path.insert(0, 'code/analysis_gateway'); import app; print('ok')"`

Expected: output contains `ok`.

- [ ] **Step 4: Review git diff for unintended changes**

Run: `git diff --stat`

Expected: only the backend UI, backend data/API files, and userscript file are modified for implementation.

- [ ] **Step 5: Commit**

```bash
git add code/analysis_gateway/admin_ui.py code/analysis_gateway/app.py code/analysis_gateway/database.py code/analysis_gateway/models.py code/userscripts/磁力金牛财务报警助手.user.js
git commit -m "feat: ship responsive monitoring UI refresh"
```
