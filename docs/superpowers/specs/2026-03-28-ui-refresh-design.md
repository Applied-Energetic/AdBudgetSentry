# AdBudgetSentry UI Refresh Design

## Goal

Upgrade the userscript panel and backend monitoring UI into a cohesive, responsive, professional control surface that works on mobile and desktop, supports day/night themes, prioritizes instance health visibility, and adds backend-only instance metadata management.

## Scope

This design covers two surfaces:

1. `code/userscripts/磁力金牛财务报警助手.user.js`
2. `code/analysis_gateway/admin_ui.py` with supporting FastAPI/database/model changes

This design does not introduce a new frontend framework. It preserves the current server-rendered backend approach and the single-panel userscript architecture.

## User-Confirmed Decisions

- Visual direction: professional panel
- Theme behavior: follow system by default, allow manual override, remember override
- Instance health ordering: red, then yellow, then green; within the same health tier sort by latest heartbeat descending
- Instance alias and remarks: maintained and displayed only in backend monitoring system
- Instance deletion: supported from backend monitoring system
- No visual companion workflow

## Product Intent

The backend should become the operational cockpit. It owns multi-instance monitoring, instance metadata, deletion, health prioritization, and detail drill-down.

The userscript should remain a lightweight local capture companion. It should surface the current status and controls cleanly, but it should not become a second admin system.

## Design Principles

### 1. First-screen clarity

The first visible area on every screen must answer the operator's most urgent question:

- Backend dashboard: which instances need attention right now
- Instance detail: what is the current spend and recent delta right now
- Userscript panel: is this page collecting correctly and what are the latest numbers

### 2. Mobile correctness before decoration

The current backend is desktop-first and relies on scrollable tables. The redesign will move the critical instance list to mobile-safe tappable cards while preserving dense desktop scanning.

The userscript panel will reduce layout fragility on narrow screens, enlarge touch targets, and avoid interaction patterns that depend on precise mouse dragging.

### 3. Theme coherence

All UI surfaces will use tokenized colors and spacing so light and dark mode are two expressions of the same interface rather than separate designs.

### 4. Operational honesty

Deleting an instance only removes backend monitoring records and metadata. If a userscript instance continues reporting afterward, it will reappear. This behavior will be explicit in the interface copy.

## Proposed Approach

### Recommended Approach: server-rendered backend with targeted client enhancement

Keep the backend pages in `admin_ui.py`, add shared theme tokens and reusable HTML helpers, and use small amounts of vanilla JavaScript for:

- manual refresh
- theme switching
- mobile-safe click handling
- instance metadata editing
- instance deletion

This matches the codebase, minimizes risk, and delivers the requested UI improvements without turning the task into a frontend rewrite.

### Alternatives Considered

#### Alternative A: lightweight SPA backend

Rejected for this phase. It improves future extensibility but is disproportionate to the current system and would delay delivery.

#### Alternative B: visual-only refresh without data changes

Rejected because alias, remarks, and deletion are core requested capabilities and require backend persistence.

## Information Architecture

## Backend Dashboard

### Top section

The top of `/admin` will be reorganized to prioritize instance health:

1. compact hero with title, environment summary, theme toggle, and refresh action
2. instance health list as the primary top module
3. summary metrics as secondary context
4. recent alerts below the health list

### Instance health list

The current table will become a hybrid list:

- Desktop: card-table hybrid with aligned columns for fast scanning
- Mobile: stacked cards with the full card tappable

Each instance item shows:

- alias if present, otherwise account name and account ID
- remarks preview if present
- health status chip
- latest heartbeat time
- latest capture time
- latest capture status and last error preview
- last anomaly type and severity
- script version

Each item supports:

- tap/click to open detail
- metadata edit action
- delete action

Manual refresh appears in the section header and refreshes the instance list without requiring a full page reload when JavaScript is available.

### Ordering

Instances are sorted:

1. by health priority: red, yellow, green
2. by latest heartbeat descending

### Empty states

If there are no instances, show a clean zero-state that explains the system is waiting for script heartbeat and ingest events.

## Instance Detail

The current detail page already has trend, analysis, alerts, and errors. The redesign changes the top information hierarchy.

### New top summary strip

Immediately below the hero, add two prominent metric cards:

- current total spend
- current window delta

These values are derived from the latest capture point and displayed before the larger history/trend sections.

### Metadata section

Add a backend-owned metadata editor for:

- alias
- remarks

This appears near the top of the detail page so operators can label an instance without leaving the page.

### Remaining sections

Preserve existing sections but improve visual hierarchy:

- trend chart
- recent analyses
- capture history
- recent alerts
- recent errors

## Alerts Page

The alerts page is not the primary focus, but theme coherence and responsive token reuse will be applied so it does not visually diverge from dashboard and detail pages.

## Userscript Panel

The userscript remains a single floating panel, but it gets a cleaner professional layout.

### Layout changes

- tighter header
- clearer split between key metrics, connection status, and actions
- stronger emphasis on total spend and window delta
- more restrained analysis box styling
- improved config drawer hierarchy

### Responsive behavior

- reduced default width on narrow screens
- safe max-height and internal scrolling
- larger tap targets for action buttons and disclosure controls
- panel drag remains for desktop but must not block basic mobile use

### Theme behavior

- default theme follows system preference
- users can override to light or dark
- override is persisted in `GM_setValue`

### Non-goals

- no multi-instance list in the userscript
- no alias/remarks editing in the userscript
- no deletion controls in the userscript

## Data Model Changes

## `script_instances`

Add two nullable columns:

- `alias`
- `remarks`

These fields belong to the backend only and are keyed by `instance_id`.

## Derived detail metrics

Add explicit detail fields derived from latest capture history:

- `latest_current_spend`
- `latest_increase_amount`

This avoids template-layer parsing and makes the detail UI deterministic.

## Deletion semantics

Deleting an instance removes backend records associated with the selected `instance_id`, including:

- `script_instances`
- `script_heartbeats`
- `capture_events`
- `error_reports`
- `analysis_summaries`
- `alert_records`

Because the userscript can report again later, deletion is a backend cleanup operation, not a permanent block.

## Backend API Changes

### Add instance metadata update endpoint

Add a JSON endpoint to update alias and remarks for one instance.

Expected behavior:

- validates instance existence
- trims input
- allows blank alias/remarks to clear the value
- returns updated metadata payload

### Add instance deletion endpoint

Add a JSON endpoint to delete one instance and its related monitoring records.

Expected behavior:

- requires explicit instance id
- returns deletion success status
- frontend asks for confirmation before calling it

### Reuse existing instance list endpoint

Manual refresh on dashboard should prefer reusing the existing `/admin/instances` JSON endpoint rather than inventing a parallel health-list endpoint, unless the current payload proves insufficient during implementation.

## Responsive Design Rules

## Desktop

- keep fast-scan density
- preserve side-by-side sections where useful
- maintain aligned health/status fields for comparison across instances

## Mobile

- replace health table dependence with stacked cards
- make the entire instance card tappable
- keep action buttons separated from the main tap target to avoid accidental navigation
- prevent horizontal scrolling in the main instance list
- allow internal horizontal scroll only for dense history tables where unavoidable

## Theme System

Use shared CSS tokens for:

- page background
- panel background
- elevated surfaces
- borders
- primary text
- secondary text
- status colors
- action accents

Theme resolution order:

1. explicit user override from local storage / GM storage
2. system `prefers-color-scheme`
3. default light mode fallback

The backend stores theme preference client-side only. No database persistence is needed.

## Interaction Details

## Dashboard manual refresh

- button in the instance health section header
- JavaScript fetches the latest instance list JSON and re-renders the list
- fallback remains a normal page reload if JS enhancement fails

## Mobile navigation correctness

The current backend uses clickable rows. The redesign will avoid fragile row-only interaction on mobile by making the primary content block an anchor-driven card with explicit action buttons. The action buttons must stop propagation so edit/delete do not trigger navigation.

## Alias and remarks editing

- primary edit surface: instance detail page
- optional secondary quick-edit trigger on dashboard cards
- save inline without full-page submission when JS is available
- show success/error feedback near the form

## Instance deletion

- available on detail page and optionally dashboard quick action
- requires confirm step
- after deletion, return user to dashboard or remove card from current list
- UI copy must explain the instance may reappear if the script reports again

## Error Handling

- failed refresh shows inline warning and preserves previous list content
- failed metadata update keeps user input visible and shows inline error
- failed deletion preserves UI state and shows inline error
- missing latest capture metrics on detail page show `-` instead of misleading zero

## Testing Strategy

### Backend

- schema migration tests for additive columns
- instance metadata update tests
- instance deletion tests across related tables
- ordering tests for red/yellow/green plus latest heartbeat sort
- detail payload tests for latest spend and delta fields

### UI behavior

- dashboard HTML contains top health section before alerts
- detail HTML contains the two new metric cards
- mobile class names and action containers render correctly
- theme toggle script applies the correct theme attribute

### Manual verification

- desktop light mode
- desktop dark mode
- mobile-width dashboard
- mobile-width instance detail
- userscript panel in light and dark mode
- tap navigation on mobile emulation
- metadata save and delete flows

## Implementation Boundaries

This work should stay focused on the requested UI and instance-management improvements.

It should not:

- replace the backend rendering system
- redesign analysis logic
- change userscript reporting semantics
- add permanent suppression or blacklist logic for deleted instances

## Risks

### Repeated CSS in `admin_ui.py`

Theme support touches multiple inline style blocks. This is manageable, but shared helpers should be introduced where they reduce duplication without forcing a large refactor.

### Existing mojibake strings

Several current Chinese strings are encoding-corrupted. Edits inside large HTML strings must be surgical to avoid making this worse.

### Refresh performance

The existing instance list query already performs non-trivial work. Manual refresh should reuse current query logic first, then optimize only if it proves slow.

## Success Criteria

The redesign is successful when:

- the backend dashboard opens with the instance health list at the top
- instance ordering is red/yellow/green with latest heartbeat tie-break
- operators can refresh, relabel, remark, and delete instances from the backend
- instance detail shows current total spend and window delta in top-level cards
- mobile users can reliably tap into instance details without row-selection bugs
- backend and userscript both support light/dark themes with system-follow plus manual override
- the userscript panel looks cleaner and remains usable on narrow screens
