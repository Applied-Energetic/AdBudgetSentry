// ==UserScript==
// @name         磁力金牛财务报警助手
// @namespace    http://tampermonkey.net/
// @version      2.6.1
// @description  磁力金牛悬浮监控面板，支持采集、告警、AI 分析、设置和主题切换
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

	const C = { id: "ad-budget-sentry-panel", keepMs: 864e5, checkDelay: 3000, uiTick: 1000, sampleMs: 6e4, heartbeatMs: 12e4, retryCount: 10, retryDelay: 1500, backend: "http://127.0.0.1:8787" };
	const K = { i: "instance_id", l: "panel_left", t: "panel_top", cs: "current_spend", inc: "increase_in_window", bs: "baseline_spend", bt: "baseline_time", lc: "last_check_time", la: "last_eval", lr: "last_reload_time", lt: "last_analysis_text", lm: "last_backend_message", lh: "last_heartbeat_sent_at", st: "last_capture_status", le: "last_error_message", h: "spend_history", aid: "account_id_override", anm: "account_name_override", ri: "refresh_interval_min", ci: "compare_interval_min", th: "notify_threshold", ae: "ai_enabled", ap: "ai_provider", bu: "backend_base_url", au: "analysis_gateway_url", theme: "ui_theme_mode" };
	const THEMES = ["system", "light", "dark"];
	const getVal = (k, d) => { const v = GM_getValue(k, d); return v === undefined || v === null ? d : v; };
	const setVal = (k, v) => GM_setValue(k, v);
	const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
	const fmtMoney = (v) => `${Number(v || 0).toFixed(2)} 元`;
	const backendBase = (v) => String(v || C.backend).trim().replace(/\/analyze$/i, "").replace(/\/$/, "") || C.backend;

	const state = {
		id: String(getVal(K.i, `tm-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`)),
		pos: { left: getVal(K.l, null), top: getVal(K.t, null) },
		current: Number(getVal(K.cs, 0)) || 0,
		increase: Number(getVal(K.inc, 0)) || 0,
		base: Number(getVal(K.bs, 0)) || 0,
		baseTime: Number(getVal(K.bt, 0)) || 0,
		lastCheck: Number(getVal(K.lc, 0)) || 0,
		lastEval: Number(getVal(K.la, 0)) || 0,
		lastReload: Number(getVal(K.lr, Date.now())) || Date.now(),
		lastAnalysis: String(getVal(K.lt, "")),
		lastBackend: String(getVal(K.lm, "后端空闲")),
		lastHeartbeat: Number(getVal(K.lh, 0)) || 0,
		lastStatus: String(getVal(K.st, "warning")),
		lastError: String(getVal(K.le, "")),
		history: Array.isArray(getVal(K.h, [])) ? getVal(K.h, []) : [],
		theme: THEMES.includes(String(getVal(K.theme, "system"))) ? String(getVal(K.theme, "system")) : "system",
		evaluating: false,
		cfg: {
			accountId: String(getVal(K.aid, "")),
			accountName: String(getVal(K.anm, "")),
			refresh: Number(getVal(K.ri, 5)) || 5,
			compare: Number(getVal(K.ci, 30)) || 30,
			threshold: Number(getVal(K.th, 1000)) || 1000,
			aiEnabled: getVal(K.ae, true) !== false,
			aiProvider: String(getVal(K.ap, "deepseek")),
			backend: backendBase(getVal(K.bu, getVal(K.au, C.backend))),
		},
	};
	setVal(K.i, state.id);

	const ui = { panel: null, dragging: false, ox: 0, oy: 0 };
	const qs = (sel) => (ui.panel ? ui.panel.querySelector(sel) : null);
	const put = (sel, text) => { const el = qs(sel); if (el) el.textContent = text; };

	const pageType = () => location.pathname.includes("/financial/record") ? "financial" : location.pathname.includes("/manage") ? "manage" : location.pathname.includes("/superManage") ? "super-manage" : "unknown";
	function accountId() { if (state.cfg.accountId) return state.cfg.accountId; const q = new URLSearchParams(location.search); for (const k of ["accountId", "account_id", "advertiserId", "advertiser_id", "cid"]) { const v = q.get(k); if (v) return v; } return "未知账号"; }
	function accountName() { if (state.cfg.accountName) return state.cfg.accountName; for (const s of [".account-info-name", ".account-name", "[class*='Account'] [class*='name']", "header [class*='name']"]) { const el = document.querySelector(s); const txt = el ? el.textContent.trim() : ""; if (txt) return txt; } return document.title || "未知账号"; }
	function rows() { for (const s of ["#root section section main table tbody tr", ".ant-table-tbody tr.ant-table-row", ".ant-table-row"]) { const els = document.querySelectorAll(s); if (els.length) return els; } return []; }
	function scrapeSpend() { const d = new Date(); const ds = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; for (const row of rows()) { const cells = row.querySelectorAll("td"); if (cells.length < 2) continue; const txt = cells[0].textContent.trim(); if (txt === ds || txt.includes(ds)) return parseFloat(String(cells[1].textContent).replace(/[^\d.-]/g, "")) || 0; } return -1; }
	async function scrapeSpendRetry() { let spend = -1; for (let i = 0; i < C.retryCount; i += 1) { spend = scrapeSpend(); if (spend >= 0) return spend; if (i < C.retryCount - 1) await sleep(C.retryDelay); } return spend; }
	function ctx() { return { instance_id: state.id, account_id: accountId(), account_name: accountName(), page_type: pageType(), page_url: location.href, script_version: (typeof GM_info !== "undefined" && GM_info.script && GM_info.script.version) || "unknown", row_count: rows().length }; }
	function request(url, body) { return new Promise((resolve, reject) => GM_xmlhttpRequest({ method: "POST", url, headers: { "Content-Type": "application/json" }, data: JSON.stringify(body), timeout: 45000, onload: resolve, onerror: reject, ontimeout: reject })); }
	function trimHistory() { const now = Date.now(); state.history = state.history.filter((x) => now - x.time <= C.keepMs); }
	function pushHistory(spend) { const now = Date.now(); const last = state.history[state.history.length - 1]; if (!last || Math.abs(last.spend - spend) > 0.009 || now - last.time >= 55e3) state.history.push({ time: now, spend }); trimHistory(); setVal(K.h, state.history); }
	function baseline() { const start = Date.now() - state.cfg.compare * 6e4; const fallback = state.history[0] || { time: Date.now(), spend: state.current }; let before = null; let after = null; for (const item of state.history) { if (item.time <= start) before = item; else if (!after) after = item; } return before || after || fallback; }
	function persist() { setVal(K.cs, state.current); setVal(K.inc, state.increase); setVal(K.bs, state.base); setVal(K.bt, state.baseTime); setVal(K.lc, state.lastCheck); setVal(K.la, state.lastEval); setVal(K.lr, state.lastReload); setVal(K.lh, state.lastHeartbeat); setVal(K.st, state.lastStatus); setVal(K.le, state.lastError); setVal(K.lm, state.lastBackend); }
	function effectiveTheme() { return state.theme === "system" ? (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light") : state.theme; }

	function addStyles() {
		GM_addStyle(`#${C.id}{position:fixed;top:14px;right:14px;z-index:99999;width:min(360px,calc(100vw - 20px));max-height:84vh;display:flex;flex-direction:column;overflow:hidden;border-radius:20px;border:1px solid rgba(148,163,184,.24);background:rgba(255,255,255,.96);color:#142033;box-shadow:0 18px 42px rgba(15,23,42,.18);backdrop-filter:blur(18px);font-family:"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;--ink:#142033;--muted:#617085;--border:rgba(148,163,184,.24);--soft:#f4f7fb;--accent:#0f766e}#${C.id}[data-theme=dark]{background:rgba(15,23,42,.96);color:#e6eef9;box-shadow:0 18px 42px rgba(2,6,23,.42);--ink:#e6eef9;--muted:#94a3b8;--border:rgba(148,163,184,.18);--soft:rgba(30,41,59,.96);--accent:#5eead4}#${C.id} *{box-sizing:border-box}#${C.id} .head{display:flex;justify-content:space-between;gap:10px;align-items:center;padding:12px 16px;background:linear-gradient(135deg,rgba(16,76,103,.96),rgba(16,24,40,.94));color:#fff;cursor:move;user-select:none}#${C.id} .body{padding:16px;overflow-y:auto;display:grid;gap:12px}#${C.id} .grid,#${C.id} .actions,#${C.id} .theme{display:grid;gap:8px;grid-template-columns:1fr 1fr}#${C.id} .theme{grid-template-columns:repeat(3,1fr)}#${C.id} .card,#${C.id} .metric,#${C.id} .toggle,#${C.id} input,#${C.id} select,#${C.id} .analysis{border:1px solid var(--border);background:var(--soft);border-radius:14px}#${C.id} .metric,#${C.id} .card,#${C.id} .analysis{padding:12px}#${C.id} .small{font-size:11px;color:var(--muted)}#${C.id} .big{font-size:18px;font-weight:800;color:var(--accent)}#${C.id} .analysis{min-height:72px;max-height:200px;overflow:auto;white-space:pre-wrap;line-height:1.65;background:rgba(15,23,42,.96);color:#e2e8f0}#${C.id} .toggle{padding:8px 12px;text-align:center;font-size:12px;color:var(--accent);cursor:pointer}#${C.id} .config{display:none;gap:10px}#${C.id} label{display:block;font-size:11px;color:var(--muted);margin-bottom:4px}#${C.id} input,#${C.id} select{width:100%;min-height:36px;padding:0 10px;color:var(--ink)}#${C.id} button{min-height:38px;border-radius:12px;border:1px solid transparent;cursor:pointer;font:inherit;font-weight:600}#${C.id} .primary{background:linear-gradient(135deg,#0f766e,#115e59);color:#fff}#${C.id} .soft{background:var(--soft);color:var(--ink);border-color:var(--border)}#${C.id} .warn{background:#fffbeb;color:#b45309;border-color:#fde68a}#${C.id} .theme button{background:var(--soft);color:var(--ink);border-color:var(--border)}#${C.id} .theme button[data-active=true]{outline:2px solid rgba(94,234,212,.24)}#${C.id} .subtle{font-size:11px;color:var(--muted);line-height:1.5}@media (max-width:640px){#${C.id}{top:10px;right:10px;width:min(92vw,360px)}#${C.id} .grid,#${C.id} .actions,#${C.id} .theme{grid-template-columns:1fr}}`);
	}

	function render() {
		if (!ui.panel) return;
		ui.panel.dataset.theme = effectiveTheme();
		put("#metric-total", fmtMoney(state.current));
		put("#metric-window", fmtMoney(state.increase));
		put("#metric-window-label", `${state.cfg.compare} 分钟窗口增量`);
		const left = Math.max(0, Math.floor((state.lastReload + state.cfg.refresh * 6e4 - Date.now()) / 1e3));
		put("#refresh-countdown", `${String(Math.floor(left / 60)).padStart(2, "0")}:${String(left % 60).padStart(2, "0")}`);
		put("#theme-badge", `${state.theme}/${effectiveTheme()}`);
		put("#instance-id", state.id); put("#backend-status", state.lastBackend); put("#account-name", accountName()); put("#account-id", accountId()); put("#page-type", pageType()); put("#analysis-output", state.lastAnalysis || "等待 AI 分析结果。");
		ui.panel.querySelectorAll("[data-theme-mode]").forEach((btn) => { btn.dataset.active = String(btn.dataset.themeMode === state.theme); });
	}

	function loadInputs() {
		qs("#backend-base-url").value = state.cfg.backend; qs("#account-name-override").value = state.cfg.accountName; qs("#account-id-override").value = state.cfg.accountId; qs("#refresh-interval").value = state.cfg.refresh; qs("#compare-interval").value = state.cfg.compare; qs("#notify-threshold").value = state.cfg.threshold; qs("#ai-enabled").value = String(state.cfg.aiEnabled); qs("#ai-provider").value = state.cfg.aiProvider;
	}

	function saveInputs() {
		state.cfg.backend = backendBase(qs("#backend-base-url").value.trim()); state.cfg.accountName = qs("#account-name-override").value.trim(); state.cfg.accountId = qs("#account-id-override").value.trim(); state.cfg.refresh = Number(qs("#refresh-interval").value) || 5; state.cfg.compare = Number(qs("#compare-interval").value) || 30; state.cfg.threshold = Number(qs("#notify-threshold").value) || 1000; state.cfg.aiEnabled = qs("#ai-enabled").value === "true"; state.cfg.aiProvider = qs("#ai-provider").value || "deepseek";
		setVal(K.bu, state.cfg.backend); setVal(K.au, `${state.cfg.backend}/analyze`); setVal(K.anm, state.cfg.accountName); setVal(K.aid, state.cfg.accountId); setVal(K.ri, state.cfg.refresh); setVal(K.ci, state.cfg.compare); setVal(K.th, state.cfg.threshold); setVal(K.ae, state.cfg.aiEnabled); setVal(K.ap, state.cfg.aiProvider);
	}

	async function analyze() {
		if (!state.cfg.aiEnabled) { state.lastAnalysis = "AI 分析已关闭。"; setVal(K.lt, state.lastAnalysis); render(); return state.lastAnalysis; }
		try {
			const response = await request(`${state.cfg.backend}/analyze`, { provider_override: state.cfg.aiProvider, event: { current_spend: state.current, increase_amount: state.increase, compare_interval_min: state.cfg.compare, threshold: state.cfg.threshold, baseline_time: state.baseTime, event_time: Date.now(), extra_metrics: { baseline_spend: state.base, samples: state.history.length } }, history: state.history.map((x) => ({ timestamp: x.time, spend: x.spend })), business_context: [`账号名称：${accountName()}`, `账号 ID：${accountId()}`, `实例 ID：${state.id}`, `页面类型：${pageType()}`, `页面地址：${location.href}`].join("\n") });
			const body = JSON.parse(response.responseText || "{}");
			state.lastAnalysis = body.raw_text || body.summary || "AI 未返回内容。";
		} catch (error) { state.lastAnalysis = `AI 分析失败：${error?.error || error?.message || "未知错误"}`; }
		setVal(K.lt, state.lastAnalysis); render(); return state.lastAnalysis;
	}

	async function heartbeat(status = state.lastStatus, errorMessage = state.lastError) {
		try { await request(`${state.cfg.backend}/heartbeat`, { ...ctx(), heartbeat_at: Date.now(), browser_visible: document.visibilityState === "visible", capture_status: status, last_capture_at: state.lastCheck || null, error_message: errorMessage || null }); state.lastHeartbeat = Date.now(); state.lastBackend = `心跳已上报 ${new Date().toLocaleTimeString()}`; }
		catch (error) { state.lastBackend = `心跳上报失败：${error?.error || error?.message || "未知错误"}`; }
		persist(); render();
	}

	async function reportError(type, message) { try { await request(`${state.cfg.backend}/error`, { instance_id: state.id, occurred_at: Date.now(), error_type: type, error_message: message, page_url: location.href, script_version: (typeof GM_info !== "undefined" && GM_info.script && GM_info.script.version) || "unknown" }); } catch (_) {} }
	async function testAlert(text) { try { const response = await request(`${state.cfg.backend}/alerts/test`, { ...ctx(), current_spend: state.current, increase_amount: state.increase, compare_interval_min: state.cfg.compare, baseline_spend: state.base || null, baseline_time: state.baseTime || null, analysis_text: text || "", triggered_at: Date.now() }); return JSON.parse(response.responseText || "{}"); } catch (error) { return { ok: false, message: error?.error || error?.message || "未知错误" }; } }

	async function evaluate() {
		if (state.evaluating) return; state.evaluating = true; state.lastEval = Date.now(); setVal(K.la, state.lastEval);
		try {
			const spend = await scrapeSpendRetry();
			if (spend < 0) { const msg = "未找到当日消耗行。"; state.lastStatus = "warning"; state.lastError = msg; state.lastBackend = msg; persist(); render(); await heartbeat("warning", msg); return; }
			state.current = spend; pushHistory(spend); const base = baseline(); state.base = base.spend; state.baseTime = base.time; state.increase = Math.max(0, spend - base.spend); state.lastCheck = Date.now(); state.lastStatus = "success"; state.lastError = ""; state.lastBackend = `采集成功 ${new Date().toLocaleTimeString()}`; persist(); render();
			await request(`${state.cfg.backend}/ingest`, { ...ctx(), captured_at: Date.now(), metrics: { current_spend: state.current, increase_amount: state.increase, baseline_spend: state.base, compare_interval_min: state.cfg.compare, notify_threshold: state.cfg.threshold }, raw_context: { history_samples: state.history.length, baseline_time: state.baseTime, ai_enabled: state.cfg.aiEnabled, ai_provider: state.cfg.aiProvider } });
		} catch (error) {
			const msg = `采集失败：${error?.message || "未知错误"}`; state.lastStatus = "error"; state.lastError = msg; state.lastBackend = msg; persist(); render(); await reportError("capture_error", msg); await heartbeat("error", msg);
		} finally { state.evaluating = false; }
	}

	function createPanel() {
		const panel = document.createElement("div");
		panel.id = C.id;
		panel.innerHTML = `<div class="head"><div><div style="font-size:15px;font-weight:800;">磁力金牛财务报警助手</div><div style="font-size:11px;opacity:.82;">单实例投流监控面板</div></div><div><div id="theme-badge" style="font-size:12px;text-align:right;">主题</div><div style="font-size:12px;text-align:right;">刷新 <span id="refresh-countdown">--:--</span></div></div></div><div class="body"><div class="grid"><div class="metric"><div class="small">今日总消耗</div><div class="big" id="metric-total">-</div></div><div class="metric"><div class="small" id="metric-window-label">30 分钟窗口增量</div><div class="big" id="metric-window">-</div></div></div><div class="card"><div class="small">账号名称</div><div id="account-name"></div><div class="small" style="margin-top:8px;">账号 ID</div><div id="account-id"></div><div class="small" style="margin-top:8px;">页面类型</div><div id="page-type"></div><div class="small" style="margin-top:8px;">实例 ID</div><div id="instance-id"></div><div class="small" style="margin-top:8px;">后端状态</div><div id="backend-status"></div></div><div class="analysis" id="analysis-output">等待 AI 分析结果。</div><div class="toggle" id="toggle-config-btn">打开设置</div><div class="config" id="config-wrap"><div class="grid"><div><label>后端地址</label><input id="backend-base-url" type="text" /></div><div><label>账号名称覆盖</label><input id="account-name-override" type="text" /></div><div><label>账号 ID 覆盖</label><input id="account-id-override" type="text" /></div><div><label>刷新间隔（分钟）</label><input id="refresh-interval" type="number" min="1" /></div><div><label>对比窗口（分钟）</label><input id="compare-interval" type="number" min="1" /></div><div><label>报警阈值</label><input id="notify-threshold" type="number" min="0" /></div><div><label>是否启用 AI</label><select id="ai-enabled"><option value="true">启用</option><option value="false">关闭</option></select></div><div><label>AI 提供方</label><select id="ai-provider"><option value="local">本地模型</option><option value="deepseek">DeepSeek</option></select></div></div><div class="theme" style="margin-top:10px;"><button type="button" data-theme-mode="system">跟随系统</button><button type="button" data-theme-mode="light">浅色</button><button type="button" data-theme-mode="dark">深色</button></div><div class="actions" style="margin-top:10px;"><button type="button" class="primary" id="save-config-btn">保存设置</button><button type="button" class="soft" id="manual-refresh-btn">立即刷新</button><button type="button" class="warn" id="test-alert-btn">测试报警</button><button type="button" class="soft" id="reset-history-btn">重置历史</button><button type="button" class="soft" id="run-ai-btn">执行 AI 分析</button></div><div class="subtle">默认主题跟随系统。移动端会自动切换为更适合点击的窄屏布局。</div></div></div>`;
		document.body.appendChild(panel); ui.panel = panel; loadInputs(); render();
		if (state.pos.left && state.pos.top) { panel.style.right = "auto"; panel.style.left = state.pos.left; panel.style.top = state.pos.top; }
	}

	function bindDrag() {
		const handle = qs(".head");
		handle.addEventListener("mousedown", (event) => {
			if (window.innerWidth <= 640) return;
			if (["INPUT", "BUTTON", "SELECT", "TEXTAREA", "OPTION"].includes(event.target.tagName)) return;
			ui.dragging = true; const rect = ui.panel.getBoundingClientRect(); ui.panel.style.right = "auto"; ui.panel.style.left = `${rect.left}px`; ui.panel.style.top = `${rect.top}px`; ui.ox = event.clientX - rect.left; ui.oy = event.clientY - rect.top; event.preventDefault();
		});
		document.addEventListener("mousemove", (event) => { if (!ui.dragging) return; ui.panel.style.left = `${Math.max(8, Math.min(window.innerWidth - ui.panel.offsetWidth - 8, event.clientX - ui.ox))}px`; ui.panel.style.top = `${Math.max(8, Math.min(window.innerHeight - ui.panel.offsetHeight - 8, event.clientY - ui.oy))}px`; });
		document.addEventListener("mouseup", () => { if (!ui.dragging) return; ui.dragging = false; state.pos.left = ui.panel.style.left; state.pos.top = ui.panel.style.top; setVal(K.l, state.pos.left); setVal(K.t, state.pos.top); });
	}

	function bindUI() {
		qs("#toggle-config-btn").addEventListener("click", function () { const wrap = qs("#config-wrap"); const visible = wrap.style.display === "grid"; wrap.style.display = visible ? "none" : "grid"; this.textContent = visible ? "打开设置" : "收起设置"; });
		qs("#save-config-btn").addEventListener("click", () => { saveInputs(); render(); alert("设置已保存。"); });
		qs("#manual-refresh-btn").addEventListener("click", () => { state.lastReload = Date.now(); setVal(K.lr, state.lastReload); location.reload(); });
		qs("#reset-history-btn").addEventListener("click", () => { state.history = []; state.base = 0; state.baseTime = 0; state.current = 0; state.increase = 0; state.lastCheck = 0; state.lastEval = 0; state.lastAnalysis = ""; setVal(K.h, []); setVal(K.lt, ""); persist(); render(); alert("历史数据已重置。"); });
		qs("#test-alert-btn").addEventListener("click", async () => { saveInputs(); const text = await analyze(); const result = await testAlert(text); state.lastBackend = result.ok ? "测试报警已发送。" : `测试报警失败：${result.message || "未知错误"}`; persist(); render(); alert(state.lastBackend); });
		qs("#run-ai-btn").addEventListener("click", async () => { saveInputs(); await analyze(); });
		ui.panel.querySelectorAll("[data-theme-mode]").forEach((button) => button.addEventListener("click", function () { state.theme = this.dataset.themeMode || "system"; setVal(K.theme, state.theme); render(); }));
		if (window.matchMedia) window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { if (state.theme === "system") render(); });
	}

	async function loop() {
		const now = Date.now();
		if (now - state.lastReload >= state.cfg.refresh * 6e4) { state.lastReload = now; setVal(K.lr, state.lastReload); location.reload(); return; }
		if (!state.evaluating && now - state.lastEval >= C.sampleMs) await evaluate();
		if (now - state.lastHeartbeat >= C.heartbeatMs) await heartbeat(state.lastStatus, state.lastError);
		render();
	}

	function startup() {
		addStyles(); createPanel(); bindDrag(); bindUI();
		setTimeout(async () => { await evaluate(); await heartbeat(state.lastStatus, state.lastError); setInterval(() => { loop().catch(() => {}); }, C.uiTick); }, C.checkDelay);
	}

	$(document).ready(startup);
})();
