// ==UserScript==
// @name         磁力金牛财务报警助手
// @namespace    http://tampermonkey.net/
// @version      2.2.0
// @description  监控磁力金牛财务页消耗，并向本地后端上报采集、心跳和错误信息
// @author       Codex
// @match        https://niu.e.kuaishou.com/financial/record*
// @match        https://niu.e.kuaishou.com/*
// @require      https://cdn.jsdelivr.net/npm/jquery@3.7.1/dist/jquery.min.js
// @grant        GM_addStyle
// @grant        GM_notification
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_xmlhttpRequest
// @connect      *
// ==/UserScript==

(function () {
    "use strict";

    const CONFIG = {
        panelId: "ad-budget-sentry-panel",
        historyRetentionMs: 24 * 60 * 60 * 1000,
        checkDelayMs: 3000,
        uiTickMs: 1000,
        heartbeatIntervalMs: 2 * 60 * 1000,
        defaultBackendBaseUrl: "http://127.0.0.1:8787",
        audioAlertUrl: "https://actions.google.com/sounds/v1/alarms/alarm_clock_short.ogg",
    };

    function normalizeBackendBaseUrl(raw) {
        const fallback = CONFIG.defaultBackendBaseUrl;
        const value = String(raw || fallback).trim();
        if (!value) return fallback;
        return value.replace(/\/analyze$/i, "").replace(/\/$/, "");
    }

    function makeInstanceId() {
        return `tm-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
    }

    const state = {
        instanceId: GM_getValue("instance_id", makeInstanceId()),
        panelPosition: {
            left: GM_getValue("panel_left", null),
            top: GM_getValue("panel_top", null),
        },
        currentSpend: 0,
        increaseInWindow: 0,
        baselineSpend: 0,
        baselineTime: 0,
        lastCheckTime: 0,
        lastReloadTime: GM_getValue("last_reload_time", Date.now()),
        lastNotifyTime: GM_getValue("last_notify_time", 0),
        lastAnalysisText: GM_getValue("last_analysis_text", ""),
        lastBackendMessage: GM_getValue("last_backend_message", "等待上报"),
        lastHeartbeatSentAt: GM_getValue("last_heartbeat_sent_at", 0),
        lastCaptureStatus: GM_getValue("last_capture_status", "warning"),
        lastErrorMessage: GM_getValue("last_error_message", ""),
        history: GM_getValue("spend_history", []),
        config: {
            accountIdOverride: GM_getValue("account_id_override", ""),
            accountNameOverride: GM_getValue("account_name_override", ""),
            pushplusToken: GM_getValue("pushplus_token", ""),
            pushplusChannel: GM_getValue("pushplus_channel", "mail"),
            pushplusOption: GM_getValue("pushplus_option", ""),
            refreshIntervalMin: GM_getValue("refresh_interval_min", 5),
            compareIntervalMin: GM_getValue("compare_interval_min", 30),
            notifyThreshold: GM_getValue("notify_threshold", 1000),
            aiEnabled: GM_getValue("ai_enabled", true),
            aiProvider: GM_getValue("ai_provider", "deepseek"),
            backendBaseUrl: normalizeBackendBaseUrl(
                GM_getValue("backend_base_url", GM_getValue("analysis_gateway_url", CONFIG.defaultBackendBaseUrl))
            ),
        },
    };

    GM_setValue("instance_id", state.instanceId);

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
                cursor: move;
                user-select: none;
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
            #${CONFIG.panelId} .field-stack.compact {
                gap: 8px;
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
                min-height: 120px;
                max-height: 360px;
                overflow: auto;
                resize: vertical;
            }
            #${CONFIG.panelId} .status-row {
                margin-top: 10px;
                font-size: 12px;
                color: #475569;
                display: flex;
                justify-content: space-between;
                gap: 12px;
            }
            #${CONFIG.panelId} .status-stack {
                margin-top: 10px;
                display: grid;
                gap: 6px;
                font-size: 12px;
                color: #475569;
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
                padding: 10px;
            }
            #${CONFIG.panelId} .status-stack strong {
                color: #0f172a;
            }
            #${CONFIG.panelId} .sentry-subtle {
                color: #64748b;
                font-size: 12px;
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
        return `${Number(value || 0).toFixed(2)} 元`;
    }

    function getTodayStr() {
        const now = new Date();
        const year = now.getFullYear();
        const month = String(now.getMonth() + 1).padStart(2, "0");
        const day = String(now.getDate()).padStart(2, "0");
        return `${year}-${month}-${day}`;
    }

    function getPageType() {
        const path = location.pathname;
        if (path.includes("/financial/record")) return "financial";
        if (path.includes("/manage")) return "manage";
        if (path.includes("/superManage")) return "super-manage";
        return "unknown";
    }

    function getAccountId() {
        if (state.config.accountIdOverride) return state.config.accountIdOverride;

        const query = new URLSearchParams(location.search);
        const candidateKeys = ["accountId", "account_id", "advertiserId", "advertiser_id", "cid"];
        for (const key of candidateKeys) {
            const value = query.get(key);
            if (value) return value;
        }

        return "未识别账号ID";
    }

    function getAccountName() {
        if (state.config.accountNameOverride) return state.config.accountNameOverride;

        const candidates = [
            ".account-info-name",
            ".account-name",
            "[class*='Account'] [class*='name']",
            "header [class*='name']",
        ];
        for (const selector of candidates) {
            const text = $(selector).first().text().trim();
            if (text) return text;
        }
        return document.title || "未识别账号";
    }

    function hasRecognizedAccountId() {
        const accountId = getAccountId();
        return Boolean(accountId && accountId !== "未识别账号ID");
    }

    function buildAlertAccountLabel() {
        return hasRecognizedAccountId() ? `${getAccountName()} (${getAccountId()})` : getAccountName();
    }

    function buildAccountInfoLines() {
        const lines = [`账号名称：${getAccountName()}`];
        if (hasRecognizedAccountId()) {
            lines.push(`账号ID：${getAccountId()}`);
        }
        return lines;
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

    function buildBusinessContext() {
        const lines = [
            `当前账号名称：${getAccountName()}`,
            `脚本实例ID：${state.instanceId}`,
            `当前页面类型：${getPageType()}`,
            `当前页面地址：${location.href}`,
        ];
        if (hasRecognizedAccountId()) {
            lines.splice(1, 0, `当前账号ID：${getAccountId()}`);
        }
        return lines.join("\n");
    }

    function getAnalyzeUrl() {
        return `${state.config.backendBaseUrl}/analyze`;
    }

    function getIngestUrl() {
        return `${state.config.backendBaseUrl}/ingest`;
    }

    function getHeartbeatUrl() {
        return `${state.config.backendBaseUrl}/heartbeat`;
    }

    function getErrorUrl() {
        return `${state.config.backendBaseUrl}/error`;
    }

    function getAlertRecordUrl() {
        return `${state.config.backendBaseUrl}/alert-record`;
    }

    function getThresholdAlertSeverity() {
        if (!state.config.notifyThreshold) return "medium";
        const ratio = state.increaseInWindow / state.config.notifyThreshold;
        if (ratio >= 2) return "high";
        if (ratio >= 1.2) return "medium";
        return "low";
    }

    function setBackendMessage(message) {
        state.lastBackendMessage = message;
        GM_setValue("last_backend_message", message);
        $("#backend-status").text(message);
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

    function buildCommonContext() {
        const rows = getRowsBySelectors();
        return {
            instance_id: state.instanceId,
            account_id: getAccountId(),
            account_name: getAccountName(),
            page_type: getPageType(),
            page_url: location.href,
            script_version: GM_info?.script?.version || "unknown",
            row_count: rows.length,
        };
    }

    async function sendHeartbeat(captureStatus = state.lastCaptureStatus || "warning", errorMessage = state.lastErrorMessage || "") {
        const now = Date.now();
        const payload = {
            ...buildCommonContext(),
            heartbeat_at: now,
            browser_visible: document.visibilityState === "visible",
            capture_status: captureStatus,
            last_capture_at: state.lastCheckTime || null,
            error_message: errorMessage || null,
        };

        try {
            const response = await gmRequest({
                method: "POST",
                url: getHeartbeatUrl(),
                headers: { "Content-Type": "application/json" },
                data: JSON.stringify(payload),
                timeout: 15000,
            });
            const body = JSON.parse(response.responseText || "{}");
            state.lastHeartbeatSentAt = now;
            GM_setValue("last_heartbeat_sent_at", now);
            setBackendMessage(`心跳成功 ${new Date(now).toLocaleTimeString()}`);
            return body;
        } catch (error) {
            setBackendMessage(`心跳失败 ${error?.error || error?.message || "unknown error"}`);
            return null;
        }
    }

    async function sendIngest() {
        const payload = {
            ...buildCommonContext(),
            captured_at: Date.now(),
            metrics: {
                current_spend: state.currentSpend,
                increase_amount: state.increaseInWindow,
                baseline_spend: state.baselineSpend,
                compare_interval_min: state.config.compareIntervalMin,
                notify_threshold: state.config.notifyThreshold,
            },
            raw_context: {
                history_samples: state.history.length,
                baseline_time: state.baselineTime,
                today: getTodayStr(),
                ai_enabled: state.config.aiEnabled,
                ai_provider: state.config.aiProvider,
                business_context: buildBusinessContext(),
            },
        };

        try {
            const response = await gmRequest({
                method: "POST",
                url: getIngestUrl(),
                headers: { "Content-Type": "application/json" },
                data: JSON.stringify(payload),
                timeout: 15000,
            });
            state.lastCaptureStatus = "success";
            state.lastErrorMessage = "";
            GM_setValue("last_capture_status", state.lastCaptureStatus);
            GM_setValue("last_error_message", "");
            setBackendMessage(`采集上报成功 ${new Date().toLocaleTimeString()}`);
            return JSON.parse(response.responseText || "{}");
        } catch (error) {
            const message = `采集上报失败：${error?.error || error?.message || "unknown error"}`;
            state.lastCaptureStatus = "error";
            state.lastErrorMessage = message;
            GM_setValue("last_capture_status", state.lastCaptureStatus);
            GM_setValue("last_error_message", message);
            setBackendMessage(message);
            await sendErrorReport("ingest_error", message);
            return null;
        }
    }

    async function sendErrorReport(errorType, errorMessage) {
        try {
            await gmRequest({
                method: "POST",
                url: getErrorUrl(),
                headers: { "Content-Type": "application/json" },
                data: JSON.stringify({
                    instance_id: state.instanceId,
                    occurred_at: Date.now(),
                    error_type: errorType,
                    error_message: errorMessage,
                    page_url: location.href,
                    script_version: GM_info?.script?.version || "unknown",
                }),
                timeout: 15000,
            });
        } catch (_error) {
            // Ignore report failures to avoid recursive error loops.
        }
    }

    async function sendAlertRecord(payload) {
        try {
            await gmRequest({
                method: "POST",
                url: getAlertRecordUrl(),
                headers: { "Content-Type": "application/json" },
                data: JSON.stringify(payload),
                timeout: 15000,
            });
        } catch (_error) {
            // Ignore backend alert-record failures to avoid blocking the user-facing alert.
        }
    }

    function buildAlertRecordPayload({ alertKind, title, contentPreview, sendStatus, providerResponse, severity, anomalyType, triggeredAt }) {
        return {
            ...buildCommonContext(),
            alert_kind: alertKind,
            title,
            content_preview: contentPreview || "",
            channel: state.config.pushplusChannel || "mail",
            channel_option: state.config.pushplusOption || "",
            delivery_provider: "pushplus",
            send_status: sendStatus,
            provider_response: providerResponse || null,
            severity: severity || null,
            anomaly_type: anomalyType || null,
            triggered_at: triggeredAt || Date.now(),
        };
    }

    async function requestAiAnalysis() {
        if (!state.config.aiEnabled) return "";

        const payload = {
            provider_override: state.config.aiProvider,
            event: buildEventPayload(),
            history: serializeHistory(),
            business_context: buildBusinessContext(),
        };

        try {
            const response = await gmRequest({
                method: "POST",
                url: getAnalyzeUrl(),
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

    async function pushAlert({ title, content, alertKind, contentPreview, severity, anomalyType }) {
        const triggeredAt = Date.now();
        if (!state.config.pushplusToken) {
            await sendAlertRecord(
                buildAlertRecordPayload({
                    alertKind,
                    title,
                    contentPreview,
                    sendStatus: "skipped",
                    providerResponse: "未配置 PushPlus Token",
                    severity,
                    anomalyType,
                    triggeredAt,
                })
            );
            return { ok: false, skipped: true };
        }

        try {
            const response = await gmRequest({
                method: "POST",
                url: "https://www.pushplus.plus/send",
                headers: { "Content-Type": "application/json" },
                data: JSON.stringify({
                    token: state.config.pushplusToken,
                    title,
                    content,
                    template: "html",
                    channel: state.config.pushplusChannel || "mail",
                    option: state.config.pushplusOption || "",
                }),
                timeout: 20000,
            });
            let body = {};
            try {
                body = JSON.parse(response.responseText || "{}");
            } catch (_error) {
                body = { raw: response.responseText || "" };
            }
            const ok = response.status >= 200 && response.status < 300 && (!body.code || body.code === 200);
            await sendAlertRecord(
                buildAlertRecordPayload({
                    alertKind,
                    title,
                    contentPreview,
                    sendStatus: ok ? "sent" : "failed",
                    providerResponse: JSON.stringify(body).slice(0, 500),
                    severity,
                    anomalyType,
                    triggeredAt,
                })
            );
            if (!ok) {
                setBackendMessage(`PushPlus 返回异常 ${body.msg || body.message || response.status}`);
            }
            return { ok, body };
        } catch (error) {
            const message = error?.error || error?.message || "unknown error";
            await sendAlertRecord(
                buildAlertRecordPayload({
                    alertKind,
                    title,
                    contentPreview,
                    sendStatus: "failed",
                    providerResponse: message,
                    severity,
                    anomalyType,
                    triggeredAt,
                })
            );
            setBackendMessage(`PushPlus 发送失败 ${message}`);
            return { ok: false, error: message };
        }
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
        $("#instance-id").text(state.instanceId);
        $("#backend-status").text(state.lastBackendMessage);
        renderAnalysisText(state.lastAnalysisText);
    }

    function saveConfigFromUI() {
        state.config.accountIdOverride = $("#account-id-override").val().trim();
        state.config.accountNameOverride = $("#account-name-override").val().trim();
        state.config.pushplusToken = $("#pushplus-token").val().trim();
        state.config.pushplusChannel = $("#pushplus-channel").val() || "mail";
        state.config.pushplusOption = $("#pushplus-option").val().trim();
        state.config.refreshIntervalMin = Number($("#refresh-interval").val()) || 5;
        state.config.compareIntervalMin = Number($("#compare-interval").val()) || 30;
        state.config.notifyThreshold = Number($("#notify-threshold").val()) || 1000;
        state.config.aiEnabled = $("#ai-enabled").val() === "true";
        state.config.aiProvider = $("#ai-provider").val() || "deepseek";
        state.config.backendBaseUrl = normalizeBackendBaseUrl($("#backend-base-url").val().trim());

        GM_setValue("account_id_override", state.config.accountIdOverride);
        GM_setValue("account_name_override", state.config.accountNameOverride);
        GM_setValue("pushplus_token", state.config.pushplusToken);
        GM_setValue("pushplus_channel", state.config.pushplusChannel);
        GM_setValue("pushplus_option", state.config.pushplusOption);
        GM_setValue("refresh_interval_min", state.config.refreshIntervalMin);
        GM_setValue("compare_interval_min", state.config.compareIntervalMin);
        GM_setValue("notify_threshold", state.config.notifyThreshold);
        GM_setValue("ai_enabled", state.config.aiEnabled);
        GM_setValue("ai_provider", state.config.aiProvider);
        GM_setValue("backend_base_url", state.config.backendBaseUrl);
        GM_setValue("analysis_gateway_url", `${state.config.backendBaseUrl}/analyze`);
    }

    function enablePanelDrag() {
        const panel = document.getElementById(CONFIG.panelId);
        if (!panel) return;
        const handle = panel.querySelector(".sentry-head");
        if (!handle) return;

        let isDragging = false;
        let offsetX = 0;
        let offsetY = 0;

        handle.addEventListener("mousedown", (event) => {
            if (["INPUT", "BUTTON", "SELECT", "TEXTAREA", "OPTION"].includes(event.target.tagName)) {
                return;
            }
            isDragging = true;
            const rect = panel.getBoundingClientRect();
            panel.style.right = "auto";
            panel.style.left = `${rect.left}px`;
            panel.style.top = `${rect.top}px`;
            offsetX = event.clientX - rect.left;
            offsetY = event.clientY - rect.top;
            event.preventDefault();
        });

        document.addEventListener("mousemove", (event) => {
            if (!isDragging) return;
            const nextLeft = Math.max(8, Math.min(window.innerWidth - panel.offsetWidth - 8, event.clientX - offsetX));
            const nextTop = Math.max(8, Math.min(window.innerHeight - panel.offsetHeight - 8, event.clientY - offsetY));
            panel.style.left = `${nextLeft}px`;
            panel.style.top = `${nextTop}px`;
        });

        document.addEventListener("mouseup", () => {
            if (!isDragging) return;
            isDragging = false;
            state.panelPosition.left = panel.style.left;
            state.panelPosition.top = panel.style.top;
            GM_setValue("panel_left", state.panelPosition.left);
            GM_setValue("panel_top", state.panelPosition.top);
        });
    }

    function restorePanelPosition() {
        const panel = document.getElementById(CONFIG.panelId);
        if (!panel) return;
        if (state.panelPosition.left && state.panelPosition.top) {
            panel.style.right = "auto";
            panel.style.left = state.panelPosition.left;
            panel.style.top = state.panelPosition.top;
        }
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
                    <div class="field-stack compact">
                        <div class="field-group">
                            <label for="backend-base-url">后端网关地址</label>
                            <input id="backend-base-url" type="text" value="${state.config.backendBaseUrl}" />
                        </div>
                        <div class="sentry-grid">
                            <div class="field-group">
                                <label for="account-name-override">账号名称(可选覆盖)</label>
                                <input id="account-name-override" type="text" value="${state.config.accountNameOverride}" placeholder="未填则自动识别" />
                            </div>
                            <div class="field-group">
                                <label for="account-id-override">账号ID(可选覆盖)</label>
                                <input id="account-id-override" type="text" value="${state.config.accountIdOverride}" placeholder="未填则尝试自动识别" />
                            </div>
                        </div>
                        <div class="field-group">
                            <label for="pushplus-token">PushPlus Token</label>
                            <input id="pushplus-token" type="password" value="${state.config.pushplusToken}" placeholder="输入 PushPlus Token" />
                        </div>
                        <div class="sentry-grid">
                            <div class="field-group">
                                <label for="pushplus-channel">PushPlus 渠道</label>
                                <select id="pushplus-channel">
                                    <option value="mail" ${state.config.pushplusChannel === "mail" ? "selected" : ""}>QQ邮箱 / 邮件</option>
                                    <option value="wechat" ${state.config.pushplusChannel === "wechat" ? "selected" : ""}>微信公众号</option>
                                    <option value="webhook" ${state.config.pushplusChannel === "webhook" ? "selected" : ""}>Webhook</option>
                                </select>
                            </div>
                            <div class="field-group">
                                <label for="pushplus-option">渠道编码(option)</label>
                                <input id="pushplus-option" type="text" value="${state.config.pushplusOption}" placeholder="邮件渠道可留空或填自定义邮件编码" />
                            </div>
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
                    <div class="status-stack">
                        <div><strong>实例 ID：</strong><span id="instance-id">${state.instanceId}</span></div>
                        <div><strong>后端状态：</strong><span id="backend-status">${state.lastBackendMessage}</span></div>
                        <div class="sentry-subtle">面板支持拖拽，位置会自动记住。</div>
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
        restorePanelPosition();
        enablePanelDrag();

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
            const alertTitle = `【磁力金牛】【测试】${buildAlertAccountLabel()}`;
            const previewLines = [
                "测试报警",
                ...buildAccountInfoLines(),
                `脚本实例：${state.instanceId}`,
                `当前总消耗：${formatMoney(state.currentSpend)}`,
                `${state.config.compareIntervalMin} 分钟增量：${formatMoney(state.increaseInWindow)}`,
                `分析结果：${analysisText || "未开启 AI 分析"}`,
            ];
            const alertResult = await pushAlert(
                {
                    title: alertTitle,
                    alertKind: "test",
                    contentPreview: previewLines.join("\n"),
                    severity: "info",
                    anomalyType: "test_alert",
                    content: `
                <div style="font-family:sans-serif;padding:12px;">
                    <h3>测试报警</h3>
                    <p>账号名称：${getAccountName()}</p>
                    ${hasRecognizedAccountId() ? `<p>账号ID：${getAccountId()}</p>` : ""}
                    <p>脚本实例：${state.instanceId}</p>
                    <p>当前总消耗：${formatMoney(state.currentSpend)}</p>
                    <p>${state.config.compareIntervalMin} 分钟增量：${formatMoney(state.increaseInWindow)}</p>
                    <pre style="white-space:pre-wrap;">${analysisText || "未开启 AI 分析"}</pre>
                </div>
                `,
                }
            );
            if (alertResult.ok) {
                alert("测试报警已发送。");
            } else if (alertResult.skipped) {
                alert("未配置 PushPlus Token，后台已记录为跳过。");
            } else {
                alert("测试报警发送失败，后台已记录失败结果。");
            }
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
        const title = `【磁力金牛预警】${buildAlertAccountLabel()}`;
        const previewLines = [
            "消耗异常提醒",
            ...buildAccountInfoLines(),
            `脚本实例：${state.instanceId}`,
            `页面类型：${getPageType()}`,
            `当前总消耗：${formatMoney(state.currentSpend)}`,
            `对比窗口：${state.config.compareIntervalMin} 分钟`,
            `窗口增量：${formatMoney(state.increaseInWindow)}`,
            `阈值：${formatMoney(state.config.notifyThreshold)}`,
            `分析结果：${analysisText || "未开启 AI 分析"}`,
        ];
        const content = `
            <div style="font-family:sans-serif;padding:14px;border:1px solid #e5e7eb;border-radius:8px;">
                <h2 style="color:#b91c1c;">消耗异常提醒</h2>
                <p>账号名称：<strong>${getAccountName()}</strong></p>
                ${hasRecognizedAccountId() ? `<p>账号ID：<strong>${getAccountId()}</strong></p>` : ""}
                <p>脚本实例：<strong>${state.instanceId}</strong></p>
                <p>页面类型：<strong>${getPageType()}</strong></p>
                <p>当前总消耗：<strong>${formatMoney(state.currentSpend)}</strong></p>
                <p>对比窗口：<strong>${state.config.compareIntervalMin} 分钟</strong></p>
                <p>窗口增量：<strong style="color:#b91c1c;">${formatMoney(state.increaseInWindow)}</strong></p>
                <p>阈值：<strong>${formatMoney(state.config.notifyThreshold)}</strong></p>
                <p>基线时间：${state.baselineTime ? new Date(state.baselineTime).toLocaleString() : "-"}</p>
                <p>后端地址：${state.config.backendBaseUrl}</p>
                <h3>AI 分析</h3>
                <pre style="white-space:pre-wrap;font-size:12px;background:#f8fafc;padding:10px;border-radius:6px;">${analysisText || "未开启 AI 分析"}</pre>
            </div>
        `;

        await pushAlert({
            title,
            content,
            alertKind: "threshold",
            contentPreview: previewLines.join("\n"),
            severity: getThresholdAlertSeverity(),
            anomalyType: "threshold_breach",
        });

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
        try {
            const spend = scrapeTodaySpend();
            if (spend < 0) {
                state.lastCaptureStatus = "warning";
                state.lastErrorMessage = "未找到今日消耗数据行";
                GM_setValue("last_capture_status", state.lastCaptureStatus);
                GM_setValue("last_error_message", state.lastErrorMessage);
                renderStatus();
                await sendHeartbeat("warning", state.lastErrorMessage);
                return;
            }

            state.currentSpend = spend;
            appendHistory(spend);

            const baseline = getBaselineRecord();
            state.baselineSpend = baseline.spend;
            state.baselineTime = baseline.time;
            state.increaseInWindow = Math.max(0, spend - baseline.spend);
            state.lastCheckTime = Date.now();
            state.lastCaptureStatus = "success";
            state.lastErrorMessage = "";
            GM_setValue("last_capture_status", state.lastCaptureStatus);
            GM_setValue("last_error_message", "");

            renderStatus();
            await sendIngest();
            await handleThresholdAlert();
        } catch (error) {
            const message = `采集失败：${error?.message || "unknown error"}`;
            state.lastCaptureStatus = "error";
            state.lastErrorMessage = message;
            GM_setValue("last_capture_status", state.lastCaptureStatus);
            GM_setValue("last_error_message", message);
            setBackendMessage(message);
            await sendErrorReport("capture_error", message);
            await sendHeartbeat("error", message);
        }
    }

    async function mainLoop() {
        const refreshMs = state.config.refreshIntervalMin * 60 * 1000;
        if (Date.now() - state.lastReloadTime >= refreshMs) {
            GM_setValue("last_reload_time", Date.now());
            location.reload();
            return;
        }

        if (Date.now() - state.lastHeartbeatSentAt >= CONFIG.heartbeatIntervalMs) {
            await sendHeartbeat(state.lastCaptureStatus, state.lastErrorMessage);
        }

        renderStatus();
    }

    function bindStartup() {
        addStyles();
        createPanel();
        renderStatus();

        setTimeout(async () => {
            await evaluateSpend();
            await sendHeartbeat(state.lastCaptureStatus, state.lastErrorMessage);
            setInterval(() => {
                mainLoop().catch(() => {});
            }, CONFIG.uiTickMs);
        }, CONFIG.checkDelayMs);
    }

    $(document).ready(bindStartup);
})();
