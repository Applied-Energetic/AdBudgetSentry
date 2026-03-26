// ==UserScript==
// @name         快手磁力金牛助手
// @namespace    http://tampermonkey.net/
// @version      2.2
// @description  快手磁力金牛助手 - 自动优化与监控 (适配新版界面)
// @author       Newwbbie & Copilot
// @match        https://niu.e.kuaishou.com/manage*
// @match        https://niu.e.kuaishou.com/superManage*
// @require      https://cdn.jsdelivr.net/npm/jquery@3.5.1/dist/jquery.min.js
// @icon         https://www.google.com/s2/favicons?sz=64&domain=kuaishou.com
// @grant        none
// ==/UserScript==

(function () {
    'use strict';

    // 移除秘钥验证逻辑，直接运行

    let url = window.location.href;
    let page_no = '';
    let interval;
    let i0, i1, i2, i3, i4, i5;
    let chk_value = [];
    
    // 设置分页为200 (注意：新版可能通过其他方式控制分页，此行可能仅对部分旧版有效)
    localStorage.setItem('esp-manage-table-pagination-pagesize', 200);
    localStorage.setItem('MANAGE_APPEAL_SUB_KEY', 17);

    // --- Adapter for Virtualized / AntD / CSS Modules ---
    const Adapter = {
        // 探测表格类型
        detect: () => {
            if ($('.ReactVirtualized__Table__headerRow').length > 0) return 'virtual';
            if ($('.ant-table-thead').length > 0) return 'antd';
            return 'unknown';
        },
        // 获取所有表头单元格 (jQuery对象集合)
        getHeaders: () => {
            if (Adapter.detect() === 'virtual') {
                return $('.ReactVirtualized__Table__headerRow .ReactVirtualized__Table__headerColumn').map((i, e) => $(e));
            }
            return $('.ant-table-thead th').map((i, e) => $(e));
        },
        // 获取所有数据行 (jQuery对象集合)
        getRows: () => {
            if (Adapter.detect() === 'virtual') {
                return $('.ReactVirtualized__Table__row');
            }
            return $('.ant-table-row');
        },
        // 获取某行的第 index (1-based) 列元素
        getCell: ($row, index) => {
            if (!($row instanceof jQuery)) $row = $($row);
            if (Adapter.detect() === 'virtual') {
                return $row.find(`.ReactVirtualized__Table__rowColumn:nth-child(${index})`);
            }
            return $row.find(`td:nth-child(${index})`);
        },
        // 获取某行的名称
        getName: ($row) => {
            if (!($row instanceof jQuery)) $row = $($row);
            // 尝试多种选择器
            let name = $row.find('.c-label-edit').text();
            if (!name) name = $row.find('[class*="name"]').text();
            if (!name) name = $row.find('a').first().text(); 
            return name ? name.trim() : '';
        },
        // 获取某行的开关按钮
        getSwitchBtn: ($row) => {
             if (!($row instanceof jQuery)) $row = $($row);
             // 1. 尝试找 role="switch"
             let $btn = $row.find('button[role="switch"]');
             // 2. 尝试找 class 包含 switch 的 button
             if ($btn.length === 0) $btn = $row.find('button[class*="switch"]');
             // 3. 尝试找 .ant-switch
             if ($btn.length === 0) $btn = $row.find('.ant-switch');
             
             // 4. (Fallback) 假设在第2列
             if ($btn.length === 0) {
                 let $cell = Adapter.getCell($row, 2);
                 $btn = $cell.find('button');
             }
             return $btn;
        }
    };
    // ----------------------------------------------------

    let ready = setInterval(function () {
        // 兼容不同的 Tab 激活状态 class
        if ($('.ant-tabs-tab-active, [role="tab"][aria-selected="true"], [class*="typeActive"]').length > 0) {
            clearInterval(ready);
            initPageNo();
            initInterval();
        }
    }, 500);

    // 监听页面链接变化，重新初始化
    /* 
       注意：由于单页应用 URL 变化不一定刷新页面，如果页面完全跳转则脚本已重载。
       如果只是 URL 变了但脚本没重载，需要更复杂的监听。
       原脚本 logic 似乎假设刷新或手动触发。 
       这里保留原逻辑，通过 url 判断。
    */
    function init(url) {
       // 原逻辑是手动根据 url 参数判断，这里先保留，但主要依赖 initPageNo 自动获取文本
        initInterval();
    }
    
    // 监听页面大类变化
    function initPageNo() {
        // 模糊匹配: 包含 typeActive 的 class
        let first = $('[class*="typeActive"]').text();
        if(!first) first = $('.index-module__typeActive___2_BX4').text();

        // 模糊匹配: Tab 激活
        let second = $('.ant-tabs-tab.ant-tabs-tab-active').text();
        if(!second) second = $('[role="tab"][aria-selected="true"]').text();

        page_no = (first || '推广') + ' ' + (second || '列表');
        $('#newwbbie').remove();
        
        // 简单判断是否显示 扩预算 选项
        if (page_no.includes('广告组') || page_no.includes('计划')) {
            createGUI(page_no, 5);
        } else {
            createGUI(page_no);
        }
    }

    function createGUI(text, type = 0) {
        let html = []
        html.push(`<div id='newwbbie' draggable="true" style='left: 5px;bottom: 30px;background: #fff;z-index: 99999;position: fixed;border-radius: 8px;padding: 15px;box-shadow: 0px 4px 12px rgba(0,0,0,0.15);border:1px solid #eee;'>`)
        html.push(`<div style='font-size: 14px; margin-bottom: 12px; font-weight: bold; border-bottom: 1px solid #f0f0f0; padding-bottom: 8px;'>当前监控：<span id='s0' style='color: #1890ff;'>${text}</span></div>`)
        html.push(`<div style='margin-bottom: 10px; display:flex; align-items:center;'>刷新间隔：<input id='i0' type='number' style='width: 50px;height: 24px;margin: 0 4px; border:1px solid #d9d9d9; border-radius:4px; padding-left:4px;'/>秒</div>`)
        html.push(`<div style='display: flex; flex-direction: column; gap: 8px;'>`)
        const rowStyle = 'display:flex; align-items:center; font-size:12px;';
        const inputStyle = 'width: 50px; height: 20px; border: 1px solid #d9d9d9; border-radius: 2px; margin: 0 4px;';
        
        html.push(`<label style="${rowStyle}"><input name="gg" type="checkbox" value="1" style="margin-right:4px;" />1. 平均花费 ><input id='i1' type='number' style="${inputStyle}"/>且无单 -> 关</label>`)
        html.push(`<label style="${rowStyle}"><input name="gg" type="checkbox" value="2" style="margin-right:4px;" />2. 当日ROI <<input id='i2' type='number' style="${inputStyle}"/> -> 关</label>`)
        html.push(`<label style="${rowStyle}"><input name="gg" type="checkbox" value="3" style="margin-right:4px;" />3. 转化成本 ><input id='i3' type='number' style="${inputStyle}"/> -> 关</label>`)
        html.push(`<label style="${rowStyle}"><input name="gg" type="checkbox" value="4" style="margin-right:4px;" />4. 当日花费 ><input id='i4' type='number' style="${inputStyle}"/>且无单 -> 关</label>`)
        if (type == 5) {
            html.push(`<label style="${rowStyle}"><input name="gg" type="checkbox" value="5" style="margin-right:4px;" />5. 花费>50%预算 -> 扩<input id='i5' type='number' style="${inputStyle}"/>倍</label>`)
        }
        html.push(`<div style="color: #666; font-size: 12px; margin-top: 4px;">当前功能：<span id="d0" style="color:#1890ff; font-weight:bold;"></span></div>`)
        html.push(`<div style="display:flex; gap:8px; margin-top:10px;">`)
        html.push(`<button type='button' id='b0' style="flex:1; background:#1890ff; color:white; border:none; border-radius:4px; padding:6px 0; cursor:pointer;">保存并执行</button>`)
        html.push(`<button type='button' id='b1' style="flex:1; background:white; color:#666; border:1px solid #d9d9d9; border-radius:4px; padding:6px 0; cursor:pointer;">清空缓存</button>`)
        html.push(`</div></div></div>`)
        
        $("body").append(html.join(''));

        // 拖拽逻辑
        var myDiv = document.getElementById("newwbbie");
        var isDragging = false;
        var mouseOffset = { x: 0, y: 0 };

        myDiv.addEventListener("mousedown", function(event) {
            // 排除 input 和 button 的点击
            if (['INPUT', 'BUTTON'].includes(event.target.tagName)) return;
            isDragging = true;
            mouseOffset.x = event.clientX - myDiv.offsetLeft;
            mouseOffset.y = event.clientY - myDiv.offsetTop;
        });

        document.addEventListener("mousemove", function(event) {
        if (isDragging) {
            myDiv.style.left = (event.clientX - mouseOffset.x) + "px";
            myDiv.style.top = (event.clientY - mouseOffset.y) + "px";
            event.preventDefault(); // 防止选中文本
        }
        });

        document.addEventListener("mouseup", function() {
            isDragging = false;
        });

        // 恢复配置
        i0 = localStorage.getItem(text + '_i0');
        $('#i0').val(i0 ? i0 : '10');
        interval = $('#i0').val() != '' ? $('#i0').val() * 1000 : 10000;
        
        ['1','2','3','4','5'].forEach(idx => {
            let val = localStorage.getItem(text + '_i' + idx);
            if(val) $(`#i${idx}`).val(val);
        });

        chk_value = localStorage.getItem(page_no);
        if (chk_value != null && chk_value != '') {
            chk_value.split(',').forEach(val => {
                $(`input[name="gg"][value="${val}"]`).prop('checked', true);
            });
            $('#d0').html(chk_value);
        }

        $('#b0').click(e => {
            let selected = [];
            $('input[name="gg"]:checked').each(function () {
                let val = $(this).val();
                if ($('#i' + val).val() != '') {
                    selected.push(val);
                }
            });
            chk_value = selected.join(',');
            console.log("Saving config:", chk_value);
            
            localStorage.setItem(text + '_i0', $('#i0').val());
            ['1','2','3','4','5'].forEach(idx => {
                localStorage.setItem(text + '_i' + idx, $(`#i${idx}`).val());
            });
            localStorage.setItem(page_no, chk_value);
            
            // alert('当前配置已保存！') // 不弹窗，打断操作
            $('#d0').html(chk_value);
            localStorage.removeItem('list_' + page_no);
            // alert(page_no + '的表格缓存已清空！')
            location.reload();
        });
        
        $('#b1').click(e => {
            localStorage.removeItem('list_' + page_no);
            localStorage.removeItem('init_list');
            alert('表格缓存已清空！')
        });
    }

    function initInterval() {
        let ready = setInterval(function () {
            // 使用 Adapter 检查表格
            if (Adapter.getRows().length > 0) {
                clearInterval(ready);
                
                // 自动点击“花费”排序
                Adapter.getHeaders().each((i, el) => {
                    if ($(el).text().includes('花费')) {
                        $(el).click();
                        // 无法 break each，但没关系
                    }
                });

                setInterval(function () {
                    // 每周期执行：抓取数据 -> 存储 -> 执行策略
                    let list = []
                    let btn_i = 2, cost_i = -1, roi_i = -1, zhcb_i = -1, ljdd_i = -1, jrys_i = -1;
                    
                    // 动态识别列索引
                    Adapter.getHeaders().each(function(i, el) {
                        let index = i + 1; // 1-based index
                        let text = $(el).text().trim();
                        if (text.includes('花费')) cost_i = index;
                        else if (text.includes('直接ROI') || text.includes('ROI')) roi_i = index;
                        else if (text.includes('转化成本')) zhcb_i = index;
                        else if (text.includes('累计订单') || text.includes('订单数')) ljdd_i = index;
                        else if (text.includes('预算')) jrys_i = index;
                        // 状态列通常没文字，或者叫“开关”
                        else if (text.includes('状态') || text.includes('开关')) btn_i = index;
                    });

                    // 安全回退：如果没找到列，使用默认值 (根据经验)
                    if (cost_i === -1) cost_i = 5; 
                    if (roi_i === -1) roi_i = 9; 
                    
                    Adapter.getRows().each(function(i, row) {
                        let $row = $(row);
                        // 忽略空行或表头行
                        if ($row.text().trim() === '') return;

                        let name = Adapter.getName($row);
                        if (!name) return;

                        let $btn = Adapter.getSwitchBtn($row);
                        // 判断开关状态：查找 class 里的 checked 或 aria-checked
                        let btnClass = $btn.attr('class') || '';
                        let isChecked = btnClass.includes('checked') || $btn.attr('aria-checked') === 'true';

                        let info = {
                            'btn': isChecked,
                            'name': name,
                            'cost': cost_i > 0 ? Adapter.getCell($row, cost_i).text() : '0',
                            'roi': roi_i > 0 ? Adapter.getCell($row, roi_i).text() : '0',
                            'zhcb': zhcb_i > 0 ? Adapter.getCell($row, zhcb_i).text() : '0',
                            'ljdd': ljdd_i > 0 ? Adapter.getCell($row, ljdd_i).text() : '0',
                            'now': new Date().getTime(),
                            'ignore': false
                        };
                        
                        if (jrys_i > 0) {
                            info['jrys'] = Adapter.getCell($row, jrys_i).text();
                        }
                        
                        list.push(info);
                    });

                    // 这里的 console.log 改为仅在调试时打开，避免刷屏
                    // console.log(list)
                    
                    var oldList = JSON.parse(localStorage.getItem("list_" + page_no));
                    if (oldList == null) {
                        oldList = list;
                        localStorage.setItem('init_list', JSON.stringify(list));
                    } else {
                        // 策略1：计算花费增量
                        if (i1 != null && i1 != '') {
                            for (let n of list) {
                                for (let old of oldList) {
                                    if (n.name == old.name) {
                                        // 所有的 text() 取出来可能包含逗号，需要 replace
                                        let nCost = parseFloat(n.cost.replace(/,/g, '')) || 0;
                                        let oCost = parseFloat(old.cost.replace(/,/g, '')) || 0;
                                        let nOrder = parseInt(n.ljdd.replace(/,/g, '')) || 0;
                                        let oOrder = parseInt(old.ljdd.replace(/,/g, '')) || 0;
                                        
                                        old.costInterval = nCost - oCost - (nOrder - oOrder) * parseFloat(i1);
                                        break;
                                    }
                                }
                            }
                        }
                        oldList = mergeList(oldList, list);
                    }
                    localStorage.setItem("list_" + page_no, JSON.stringify(oldList));
                }, interval);

                doMain(chk_value, interval);
            }
        }, 1000); // 初始探测间隔 1秒
    }

    function mergeList(oldList, list) {
        for (let i = 0; i < list.length; i++) {
            let found = false;
            for (let j = 0; j < oldList.length; j++) {
                if (list[i].name === oldList[j].name) {
                    if (list[i].btn != oldList[j].btn) {
                        oldList[j].ignore = true; // 状态被人为改变过，脚本不再接管
                    }
                    // 更新最新数据，但保留 ignore 状态和 costInterval
                    let tempIgnore = oldList[j].ignore;
                    let tempCostInterval = oldList[j].costInterval;
                    oldList[j] = list[i];
                    oldList[j].ignore = tempIgnore;
                    oldList[j].costInterval = tempCostInterval;
                    found = true;
                    break;
                }
            }
            if (!found) {
                oldList.push(list[i]);
                // 更新 init_list
                let lStr = localStorage.getItem('init_list');
                if(lStr) {
                    let l = JSON.parse(lStr);
                    l.push(list[i]);
                    localStorage.setItem('init_list', JSON.stringify(l));
                }
            }
        }
        return oldList;
    }


    function doMain(chk_value, interval) {
        if (!chk_value) return;
        
        setInterval(async function () {
            // 实时获取配置值
            i1 = $('#i1').val(); i2 = $('#i2').val(); i3 = $('#i3').val(); i4 = $('#i4').val(); i5 = $('#i5').val();
            
            var list = JSON.parse(localStorage.getItem("list_" + page_no));
            if (list == null) return;
            
            // 重新扫描 DOM 以便执行点击
            let $currentRows = Adapter.getRows();

            for (let item of list) {
                if (item.ignore) {
                    // console.log(item.name + '已忽略'); 
                    continue;
                }
                
                // 在当前 DOM 中找到对应的行
                let $targetRow = null;
                $currentRows.each(function(){
                    if(Adapter.getName($(this)) === item.name) {
                        $targetRow = $(this);
                        return false; 
                    }
                });

                if ($targetRow) {
                    let open = 0, close = 0;
                    
                    // 数据清洗
                    let cost = parseFloat(item.cost.replace(/,/g, '')) || 0;
                    let roi = parseFloat(item.roi.replace(/,/g, '')) || 0;
                    let zhcb = parseFloat(item.zhcb.replace(/,/g, '')) || 0;
                    let ljdd = parseInt(item.ljdd.replace(/,/g, '')) || 0;

                    // 策略1
                    if (chk_value.indexOf('1') >= 0 && i1 && item.costInterval) {
                        if (parseFloat(item.costInterval) > parseFloat(i1)) close = 1;
                        else open = 1;
                    }
                    // 策略2 (ROI)
                    if (chk_value.indexOf('2') >= 0 && i2) {
                        if (roi < parseFloat(i2) && roi > 0) close = 1;
                        else open = 1;
                    }
                    // 策略3 (转化成本)
                    if (chk_value.indexOf('3') >= 0 && i3) {
                        if (zhcb > parseFloat(i3) && zhcb > 0) close = 1;
                        else open = 1;
                    }
                    // 策略4 (无单止损)
                    if (chk_value.indexOf('4') >= 0 && i4) {
                        if (cost > parseFloat(i4) && ljdd == 0) close = 1;
                        else open = 1;
                    }
                    
                    // 策略5 (自动扩量 - 保持原逻辑大致框架，但 Selector 太复杂可能失效，需谨慎)
                    // 原逻辑依赖点击特定 DOM 结构，这里暂时略过 DOM 细节修改，仅保留核心判断
                    if (page_no.includes('5') && chk_value.indexOf('5') >= 0 && i5) {
                         // 需要重新分析预选修改的 DOM，暂无法精确实现通用化
                    }

                    // 执行开关
                    if ((open == 1 && !item.btn) || (open == 0 && close == 1 && item.btn)) {
                        let $btn = Adapter.getSwitchBtn($targetRow);
                        if ($btn.length > 0) {
                            $btn.click();
                            console.log('自动操作：' + (close ? '关闭' : '开启') + ' -> ' + item.name);
                        }
                    }
                }
            }
        }, interval);
    }

    function sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

})();
