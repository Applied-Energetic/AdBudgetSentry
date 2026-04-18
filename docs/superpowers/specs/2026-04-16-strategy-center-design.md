# AdBudgetSentry Strategy Center Design

## Goal

Build a strategy-centered alerting system where each instance can bind multiple strategies, each strategy can trigger independent alerts, and the admin backend can manage strategies, bindings, and strategy-caused alerts.

## Confirmed Product Decisions

- Tampermonkey becomes a pure data collection client.
- The userscript keeps only one configurable setting: refresh interval.
- Strategy configuration moves entirely to the backend admin.
- The first phase reserves a metric registry and extensible metric fields.
- Only the `spend` metric is actually executable in phase one.
- A single ingest can trigger multiple strategies.
- Each triggered strategy produces its own independent alert.
- New strategies in phase one are created from built-in templates, not custom expressions.
- Work is developed on a dedicated feature branch and merged after validation.

## Current Problems

- Alerting logic is effectively hard-coded in `anomaly.py`.
- Strategy concepts do not exist in the persistence model.
- Instances cannot bind different sets of strategies.
- Alerts cannot be traced back to a concrete strategy entity.
- The userscript still owns threshold, compare window, and AI-related settings.
- Existing admin pages do not expose strategy management or strategy-hit history.

## Target Architecture

The ingest pipeline becomes:

1. Userscript captures raw metrics and context.
2. Backend saves the capture event.
3. Backend loads active strategy bindings for the instance.
4. Backend executes each bound strategy independently.
5. Triggered strategies create strategy-hit records.
6. Each triggered strategy sends or skips one independent alert with its own cooldown.
7. The admin backend exposes strategy definitions, bindings, hits, and alert relationships.

Offline and capture-failure alerts remain as backend-owned operational alerts and do not become instance-configured strategies in phase one.

## Domain Model

### Metric Registry

Table: `metric_registry`

Purpose:
- Register supported and reserved metrics.
- Provide a backend-owned list for future expansion.

Phase-one rows:
- `spend` as active and executable
- reserved placeholders such as `impressions`, `clicks`, `ctr`, `accelerated_spend`, `creative_boost_spend`, `video_3s`, `video_5s`, `video_complete`, `yellow_cart_clicks`, `product_card_clicks`, `merchant_coupon_penetration`

Suggested fields:
- `metric_key`
- `display_name`
- `description`
- `unit`
- `is_enabled`
- `is_strategy_ready`
- `created_at`
- `updated_at`

### Strategy Definition

Table: `strategy_definitions`

Purpose:
- Store reusable strategy configurations.

Suggested fields:
- `id`
- `name`
- `description`
- `template_type`
- `target_metric`
- `params_json`
- `enabled`
- `is_default`
- `auto_bind_new_instances`
- `created_at`
- `updated_at`

Phase-one template types:
- `window_threshold`
- `historical_baseline`

### Instance Binding

Table: `instance_strategy_bindings`

Purpose:
- Bind strategies to instances.

Suggested fields:
- `id`
- `instance_id`
- `strategy_id`
- `enabled`
- `priority`
- `created_at`
- `updated_at`

Constraints:
- unique on `instance_id + strategy_id`

### Strategy Hit

Table: `strategy_hits`

Purpose:
- Persist every triggered strategy evaluation that should be traceable later.

Suggested fields:
- `id`
- `instance_id`
- `strategy_id`
- `binding_id`
- `capture_event_id`
- `target_metric`
- `strategy_name`
- `template_type`
- `severity`
- `score`
- `anomaly_type`
- `evidence_json`
- `snapshot_json`
- `recommendation`
- `triggered_at`
- `created_at`

### Alert Extension

Existing table: `alert_records`

Add relationship fields:
- `strategy_id`
- `strategy_hit_id`
- `capture_event_id`
- `strategy_name`
- `target_metric`

This allows the admin to answer:
- which alert came from which strategy
- which capture event produced the alert
- which metric the strategy evaluated

## Strategy Execution Model

### Common Interface

Each strategy executor returns a normalized result:

- `triggered`
- `severity`
- `score`
- `anomaly_type`
- `evidence`
- `recommendation`
- `metric_value`
- `baseline_value`
- `snapshot`

The alerting layer depends on this normalized result, not on strategy-specific internals.

### Template 1: Window Threshold

Template key: `window_threshold`

Phase-one supported metric:
- `spend`

Parameters:
- `window_minutes`
- `threshold_value`
- `cooldown_minutes`
- `severity`

Rule:
- Compute spend delta across the configured window.
- Trigger when delta exceeds threshold.

### Template 2: Historical Baseline

Template key: `historical_baseline`

Phase-one supported metric:
- `spend`

Parameters:
- `window_minutes`
- `lookback_days`
- `zscore_threshold`
- `min_samples`
- `severity`

Rule:
- Compute the current spend delta for the configured window.
- Compare against historical samples for the same hour bucket.
- Trigger when the deviation exceeds the configured z-score threshold.

## Ingest Payload Direction

The userscript no longer sends strategy-owned settings.

The backend should accept a simpler payload:

- instance metadata
- capture time
- raw metrics
- raw context

Phase-one actual metric:
- `current_spend`

Compatibility:
- the backend continues accepting the old `metrics` shape during migration
- the new userscript sends only the data required for collection

## Admin UX

### New Strategies Page

Capabilities:
- list strategies
- create from built-in template
- edit strategy metadata and parameters
- enable or disable strategy
- delete strategy
- show how many instances are bound
- show how many recent hits and alerts were caused by the strategy

### Instance Detail Page

Add:
- bound strategies section
- bind or unbind strategies for the current instance
- enable or disable a binding
- recent strategy hits for the instance

### Alerts Page

Add:
- strategy filter
- template filter
- metric filter
- strategy metadata in the alert table

### Dashboard

Phase-one dashboard changes remain light:
- retain current operational summary
- expose strategy-aware labels where recent alerts are shown

## Migration and Defaults

To preserve existing behavior after rollout:

- seed the metric registry on startup
- seed at least one default strategy for the existing threshold behavior
- optionally seed a historical baseline strategy definition but keep it disabled by default
- automatically bind enabled default strategies to newly seen instances
- allow operators to unbind or disable them later

This preserves current alert continuity while still moving configuration control to the admin backend.

## Compatibility Decisions

- Existing offline and capture-failure scans remain in place.
- Existing analysis records remain readable.
- Existing alert records without strategy links are valid historical data.
- New records may include strategy linkage fields while old rows keep them null.

## Risks

- The current admin pages assume a single “window increase” concept; that assumption must be weakened because multiple strategy windows may coexist.
- Existing tests cover threshold behavior directly and will need to be rewritten around strategy evaluation.
- Backward compatibility for ingest payloads must be preserved during the userscript transition.
- Auto-binding defaults must not create duplicate instance bindings.

## Phase-One Non-Goals

- Custom rule expressions or DSL
- Multi-metric executable strategies
- Strategy chaining or dependencies
- Alert aggregation across multiple strategy hits
- Full deprecation of legacy `/analyze` endpoint

## Acceptance Criteria

- An instance can bind multiple strategies.
- A single ingest can trigger multiple independent alerts.
- Each alert can be traced back to a strategy.
- Admin can create, edit, delete, enable, and disable strategies.
- Admin can bind and unbind strategies on an instance page.
- The userscript no longer exposes threshold, compare window, AI, or account override settings.
- The userscript keeps refresh interval configuration and still reports spend data correctly.
- Existing operational offline and capture-failure alerts still work.
