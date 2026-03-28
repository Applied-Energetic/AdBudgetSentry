// ==UserScript==
// @name         磁力金牛财务报警助手
// @namespace    http://tampermonkey.net/
// @version      2.4.0
// @description  监控磁力金牛财务页消耗，并由本地后端统一负责分析与告警
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
		sampleIntervalMs: 60 * 1000,
		heartbeatIntervalMs: 2 * 60 * 1000,
		scrapeRetryCount: 10,
		scrapeRetryDelayMs: 1500,
		defaultBackendBaseUrl: "http://127.0.0.1:8787",
		audioAlertUrl:
			"https://actions.google.com/sounds/v1/alarms/alarm_clock_short.ogg",
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
		currentSpend: GM_getValue("current_spend", 0),
		increaseInWindow: GM_getValue("increase_in_window", 0),
		baselineSpend: GM_getValue("baseline_spend", 0),
		baselineTime: GM_getValue("baseline_time", 0),
		lastCheckTime: GM_getValue("last_check_time", 0),
		lastEvaluateAttemptAt: GM_getValue("last_evaluate_attempt_at", 0),
		lastReloadTime: GM_getValue("last_reload_time", Date.now()),
		lastAnalysisText: GM_getValue("last_analysis_text", ""),
		lastBackendMessage: GM_getValue("last_backend_message", "等待上报"),
		lastHeartbeatSentAt: GM_getValue("last_heartbeat_sent_at", 0),
		lastCaptureStatus: GM_getValue("last_capture_status", "warning"),
		lastErrorMessage: GM_getValue("last_error_message", ""),
		history: GM_getValue("spend_history", []),
		isEvaluating: false,
		config: {
			accountIdOverride: GM_getValue("account_id_override", ""),
			accountNameOverride: GM_getValue("account_name_override", ""),
			refreshIntervalMin: GM_getValue("refresh_interval_min", 5),
			compareIntervalMin: GM_getValue("compare_interval_min", 30),
			notifyThreshold: GM_getValue("notify_threshold", 1000),
			aiEnabled: GM_getValue("ai_enabled", true),
			aiProvider: GM_getValue("ai_provider", "deepseek"),
			backendBaseUrl: normalizeBackendBaseUrl(
				GM_getValue(
					"backend_base_url",
					GM_getValue(
						"analysis_gateway_url",
						CONFIG.defaultBackendBaseUrl,
					),
				),
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
                width: 320px;
                background: #ffffff;
                color: #1e293b;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                box-shadow: 0 10px 25px rgba(15, 23, 42, 0.15);
                font-family: "Avenir Next", "PingFang SC", "Microsoft YaHei", sans-serif;
                overflow: hidden;
                display: flex;
                flex-direction: column;
                max-height: 90vh;
            }
            #${CONFIG.panelId} .sentry-head {
                background: #0f172a;
                color: #f8fafc;
                padding: 10px 14px;
                font-size: 13px;
                font-weight: 600;
                display: flex;
                justify-content: space-between;
                align-items: center;
                cursor: move;
                user-select: none;
            }
            #${CONFIG.panelId} .sentry-head-right {
                display: flex;
                gap: 10px;
                align-items: center;
                font-size: 12px;
                color: #94a3b8;
                font-weight: normal;
            }
            #${CONFIG.panelId} .sentry-body {
                padding: 14px;
                overflow-y: auto;
                flex: 1;
            }
            #${CONFIG.panelId} .sentry-section-label {
                font-size: 12px;
                font-weight: 600;
                color: #475569;
                margin: 14px 0 8px;
                border-bottom: 1px solid #e2e8f0;
                padding-bottom: 4px;
            }
            #${CONFIG.panelId} .sentry-section-label:first-child {
                margin-top: 0;
            }
            #${CONFIG.panelId} .sentry-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 8px;
            }
            #${CONFIG.panelId} .metric {
                background: #f1f5f9;
                border-radius: 6px;
                padding: 8px 10px;
                border: 1px solid #e2e8f0;
            }
            #${CONFIG.panelId} .metric-label {
                display: block;
                font-size: 11px;
                color: #64748b;
                margin-bottom: 2px;
            }
            #${CONFIG.panelId} .metric-value {
                font-size: 16px;
                font-weight: 700;
                color: #0f766e;
            }
            #${CONFIG.panelId} .status-stack {
                display: grid;
                gap: 4px;
                font-size: 11px;
                color: #475569;
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                padding: 8px 10px;
                margin-top: 8px;
            }
            #${CONFIG.panelId} .status-stack strong {
                color: #1e293b;
            }
            #${CONFIG.panelId} .analysis-box {
                margin-top: 8px;
                background: #1e293b;
                color: #e2e8f0;
                border-radius: 6px;
                padding: 10px;
                font-size: 12px;
                line-height: 1.6;
                white-space: pre-wrap;
                min-height: 60px;
                max-height: 200px;
                overflow-y: auto;
                word-break: break-all;
            }
            #${CONFIG.panelId} .config-toggle {
                font-size: 12px;
                color: #0284c7;
                cursor: pointer;
                text-align: center;
                margin: 10px 0;
                padding: 4px;
            }
            #${CONFIG.panelId} .config-toggle:hover {
                text-decoration: underline;
            }
            #${CONFIG.panelId} .config-area {
                display: none;
                margin-bottom: 4px;
            }
            #${CONFIG.panelId} .field-group {
                margin-bottom: 8px;
            }
            #${CONFIG.panelId} label {
                display: block;
                font-size: 11px;
                color: #64748b;
                margin-bottom: 3px;
            }
            #${CONFIG.panelId} input,
            #${CONFIG.panelId} select {
                width: 100%;
                height: 28px;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 0 8px;
                font-size: 12px;
                box-sizing: border-box;
                background: #fff;
                color: #1e293b;
            }
            #${CONFIG.panelId} .button-row {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 8px;
                margin-bottom: 8px;
            }
            #${CONFIG.panelId} button {
                height: 28px;
                border: 1px solid transparent;
                border-radius: 4px;
                font-size: 12px;
                cursor: pointer;
                font-weight: 500;
                transition: all 0.15s;
            }
            #save-config-btn {
                width: 100%;
                margin-bottom: 10px;
                background: #0f766e;
                color: #fff;
            }
            #save-config-btn:hover { background: #115e59; }
            #manual-refresh-btn, #reset-history-btn {
                background: #f1f5f9;
                color: #334155;
                border-color: #cbd5e1;
            }
            #manual-refresh-btn:hover, #reset-history-btn:hover { background: #e2e8f0; }
            #test-alert-btn {
                background: #fffbeb;
                color: #b45309;
                border-color: #fde68a;
            }
            #test-alert-btn:hover { background: #fef3c7; }
            #run-ai-btn {
                background: #eff6ff;
                color: #1d4ed8;
                border-color: #bfdbfe;
            }
            #run-ai-btn:hover { background: #dbeafe; }
            #${CONFIG.panelId} .sentry-subtle {
                color: #94a3b8;
                font-size: 10px;
                text-align: center;
                margin-top: 8px;
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
		if (state.config.accountIdOverride)
			return state.config.accountIdOverride;

		const query = new URLSearchParams(location.search);
		const candidateKeys = [
			"accountId",
			"account_id",
			"advertiserId",
			"advertiser_id",
			"cid",
		];
		for (const key of candidateKeys) {
			const value = query.get(key);
			if (value) return value;
		}

		return "未识别账号ID";
	}

	function getAccountName() {
		if (state.config.accountNameOverride)
			return state.config.accountNameOverride;

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
		return hasRecognizedAccountId()
			? `${getAccountName()} (${getAccountId()})`
			: getAccountName();
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

	function sleep(ms) {
		return new Promise((resolve) => setTimeout(resolve, ms));
	}

	function trimHistory() {
		const now = Date.now();
		state.history = state.history.filter(
			(item) => now - item.time <= CONFIG.historyRetentionMs,
		);
	}

	function persistRuntimeMetrics() {
		GM_setValue("current_spend", state.currentSpend);
		GM_setValue("increase_in_window", state.increaseInWindow);
		GM_setValue("baseline_spend", state.baselineSpend);
		GM_setValue("baseline_time", state.baselineTime);
		GM_setValue("last_check_time", state.lastCheckTime);
		GM_setValue("last_evaluate_attempt_at", state.lastEvaluateAttemptAt);
	}

	function appendHistory(spend) {
		const now = Date.now();
		const lastPoint = state.history[state.history.length - 1];
		if (
			!lastPoint ||
			Math.abs(lastPoint.spend - spend) > 0.009 ||
			now - lastPoint.time >= 55 * 1000
		) {
			state.history.push({ time: now, spend });
		}
		trimHistory();
		GM_setValue("spend_history", state.history);
	}

	function getBaselineRecord() {
		const compareStart =
			Date.now() - state.config.compareIntervalMin * 60 * 1000;
		const fallback = state.history[0] || {
			time: Date.now(),
			spend: state.currentSpend,
		};
		let latestBeforeWindow = null;
		let earliestAfterWindow = null;

		for (const item of state.history) {
			if (item.time <= compareStart) {
				latestBeforeWindow = item;
				continue;
			}
			if (!earliestAfterWindow) {
				earliestAfterWindow = item;
			}
		}

		return latestBeforeWindow || earliestAfterWindow || fallback;
	}

	async function scrapeTodaySpendWithRetry() {
		let spend = -1;
		for (let attempt = 0; attempt < CONFIG.scrapeRetryCount; attempt++) {
			spend = scrapeTodaySpend();
			if (spend >= 0) {
				return spend;
			}
			if (attempt < CONFIG.scrapeRetryCount - 1) {
				await sleep(CONFIG.scrapeRetryDelayMs);
			}
		}
		return spend;
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

	function getTestAlertUrl() {
		return `${state.config.backendBaseUrl}/alerts/test`;
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

	async function sendHeartbeat(
		captureStatus = state.lastCaptureStatus || "warning",
		errorMessage = state.lastErrorMessage || "",
	) {
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
			setBackendMessage(
				`心跳失败 ${error?.error || error?.message || "unknown error"}`,
			);
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
			setBackendMessage(
				`采集上报成功 ${new Date().toLocaleTimeString()}`,
			);
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

	async function triggerBackendTestAlert(analysisText) {
		try {
			const response = await gmRequest({
				method: "POST",
				url: getTestAlertUrl(),
				headers: { "Content-Type": "application/json" },
				data: JSON.stringify({
					...buildCommonContext(),
					current_spend: state.currentSpend,
					increase_amount: state.increaseInWindow,
					compare_interval_min: state.config.compareIntervalMin,
					baseline_spend: state.baselineSpend || null,
					baseline_time: state.baselineTime || null,
					analysis_text: analysisText || "",
					triggered_at: Date.now(),
				}),
				timeout: 20000,
			});
			return JSON.parse(response.responseText || "{}");
		} catch (error) {
			return {
				ok: false,
				message: error?.error || error?.message || "unknown error",
			};
		}
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

	function renderAnalysisText(text) {
		$("#analysis-output").text(text || "暂无 AI 分析结果。");
	}

	function renderStatus() {
		$("#metric-total").text(formatMoney(state.currentSpend));
		$("#metric-window").text(formatMoney(state.increaseInWindow));

		const nextReloadAt =
			state.lastReloadTime + state.config.refreshIntervalMin * 60 * 1000;
		const diffSec = Math.max(
			0,
			Math.floor((nextReloadAt - Date.now()) / 1000),
		);
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
		state.config.accountNameOverride = $("#account-name-override")
			.val()
			.trim();
		state.config.refreshIntervalMin =
			Number($("#refresh-interval").val()) || 5;
		state.config.compareIntervalMin =
			Number($("#compare-interval").val()) || 30;
		state.config.notifyThreshold =
			Number($("#notify-threshold").val()) || 1000;
		state.config.aiEnabled = $("#ai-enabled").val() === "true";
		state.config.aiProvider = $("#ai-provider").val() || "deepseek";
		state.config.backendBaseUrl = normalizeBackendBaseUrl(
			$("#backend-base-url").val().trim(),
		);

		GM_setValue("account_id_override", state.config.accountIdOverride);
		GM_setValue("account_name_override", state.config.accountNameOverride);
		GM_setValue("refresh_interval_min", state.config.refreshIntervalMin);
		GM_setValue("compare_interval_min", state.config.compareIntervalMin);
		GM_setValue("notify_threshold", state.config.notifyThreshold);
		GM_setValue("ai_enabled", state.config.aiEnabled);
		GM_setValue("ai_provider", state.config.aiProvider);
		GM_setValue("backend_base_url", state.config.backendBaseUrl);
		GM_setValue(
			"analysis_gateway_url",
			`${state.config.backendBaseUrl}/analyze`,
		);
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
			if (
				["INPUT", "BUTTON", "SELECT", "TEXTAREA", "OPTION"].includes(
					event.target.tagName,
				)
			) {
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
			const nextLeft = Math.max(
				8,
				Math.min(
					window.innerWidth - panel.offsetWidth - 8,
					event.clientX - offsetX,
				),
			);
			const nextTop = Math.max(
				8,
				Math.min(
					window.innerHeight - panel.offsetHeight - 8,
					event.clientY - offsetY,
				),
			);
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
                    <span>AdBudgetSentry</span>
                    <div class="sentry-head-right">
                        <span>刷新: <span id="refresh-countdown">--:--</span></span>
                    </div>
                </div>
                <div class="sentry-body">
                    <div class="sentry-section-label">实时监控</div>
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
                    <div class="status-stack">
                        <div><strong>通信：</strong><span id="backend-status">${state.lastBackendMessage}</span></div>
                        <div style="display:flex; justify-content:space-between;">
                            <span><strong>实例：</strong><span id="instance-id">${state.instanceId}</span></span>
                            <span>更新：<span id="last-update-time">-</span></span>
                        </div>
                    </div>

                    <div class="sentry-section-label">最近分析</div>
                    <div class="analysis-box" id="analysis-output">暂无 AI 分析结果。</div>

                    <div class="config-toggle" id="toggle-config-btn">⚙️ 展开配置与操作</div>
                    <div class="config-area" id="config-area-wrap">
                        <div class="field-group">
                            <label for="backend-base-url">后端网关地址</label>
                            <input id="backend-base-url" type="text" value="${state.config.backendBaseUrl}" />
                        </div>
                        <div class="sentry-grid">
                            <div class="field-group">
                                <label for="account-name-override">账号名称(可选覆盖)</label>
                                <input id="account-name-override" type="text" value="${state.config.accountNameOverride}" placeholder="自动识别" />
                            </div>
                            <div class="field-group">
                                <label for="account-id-override">账号ID(可选覆盖)</label>
                                <input id="account-id-override" type="text" value="${state.config.accountIdOverride}" placeholder="自动识别" />
                            </div>
                        </div>
                        <div class="status-stack" style="margin: 0 0 10px 0;">
                            <div><strong>告警发送：</strong>已改由后端统一处理</div>
                            <div>PushPlus Token、渠道和冷却规则请在后端配置文件中维护。</div>
                        </div>
                        <div class="sentry-grid">
                            <div class="field-group">
                                <label for="refresh-interval">刷新(分钟)</label>
                                <input id="refresh-interval" type="number" value="${state.config.refreshIntervalMin}" />
                            </div>
                            <div class="field-group">
                                <label for="compare-interval">窗口(分钟)</label>
                                <input id="compare-interval" type="number" value="${state.config.compareIntervalMin}" />
                            </div>
                        </div>
                        <div class="sentry-grid">
                            <div class="field-group">
                                <label for="notify-threshold">阈值(元)</label>
                                <input id="notify-threshold" type="number" value="${state.config.notifyThreshold}" />
                            </div>
                            <div class="field-group">
                                <label for="ai-enabled">智能分析</label>
                                <select id="ai-enabled">
                                    <option value="true" ${state.config.aiEnabled ? "selected" : ""}>开启</option>
                                    <option value="false" ${state.config.aiEnabled ? "" : "selected"}>关闭</option>
                                </select>
                            </div>
                        </div>
                        <div class="field-group">
                            <label for="ai-provider">分析路线</label>
                            <select id="ai-provider">
                                <option value="local" ${state.config.aiProvider === "local" ? "selected" : ""}>本地 Qwen/OpenAI</option>
                                <option value="deepseek" ${state.config.aiProvider === "deepseek" ? "selected" : ""}>DeepSeek API</option>
                            </select>
                        </div>
                        
                        <button id="save-config-btn">保存配置</button>
                        <div class="button-row">
                            <button id="manual-refresh-btn">手动刷新</button>
                            <button id="test-alert-btn">测试报警</button>
                        </div>
                        <div class="button-row">
                            <button id="reset-history-btn">清空历史</button>
                            <button id="run-ai-btn">立即分析</button>
                        </div>
                        <div class="sentry-subtle">面板支持拖拽，位置自动记忆</div>
                    </div>
                </div>
            </div>
        `;

		$("body").append(html);
		restorePanelPosition();
		enablePanelDrag();

		// 交互：切换设置菜单的展开状态
		$("#toggle-config-btn").on("click", function () {
			const area = $("#config-area-wrap");
			if (area.is(":visible")) {
				area.hide();
				$(this).text("⚙️ 展开配置与操作");
			} else {
				area.show();
				$(this).text("收起配置与操作");
			}
		});

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
			state.baselineSpend = 0;
			state.baselineTime = 0;
			state.currentSpend = 0;
			state.increaseInWindow = 0;
			state.lastCheckTime = 0;
			state.lastEvaluateAttemptAt = 0;
			GM_setValue("spend_history", []);
			state.lastAnalysisText = "";
			GM_setValue("last_analysis_text", "");
			persistRuntimeMetrics();
			renderStatus();
			alert("历史数据已重置。");
		});

		$("#test-alert-btn").on("click", async () => {
			saveConfigFromUI();
			const analysisText = await requestAiAnalysis();
			const result = await triggerBackendTestAlert(analysisText);
			if (result.ok) {
				setBackendMessage("后端测试报警已发送");
				alert("测试报警已发送。");
			} else {
				setBackendMessage(`后端测试报警失败 ${result.message || "unknown error"}`);
				alert("测试报警发送失败，请检查后端 PushPlus 配置。");
			}
		});

		$("#run-ai-btn").on("click", async () => {
			saveConfigFromUI();
			const analysisText = await requestAiAnalysis();
			renderAnalysisText(analysisText);
		});
	}

	async function evaluateSpend() {
		if (state.isEvaluating) return;
		state.isEvaluating = true;
		state.lastEvaluateAttemptAt = Date.now();
		GM_setValue("last_evaluate_attempt_at", state.lastEvaluateAttemptAt);
		try {
			const spend = await scrapeTodaySpendWithRetry();
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
			persistRuntimeMetrics();

			renderStatus();
			await sendIngest();
		} catch (error) {
			const message = `采集失败：${error?.message || "unknown error"}`;
			state.lastCaptureStatus = "error";
			state.lastErrorMessage = message;
			GM_setValue("last_capture_status", state.lastCaptureStatus);
			GM_setValue("last_error_message", message);
			setBackendMessage(message);
			await sendErrorReport("capture_error", message);
			await sendHeartbeat("error", message);
		} finally {
			state.isEvaluating = false;
		}
	}

	async function mainLoop() {
		const now = Date.now();
		const refreshMs = state.config.refreshIntervalMin * 60 * 1000;
		if (now - state.lastReloadTime >= refreshMs) {
			GM_setValue("last_reload_time", now);
			location.reload();
			return;
		}

		if (
			!state.isEvaluating &&
			now - state.lastEvaluateAttemptAt >= CONFIG.sampleIntervalMs
		) {
			await evaluateSpend();
		}

		if (now - state.lastHeartbeatSentAt >= CONFIG.heartbeatIntervalMs) {
			await sendHeartbeat(
				state.lastCaptureStatus,
				state.lastErrorMessage,
			);
		}

		renderStatus();
	}

	function bindStartup() {
		addStyles();
		createPanel();
		renderStatus();

		setTimeout(async () => {
			await evaluateSpend();
			await sendHeartbeat(
				state.lastCaptureStatus,
				state.lastErrorMessage,
			);
			setInterval(() => {
				mainLoop().catch(() => {});
			}, CONFIG.uiTickMs);
		}, CONFIG.checkDelayMs);
	}

	$(document).ready(bindStartup);
})();
