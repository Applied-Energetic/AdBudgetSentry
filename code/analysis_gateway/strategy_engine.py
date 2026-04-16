from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import sqrt


@dataclass
class StrategyExecutionResult:
    triggered: bool
    severity: str
    score: float
    anomaly_type: str
    evidence: list[str]
    recommendation: str
    metric_value: float
    baseline_value: float | None
    snapshot: dict


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _std(values: list[float], mean: float) -> float:
    if len(values) < 2:
        return 0.0
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return sqrt(variance)


def _normalize_history(history: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for item in history:
        try:
            normalized.append({"timestamp": int(item["timestamp"]), "spend": float(item["spend"])})
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(normalized, key=lambda item: item["timestamp"])


def compute_window_delta(history: list[dict], end_timestamp: int, window_minutes: int) -> tuple[float, float]:
    ordered = _normalize_history(history)
    if not ordered:
        return 0.0, 0.0

    current_candidates = [item for item in ordered if item["timestamp"] <= end_timestamp]
    if not current_candidates:
        return 0.0, 0.0

    current = current_candidates[-1]
    cutoff = end_timestamp - (window_minutes * 60 * 1000)
    baseline_candidates = [item for item in current_candidates if item["timestamp"] <= cutoff]
    baseline = baseline_candidates[-1] if baseline_candidates else current_candidates[0]
    delta = max(0.0, current["spend"] - baseline["spend"])
    return delta, baseline["spend"]


def evaluate_window_threshold(history: list[dict], end_timestamp: int, params: dict) -> StrategyExecutionResult:
    window_minutes = max(1, int(params.get("window_minutes") or 10))
    threshold_value = float(params.get("threshold_value") or 0)
    severity = str(params.get("severity") or "high")
    delta, baseline_spend = compute_window_delta(history, end_timestamp, window_minutes)
    triggered = delta >= threshold_value > 0
    score = min(0.99, delta / threshold_value) if threshold_value > 0 else 0.0

    evidence = [
        f"{window_minutes} 分钟窗口增量 {delta:.2f}",
        f"阈值 {threshold_value:.2f}",
    ]
    recommendation = "继续观察"
    anomaly_type = "window_threshold_clear"
    if triggered:
        anomaly_type = "window_threshold_breach"
        recommendation = "建议立即复核当前投放和成交质量，并查看该实例的其他策略命中情况。"

    return StrategyExecutionResult(
        triggered=triggered,
        severity=severity,
        score=round(score, 2),
        anomaly_type=anomaly_type,
        evidence=evidence,
        recommendation=recommendation,
        metric_value=round(delta, 2),
        baseline_value=round(threshold_value, 2),
        snapshot={
            "window_minutes": window_minutes,
            "threshold_value": threshold_value,
            "baseline_spend": round(baseline_spend, 2),
        },
    )


def evaluate_historical_baseline(history: list[dict], end_timestamp: int, params: dict) -> StrategyExecutionResult:
    window_minutes = max(1, int(params.get("window_minutes") or 10))
    min_samples = max(1, int(params.get("min_samples") or 3))
    zscore_threshold = float(params.get("zscore_threshold") or 2.5)
    severity = str(params.get("severity") or "medium")
    ordered = _normalize_history(history)
    current_delta, baseline_spend = compute_window_delta(ordered, end_timestamp, window_minutes)
    current_hour = datetime.fromtimestamp(end_timestamp / 1000).hour

    samples: list[float] = []
    for point in ordered[:-1]:
        hour = datetime.fromtimestamp(point["timestamp"] / 1000).hour
        if hour != current_hour:
            continue
        sample_delta, _sample_baseline = compute_window_delta(ordered, point["timestamp"], window_minutes)
        if sample_delta > 0:
            samples.append(sample_delta)

    if len(samples) < min_samples:
        return StrategyExecutionResult(
            triggered=False,
            severity=severity,
            score=0.0,
            anomaly_type="historical_baseline_insufficient_history",
            evidence=[
                f"历史样本不足，当前同小时样本数 {len(samples)}",
                f"最少要求 {min_samples}",
            ],
            recommendation="继续积累历史数据后再启用基线策略。",
            metric_value=round(current_delta, 2),
            baseline_value=None,
            snapshot={
                "window_minutes": window_minutes,
                "sample_count": len(samples),
                "baseline_spend": round(baseline_spend, 2),
            },
        )

    mean_value = _mean(samples)
    std_value = _std(samples, mean_value)
    zscore = 0.0 if std_value == 0 else (current_delta - mean_value) / std_value
    triggered = zscore >= zscore_threshold and current_delta > mean_value
    score = min(0.99, 0.65 + max(0.0, zscore) / 10)
    evidence = [
        f"{window_minutes} 分钟窗口增量 {current_delta:.2f}",
        f"历史同小时均值 {mean_value:.2f}",
        f"Z-Score {zscore:.2f}",
    ]
    recommendation = "继续观察"
    anomaly_type = "historical_baseline_normal"
    if triggered:
        anomaly_type = "historical_baseline_breach"
        recommendation = "建议核查同时间段波动原因，并结合阈值策略和告警历史判断是否需要人工介入。"

    return StrategyExecutionResult(
        triggered=triggered,
        severity=severity,
        score=round(score if triggered else max(0.0, zscore / 10), 2),
        anomaly_type=anomaly_type,
        evidence=evidence,
        recommendation=recommendation,
        metric_value=round(current_delta, 2),
        baseline_value=round(mean_value, 2),
        snapshot={
            "window_minutes": window_minutes,
            "zscore": round(zscore, 2),
            "sample_count": len(samples),
            "baseline_spend": round(baseline_spend, 2),
        },
    )


def execute_strategy(template_type: str, history: list[dict], end_timestamp: int, params: dict) -> StrategyExecutionResult:
    if template_type == "window_threshold":
        return evaluate_window_threshold(history, end_timestamp, params)
    if template_type == "historical_baseline":
        return evaluate_historical_baseline(history, end_timestamp, params)
    raise ValueError(f"Unsupported strategy template: {template_type}")
