from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException

from anomaly import detect_spend_anomaly
from models import AnalysisRequest, AnalysisResponse
from providers import OpenAICompatibleProvider, ProviderResult


APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "config.json"
EXAMPLE_CONFIG_PATH = APP_DIR / "config.example.json"

DEFAULT_CONTEXT = """业务背景：快手磁力金牛在高客单价、目标成本偏高时，可能引入低质量流量，造成虚假转化、疯狂消耗、成本失控。请区分正常爆量与低质流量嫌疑，输出风险等级、证据和操作建议。"""


def load_config() -> dict:
    path = CONFIG_PATH if CONFIG_PATH.exists() else EXAMPLE_CONFIG_PATH
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def build_provider(config: dict, provider_name: str) -> OpenAICompatibleProvider:
    provider_config = config.get(provider_name)
    if not provider_config:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider_name}")

    return OpenAICompatibleProvider(
        provider_name=provider_name,
        base_url=provider_config["base_url"],
        api_key=provider_config.get("api_key", ""),
        model=provider_config["model"],
    )


def build_prompt(request: AnalysisRequest, detection_summary) -> str:
    event = request.event
    context = request.business_context or DEFAULT_CONTEXT
    metrics = json.dumps(event.extra_metrics, ensure_ascii=False)
    evidence_lines = "\n".join(f"- {item}" for item in detection_summary.evidence)

    return f"""
{context}

当前事件：
- 当前总消耗：{event.current_spend:.2f}
- 窗口增量：{event.increase_amount:.2f}
- 对比窗口：{event.compare_interval_min} 分钟
- 预警阈值：{event.threshold:.2f}
- 规则检测类型：{detection_summary.anomaly_type}
- 规则严重度：{detection_summary.severity}
- 规则分数：{detection_summary.score}
- 附加指标：{metrics}

规则证据：
{evidence_lines}

请输出：
1. 结论：这是正常爆量、低质流量嫌疑、还是暂时无法判断
2. 核心依据：2到3条
3. 建议动作：继续观察 / 降预算 / 暂停计划 / 人工复核退款与场观
4. 一句话风险提示
""".strip()


def fallback_text(detection_summary) -> str:
    evidence = "；".join(detection_summary.evidence)
    return (
        f"规则判断为 {detection_summary.anomaly_type}，严重度 {detection_summary.severity}。"
        f"证据：{evidence}。建议：{detection_summary.recommendation}"
    )


async def run_provider(provider: OpenAICompatibleProvider, prompt: str) -> ProviderResult:
    return await provider.complete(prompt)


app = FastAPI(title="AdBudgetSentry Analysis Gateway")


@app.get("/health")
def health() -> dict:
    config = load_config()
    return {
        "status": "ok",
        "default_provider": config.get("default_provider", "deepseek"),
    }


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze(request: AnalysisRequest) -> AnalysisResponse:
    config = load_config()
    provider_name = request.provider_override or config.get("default_provider", "deepseek")

    detection_summary = detect_spend_anomaly(
        history=request.history,
        increase_amount=request.event.increase_amount,
        compare_interval_min=request.event.compare_interval_min,
        threshold=request.event.threshold,
    )

    prompt = build_prompt(request, detection_summary)

    try:
        provider = build_provider(config, provider_name)
        result = await run_provider(provider, prompt)
        raw_text = result.text
    except Exception as exc:  # noqa: BLE001
        provider = build_provider(config, provider_name)
        raw_text = f"{fallback_text(detection_summary)}\n\n模型调用失败：{exc}"

    summary = raw_text.splitlines()[0].strip() if raw_text.strip() else fallback_text(detection_summary)

    return AnalysisResponse(
        provider=provider.provider_name,
        model=provider.model,
        detection=detection_summary,
        summary=summary,
        raw_text=raw_text,
    )


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("ADBUDGET_HOST", "127.0.0.1")
    port = int(os.getenv("ADBUDGET_PORT", "8787"))
    uvicorn.run("app:app", host=host, port=port, reload=False)
