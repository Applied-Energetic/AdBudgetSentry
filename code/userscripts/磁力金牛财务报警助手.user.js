// ==UserScript==
// @name         磁力金牛财务报警助手
// @namespace    http://tampermonkey.net/
// @version      3.0.0
// @description  纯采集版磁力金牛监控助手，只负责采集花费和发送心跳，上层策略统一在后台管理
// @author       Codex
// @match        https://niu.e.kuaishou.com/financial/record*
// @match        https://niu.e.kuaishou.com/*
// @grant        GM_addStyle
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_xmlhttpRequest
// @connect      *
// ==/UserScript==

(function () {
  "use strict"

  const CONFIG = {
    panelId: "ad-budget-sentry-panel",
    backendBaseUrl: "http://127.0.0.1:8787",
    initialDelayMs: 3000,
    uiTickMs: 1000,
    sampleIntervalMs: 60 * 1000,
    heartbeatIntervalMs: 2 * 60 * 1000,
    scrapeRetryCount: 10,
    scrapeRetryDelayMs: 1500,
  }

  const STORAGE_KEYS = {
    instanceId: "instance_id",
    refreshMinutes: "refresh_interval_min",
    history: "spend_history",
    lastReloadAt: "last_reload_at",
    lastCaptureAt: "last_capture_at",
    lastHeartbeatAt: "last_heartbeat_at",
    lastCaptureStatus: "last_capture_status",
    lastError: "last_error_message",
    lastBackendMessage: "last_backend_message",
    currentSpend: "current_spend",
  }

  const getValue = (key, fallback) => {
    const value = GM_getValue(key, fallback)
    return value === undefined || value === null ? fallback : value
  }

  const setValue = (key, value) => GM_setValue(key, value)
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
  const formatMoney = (value) => `${Number(value || 0).toFixed(2)} 元`

  const state = {
    instanceId: String(getValue(STORAGE_KEYS.instanceId, `tm-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`)),
    refreshMinutes: Number(getValue(STORAGE_KEYS.refreshMinutes, 5)) || 5,
    history: Array.isArray(getValue(STORAGE_KEYS.history, [])) ? getValue(STORAGE_KEYS.history, []) : [],
    currentSpend: Number(getValue(STORAGE_KEYS.currentSpend, 0)) || 0,
    lastReloadAt: Number(getValue(STORAGE_KEYS.lastReloadAt, Date.now())) || Date.now(),
    lastCaptureAt: Number(getValue(STORAGE_KEYS.lastCaptureAt, 0)) || 0,
    lastHeartbeatAt: Number(getValue(STORAGE_KEYS.lastHeartbeatAt, 0)) || 0,
    lastCaptureStatus: String(getValue(STORAGE_KEYS.lastCaptureStatus, "warning")),
    lastError: String(getValue(STORAGE_KEYS.lastError, "")),
    lastBackendMessage: String(getValue(STORAGE_KEYS.lastBackendMessage, "等待首次采集")),
    collecting: false,
    panel: null,
  }

  setValue(STORAGE_KEYS.instanceId, state.instanceId)

  function pageType() {
    if (location.pathname.includes("/financial/record")) return "financial"
    if (location.pathname.includes("/manage")) return "manage"
    if (location.pathname.includes("/superManage")) return "super-manage"
    return "unknown"
  }

  function accountId() {
    const query = new URLSearchParams(location.search)
    for (const key of ["accountId", "account_id", "advertiserId", "advertiser_id", "cid"]) {
      const value = query.get(key)
      if (value) return value
    }
    return "未知账户ID"
  }

  function accountName() {
    for (const selector of [".account-info-name", ".account-name", "[class*='Account'] [class*='name']", "header [class*='name']"]) {
      const element = document.querySelector(selector)
      const text = element ? element.textContent.trim() : ""
      if (text) return text
    }
    return document.title || "未知账户"
  }

  function rows() {
    for (const selector of ["#root section section main table tbody tr", ".ant-table-tbody tr.ant-table-row", ".ant-table-row"]) {
      const elements = document.querySelectorAll(selector)
      if (elements.length) return elements
    }
    return []
  }

  function scrapeSpend() {
    const now = new Date()
    const dateString = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`
    for (const row of rows()) {
      const cells = row.querySelectorAll("td")
      if (cells.length < 2) continue
      const label = cells[0].textContent.trim()
      if (label === dateString || label.includes(dateString)) {
        return parseFloat(String(cells[1].textContent).replace(/[^\d.-]/g, "")) || 0
      }
    }
    return -1
  }

  async function scrapeSpendWithRetry() {
    for (let index = 0; index < CONFIG.scrapeRetryCount; index += 1) {
      const spend = scrapeSpend()
      if (spend >= 0) return spend
      if (index < CONFIG.scrapeRetryCount - 1) {
        await sleep(CONFIG.scrapeRetryDelayMs)
      }
    }
    return -1
  }

  function buildContext() {
    return {
      instance_id: state.instanceId,
      account_id: accountId(),
      account_name: accountName(),
      page_type: pageType(),
      page_url: location.href,
      script_version: (typeof GM_info !== "undefined" && GM_info.script && GM_info.script.version) || "unknown",
      row_count: rows().length,
    }
  }

  function postJson(url, body) {
    return new Promise((resolve, reject) => {
      GM_xmlhttpRequest({
        method: "POST",
        url,
        headers: { "Content-Type": "application/json" },
        data: JSON.stringify(body),
        timeout: 45000,
        onload: resolve,
        onerror: reject,
        ontimeout: reject,
      })
    })
  }

  function pushHistory(spend, capturedAt) {
    const last = state.history[state.history.length - 1]
    if (!last || Math.abs(last.spend - spend) > 0.009 || capturedAt - last.time >= 55_000) {
      state.history.push({ time: capturedAt, spend })
    }
    state.history = state.history.filter((item) => capturedAt - item.time <= 24 * 60 * 60 * 1000)
    setValue(STORAGE_KEYS.history, state.history)
  }

  function persistStatus() {
    setValue(STORAGE_KEYS.refreshMinutes, state.refreshMinutes)
    setValue(STORAGE_KEYS.currentSpend, state.currentSpend)
    setValue(STORAGE_KEYS.lastReloadAt, state.lastReloadAt)
    setValue(STORAGE_KEYS.lastCaptureAt, state.lastCaptureAt)
    setValue(STORAGE_KEYS.lastHeartbeatAt, state.lastHeartbeatAt)
    setValue(STORAGE_KEYS.lastCaptureStatus, state.lastCaptureStatus)
    setValue(STORAGE_KEYS.lastError, state.lastError)
    setValue(STORAGE_KEYS.lastBackendMessage, state.lastBackendMessage)
  }

  async function sendHeartbeat(status = state.lastCaptureStatus, errorMessage = state.lastError) {
    try {
      await postJson(`${CONFIG.backendBaseUrl}/heartbeat`, {
        ...buildContext(),
        heartbeat_at: Date.now(),
        browser_visible: document.visibilityState === "visible",
        capture_status: status,
        last_capture_at: state.lastCaptureAt || null,
        error_message: errorMessage || null,
      })
      state.lastHeartbeatAt = Date.now()
      state.lastBackendMessage = `心跳已上报 ${new Date().toLocaleTimeString()}`
    } catch (error) {
      state.lastBackendMessage = `心跳上报失败：${error?.message || "未知错误"}`
    }
    persistStatus()
    render()
  }

  async function reportError(type, message) {
    try {
      await postJson(`${CONFIG.backendBaseUrl}/error`, {
        instance_id: state.instanceId,
        occurred_at: Date.now(),
        error_type: type,
        error_message: message,
        page_url: location.href,
        script_version: (typeof GM_info !== "undefined" && GM_info.script && GM_info.script.version) || "unknown",
      })
    } catch (_) {}
  }

  async function collect() {
    if (state.collecting) return
    state.collecting = true

    try {
      const spend = await scrapeSpendWithRetry()
      if (spend < 0) {
        const message = "未找到当日花费行"
        state.lastCaptureStatus = "warning"
        state.lastError = message
        state.lastBackendMessage = message
        persistStatus()
        render()
        await sendHeartbeat("warning", message)
        return
      }

      const capturedAt = Date.now()
      state.currentSpend = spend
      state.lastCaptureAt = capturedAt
      state.lastCaptureStatus = "success"
      state.lastError = ""
      state.lastBackendMessage = `采集成功 ${new Date().toLocaleTimeString()}`
      pushHistory(spend, capturedAt)
      persistStatus()
      render()

      await postJson(`${CONFIG.backendBaseUrl}/ingest`, {
        ...buildContext(),
        captured_at: capturedAt,
        metrics: {
          current_spend: spend,
        },
        raw_context: {
          history_samples: state.history.length,
        },
      })
    } catch (error) {
      const message = `采集失败：${error?.message || "未知错误"}`
      state.lastCaptureStatus = "error"
      state.lastError = message
      state.lastBackendMessage = message
      persistStatus()
      render()
      await reportError("capture_error", message)
      await sendHeartbeat("error", message)
    } finally {
      state.collecting = false
    }
  }

  function addStyles() {
    GM_addStyle(`
      #${CONFIG.panelId}{
        position:fixed;top:14px;right:14px;z-index:99999;width:min(320px,calc(100vw - 20px));
        border-radius:18px;border:1px solid rgba(148,163,184,.24);background:rgba(255,255,255,.96);
        color:#142033;box-shadow:0 18px 42px rgba(15,23,42,.18);backdrop-filter:blur(18px);
        font-family:"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif
      }
      #${CONFIG.panelId} *{box-sizing:border-box}
      #${CONFIG.panelId} .head{padding:12px 16px;background:linear-gradient(135deg,#0f766e,#0f172a);color:#fff;border-radius:18px 18px 0 0}
      #${CONFIG.panelId} .body{padding:16px;display:grid;gap:12px}
      #${CONFIG.panelId} .metric,#${CONFIG.panelId} .card,#${CONFIG.panelId} input,#${CONFIG.panelId} button{
        border:1px solid rgba(148,163,184,.24);border-radius:14px;background:#f4f7fb
      }
      #${CONFIG.panelId} .metric,#${CONFIG.panelId} .card{padding:12px}
      #${CONFIG.panelId} .label{font-size:11px;color:#64748b}
      #${CONFIG.panelId} .value{font-size:18px;font-weight:800;color:#0f766e}
      #${CONFIG.panelId} .stack{display:grid;gap:8px}
      #${CONFIG.panelId} input{width:100%;min-height:36px;padding:0 10px;color:#142033}
      #${CONFIG.panelId} button{min-height:38px;padding:0 12px;cursor:pointer;font:inherit;font-weight:600}
      #${CONFIG.panelId} .primary{background:linear-gradient(135deg,#0f766e,#115e59);color:#fff}
      #${CONFIG.panelId} .soft{background:#f4f7fb;color:#142033}
    `)
  }

  function setText(selector, text) {
    const element = state.panel?.querySelector(selector)
    if (element) element.textContent = text
  }

  function render() {
    if (!state.panel) return
    const remainingSeconds = Math.max(0, Math.floor((state.lastReloadAt + state.refreshMinutes * 60 * 1000 - Date.now()) / 1000))
    setText("#metric-total", formatMoney(state.currentSpend))
    setText("#refresh-countdown", `${String(Math.floor(remainingSeconds / 60)).padStart(2, "0")}:${String(remainingSeconds % 60).padStart(2, "0")}`)
    setText("#instance-id", state.instanceId)
    setText("#backend-status", state.lastBackendMessage)
    setText("#account-name", accountName())
    setText("#account-id", accountId())
    setText("#page-type", pageType())
    setText("#capture-status", state.lastCaptureStatus)
    const input = state.panel.querySelector("#refresh-interval")
    if (input) input.value = String(state.refreshMinutes)
  }

  function createPanel() {
    const panel = document.createElement("div")
    panel.id = CONFIG.panelId
    panel.innerHTML = `
      <div class="head">
        <div style="font-size:15px;font-weight:800;">磁力金牛财务报警助手</div>
        <div style="font-size:11px;opacity:.82;">纯采集版</div>
      </div>
      <div class="body">
        <div class="metric">
          <div class="label">今日总花费</div>
          <div class="value" id="metric-total">-</div>
        </div>
        <div class="card stack">
          <div><span class="label">实例 ID</span><div id="instance-id"></div></div>
          <div><span class="label">账户名称</span><div id="account-name"></div></div>
          <div><span class="label">账户 ID</span><div id="account-id"></div></div>
          <div><span class="label">页面类型</span><div id="page-type"></div></div>
          <div><span class="label">采集状态</span><div id="capture-status"></div></div>
          <div><span class="label">后端状态</span><div id="backend-status"></div></div>
        </div>
        <div class="card stack">
          <label class="label" for="refresh-interval">刷新频率（分钟）</label>
          <input id="refresh-interval" type="number" min="1" />
          <div class="label">自动刷新倒计时 <span id="refresh-countdown">--:--</span></div>
          <div style="display:grid;gap:8px;grid-template-columns:1fr 1fr;">
            <button type="button" class="primary" id="save-config-btn">保存频率</button>
            <button type="button" class="soft" id="manual-refresh-btn">立即刷新</button>
          </div>
        </div>
      </div>
    `
    document.body.appendChild(panel)
    state.panel = panel
    render()
  }

  function bindUi() {
    state.panel.querySelector("#save-config-btn")?.addEventListener("click", () => {
      const nextValue = Number(state.panel.querySelector("#refresh-interval")?.value || 5) || 5
      state.refreshMinutes = Math.max(1, nextValue)
      persistStatus()
      render()
      alert("刷新频率已保存。")
    })

    state.panel.querySelector("#manual-refresh-btn")?.addEventListener("click", () => {
      state.lastReloadAt = Date.now()
      setValue(STORAGE_KEYS.lastReloadAt, state.lastReloadAt)
      location.reload()
    })
  }

  async function loop() {
    const now = Date.now()
    if (now - state.lastReloadAt >= state.refreshMinutes * 60 * 1000) {
      state.lastReloadAt = now
      setValue(STORAGE_KEYS.lastReloadAt, state.lastReloadAt)
      location.reload()
      return
    }
    if (!state.collecting && now - state.lastCaptureAt >= CONFIG.sampleIntervalMs) {
      await collect()
    }
    if (now - state.lastHeartbeatAt >= CONFIG.heartbeatIntervalMs) {
      await sendHeartbeat(state.lastCaptureStatus, state.lastError)
    }
    render()
  }

  function startup() {
    addStyles()
    createPanel()
    bindUi()
    setTimeout(async () => {
      await collect()
      await sendHeartbeat(state.lastCaptureStatus, state.lastError)
      setInterval(() => {
        void loop()
      }, CONFIG.uiTickMs)
    }, CONFIG.initialDelayMs)
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", startup)
  } else {
    startup()
  }
})()
