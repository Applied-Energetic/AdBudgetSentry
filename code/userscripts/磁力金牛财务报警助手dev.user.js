// ==UserScript==
// @name         磁力金牛财务报警助手
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  监控磁力金牛当日总花费，一小时内超过100元进行报警
// @author       Assistant
// @match        https://niu.e.kuaishou.com/financial/record*
// @match        https://niu.e.kuaishou.com/*
// @require      https://cdn.jsdelivr.net/npm/jquery@3.5.1/dist/jquery.min.js
// @grant        GM_addStyle
// @grant        GM_notification
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_xmlhttpRequest
// ==/UserScript==

(function () {
	"use strict";

	// 默认配置
	const CONFIG = {
		checkInterval: 10 * 1000, // 每10秒检查一次
		debugPanelId: "sentry-debug-panel",
		audioAlertUrl:
			"https://actions.google.com/sounds/v1/alarms/alarm_clock_short.ogg",
	};

	// 初始化状态
	let state = {
		currentSpend: 0,
		lastSpend: GM_getValue("last_spend", 0),
		increaseInHour: 0,
		lastCheckTime: null,
		lastReloadTime: GM_getValue("last_reload_time", Date.now()),
		pushPlusToken: GM_getValue("pushplus_token", ""),
		// 用户配置
		refreshIntervalMin: GM_getValue("refresh_interval_min", 5), // 页面重载频率(分)
		compareIntervalMin: GM_getValue("compare_interval_min", 60), // 判定时间间隔(分)，原1h增长
		notifyThreshold: GM_getValue("notify_threshold", 10), // 变动通知阈值(元)
		// 上次通知的时间
		lastNotifyTime: GM_getValue("last_notify_time", 0),
		spendAtLastNotify: GM_getValue("spend_at_last_notify", 0),

		history: GM_getValue("spend_history", []), // 存储格式: {time: timestamp, spend: value}

		// UI 位置
		panelPos: GM_getValue("panel_pos", { top: 20, right: 20 }),
	};

	// 格式化日期 YYYY-MM-DD
	function getTodayStr() {
		const now = new Date();
		const y = now.getFullYear();
		const m = (now.getMonth() + 1).toString().padStart(2, "0");
		const d = now.getDate().toString().padStart(2, "0");
		return `${y}-${m}-${d}`;
	}

	// 抓取数据
	function scrapeData() {
		const todayStr = getTodayStr();

		// 尝试多种选择器以提高健壮性
		const selectors = [
			"#root section section main div div:nth-child(3) div:nth-child(2) div div div div div table tbody tr",
			".ant-table-tbody tr.ant-table-row",
			".ant-table-row",
		];

		let foundSpend = -1;

		for (const selector of selectors) {
			const rows = $(selector);
			if (rows.length > 0) {
				rows.each(function () {
					const cells = $(this).find("td");
					if (cells.length >= 2) {
						const dateCell = cells.eq(0).text().trim();
						// 这里的日期匹配支持 YYYY-MM-DD
						if (
							dateCell === todayStr ||
							dateCell.includes(todayStr)
						) {
							const spendText = cells
								.eq(1)
								.text()
								.trim()
								.replace(/,/g, "");
							const val = parseFloat(spendText);
							if (!isNaN(val)) {
								foundSpend = val;
								return false; // 找到即跳出 each
							}
						}
					}
				});
			}
			if (foundSpend !== -1) break;
		}

		return foundSpend;
	}

	// 报警逻辑
	function updateHistory(currentSpend) {
		const now = Date.now();
		state.history.push({ time: now, spend: currentSpend });

		// 判定时间间隔(小时改为动态设置)
		const compareLimitMs = state.compareIntervalMin * 60 * 1000;
		const compareStartTime = now - compareLimitMs;

		// 我们需要保留足够长的历史数据以便进行动态间隔对比，但也要定期清理过旧的数据(比如保留24小时)
		const dayAgo = now - 24 * 60 * 60 * 1000;
		state.history = state.history.filter((h) => h.time >= dayAgo);

		// 寻找最接近 compareStartTime 的那个点作为对比基准
		let baselineRecord = state.history[0];
		for (let i = 0; i < state.history.length; i++) {
			if (state.history[i].time >= compareStartTime) {
				baselineRecord = state.history[i];
				break;
			}
		}

		if (state.history.length > 0) {
			state.increaseInHour = currentSpend - baselineRecord.spend;

			console.log(
				`[判定逻辑] 当前金额: ${currentSpend.toFixed(2)}, 对比基准点金额: ${baselineRecord.spend.toFixed(2)} (${new Date(baselineRecord.time).toLocaleTimeString()})`,
			);
			console.log(
				`[判定逻辑] ${state.compareIntervalMin}分钟内增长: ${state.increaseInHour.toFixed(2)}, 设定阈值: ${state.notifyThreshold}`,
			);

			const cooldownMs = 10 * 60 * 1000;
			if (
				state.increaseInHour >= state.notifyThreshold &&
				now - state.lastNotifyTime > cooldownMs
			) {
				console.log(`[判定结果] 满足阈值条件！触发邮件提醒。`);
				const title = `【磁力金牛】预算消耗变动提醒`;
				const content = `
                    <div style="font-family: sans-serif; padding: 10px; border: 1px solid #eee; border-radius: 5px;">
                        <h2 style="color: #d9363e; border-bottom: 2px solid #d9363e; padding-bottom: 10px;">消耗异常报警</h2>
                        <p style="font-size: 16px;"><b>警告：</b>当前磁力金牛账户 <b>${state.compareIntervalMin}分钟内</b> 增长已超过设定的阈值 <b>${state.notifyThreshold}</b> 元。</p>
                        <p><b>时间区间增长:</b> <span style="color: #d9363e; font-size: 20px; font-weight: bold;">+${state.increaseInHour.toFixed(2)}</span> 元</p>
                        <p><b>今日总金额:</b> <span style="font-size: 18px; font-weight: bold;">${currentSpend.toFixed(2)}</span> 元</p>
                        <hr style="border: 0; border-top: 1px solid #eee;"/>
                        <p><b>对比基准时间:</b> ${new Date(baselineRecord.time).toLocaleTimeString()}</p>
                        <p><b>当前判定时间:</b> ${new Date().toLocaleString()}</p>
                        <p style="font-size: 12px; color: #888;">此邮件由磁力金牛助手自动发送。请及时检查广告计划设置。</p>
                    </div>
                `;
				pushToWechat(title, content);

				GM_notification({
					title: "磁力金牛变动提醒",
					text: `${state.compareIntervalMin}分增长: ${state.increaseInHour.toFixed(2)}元，总消耗: ${currentSpend.toFixed(2)}元`,
					timeout: 10000,
				});
				const audio = new Audio(CONFIG.audioAlertUrl);
				audio.play().catch((e) => console.warn("音频播放受限:", e));

				state.lastNotifyTime = now;
				GM_setValue("last_notify_time", state.lastNotifyTime);
			}
		}

		GM_setValue("spend_history", state.history);
	}

	// PushPlus 推送 (支持邮件频道)
	function pushToWechat(title, content) {
		if (!state.pushPlusToken) {
			console.warn("[磁力金牛财务助手] 未配置 PushPlus Token，跳过推送");
			return;
		}

		GM_xmlhttpRequest({
			method: "POST",
			url: "http://www.pushplus.plus/send",
			headers: {
				"Content-Type": "application/json",
			},
			data: JSON.stringify({
				token: state.pushPlusToken,
				title: title,
				content: content,
				template: "html",
				channel: "mail", // 指定邮件渠道
				option: "", // 邮件编码/服务器配置
			}),
			onload: function (response) {
				console.log(
					"[磁力金牛财务助手] PushPlus 推送结果:",
					response.responseText,
				);
			},
		});
	}

	// GUI 面板
	function createGUI() {
		if ($(`#${CONFIG.debugPanelId}`).length) return;

		const panelHtml = `
            <div id="${CONFIG.debugPanelId}" style="position: fixed; top: ${state.panelPos.top}px; right: ${state.panelPos.right}px; z-index: 10000; background: #ffffff; color: #374151; padding: 20px; border-radius: 16px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 14px; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1), 0 10px 10px -5px rgba(0,0,0,0.04); min-width: 280px; border: 1px solid #e5e7eb; pointer-events: auto; cursor: default;">
                <h4 id="${CONFIG.debugPanelId}-header" style="margin: 0 0 16px 0; font-size: 16px; font-weight: 600; display: flex; justify-content: space-between; align-items: center; color: #111827; cursor: move; user-select: none;">
                    磁力金牛助手
                    <span id="sentry-toggle" style="cursor: pointer; color: #9ca3af; font-weight: normal; font-size: 18px;">⚊</span>
                </h4>
                <div id="sentry-content">
                    <!-- 基本数据 -->
                    <div style="background: #f9fafb; border-radius: 12px; padding: 12px; margin-bottom: 16px; border: 1px solid #f3f4f6;">
                            <div style="margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center;">
                                <span style="color: #6b7280; font-size: 12px;">今日消耗总额</span>
                                <span id="sentry-total-spend" style="color: #10a37f; font-weight: 700; font-size: 18px;">-</span>
                            </div>
                            <div style="margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center;">
                                <span id="sentry-compare-label" style="color: #6b7280; font-size: 12px;">${state.compareIntervalMin}分增长</span>
                                <span id="sentry-hour-increase" style="color: #f59e0b; font-weight: 600;">-</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span style="color: #6b7280; font-size: 12px;">自动刷新计时</span>
                                <span id="sentry-refresh-timer" style="color: #6b7280; font-family: monospace;">-</span>
                            </div>
                        </div>

                        <!-- 配置区域 -->
                        <div style="display: flex; flex-direction: column; gap: 12px;">
                            <div>
                                <label style="display: block; font-size: 11px; font-weight: 600; color: #4b5563; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.025em;">PushPlus Token</label>
                                <input id="pp-token-input" type="password" value="${state.pushPlusToken}" style="width: 100%; height: 36px; background: #fff; border: 1px solid #d1d5db; color: #111827; border-radius: 8px; padding: 0 10px; font-size: 13px; outline: none; box-sizing: border-box; transition: border-color 0.2s;" placeholder="输入推送 Token"/>
                            </div>

                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                                <div>
                                    <label style="display: block; font-size: 11px; font-weight: 600; color: #4b5563; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.025em;">刷新间隔(分)</label>
                                    <input id="refresh-interval-input" type="number" value="${state.refreshIntervalMin}" style="width: 100%; height: 32px; background: #fff; border: 1px solid #d1d5db; color: #111827; border-radius: 8px; padding: 0 8px; font-size: 13px; outline: none; box-sizing: border-box;"/>
                                </div>
                                <div>
                                    <label style="display: block; font-size: 11px; font-weight: 600; color: #4b5563; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.025em;">查询间隔(分)</label>
                                    <input id="compare-interval-input" type="number" value="${state.compareIntervalMin}" style="width: 100%; height: 32px; background: #fff; border: 1px solid #d1d5db; color: #111827; border-radius: 8px; padding: 0 8px; font-size: 13px; outline: none; box-sizing: border-box;"/>
                                </div>
                            </div>

                            <div>
                                <label style="display: block; font-size: 11px; font-weight: 600; color: #4b5563; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.025em;">报警阈值(元)</label>
                                <input id="notify-threshold-input" type="number" value="${state.notifyThreshold}" style="width: 100%; height: 32px; background: #fff; border: 1px solid #d1d5db; color: #111827; border-radius: 8px; padding: 0 8px; font-size: 13px; outline: none; box-sizing: border-box;"/>
                            </div>

                            <button id="save-config-btn" style="width: 100%; height: 38px; background: #10a37f; border: none; color: #fff; cursor: pointer; border-radius: 8px; font-size: 14px; font-weight: 600; transition: background 0.2s; margin-top: 4px;">保存配置</button>
                        </div>
                    <!-- 操作按钮 -->
                    <div style="margin-top: 20px; border-top: 1px solid #f3f4f6; padding-top: 16px;">
                        <button id="manual-refresh-btn" style="width: 100%; height: 36px; background: #ffffff; border: 1px solid #d1d5db; color: #374151; cursor: pointer; border-radius: 8px; font-size: 13px; font-weight: 500; margin-bottom: 12px; display: flex; align-items: center; justify-content: center; gap: 6px; transition: all 0.2s;">
                            ↻ 手动刷新页面
                        </button>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                            <button id="sentry-test-alarm" style="height: 32px; background: #fef2f2; border: 1px solid #fee2e2; color: #dc2626; cursor: pointer; border-radius: 8px; font-size: 12px; transition: all 0.2s;">测试邮件</button>
                            <button id="sentry-reset-hist" style="height: 32px; background: #f9fafb; border: 1px solid #e5e7eb; color: #6b7280; cursor: pointer; border-radius: 8px; font-size: 12px; transition: all 0.2s;">重置历史</button>
                        </div>
                        <div style="margin-top: 16px; text-align: center; font-size: 11px; color: #9ca3af; display: flex; align-items: center; justify-content: center; gap: 4px;">
                             <span id="sentry-status-dot" style="width: 6px; height: 6px; border-radius: 50%; background: #10a37f;"></span>
                             <span id="sentry-status">监控中</span>
                             <span style="margin: 0 2px;">·</span>
                             <span id="sentry-last-update">-</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
		$("body").append(panelHtml);

		// 交互逻辑
		$("#save-config-btn").click(() => {
			const token = $("#pp-token-input").val().trim();
			const rTime = parseInt($("#refresh-interval-input").val()) || 5;
			const cTime = parseInt($("#compare-interval-input").val()) || 60;
			const nThreshold =
				parseFloat($("#notify-threshold-input").val()) || 100;

			state.pushPlusToken = token;
			state.refreshIntervalMin = rTime;
			state.compareIntervalMin = cTime;
			state.notifyThreshold = nThreshold;

			GM_setValue("pushplus_token", token);
			GM_setValue("refresh_interval_min", rTime);
			GM_setValue("compare_interval_min", cTime);
			GM_setValue("notify_threshold", nThreshold);

			$("#sentry-compare-label").text(`${cTime}分增长`);

			alert("配置已成功保存！");
		});

		$("#manual-refresh-btn").click(() => {
			GM_setValue("last_reload_time", Date.now());
			location.reload();
		});

		$("#sentry-test-alarm").click(() => {
			const title = "【磁力金牛】邮件推送测试";
			const content = `
                <div style="font-family: sans-serif; padding: 10px; border: 1px solid #eee; border-radius: 5px;">
                    <h2 style="color: #007bff; border-bottom: 2px solid #007bff; padding-bottom: 10px;">推送系统测试</h2>
                    <p>这是一条来自磁力金牛助手的测试邮件。</p>
                    <p><b>今日总金额:</b> ${state.currentSpend.toFixed(2)} 元</p>
                    <p><b>一小时内增长（当前状态）:</b> ${state.increaseInHour.toFixed(2)} 元</p>
                    <p><b>发送时间:</b> ${new Date().toLocaleString()}</p>
                    <hr style="border: 0; border-top: 1px solid #eee;"/>
                    <p>如果您收到了这封邮件，说明 PushPlus 邮件通道已配置成功。</p>
                </div>
            `;
			pushToWechat(title, content);
		});

		$("#sentry-reset-hist").click(() => {
			if (
				confirm(
					"确定要重置消耗历史数据吗？这将清除1h增长基准和上次通知基准。",
				)
			) {
				state.history = [];
				state.lastNotifyTime = 0;
				state.spendAtLastNotify = 0;
				GM_setValue("spend_history", []);
				GM_setValue("last_notify_time", 0);
				GM_setValue("spend_at_last_notify", 0);
				alert("历史数据已重置");
				main();
			}
		});

		$("#sentry-toggle").click(() => {
			const content = $("#sentry-content");
			content.toggle();
			$("#sentry-toggle").text(content.is(":visible") ? "⚊" : "＋");
		});

		// 拖拽逻辑
		dragElement(
			$(`#${CONFIG.debugPanelId}`)[0],
			$(`#${CONFIG.debugPanelId}-header`)[0],
		);

		function dragElement(elmnt, header) {
			let pos1 = 0,
				pos2 = 0,
				pos3 = 0,
				pos4 = 0;
			if (header) {
				header.onmousedown = dragMouseDown;
			} else {
				elmnt.onmousedown = dragMouseDown;
			}

			function dragMouseDown(e) {
				e = e || window.event;
				e.preventDefault();
				pos3 = e.clientX;
				pos4 = e.clientY;
				document.onmouseup = closeDragElement;
				document.onmousemove = elementDrag;
			}

			function elementDrag(e) {
				e = e || window.event;
				e.preventDefault();
				pos1 = pos3 - e.clientX;
				pos2 = pos4 - e.clientY;
				pos3 = e.clientX;
				pos4 = e.clientY;

				// 此时不能使用 right 布局，因为 top/right 组合在拖动时不好算
				// 设置 top/left 比较稳定
				const left = elmnt.offsetLeft - pos1;
				const top = elmnt.offsetTop - pos2;

				elmnt.style.top = top + "px";
				elmnt.style.left = left + "px";
				elmnt.style.right = "auto";
			}

			function closeDragElement() {
				document.onmouseup = null;
				document.onmousemove = null;
				// 保存位置 (将 left 转换回窗口右侧距离以便下一次加载)
				const rect = elmnt.getBoundingClientRect();
				const winWidth = window.innerWidth;
				const savePos = {
					top: rect.top,
					right: winWidth - rect.right,
				};
				GM_setValue("panel_pos", savePos);
			}
		}
	}

	function updateGUI() {
		const now = Date.now();
		$("#sentry-total-spend").text(state.currentSpend.toFixed(2) + " 元");
		$("#sentry-hour-increase").text(
			state.increaseInHour.toFixed(2) + " 元",
		);

		// 更新距离刷新的时间
		const refreshMs = state.refreshIntervalMin * 60 * 1000;
		const nextReload = state.lastReloadTime + refreshMs;
		const diffSec = Math.max(0, Math.floor((nextReload - now) / 1000));
		const m = Math.floor(diffSec / 60);
		const s = diffSec % 60;
		$("#sentry-refresh-timer").text(`${m}分${s}秒`);

		$("#sentry-last-update").text(new Date().toLocaleTimeString());

		// 更新状态灯和文字
		if (state.currentSpend > 0) {
			$("#sentry-status-dot").css("background", "#10a37f");
			$("#sentry-status").text("监控中");
		}
	}

	// 主循环
	let hasPerformedInitialCheck = false;

	function main() {
		const now = Date.now();
		const refreshMs = state.refreshIntervalMin * 60 * 1000;

		// 1. 如果还没进行过刷新后的判定，执行一次
		if (!hasPerformedInitialCheck) {
			console.log("[磁力金牛财务助手] 正在进行刷新后的首次判定...");
			const spend = scrapeData();

			if (spend !== -1) {
				state.currentSpend = spend;
				state.lastSpend = spend;
				GM_setValue("last_spend", spend);

				state.lastCheckTime = now;
				updateHistory(spend);
				updateGUI();
				hasPerformedInitialCheck = true;
				console.log(
					`[判定] 本次刷新后的判定已完成。接下来的 ${state.refreshIntervalMin} 分钟内将不再重复判定，仅更新计时器。`,
				);
			} else {
				console.warn(`[判定] 抓取失败，10秒后重试本次判定...`);
				return; // 让 setInterval 的下一次 main 继续尝试
			}
		}

		// 2. 检查是否达到设定的下一次强制刷新时间
		if (now - state.lastReloadTime >= refreshMs) {
			console.log("[磁力金牛财务助手] 达到设定时间，强制刷新页面...");
			GM_setValue("last_reload_time", now);
			location.reload();
			return;
		}

		// 3. 仅更新 UI 上的计时器
		updateGUI();
	}

	// 启动
	function init() {
		createGUI();
		// 立即执行一次 main 来初始化数据
		main();
		// 每秒运行一次 main，确保 UI 上的计时器（倒计时）实时跳动
		setInterval(main, 1000);
	}

	// 等待页面加载
	$(document).ready(() => {
		setTimeout(init, 3000); // 延迟3秒确保Vue/React渲染完成
	});
})();
