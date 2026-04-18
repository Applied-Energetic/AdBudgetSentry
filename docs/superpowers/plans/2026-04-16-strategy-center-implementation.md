# Strategy Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single hard-coded threshold alert flow with a strategy-centered backend, add strategy management and instance binding UI, and simplify the userscript into a pure spend collector.

**Architecture:** Introduce persistent strategy entities plus a small execution layer in the FastAPI backend. Keep current instance and operational alert flows, but route spend-based anomaly alerting through bound strategies. Extend the React admin with a strategy page and strategy-aware instance and alert views. Simplify the userscript contract to send only raw collection data.

**Tech Stack:** FastAPI, SQLite, Pydantic, unittest, React, TypeScript, Vite, Tampermonkey userscript

---

## File Structure

- Modify: `code/analysis_gateway/database.py`
  - add schema migration, strategy tables, strategy queries, hit persistence, alert linkage, default seeding
- Modify: `code/analysis_gateway/models.py`
  - add strategy and hit response models plus updated alert and instance detail shapes
- Create: `code/analysis_gateway/strategy_engine.py`
  - strategy execution primitives and built-in template evaluators
- Modify: `code/analysis_gateway/app.py`
  - replace ingest strategy path, expose admin APIs for strategies and bindings, update alert flow
- Modify: `code/analysis_gateway/tests/test_analysis_and_alerts.py`
  - replace threshold-first assertions with strategy-engine and alert-linkage coverage
- Create: `code/analysis_gateway/tests/test_strategy_admin_api.py`
  - cover CRUD, binding, hits, and admin responses
- Modify: `code/analysis_gateway/admin_frontend/src/lib/types.ts`
  - add strategy, binding, hit, and alert extension types
- Modify: `code/analysis_gateway/admin_frontend/src/lib/api.ts`
  - add strategy CRUD and binding APIs
- Modify: `code/analysis_gateway/admin_frontend/src/App.tsx`
  - register strategy route
- Modify: `code/analysis_gateway/admin_frontend/src/components/app-sidebar.tsx`
  - add strategy navigation item
- Modify: `code/analysis_gateway/admin_frontend/src/components/admin-shell.tsx`
  - add page metadata for strategy pages
- Create: `code/analysis_gateway/admin_frontend/src/pages/strategies-page.tsx`
  - list strategies and manage create or edit actions
- Modify: `code/analysis_gateway/admin_frontend/src/pages/instance-detail-page.tsx`
  - show bindings and recent strategy hits
- Modify: `code/analysis_gateway/admin_frontend/src/pages/alerts-page.tsx`
  - show strategy linkage and new filters
- Modify: `code/analysis_gateway/admin_frontend/src/lib/format.ts`
  - format strategy template and metric labels
- Modify: `code/userscripts/磁力金牛财务报警助手.user.js`
  - remove strategy and AI settings and keep refresh-only configuration

## Task 1: Lock Backend Behavior With Failing Tests

**Files:**
- Modify: `code/analysis_gateway/tests/test_analysis_and_alerts.py`
- Create: `code/analysis_gateway/tests/test_strategy_admin_api.py`

- [ ] **Step 1: Write failing backend tests for strategy persistence and execution**

Cover:
- default metric registry seeding includes `spend`
- default threshold strategy exists
- ingest with a bound threshold strategy creates a strategy hit and a linked alert
- multiple bound strategies create multiple alerts
- strategy CRUD and binding APIs expose expected shapes

- [ ] **Step 2: Run backend tests to verify they fail for the missing strategy system**

Run:
```powershell
python -m unittest discover -s tests
```

Expected:
- failures referencing missing strategy tables, missing API routes, or missing fields

## Task 2: Implement Backend Schema and Strategy Engine

**Files:**
- Modify: `code/analysis_gateway/database.py`
- Modify: `code/analysis_gateway/models.py`
- Create: `code/analysis_gateway/strategy_engine.py`

- [ ] **Step 1: Add strategy and metric registry schema plus alert linkage migrations**

- [ ] **Step 2: Seed reserved metrics and default strategies idempotently**

- [ ] **Step 3: Add query helpers for strategies, bindings, hits, and enriched alerts**

- [ ] **Step 4: Implement built-in strategy evaluators in `strategy_engine.py`**

- [ ] **Step 5: Re-run backend tests and keep iterating until green**

Run:
```powershell
python -m unittest discover -s tests
```

## Task 3: Route Ingest Through Strategies

**Files:**
- Modify: `code/analysis_gateway/app.py`
- Modify: `code/analysis_gateway/database.py`
- Modify: `code/analysis_gateway/models.py`

- [ ] **Step 1: Replace `analyze_ingest_payload` spend alert path with instance-bound strategy evaluation**

- [ ] **Step 2: Persist strategy hits and linked alerts**

- [ ] **Step 3: Preserve offline and capture-failure operational alerts**

- [ ] **Step 4: Keep ingest backward compatible with the old metrics payload while supporting the simplified userscript payload**

- [ ] **Step 5: Re-run backend tests and add focused assertions if regressions appear**

Run:
```powershell
python -m unittest discover -s tests
```

## Task 4: Expose Strategy Admin APIs

**Files:**
- Modify: `code/analysis_gateway/app.py`
- Modify: `code/analysis_gateway/models.py`

- [ ] **Step 1: Add endpoints for strategy listing, creation, update, deletion**

- [ ] **Step 2: Add endpoints for instance bindings and strategy-hit inspection**

- [ ] **Step 3: Return strategy-enriched alert payloads**

- [ ] **Step 4: Re-run backend tests**

Run:
```powershell
python -m unittest discover -s tests
```

## Task 5: Add React Strategy Management UI

**Files:**
- Modify: `code/analysis_gateway/admin_frontend/src/lib/types.ts`
- Modify: `code/analysis_gateway/admin_frontend/src/lib/api.ts`
- Modify: `code/analysis_gateway/admin_frontend/src/App.tsx`
- Modify: `code/analysis_gateway/admin_frontend/src/components/app-sidebar.tsx`
- Modify: `code/analysis_gateway/admin_frontend/src/components/admin-shell.tsx`
- Create: `code/analysis_gateway/admin_frontend/src/pages/strategies-page.tsx`
- Modify: `code/analysis_gateway/admin_frontend/src/pages/instance-detail-page.tsx`
- Modify: `code/analysis_gateway/admin_frontend/src/pages/alerts-page.tsx`
- Modify: `code/analysis_gateway/admin_frontend/src/lib/format.ts`

- [ ] **Step 1: Extend shared types and API client with strategy shapes**

- [ ] **Step 2: Add the strategy route and sidebar entry**

- [ ] **Step 3: Build the strategy list and create or edit UI**

- [ ] **Step 4: Add instance binding management and recent hit rendering on the instance page**

- [ ] **Step 5: Add strategy columns and filters on the alerts page**

- [ ] **Step 6: Build the frontend bundle and fix TypeScript or UI regressions**

Run:
```powershell
npm.cmd run build
```

Workdir:
```text
E:\Code\AdBudgetSentry\code\analysis_gateway\admin_frontend
```

## Task 6: Simplify The Userscript

**Files:**
- Modify: `code/userscripts/磁力金牛财务报警助手.user.js`

- [ ] **Step 1: Write or update tests if a script test surface exists; otherwise rely on targeted manual verification**

- [ ] **Step 2: Remove strategy, AI, threshold, compare-window, and account-override settings from the UI and persistence**

- [ ] **Step 3: Keep refresh interval configuration and raw spend collection**

- [ ] **Step 4: Update payload construction to send collection-only data**

- [ ] **Step 5: Verify the script still posts heartbeat and ingest payloads without the removed fields**

## Task 7: Final Verification

**Files:**
- Modify as needed based on verification failures

- [ ] **Step 1: Run backend test suite**

Run:
```powershell
python -m unittest discover -s tests
```

- [ ] **Step 2: Run frontend production build**

Run:
```powershell
npm.cmd run build
```

Workdir:
```text
E:\Code\AdBudgetSentry\code\analysis_gateway\admin_frontend
```

- [ ] **Step 3: Inspect git diff and ensure only intended files changed**

Run:
```powershell
git -c safe.directory=E:/Code/AdBudgetSentry status --short
git -c safe.directory=E:/Code/AdBudgetSentry diff --stat
```

- [ ] **Step 4: If validation is clean, stage and commit on the feature branch with a Lore-format message**

## Self-Review

- Spec coverage:
  - strategy entities, admin CRUD, instance binding, metric registry, alert linkage, userscript simplification, and verification are all represented in dedicated tasks
- Placeholder scan:
  - no `TODO`, `TBD`, or “implement later” placeholders remain
- Type consistency:
  - strategy, binding, hit, alert-linkage, and metric registry terms are used consistently across backend, frontend, and userscript tasks
