from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from math import sqrt

from models import DetectionSummary, HistoryPoint


@dataclass
class DeltaPoint:
    timestamp: int
    delta: float


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _std(values: list[float], mean: float) -> float:
    if len(values) < 2:
        return 0.0
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return sqrt(variance)


def build_delta_series(history: list[HistoryPoint]) -> list[DeltaPoint]:
    ordered = sorted(history, key=lambda item: item.timestamp)
    deltas: list[DeltaPoint] = []

    for previous, current in zip(ordered, ordered[1:]):
        delta = max(0.0, current.spend - previous.spend)
        deltas.append(DeltaPoint(timestamp=current.timestamp, delta=delta))

    return deltas


def detect_spend_anomaly(
    history: list[HistoryPoint],
    increase_amount: float,
    compare_interval_min: int,
    threshold: float,
) -> DetectionSummary:
    deltas = build_delta_series(history)
    if len(deltas) < 6:
        severity = "high" if increase_amount >= threshold else "medium"
        return DetectionSummary(
            anomaly_type="insufficient_history",
            severity=severity,
            score=0.55,
            evidence=[
                "历史样本不足，暂时无法稳定计算分时段基线",
                f"当前窗口增量 {increase_amount:.2f}，阈值 {threshold:.2f}",
            ],
            recommendation="先保留人工复核，同时继续积累分钟级数据。",
        )

    current = deltas[-1]
    current_hour = datetime.fromtimestamp(current.timestamp / 1000).hour

    by_hour: dict[int, list[float]] = defaultdict(list)
    for point in deltas[:-1]:
        hour = datetime.fromtimestamp(point.timestamp / 1000).hour
        by_hour[hour].append(point.delta)

    baseline_pool = by_hour.get(current_hour) or [point.delta for point in deltas[:-1]]
    mean_value = _mean(baseline_pool)
    std_value = _std(baseline_pool, mean_value)
    zscore = 0.0 if std_value == 0 else (current.delta - mean_value) / std_value

    severity = "low"
    anomaly_type = "normal"
    score = 0.35

    if current.delta <= 0.01:
        anomaly_type = "stalled"
        severity = "medium"
        score = 0.7
    elif increase_amount >= threshold and zscore >= 2.5:
        anomaly_type = "surge"
        severity = "high"
        score = min(0.98, 0.65 + zscore / 10)
    elif increase_amount >= threshold:
        anomaly_type = "threshold_breach"
        severity = "medium"
        score = 0.72

    evidence = [
        f"当前分钟增量 {current.delta:.2f}",
        f"同小时段基线均值 {mean_value:.2f}",
        f"同小时段 Z-Score {zscore:.2f}",
        f"窗口 {compare_interval_min} 分钟累计增量 {increase_amount:.2f}",
    ]

    recommendation = "继续观察。"
    if anomaly_type in {"surge", "threshold_breach"}:
        recommendation = "建议立即复核流量质量、场观变化和成交退款情况，必要时暂停计划。"
    elif anomaly_type == "stalled":
        recommendation = "建议检查投放状态、预算与页面加载是否异常。"

    return DetectionSummary(
        anomaly_type=anomaly_type,
        severity=severity,
        score=round(score, 2),
        zscore=round(zscore, 2),
        evidence=evidence,
        recommendation=recommendation,
    )
