# Admin Frontend Separation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 React + TypeScript + Vite + Tailwind + shadcn/ui 接管后台总览、告警页和实例详情页，同时保留现有 FastAPI 业务接口与数据流。

**Architecture:** 新增独立前端工程输出静态资源，由 FastAPI 托管并将后台 HTML 路由切换到 SPA 入口。现有 `/admin/api/*` 接口继续复用，前端负责页面布局、组件组合和数据展示。

**Tech Stack:** FastAPI, Python, React, TypeScript, Vite, Tailwind CSS, shadcn/ui, React Router, Recharts, SQLite

---

## File Structure

- Create: `code/analysis_gateway/admin_frontend/` - 新后台前端工程
- Create: `code/analysis_gateway/admin_frontend/package.json` - 前端依赖与脚本
- Create: `code/analysis_gateway/admin_frontend/tsconfig*.json` - TypeScript 配置
- Create: `code/analysis_gateway/admin_frontend/vite.config.ts` - Vite 构建配置
- Create: `code/analysis_gateway/admin_frontend/index.html` - 前端入口模板
- Create: `code/analysis_gateway/admin_frontend/src/main.tsx` - React 入口
- Create: `code/analysis_gateway/admin_frontend/src/App.tsx` - 路由根组件
- Create: `code/analysis_gateway/admin_frontend/src/lib/` - 工具、API、格式化函数
- Create: `code/analysis_gateway/admin_frontend/src/components/` - 共享布局和 UI 组件
- Create: `code/analysis_gateway/admin_frontend/src/pages/` - Dashboard / Alerts / Instance 页面
- Create: `code/analysis_gateway/admin_frontend/src/styles/globals.css` - Tailwind 和设计变量
- Create: `code/analysis_gateway/admin_frontend/src/components/ui/*` - shadcn/ui 基础组件
- Modify: `code/analysis_gateway/app.py` - 静态资源托管与 SPA 路由接入
- Modify: `code/analysis_gateway/admin_ui.py` - 降级为可选遗留模板或最小保留，不再作为主后台实现
- Test: `code/analysis_gateway/tests/test_admin_ui_foundation.py` - 调整为新路由/新标题 smoke checks
- Create: `code/analysis_gateway/tests/test_admin_spa_routes.py` - 验证 SPA 路由返回

## Task 1: Scaffold frontend app

**Files:**
- Create: `code/analysis_gateway/admin_frontend/package.json`
- Create: `code/analysis_gateway/admin_frontend/tsconfig.json`
- Create: `code/analysis_gateway/admin_frontend/tsconfig.app.json`
- Create: `code/analysis_gateway/admin_frontend/tsconfig.node.json`
- Create: `code/analysis_gateway/admin_frontend/vite.config.ts`
- Create: `code/analysis_gateway/admin_frontend/index.html`

- [ ] Write the frontend scaffold files
- [ ] Install frontend dependencies
- [ ] Verify `npm run build` can execute against the empty scaffold

## Task 2: Create the shared frontend foundation

**Files:**
- Create: `code/analysis_gateway/admin_frontend/src/main.tsx`
- Create: `code/analysis_gateway/admin_frontend/src/App.tsx`
- Create: `code/analysis_gateway/admin_frontend/src/styles/globals.css`
- Create: `code/analysis_gateway/admin_frontend/src/lib/utils.ts`
- Create: `code/analysis_gateway/admin_frontend/src/lib/format.ts`
- Create: `code/analysis_gateway/admin_frontend/src/components/app-shell.tsx`
- Create: `code/analysis_gateway/admin_frontend/src/components/page-header.tsx`
- Create: `code/analysis_gateway/admin_frontend/src/components/kpi-card.tsx`
- Create: `code/analysis_gateway/admin_frontend/src/components/empty-state.tsx`
- Create: `code/analysis_gateway/admin_frontend/src/components/ui/*`

- [ ] Add Tailwind base styles and CSS variables for the SaaS admin visual system
- [ ] Add router shell and top-level app frame
- [ ] Add core shadcn/ui primitives needed by the three pages
- [ ] Run `npm run build`

## Task 3: Build API client and data mappers

**Files:**
- Create: `code/analysis_gateway/admin_frontend/src/lib/api.ts`
- Create: `code/analysis_gateway/admin_frontend/src/lib/types.ts`
- Create: `code/analysis_gateway/admin_frontend/src/lib/dashboard.ts`

- [ ] Define TypeScript types matching current FastAPI admin APIs
- [ ] Implement fetch helpers for summary, instances, alerts, and instance detail
- [ ] Implement mapper helpers for chart series, table rows, and status labels
- [ ] Run `npm run build`

## Task 4: Implement dashboard page

**Files:**
- Create: `code/analysis_gateway/admin_frontend/src/pages/dashboard-page.tsx`
- Modify: `code/analysis_gateway/admin_frontend/src/App.tsx`
- Create: `code/analysis_gateway/admin_frontend/src/components/dashboard/*`

- [ ] Build sidebar, top toolbar, KPI grid, charts row, and tables row
- [ ] Use shadcn/ui cards, tables, badges, inputs, and buttons
- [ ] Keep current admin data intact while redesigning the presentation only
- [ ] Run `npm run build`

## Task 5: Implement alerts page

**Files:**
- Create: `code/analysis_gateway/admin_frontend/src/pages/alerts-page.tsx`
- Create: `code/analysis_gateway/admin_frontend/src/components/alerts/*`
- Modify: `code/analysis_gateway/admin_frontend/src/App.tsx`

- [ ] Build filters, summary cards, alert list, and export action
- [ ] Preserve existing query-parameter behavior and CSV export link
- [ ] Run `npm run build`

## Task 6: Implement instance detail page

**Files:**
- Create: `code/analysis_gateway/admin_frontend/src/pages/instance-detail-page.tsx`
- Create: `code/analysis_gateway/admin_frontend/src/components/instance-detail/*`
- Modify: `code/analysis_gateway/admin_frontend/src/App.tsx`

- [ ] Build top metric cards, base info cards, trend chart, analysis list, alerts list, and errors list
- [ ] Preserve metadata edit and delete-instance actions through existing APIs
- [ ] Run `npm run build`

## Task 7: Serve the SPA from FastAPI

**Files:**
- Modify: `code/analysis_gateway/app.py`
- Create: `code/analysis_gateway/admin_frontend/dist/` after build
- Create: `code/analysis_gateway/tests/test_admin_spa_routes.py`

- [ ] Mount the frontend build output as static assets
- [ ] Change `/admin`, `/admin/alerts`, and `/admin/instances/{instance_id}` to return SPA HTML
- [ ] Keep `/admin/api/*` and CSV export routes unchanged
- [ ] Add tests covering the HTML entry route behavior
- [ ] Run Python tests and `npm run build`

## Task 8: Clean up legacy coupling and verify end to end

**Files:**
- Modify: `code/analysis_gateway/admin_ui.py`
- Modify: `code/analysis_gateway/tests/test_admin_ui_foundation.py`
- Modify: `README.md` or `scripts/WINDOWS-START.md` if startup commands need frontend build notes

- [ ] Remove assumptions that admin HTML is rendered by Python templates
- [ ] Update tests so they validate the new admin shell contract instead of old string templates
- [ ] Run `python -m unittest`
- [ ] Run `python -m py_compile admin_ui.py app.py database.py models.py`
- [ ] Run `npm run build`

## Task 9: Commit and push

**Files:**
- Modify: repository git state

- [ ] Stage only the files relevant to the frontend separation work
- [ ] Commit with a focused message describing the first admin frontend version
- [ ] Push to `origin`
