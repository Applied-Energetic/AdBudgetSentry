// ==UserScript==
// @name         磁力金牛财务报警助手
// @namespace    http://tampermonkey.net/
// @version      2.0.0
// @description  监控磁力金牛财务页消耗，并支持本地模型 / DeepSeek 智能分析切换
// @author       Codex
// @match        https://niu.e.kuaishou.com/financial/record*
// @match        https://niu.e.kuaishou.com/*
// @require      https://cdn.jsdelivr.net/npm/jquery@3.7.1/dist/jquery.min.js
// @grant        GM_addStyle
// @grant        GM_notification
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_xmlhttpRequest
// @connect      127.0.0.1
// @connect      localhost
// @connect      pushplus.plus
// @connect      api.deepseek.com
// ==/UserScript==

(function () {
    "use strict";

    const CONFIG = {
        panelId: "ad-budget-sentry-panel",
        historyRetentionMs: 24 * 60 * 60 * 1000,
        checkDelayMs: 3000,
        uiTickMs: 1000,
        defaultGatewayUrl: "http://127.0.0.1:8787/analyze",
        audioAlertUrl: "https://actions.google.com/sounds/v1/alarms/alarm_clock_short.ogg",
    };

    const state = {
        currentSpend: 0,
        increaseInWindow: 0,
        baselineSpend: 0,
        baselineTime: 0,
        lastCheckTime: 0,
        lastReloadTime: GM_getValue("last_reload_time", Date.now()),
        lastNotifyTime: GM_getValue("last_notify_time", 0),
        lastAnalysisText: GM_getValue("last_analysis_text", ""),
        history: GM_getValue("spend_history", []),
        config: {
            pushplusToken: GM_getValue("pushplus_token", ""),
            refreshIntervalMin: GM_getValue("refresh_interval_min", 5),
            compareIntervalMin: GM_getValue("compare_interval_min", 30),
            notifyThreshold: GM_getValue("notify_threshold", 1000),
            aiEnabled: GM_getValue("ai_enabled", true),
            aiProvider: GM_getValue("ai_provider", "deepseek"),
            analysisGatewayUrl: GM_getValue("analysis_gateway_url", CONFIG.defaultGatewayUrl),
        },
    };

    function addStyles() {
        GM_addStyle(`
            #${CONFIG.panelId} {
                position: fixed;
                top: 18px;
                right: 18px;
                z-index: 99999;
                width: 330px;
                background: #fff;
                color: #1f2937;
                border: 1px solid #e5e7eb;
                border-radius: 16px;
                box-shadow: 0 20px 40px rgba(15, 23, 42, 0.18);
                font-family: "Segoe UI", "PingFang SC", sans-serif;
                overflow: hidden;
            }
            #${CONFIG.panelId} .sentry-head {
                background: linear-gradient(135deg, #0f766e, #14b8a6);
                color: #fff;
                padding: 14px 16px;
                font-weight: 700;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            #${CONFIG.panelId} .sentry-body {
                padding: 16px;
            }
            #${CONFIG.panelId} .sentry-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 10px;
                margin-bottom: 14px;
            }
            #${CONFIG.panelId} .metric,
            #${CONFIG.panelId} .field-group {
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
                padding: 10px;
            }
            #${CONFIG.panelId} .metric-label,
            #${CONFIG.panelId} label {
                display: block;
                font-size: 12px;
                color: #64748b;
                margin-bottom: 4px;
            }
            #${CONFIG.panelId} .metric-value {
                font-size: 18px;
                font-weight: 700;
                color: #0f172a;
            }
            #${CONFIG.panelId} input,
            #${CONFIG.panelId} select {
                width: 100%;
                height: 34px;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 0 10px;
                box-sizing: border-box;
                background: #fff;
            }
            #${CONFIG.panelId} .field-stack {
                display: grid;
                gap: 10px;
                margin-bottom: 12px;
            }
            #${CONFIG.panelId} .button-row {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 8px;
            }
            #${CONFIG.panelId} button {
                height: 36px;
                border: none;
                border-radius: 10px;
                cursor: pointer;
                font-weight: 600;
            }
            #save-config-btn {
                width: 100%;
                margin: 10px 0 12px;
                background: #0f766e;
                color: #fff;
            }
            #manual-refresh-btn {
                background: #e2e8f0;
                color: #0f172a;
            }
            #test-alert-btn {
                background: #fef3c7;
                color: #92400e;
            }
            #reset-history-btn {
                background: #fee2e2;
                color: #991b1b;
            }
            #run-ai-btn {
                background: #dbeafe;
                color: #1d4ed8;
            }
            #${CONFIG.panelId} .analysis-box {
                margin-top: 14px;
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
                padding: 10px;
                font-size: 12px;
                line-height: 1.5;
                white-space: pre-wrap;
            }
            #${CONFIG.panelId} .status-row {
                margin-top: 10px;
                font-size: 12px;
                color: #475569;
                display: flex;
                justify-content: space-between;
            }
        `);
    }

    function parseMoney(text) {
        if (!text) return 0;
        const normalized = String(text).replace(/[^\d.-]/g, "");
        const value = parseFloat(normalized);
        return Number.isFinite(value) ? value : 0;
    }

    function formatMoney(value) {
        return `${value.toFixed(2)} 元`;
    }

    function getTodayStr() {
        const now = new Date();
        const year = now.getFullYear();
        const month = String(now.getMonth() + 1).padStart(2, "0");
        const day = String(now.getDate()).padStart(2, "0");
        return `${year}-${month}-${day}`;
    }

    function getRowsBySelectors() {
        const selectors = [
            "#root section section main table tbody tr",
            ".ant-table-tbody tr.ant-table-row",
            ".ant-table-row",
        ];

        for (const selector of selectors) {
            const rows = $(selector);
            if (rows.length > 0) return rows;
        }

        return $();
    }

    function scrapeTodaySpend() {
        const todayStr = getTodayStr();
        const rows = getRowsBySelectors();
        let detectedSpend = -1;

        rows.each(function () {
            const cells = $(this).find("td");
            if (cells.length < 2) return;

            const dateCell = cells.eq(0).text().trim();
            if (dateCell === todayStr || dateCell.includes(todayStr)) {
                detectedSpend = parseMoney(cells.eq(1).text());
                return false;
            }
        });

        return detectedSpend;
    }

    function trimHistory() {
        const now = Date.now();
        state.history = state.history.filter((item) => now - item.time <= CONFIG.historyRetentionMs);
    }

    function appendHistory(spend) {
        const now = Date.now();
        const lastPoint = state.history[state.history.length - 1];
        if (!lastPoint || Math.abs(lastPoint.spend - spend) > 0.009 || now - lastPoint.time >= 55 * 1000) {
            state.history.push({ time: now, spend });
        }
        trimHistory();
        GM_setValue("spend_history", state.history);
    }

    function getBaselineRecord() {
        const compareStart = Date.now() - state.config.compareIntervalMin * 60 * 1000;
        let baseline = state.history[0] || { time: Date.now(), spend: state.currentSpend };

        for (const item of state.history) {
            if (item.time >= compareStart) {
                baseline = item;
                break;
            }
        }

        return baseline;
    }

    function serializeHistory() {
        return state.history.map((item) => ({
            timestamp: item.time,
            spend: item.spend,
        }));
    }

    function buildEventPayload() {
        return {
            current_spend: state.currentSpend,
            increase_amount: state.increaseInWindow,
            compare_interval_min: state.config.compareIntervalMin,
            threshold: state.config.notifyThreshold,
            baseline_time: state.baselineTime,
            event_time: Date.now(),
            extra_metrics: {
                baseline_spend: state.baselineSpend,
                samples: state.history.length,
            },
        };
    }

    function gmRequest(options) {
        return new Promise((resolve, reject) => {
            GM_xmlhttpRequest({
                ...options,
                onload: resolve,
                onerror: reject,
                ontimeout: reject,
            });
        });
    }

    async function requestAiAnalysis() {
        if (!state.config.aiEnabled) return "";

        const payload = {
            provider_override: state.config.aiProvider,
            event: buildEventPayload(),
            history: serializeHistory(),
        };

        try {
            const response = await gmRequest({
                method: "POST",
                url: state.config.analysisGatewayUrl,
                headers: { "Content-Type": "application/json" },
                data: JSON.stringify(payload),
                timeout: 45000,
            });

            const body = JSON.parse(response.responseText);
            const text = body.raw_text || body.summary || "";
            state.lastAnalysisText = text;
            GM_setValue("last_analysis_text", text);
            return text;
        } catch (error) {
            const message = `AI 分析失败：${error?.error || error?.message || "unknown error"}`;
            state.lastAnalysisText = message;
            GM_setValue("last_analysis_text", message);
            return message;
        }
    }

    async function pushAlert(title, content) {
        if (!state.config.pushplusToken) return;

        await gmRequest({
            method: "POST",
            url: "https://www.pushplus.plus/send",
            headers: { "Content-Type": "application/json" },
            data: JSON.stringify({
                token: state.config.pushplusToken,
                title,
                content,
                template: "html",
                channel: "mail",
                option: "",
            }),
        });
    }

    function renderAnalysisText(text) {
        $("#analysis-output").text(text || "暂无 AI 分析结果。");
    }

    function renderStatus() {
        $("#metric-total").text(formatMoney(state.currentSpend));
        $("#metric-window").text(formatMoney(state.increaseInWindow));

        const nextReloadAt = state.lastReloadTime + state.config.refreshIntervalMin * 60 * 1000;
        const diffSec = Math.max(0, Math.floor((nextReloadAt - Date.now()) / 1000));
        const minutes = String(Math.floor(diffSec / 60)).padStart(2, "0");
        const seconds = String(diffSec % 60).padStart(2, "0");

        $("#refresh-countdown").text(`${minutes}:${seconds}`);
        $("#last-update-time").text(new Date().toLocaleTimeString());
        renderAnalysisText(state.lastAnalysisText);
    }

    function saveConfigFromUI() {
        state.config.pushplusToken = $("#pushplus-token").val().trim();
        state.config.refreshIntervalMin = Number($("#refresh-interval").val()) || 5;
        state.config.compareIntervalMin = Number($("#compare-interval").val()) || 30;
        state.config.notifyThreshold = Number($("#notify-threshold").val()) || 1000;
        state.config.aiEnabled = $("#ai-enabled").val() === "true";
        state.config.aiProvider = $("#ai-provider").val() || "deepseek";
        state.config.analysisGatewayUrl = $("#analysis-gateway").val().trim() || CONFIG.defaultGatewayUrl;

        GM_setValue("pushplus_token", state.config.pushplusToken);
        GM_setValue("refresh_interval_min", state.config.refreshIntervalMin);
        GM_setValue("compare_interval_min", state.config.compareIntervalMin);
        GM_setValue("notify_threshold", state.config.notifyThreshold);
        GM_setValue("ai_enabled", state.config.aiEnabled);
        GM_setValue("ai_provider", state.config.aiProvider);
        GM_setValue("analysis_gateway_url", state.config.analysisGatewayUrl);
    }

    function createPanel() {
        if ($(`#${CONFIG.panelId}`).length > 0) return;

        const html = `
            <div id="${CONFIG.panelId}">
                <div class="sentry-head">
                    <span>磁力金牛财务哨兵</span>
                    <span id="refresh-countdown">--:--</span>
                </div>
                <div class="sentry-body">
                    <div class="sentry-grid">
                        <div class="metric">
                            <span class="metric-label">今日总消耗</span>
                            <div id="metric-total" class="metric-value">-</div>
                        </div>
                        <div class="metric">
                            <span class="metric-label">${state.config.compareIntervalMin} 分钟增量</span>
                            <div id="metric-window" class="metric-value">-</div>
                        </div>
                    </div>
                    <div class="field-stack">
                        <div class="field-group">
                            <label for="pushplus-token">PushPlus Token</label>
                            <input id="pushplus-token" type="password" value="${state.config.pushplusToken}" placeholder="输入 PushPlus Token" />
                        </div>
                        <div class="sentry-grid">
                            <div class="field-group">
                                <label for="refresh-interval">刷新间隔(分钟)</label>
                                <input id="refresh-interval" type="number" value="${state.config.refreshIntervalMin}" />
                            </div>
                            <div class="field-group">
                                <label for="compare-interval">比较窗口(分钟)</label>
                                <input id="compare-interval" type="number" value="${state.config.compareIntervalMin}" />
                            </div>
                        </div>
                        <div class="field-group">
                            <label for="notify-threshold">报警阈值(元)</label>
                            <input id="notify-threshold" type="number" value="${state.config.notifyThreshold}" />
                        </div>
                        <div class="sentry-grid">
                            <div class="field-group">
                                <label for="ai-enabled">智能分析</label>
                                <select id="ai-enabled">
                                    <option value="true" ${state.config.aiEnabled ? "selected" : ""}>开启</option>
                                    <option value="false" ${state.config.aiEnabled ? "" : "selected"}>关闭</option>
                                </select>
                            </div>
                            <div class="field-group">
                                <label for="ai-provider">分析路线</label>
                                <select id="ai-provider">
                                    <option value="local" ${state.config.aiProvider === "local" ? "selected" : ""}>本地 Qwen / OpenAI 兼容</option>
                                    <option value="deepseek" ${state.config.aiProvider === "deepseek" ? "selected" : ""}>DeepSeek API</option>
                                </select>
                            </div>
                        </div>
                        <div class="field-group">
                            <label for="analysis-gateway">分析网关地址</label>
                            <input id="analysis-gateway" type="text" value="${state.config.analysisGatewayUrl}" />
                        </div>
                    </div>
                    <button id="save-config-btn">保存配置</button>
                    <div class="button-row">
                        <button id="manual-refresh-btn">手动刷新</button>
                        <button id="test-alert-btn">测试报警</button>
                    </div>
                    <div class="button-row" style="margin-top:8px;">
                        <button id="reset-history-btn">重置历史</button>
                        <button id="run-ai-btn">立即分析</button>
                    </div>
                    <div class="analysis-box" id="analysis-output">暂无 AI 分析结果。</div>
                    <div class="status-row">
                        <span>最后更新</span>
                        <span id="last-update-time">-</span>
                    </div>
                </div>
            </div>
        `;

        $("body").append(html);

        $("#save-config-btn").on("click", () => {
            saveConfigFromUI();
            alert("配置已保存。");
            renderStatus();
        });

        $("#manual-refresh-btn").on("click", () => {
            GM_setValue("last_reload_time", Date.now());
            location.reload();
        });

        $("#reset-history-btn").on("click", () => {
            state.history = [];
            state.lastNotifyTime = 0;
            state.baselineSpend = 0;
            state.baselineTime = 0;
            GM_setValue("spend_history", []);
            GM_setValue("last_notify_time", 0);
            state.lastAnalysisText = "";
            GM_setValue("last_analysis_text", "");
            renderStatus();
            alert("历史数据已重置。");
        });

        $("#test-alert-btn").on("click", async () => {
            saveConfigFromUI();
            const analysisText = await requestAiAnalysis();
            await pushAlert(
                "【磁力金牛】测试报警",
                `
                <div style="font-family:sans-serif;padding:12px;">
                    <h3>测试报警</h3>
                    <p>当前总消耗：${formatMoney(state.currentSpend)}</p>
                    <p>${state.config.compareIntervalMin} 分钟增量：${formatMoney(state.increaseInWindow)}</p>
                    <pre style="white-space:pre-wrap;">${analysisText || "未开启 AI 分析"}</pre>
                </div>
                `
            );
            alert("测试报警已发送。");
        });

        $("#run-ai-btn").on("click", async () => {
            saveConfigFromUI();
            const analysisText = await requestAiAnalysis();
            renderAnalysisText(analysisText);
        });
    }

    async function handleThresholdAlert() {
        const cooldownMs = 10 * 60 * 1000;
        const now = Date.now();
        if (state.increaseInWindow < state.config.notifyThreshold) return;
        if (now - state.lastNotifyTime < cooldownMs) return;

        const analysisText = await requestAiAnalysis();
        const title = "【磁力金牛】消耗异常预警";
        const content = `
            <div style="font-family:sans-serif;padding:14px;border:1px solid #e5e7eb;border-radius:8px;">
                <h2 style="color:#b91c1c;">消耗异常提醒</h2>
                <p>当前总消耗：<strong>${formatMoney(state.currentSpend)}</strong></p>
                <p>对比窗口：<strong>${state.config.compareIntervalMin} 分钟</strong></p>
                <p>窗口增量：<strong style="color:#b91c1c;">${formatMoney(state.increaseInWindow)}</strong></p>
                <p>阈值：<strong>${formatMoney(state.config.notifyThreshold)}</strong></p>
                <p>基线时间：${state.baselineTime ? new Date(state.baselineTime).toLocaleString() : "-"}</p>
                <h3>AI 分析</h3>
                <pre style="white-space:pre-wrap;font-size:12px;background:#f8fafc;padding:10px;border-radius:6px;">${analysisText || "未开启 AI 分析"}</pre>
            </div>
        `;

        await pushAlert(title, content);

        GM_notification({
            title: "磁力金牛消耗异常",
            text: `${state.config.compareIntervalMin} 分钟增量 ${state.increaseInWindow.toFixed(2)} 元`,
            timeout: 10000,
        });

        try {
            const audio = new Audio(CONFIG.audioAlertUrl);
            audio.play().catch(() => {});
        } catch (_error) {
            // Ignore audio failures.
        }

        state.lastNotifyTime = now;
        GM_setValue("last_notify_time", now);
        renderStatus();
    }

    async function evaluateSpend() {
        const spend = scrapeTodaySpend();
        if (spend < 0) return;

        state.currentSpend = spend;
        appendHistory(spend);

        const baseline = getBaselineRecord();
        state.baselineSpend = baseline.spend;
        state.baselineTime = baseline.time;
        state.increaseInWindow = Math.max(0, spend - baseline.spend);
        state.lastCheckTime = Date.now();

        renderStatus();
        await handleThresholdAlert();
    }

    function mainLoop() {
        const refreshMs = state.config.refreshIntervalMin * 60 * 1000;
        if (Date.now() - state.lastReloadTime >= refreshMs) {
            GM_setValue("last_reload_time", Date.now());
            location.reload();
            return;
        }
        renderStatus();
    }

    function bindStartup() {
        addStyles();
        createPanel();
        renderStatus();

        setTimeout(() => {
            evaluateSpend();
            setInterval(mainLoop, CONFIG.uiTickMs);
        }, CONFIG.checkDelayMs);
    }

    $(document).ready(bindStartup);
})();
