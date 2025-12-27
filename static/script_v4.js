/**
 * Kiwoom Trading Bot Web Dashboard
 * Enhanced Version - Windows GUI Style
 * Real-time updates via WebSocket + Settings Management + Bot Control
 */

// --- Global State Management ---
// [수정] 삭제는 세션 내에서만 유지, 새로고침하면 복구됨
let deletedTimeCutIds = [];

// [Helper] 타임컷 여부 판별 함수 (사유 기반)
const isTCFunc = (s) => /TimeCut|시간|지루|Cut|시간제한/i.test(s.reason || '');

// [Helper] 시간 추출
const getTime = (e) => e.time || e.timestamp || "";

// [Helper] 로그 항목 고유 ID 생성 (매칭용)
const getUID = (l) => l.id || `${getTime(l)}_${l.name || l.stk_nm || '-'}_${l.qty}`;
let pendingBotToggleTime = 0; // [New] 버튼 클릭 후 상태 업데이트 무시 시간

function saveDeletedIds() {
    // [수정] localStorage에 저장하지 않음 (사용자 요청: 새로고침 시 복구)
    console.log('타임컷 삭제 목록:', deletedTimeCutIds.length, '개 (세션 내에서만 유지)');
}

// Clear deleted IDs if user wants to reset (can be called from console or button)
function clearDeletedTimeCuts() {
    deletedTimeCutIds = [];
    console.log('삭제된 타임컷 복구 완료 (새로고침 효과)');
    const activeTab = document.querySelector('.tab-btn.active')?.dataset.tab || 'all';
    renderFilteredLogs(activeTab);
}
window.clearDeletedTimeCuts = clearDeletedTimeCuts; // Expose globally for debugging


let ws = null;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 10;

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        console.log('WebSocket connected');
        document.getElementById('ws-status').className = 'status-dot online';
        document.getElementById('ws-text').textContent = '실시간 연결됨';
        reconnectAttempts = 0;
        addLog('WebSocket 연결됨', 'success');
    };

    ws.onclose = () => {
        console.log('WebSocket disconnected');
        document.getElementById('ws-status').className = 'status-dot offline';
        document.getElementById('ws-text').textContent = '연결 끊김';
        addLog('WebSocket 연결 끊김', 'error');

        // Auto reconnect
        if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
            reconnectAttempts++;
            setTimeout(connectWebSocket, 2000);
        }
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        addLog('WebSocket 오류 발생', 'error');
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            updateDashboard(data);
        } catch (e) {
            console.error('Failed to parse message:', e);
        }
    };
}

// ============ Dashboard Update ============

async function loadInitialStatus() {
    try {
        const res = await fetch('/api/status');
        const data = await res.json();
        if (data && !data.error) {
            updateDashboard(data);
            addLog('초기 상태 로드 완료', 'success');
        }
    } catch (e) {
        console.error('Failed to load initial status:', e);
    }
}

// --- 1. Dashboard UI Updates ---
function updateDashboard(data) {
    if (!data || !data.summary) return;

    const s = data.summary;

    // Summary Cards (Asset Status)
    document.getElementById('total-asset').textContent = `${(s.total_asset || 0).toLocaleString()} 원`;
    document.getElementById('total-buy').textContent = `${(s.total_buy || 0).toLocaleString()} 원`;
    document.getElementById('deposit').textContent = `${(s.deposit || 0).toLocaleString()} 원`;

    const pl = s.total_pl || 0;
    const plEl = document.getElementById('total-pl');
    plEl.textContent = `${pl >= 0 ? '+' : ''}${pl.toLocaleString()} 원`;

    // [UI] 뱃지 업데이트 (설정 저장 직후 3초간은 강제 업데이트 방지 - 플리커링 차단)
    if (!window._is_saving_settings) {
        updateBadge(s.api_mode === 'MOCK' || s.api_mode === 'Mock', s.is_paper !== false);
    }
    plEl.className = 'card-value ' + (pl >= 0 ? 'profit' : 'loss');

    const yld = s.total_yield || 0;
    const yldEl = document.getElementById('total-yield');
    yldEl.textContent = `${yld >= 0 ? '+' : ''}${yld.toFixed(2)}%`;
    yldEl.className = 'card-value ' + (yld >= 0 ? 'profit' : 'loss');
    yldEl.style.fontWeight = 'bold'; // 강조

    // API Mode Badge 세분화 (통합 함수 사용)
    updateBadge(s.api_mode === 'MOCK' || s.api_mode === 'Mock', s.is_paper !== false);

    // Bot Status Button (Toggle Logic with Feedback)
    const btn = document.getElementById('btn-bot-toggle');
    const now = Date.now();

    // [Fix] 버튼 클릭 직후(10초간)는 서버 상태보다 사용자 조작을 우선시하여 깜빡임 방지 (충분한 유예 기간 부여)
    if (btn && (now - pendingBotToggleTime > 10000)) {
        btn.classList.remove('loading-process');
        if (s.bot_running) {
            btn.innerHTML = '<span>⏹</span> 종료';
            btn.dataset.state = 'running';
            btn.style.opacity = '1';
        } else {
            btn.innerHTML = '<span>▶</span> 시작';
            btn.dataset.state = 'stopped';
            btn.style.opacity = '1';
        }
        btn.disabled = false;
    }

    // Save summary globally for use in other views
    window.globalSummary = s;

    // Holdings Table
    updateHoldingsTable(data.holdings || []);
}

// --- Holdings Persistent State ---
let lastHoldingsJSON = '';
let isTableInitialized = false;

function updateHoldingsTable(stocks) {
    const tbody = document.getElementById('holdings-body');

    // 1. 데이터 변경 여부 확인 (전체 stringify 비교)
    const currentJSON = JSON.stringify(stocks);
    if (lastHoldingsJSON === currentJSON && isTableInitialized) {
        return; // 데이터가 완전히 동일하면 아무것도 하지 않음
    }
    lastHoldingsJSON = currentJSON;
    isTableInitialized = true;

    // 2. 데이터가 없는 경우 처리 (깜빡임 방지: 로딩 중이거나 일시적 오류일 수 있음)
    if (!stocks || stocks.length === 0) {
        // 이미 비어있지 않은 경우에만 비움
        if (tbody.children.length > 1 || (tbody.children.length === 1 && !tbody.querySelector('.empty-msg'))) {
            tbody.innerHTML = '<tr><td colspan="7" class="empty-msg">현재 보유 중인 종목이 없습니다.</td></tr>';
        }
        return;
    }

    // Helper function for numbers
    const parseNum = (val, defaultVal = 0) => {
        if (typeof val === 'number') return val;
        const str = String(val || '').replace(/,/g, '').trim();
        const num = parseFloat(str);
        return isNaN(num) ? defaultVal : num;
    };

    // 3. 데이터 가공
    const stocksData = stocks.map(stock => {
        const name = stock.stk_nm || stock.name || '-';
        const rate = parseNum(stock.pl_rt || stock.rate);
        const pnl = parseInt(parseNum(stock.pl_amt || stock.eval_pnl));
        const qty = parseInt(parseNum(stock.rmnd_qty || stock.qty));
        const cur_prc = parseInt(parseNum(stock.cur_prc));
        const hold_time = stock.hold_time || '0분';
        const water_step = stock.watering_step || '-';
        const rateClass = rate >= 0 ? 'profit-cell' : 'loss-cell';
        const pnlClass = pnl >= 0 ? 'profit-cell' : 'loss-cell';

        return { name, rate, pnl, qty, cur_prc, hold_time, water_step, rateClass, pnlClass };
    });

    // 4. 기존 DOM 행 관리 (Name 기준)
    const existingRows = Array.from(tbody.querySelectorAll('tr:not(.empty-msg)'));
    const rowMap = new Map();
    existingRows.forEach(row => {
        const nameNode = row.querySelector('.stock-name-cell');
        if (nameNode) {
            rowMap.set(nameNode.textContent.trim(), row);
        } else if (row.cells[0]) {
            rowMap.set(row.cells[0].textContent.trim(), row);
        }
    });

    // 5. 비어있음 메시지 제거
    const emptyMsg = tbody.querySelector('.empty-msg');
    if (emptyMsg) emptyMsg.parentNode.remove();

    // 6. 개별 행/셀 업데이트
    stocksData.forEach((data, index) => {
        let row = rowMap.get(data.name);

        if (!row) {
            // 새 행 생성
            row = document.createElement('tr');
            row.innerHTML = `
                <td class="stress stock-name-cell">${data.name}</td>
                <td class="rate-cell"></td>
                <td class="pnl-cell"></td>
                <td class="qty-cell"></td>
                <td class="price-cell"></td>
                <td class="time-cell"></td>
                <td class="step-cell"></td>
            `;
            // 위치에 삽입
            if (tbody.children[index]) {
                tbody.insertBefore(row, tbody.children[index]);
            } else {
                tbody.appendChild(row);
            }
        } else {
            // 위치가 틀리면 이동 (단, 정말 필요한 경우에만)
            if (tbody.children[index] !== row) {
                tbody.insertBefore(row, tbody.children[index]);
            }
            rowMap.delete(data.name);
        }

        // 셀 데이터 업데이트 (변경된 경우에만)
        const cells = {
            rate: row.querySelector('.rate-cell') || row.cells[1],
            pnl: row.querySelector('.pnl-cell') || row.cells[2],
            qty: row.querySelector('.qty-cell') || row.cells[3],
            price: row.querySelector('.price-cell') || row.cells[4],
            time: row.querySelector('.time-cell') || row.cells[5],
            step: row.querySelector('.step-cell') || row.cells[6]
        };

        // 수익률
        const rateText = `${data.rate >= 0 ? '+' : ''}${data.rate.toFixed(2)}%`;
        if (cells.rate.textContent !== rateText) cells.rate.textContent = rateText;
        if (cells.rate.className !== `rate-cell ${data.rateClass}`) cells.rate.className = `rate-cell ${data.rateClass}`;

        // 손익
        const pnlText = formatNumber(data.pnl);
        if (cells.pnl.textContent !== pnlText) cells.pnl.textContent = pnlText;
        if (cells.pnl.className !== `pnl-cell ${data.pnlClass}`) cells.pnl.className = `pnl-cell ${data.pnlClass}`;

        // 수량
        const qtyText = `${data.qty}주`;
        if (cells.qty.textContent !== qtyText) cells.qty.textContent = qtyText;

        // 현재가
        const priceText = formatNumber(data.cur_prc);
        if (cells.price.textContent !== priceText) cells.price.textContent = priceText;

        // 보유 시간
        if (cells.time.textContent !== data.hold_time) cells.time.textContent = data.hold_time;

        // 단계
        if (cells.step.textContent !== data.water_step) cells.step.textContent = data.water_step;
    });

    // 7. 남은 행(매도됨) 제거
    rowMap.forEach(row => row.remove());
}

// ============ Sell Log ============

// --- Trading History Logic ---
let globalTradingLogs = { buys: [], sells: [] }; // Store locally
let lastTradeLogId = 0; // Track last loaded ID for incremental updates
let currentStats = null; // Store cumulative stats from server

async function loadTradingLog(forceSinceZero = false) {
    try {
        const fetchId = forceSinceZero ? 0 : lastTradeLogId;
        const res = await fetch(`/api/trading-log?since_id=${fetchId}&t=${new Date().getTime()}`);
        const data = await res.json();

        if (data.buys && data.sells) {
            console.log(`[DEBUG] loadTradingLog: +${data.buys.length} buys, +${data.sells.length} sells from API`);

            // [Sync Fix] 강제 초기화 시 기존 로그 교체 (누적 방지)
            if (forceSinceZero) {
                globalTradingLogs.buys = [...data.buys];
                globalTradingLogs.sells = [...data.sells];
                lastTradeLogId = 0;
            }
            // New data exists (Incremental mode)
            else if (data.buys.length > 0 || data.sells.length > 0) {
                // Prepend new data (Back-end already sends newest first)
                globalTradingLogs.buys = [...data.buys, ...globalTradingLogs.buys];
                globalTradingLogs.sells = [...data.sells, ...globalTradingLogs.sells];
            }

            // Remove duplicates if any (by ID)
            const uniqueBuys = [];
            const buyIds = new Set();
            globalTradingLogs.buys.forEach(b => {
                if (!buyIds.has(b.id)) {
                    buyIds.add(b.id);
                    uniqueBuys.push(b);
                }
            });
            globalTradingLogs.buys = uniqueBuys;

            const uniqueSells = [];
            const sellIds = new Set();
            globalTradingLogs.sells.forEach(s => {
                if (!sellIds.has(s.id)) {
                    sellIds.add(s.id);
                    uniqueSells.push(s);
                }
            });
            globalTradingLogs.sells = uniqueSells;

            // Update max ID
            const allIds = [
                ...globalTradingLogs.buys.map(b => b.id),
                ...globalTradingLogs.sells.map(s => s.id),
                lastTradeLogId
            ];
            lastTradeLogId = Math.max(...allIds);

            console.log(`Incremental load: +${data.buys.length} buys, +${data.sells.length} sells. Last ID: ${lastTradeLogId}`);
        } else {
            console.error('No trading data received from API');
        }

        // Render "all" by default or current active tab
        const activeTab = document.querySelector('.tab-btn.active')?.dataset.tab || 'all';

        // [New] Update Statistics using cumulative stats from server (keeps UI fast)
        if (data.stats) {
            currentStats = data.stats;
            updateReportSummary(currentStats);
        }

        renderFilteredLogs(activeTab);

        // [New] Update Dashboard Recent Activity Section
        try {
            updateRecentActivity(globalTradingLogs);
        } catch (e) { console.error('Recent activity update error', e); }

    } catch (e) {
        console.error('Failed to load trading log:', e);
    }
}

function updateRecentActivity(data) {
    const listEl = document.getElementById('recent-trades-list');
    if (!listEl) return;

    // Combine buys and sells
    const buys = (data.buys || []).map(b => ({ ...b, type: 'Buy' }));
    const sells = (data.sells || []).map(s => ({ ...s, type: 'Sell' }));

    // Merge and sort
    const all = [...buys, ...sells].sort((a, b) => {
        const t1 = a.time || a.timestamp || '';
        const t2 = b.time || b.timestamp || '';
        if (t1 > t2) return -1;
        if (t1 < t2) return 1;
        return 0;
    });

    const recent = all.slice(0, 5); // Show last 5

    if (recent.length === 0) {
        listEl.innerHTML = '<li class="empty-list" style="padding:15px; color:#666; text-align:center;">체결 내역이 없습니다.</li>';
        return;
    }

    listEl.innerHTML = recent.map(item => {
        const timeStr = (item.time || item.timestamp || '').split(' ')[1] || (item.time || ''); // HH:mm:ss
        const isBuy = item.type === 'Buy';
        const badgeClass = isBuy ? 'badge-buy' : 'badge-sell';
        const badgeText = isBuy ? '매수' : '매도';
        const name = item.name || item.stk_nm || '-';
        const price = (item.price || item.avg_price || 0).toLocaleString();
        const qty = item.qty || 0;

        let reasonHtml = '';
        if (!isBuy) {
            const reason = item.reason || '-';
            const rate = parseFloat(item.yield || item.profit_rate || 0).toFixed(2);
            const profitClass = rate > 0 ? 'color:#10b981' : 'color:#ef4444';
            reasonHtml = `<span class="reason-text"><span style="${profitClass}; font-weight:bold; margin-right:5px;">${rate}%</span> ${reason}</span>`;
        } else {
            reasonHtml = `<span class="reason-text" style="font-size:0.8rem; color:#888;">${qty}주</span>`;
        }

        return `
            <li class="recent-item">
                <span class="recent-time">${timeStr}</span>
                <div class="recent-info">
                    <span class="recent-badge ${badgeClass}">${badgeText}</span>
                    <span style="font-weight:600;">${name}</span>
                    <span class="recent-price">${price}원</span>
                    ${reasonHtml}
                </div>
            </li>
        `;
    }).join('');
}


function renderFilteredLogs(filterType) {
    const tbody = document.getElementById('sell-body');
    const theadTr = document.querySelector('#history-thead tr');
    tbody.innerHTML = '';

    // [Simplification] 백엔드 API가 이미 현재 모드에 맞는 데이터를 필터링해서 보내주므로
    // 클라이언트 측에서 중복 필터링을 수행하지 않고 그대로 사용합니다.
    const allBuys = (globalTradingLogs.buys || []);
    const allSells = (globalTradingLogs.sells || []);

    console.log(`[DEBUG] renderFilteredLogs: Type=${filterType}, Buys=${allBuys.length}, Sells=${allSells.length}`);

    // [중요] 최신순 정렬 (ID와 시간을 모두 활용하여 가장 최신 것이 위로 가게 함)
    const getTimeVal = (e) => e.time || e.timestamp || "";
    const getSortId = (e) => parseInt(e.id || 0);

    // 날짜 정렬 함수 (내림차순) - 아래에서 덮어씌워지므로 여기서 제거하거나 유지해도 되지만, 
    // 아래쪽 로직을 따르도록 여기서는 정의만 하고 사용은 아래 로직에 맡김

    let displayLogs = [];

    // 날짜 정렬 함수 (내림차순)
    const descSort = (a, b) => {
        const timeA = new Date(a.time || a.timestamp || 0).getTime();
        const timeB = new Date(b.time || b.timestamp || 0).getTime();
        return timeB - timeA;
    };

    if (filterType === 'buy') {
        displayLogs = allBuys
            .map(b => ({ ...b, type: 'Buy' }))
            .sort(descSort);
    } else if (filterType === 'sell') {
        displayLogs = allSells
            .map(s => ({ ...s, type: 'Sell' }))
            .sort(descSort);
    } else if (filterType === 'timecut') {
        displayLogs = allSells
            .filter(s => (s.reason || '').includes('TimeCut') || (s.reason || '').includes('time_cut'))
            .filter(s => !deletedTimeCutIds.includes(getUID(s)))
            .map(s => ({ ...s, type: 'Sell' }))
            .sort(descSort);
    } else {
        // All
        const combined = [
            ...allBuys.map(b => ({ ...b, type: 'Buy' })),
            ...allSells.map(s => ({ ...s, type: 'Sell' }))
        ];
        displayLogs = combined.sort(descSort);
    }

    // [사용자 요청] 최신 내역 8개만 표시
    displayLogs = displayLogs.slice(0, 8);

    console.log(`[DEBUG] Rendering ${displayLogs.length} logs for ${filterType}`);

    // --- 3. Render (All Centered) ---
    theadTr.innerHTML = `
        <th>시간</th>
        <th>종목명</th>
        <th>구분</th>
        <th>수량</th>
        <th>수익률</th>
        <th>${filterType === 'timecut' ? '관리' : '사유'}</th>
    `;

    if (displayLogs.length === 0) {
        tbody.innerHTML = `<tr class="empty-row"><td colspan="6">조회된 데이터가 없습니다.</td></tr>`;
    } else {
        displayLogs.forEach(log => {
            const tr = document.createElement('tr');
            const logTime = getTime(log);
            const timePart = logTime.includes(' ') ? logTime.split(' ')[1] : logTime;
            const logName = log.name || log.stk_nm || '-';
            const uid = getUID(log);

            if (log.type === 'Buy') {
                tr.innerHTML = `
                    <td class="text-center">${timePart}</td>
                    <td class="stress text-center">${logName}</td>
                    <td style="color:#10b981; font-weight:bold;" class="text-center">매수</td>
                    <td class="text-center">${log.qty || 0}주</td>
                    <td class="text-center">-</td>
                    <td class="text-center">-</td>
                `;
            } else {
                // Correctly map from trading_log.json fields
                const rate = parseFloat(log.yield || log.profit_rate || 0);
                const rateClass = rate > 0 ? 'profit-cell' : 'loss-cell';
                const reason = log.reason || '-';
                const isTC = reason.includes('TimeCut') || reason.includes('시간제한');

                let lastCell = `<td class="text-center">${reason}</td>`;
                // Add delete button in timecut tab
                if (filterType === 'timecut') {
                    lastCell = `<td class="text-center">
                        <button class="btn-delete-small" onclick="deleteSingleTimeCut('${uid}')">삭제</button>
                    </td>`;
                }

                tr.innerHTML = `
                    <td class="text-center">${timePart}</td>
                    <td class="stress text-center">${logName}</td>
                    <td style="${isTC ? 'color:orange;' : 'color:#ef4444;'} font-weight:bold;" class="text-center">${isTC ? '타임컷' : '매도'}</td>
                    <td class="text-center">${log.qty}주</td>
                    <td class="${rateClass} text-center">${rate.toFixed(2)}%</td>
                    ${lastCell}
                `;
            }
            tbody.appendChild(tr);
        });
    }

    if (currentStats) {
        updateReportSummary(currentStats);
    }
}


// Global helper for deletion
window.deleteSingleTimeCut = function (uid) {
    // Delete without confirmation
    if (!deletedTimeCutIds.includes(uid)) {
        deletedTimeCutIds.push(uid);
        saveDeletedIds();
        renderFilteredLogs('timecut');
    }
};

/**
 * UI Summary Update (Cumulative Stats from Server)
 */
function updateReportSummary(stats) {
    if (!stats) return;

    // 1. 매매 횟수
    const total = stats.total || 0;
    document.getElementById('report-count').textContent = `${total}회`;

    // 2. 승률
    // wins / sells_total * 100
    // Note: 'total' from backend stats for day is count of sells
    const winRate = total > 0 ? (stats.wins / total * 100) : 0;
    const wrEl = document.getElementById('report-win-rate');
    wrEl.textContent = `${winRate.toFixed(1)}%`;
    wrEl.className = 'stat-value ' + (winRate >= 50 ? 'profit-cell' : 'loss-cell');

    // 3. 총 실현손익
    const profit = stats.total_profit || 0;
    const tpEl = document.getElementById('report-total-profit');
    tpEl.textContent = `${profit >= 0 ? '+' : ''}${Math.round(profit).toLocaleString()}원`;
    tpEl.className = 'stat-value ' + (profit >= 0 ? 'profit-cell' : 'loss-cell');

    // 4. 평균 수익률 (Server provides avg_profit)
    const avgReturn = stats.avg_profit || 0;
    const arEl = document.getElementById('report-avg-return');
    arEl.textContent = `${avgReturn >= 0 ? '+' : ''}${avgReturn.toFixed(2)}%`;
    arEl.className = 'stat-value ' + (avgReturn >= 0 ? 'profit-cell' : 'loss-cell');
}

function updateSellTable(logs) {
    const tbody = document.getElementById('sell-body');

    if (!logs || logs.length === 0 || logs.error) {
        tbody.innerHTML = '<tr class="empty-row"><td colspan="5">매도 내역이 없습니다</td></tr>';
        return;
    }

    let html = '';
    for (const log of logs.slice(0, 30)) { // 최근 30건
        const plRt = parseFloat(log.profit_rate || 0);
        const cellClass = plRt >= 0 ? 'profit-cell' : 'loss-cell';

        html += `
            <tr>
                <td>${log.time || ''}</td>
                <td><strong>${log.name || ''}</strong></td>
                <td>${formatNumber(log.qty || 0)}</td>
                <td class="${cellClass}">${plRt >= 0 ? '+' : ''}${plRt.toFixed(2)}%</td>
                <td>${log.reason || ''}</td>
            </tr>
        `;
    }
    tbody.innerHTML = html;
}

// ============ Settings ============

const SETTING_KEYS = [
    'take_profit_rate',
    'stop_loss_rate',
    'time_cut_minutes',
    'time_cut_profit',
    'target_stock_count',
    'split_buy_cnt',
    'target_profit_amt',
    'global_loss_rate',
    'trailing_stop_activation_rate',
    'trailing_stop_callback_rate'
];

async function loadSettings() {
    try {
        const res = await fetch('/api/settings');
        const settings = await res.json();

        // [NEW] trading_mode 변환 로직 (MOCK/PAPER/REAL)
        let tradingMode = 'MOCK'; // 기본값: Mock

        // trading_mode 필드가 있으면 직접 사용
        if (settings.trading_mode) {
            tradingMode = settings.trading_mode.toUpperCase();
        } else {
            // 없으면 기존 필드에서 변환
            if (settings.use_mock_server === true || settings.use_mock_server === 'true') {
                tradingMode = 'MOCK';
            } else if (settings.is_paper_trading === true || settings.is_paper_trading === 'true') {
                tradingMode = 'PAPER';
            } else {
                tradingMode = 'REAL';
            }
        }

        // trading_mode 설정
        const tradingModeEl = document.getElementById('trading_mode');
        if (tradingModeEl) {
            tradingModeEl.value = tradingMode;
        }

        // Populate all input fields automatically
        for (const [key, value] of Object.entries(settings)) {
            // trading_mode 관련 및 제거된 필드 스킵
            if (key === 'use_mock_server' || key === 'is_paper_trading' || key === 'process_name' || key === 'auto_start') {
                continue;
            }

            const el = document.getElementById(key);
            if (el) {
                try {
                    if (el.tagName === 'SELECT') {
                        const valStr = (value !== null && value !== undefined) ? value.toString() : '';
                        if (![...el.options].some(o => o.value === valStr)) {
                            const opt = document.createElement('option');
                            opt.value = valStr;
                            opt.textContent = valStr + (isNaN(value) ? '' : ' (Custom)');
                            el.appendChild(opt);
                        }
                        el.value = valStr;
                    } else if (el.type === 'checkbox') {
                        el.checked = !!value;
                    } else {
                        el.value = (value !== null && value !== undefined) ? value : '';
                    }
                } catch (fieldErr) {
                    console.warn(`Error populating field ${key}:`, fieldErr);
                }
            }
        }

        // [UX] API 모드 배지 업데이트 - 통합 함수 사용
        updateBadge(settings.use_mock_server !== false, settings.is_paper_trading !== false);

        addLog('설정 로드 완료', 'success');

        // [Safety] 설정 로드 후 상태 연동
        syncBadgePreview();
    } catch (e) {
        console.error('Failed to load settings:', e);
        addLog('설정 로드 실패', 'error');
    }
}

// [NEW] 통합 뱃지 업데이트 함수
function updateBadge(useMock, isPaper) {
    const apiBadge = document.getElementById('api-mode-badge');
    const logApiBadge = document.getElementById('log-api-mode-banner');

    let modeText = "";
    let modeClass = "";

    if (useMock) {
        modeText = "모의투자 [내부Mock]";
        modeClass = "api-badge mock";
    } else if (isPaper) {
        modeText = "모의투자 [키움API]";
        modeClass = "api-badge real";
    } else {
        modeText = "실전투자 [키움API]";
        modeClass = "api-badge danger";
    }

    if (apiBadge) {
        apiBadge.textContent = modeText;
        apiBadge.className = modeClass;
        if (modeText.includes('실전')) apiBadge.style.backgroundColor = '#ef4444';
        else if (modeText.includes('키움API')) apiBadge.style.backgroundColor = '#007bff';
    }
    if (logApiBadge) {
        logApiBadge.style.display = 'inline-block';
        logApiBadge.textContent = modeText;
        logApiBadge.className = modeClass;
        if (modeText.includes('실전')) logApiBadge.style.backgroundColor = '#ef4444';
        else if (modeText.includes('키움API')) logApiBadge.style.backgroundColor = '#007bff';
    }
}

// [UX] 드롭다운 변경 시 뱃지 실시간 미리보기
function syncBadgePreview() {
    const tradingModeEl = document.getElementById('trading_mode');
    if (!tradingModeEl) return;

    const mode = tradingModeEl.value;
    let useMock = false;
    let isPaper = false;

    if (mode === 'MOCK') {
        useMock = true;
        isPaper = false; // Mock은 계좌 유형 상관없이 가상임
    } else if (mode === 'PAPER') {
        useMock = false;
        isPaper = true;
    } else if (mode === 'REAL') {
        useMock = false;
        isPaper = false;
    }

    updateBadge(useMock, isPaper);
}

// [Safety Logic] 프로세스가 '실전'이면 하위 옵션 잠금
function toggleSafetySettings() {
    const processName = document.getElementById('process_name');
    const useMockServer = document.getElementById('use_mock_server');

    if (!processName || !useMockServer) return;

    if (processName.value === '실전') {
        // 실전 모드면 강제로 Mock 사용 해제 및 비활성화
        useMockServer.value = 'false';
        useMockServer.disabled = true;
        useMockServer.parentElement.style.opacity = '0.5';
    } else {
        // 모의 모드면 선택 가능
        useMockServer.disabled = false;
        useMockServer.parentElement.style.opacity = '1';
    }

    // 뱃지 미리보기 동기화
    syncBadgePreview();
}

// 이벤트 초기화
document.addEventListener('DOMContentLoaded', () => {
    const tradingModeSelect = document.getElementById('trading_mode');

    if (tradingModeSelect) {
        tradingModeSelect.addEventListener('change', syncBadgePreview);
        // 초기 로드 시에도 한 번 실행
        setTimeout(syncBadgePreview, 500);
    }
});

async function saveSettings() {
    const btnGeneral = document.getElementById('save-settings');
    const btnCreds = document.getElementById('save-credentials');

    const originalTextGeneral = btnGeneral ? btnGeneral.innerHTML : '';
    const originalTextCreds = btnCreds ? btnCreds.innerHTML : '';

    if (btnGeneral) {
        btnGeneral.innerHTML = '<span class="spinner-small"></span> 저장 중...';
        btnGeneral.disabled = true;
    }
    if (btnCreds) {
        btnCreds.innerHTML = '<span class="spinner-small"></span> 저장 중...';
        btnCreds.disabled = true;
    }

    // 플리커링 방지용 전역 플래그
    window._is_saving_settings = true;

    try {
        const fields = [
            'search_seq', 'take_profit_rate', 'stop_loss_rate',
            'target_stock_count', 'trading_capital_ratio', 'split_buy_cnt', 'single_stock_strategy', 'single_stock_rate',
            'global_loss_rate', 'target_profit_amt', 'liquidation_time', 'use_trailing_stop',
            'trailing_stop_activation_rate', 'trailing_stop_callback_rate', 'use_rsi_filter',
            'rsi_limit', 'upper_limit_rate', 'time_cut_minutes', 'time_cut_profit', 'mock_volatility_rate',
            'sell_rebuy_wait_seconds',
            'real_app_key', 'real_app_secret', 'paper_app_key', 'paper_app_secret',
            'telegram_token', 'telegram_chat_id', 'my_account'
        ];

        const stringFields = ['real_app_key', 'real_app_secret', 'paper_app_key', 'paper_app_secret', 'telegram_token', 'telegram_chat_id', 'my_account', 'liquidation_time'];
        const newSettings = {};

        fields.forEach(field => {
            const el = document.getElementById(field);
            if (el) {
                const val = el.value;
                if (stringFields.includes(field) || field === 'search_seq') {
                    newSettings[field] = val;
                }
                else if (val === 'true') newSettings[field] = true;
                else if (val === 'false') newSettings[field] = false;
                else if (val.trim() !== "" && !isNaN(val)) {
                    newSettings[field] = val.includes('.') ? parseFloat(val) : parseInt(val);
                }
                else newSettings[field] = val;
            }
        });

        // [NEW] trading_mode를 단일 필드로 저장 (MOCK/PAPER/REAL)
        const tradingModeEl = document.getElementById('trading_mode');
        if (tradingModeEl) {
            const mode = tradingModeEl.value;
            newSettings['trading_mode'] = mode;

            // 하위 호환성을 위해 기존 필드도 설정
            if (mode === 'MOCK') {
                newSettings['use_mock_server'] = true;
                newSettings['is_paper_trading'] = false;
                newSettings['process_name'] = '모의';
            } else if (mode === 'PAPER') {
                newSettings['use_mock_server'] = false;
                newSettings['is_paper_trading'] = true;
                newSettings['process_name'] = '모의';
            } else if (mode === 'REAL') {
                newSettings['use_mock_server'] = false;
                newSettings['is_paper_trading'] = false;
                newSettings['process_name'] = '실전';
            }
        }

        console.log('📤 저장 요청:', newSettings);

        const response = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(newSettings)
        });

        const result = await response.json();
        console.log('📥 서버 응답:', result);

        if (btnGeneral) btnGeneral.innerHTML = '✅ 저장 완료!';
        if (btnCreds) btnCreds.innerHTML = '✅ 저장 완료!';

        // [NEW] 모드 표시 개선
        let modeText = 'Mock';
        if (!newSettings.use_mock_server) {
            modeText = newSettings.is_paper_trading ? 'Paper' : 'Real';
        }

        showToast('설정 저장 및 동기화 완료!', 'success');
        addLog(`시스템 설정이 업데이트되었습니다. (모드: ${modeText})`, 'success');

        // [UX] 즉시 UI 배지 갱신
        updateBadge(newSettings.use_mock_server, newSettings.is_paper_trading);

        // 저장 후 즉시 데이터 동기화 시도
        console.log('🔄 모드 전환 감지 - 데이터 강제 갱신 시작');

        // [Critical Fix] 모든 캐시 초기화
        isTableInitialized = false;
        lastHoldingsJSON = '';
        globalTradingLogs = { buys: [], sells: [] };
        lastTradeLogId = 0; // [Sync Fix] ID 리셋하여 새로운 모드 로그를 처음부터 가져오게 함
        currentStats = null; // 통계 리셋

        // UI 즉시 초기화 (보고서 상단)
        document.getElementById('report-count').textContent = '0회';
        document.getElementById('report-win-rate').textContent = '0%';
        document.getElementById('report-total-profit').textContent = '0원';

        // 잠시 대기 (봇이 명령을 수신하고 재초기화를 완료할 시간 부여)
        await new Promise(resolve => setTimeout(resolve, 1000));

        await loadSettings();
        await loadInitialStatus();
        await loadTradingLog(true); // [Sync Fix] 강제 초기화 로드

        // 추가 동기화 (네트워크 지연 등에 대비해 1초 후에 한 번 더 갱신)
        setTimeout(async () => {
            await loadInitialStatus();
            await loadTradingLog(true); // 강제 초기화 재시도
        }, 1000);

        console.log('✅ 데이터 갱신 완료');

        // 1초 후 lock 해제 및 버튼 복구
        setTimeout(() => {
            if (btnGeneral) {
                btnGeneral.innerHTML = originalTextGeneral || '💾 설정 저장 및 동기화';
                btnGeneral.disabled = false;
            }
            if (btnCreds) {
                btnCreds.innerHTML = originalTextCreds || '💾 인증 정보 저장 및 동기화';
                btnCreds.disabled = false;
            }
            window._is_saving_settings = false;
        }, 1000);

    } catch (e) {
        console.error('❌ 저장 실패:', e);
        if (btnGeneral) {
            btnGeneral.innerHTML = '❌ 저장 실패';
            btnGeneral.disabled = false;
        }
        if (btnCreds) {
            btnCreds.innerHTML = '❌ 저장 실패';
            btnCreds.disabled = false;
        }
        showToast('저장 실패: ' + e.message, 'error');
        window._is_saving_settings = false;
    }
}

// ===== Apply Preset Settings =====
function applyPreset(presetId) {
    const presets = {
        molppang_water: {
            // 기본 설정
            target_stock_count: 1,
            split_buy_cnt: 4,

            // 매수 전략
            single_stock_strategy: "WATER",
            single_stock_rate: 1.0,

            // 매도 및 리스크
            take_profit_rate: 2.5,
            stop_loss_rate: -3.0,
            upper_limit_rate: 29.0,
            time_cut_minutes: 5,
            time_cut_profit: 0.3,

            // 고급 설정
            use_trailing_stop: "true",
            trailing_stop_activation_rate: 1.5,
            trailing_stop_callback_rate: 0.7,

            // 위험 관리
            global_loss_rate: -10.0,
            use_rsi_filter: "false"
        },
        molppang_fire: {
            // 기본 설정
            target_stock_count: 1,
            split_buy_cnt: 4,

            // 매수 전략
            single_stock_strategy: "FIRE",
            single_stock_rate: 1.0,

            // 매도 및 리스크
            take_profit_rate: 3.0,
            stop_loss_rate: -3.0,
            upper_limit_rate: 29.0,
            time_cut_minutes: 7,
            time_cut_profit: 0.3,

            // 고급 설정
            use_trailing_stop: "true",
            trailing_stop_activation_rate: 1.5,
            trailing_stop_callback_rate: 0.7,

            // 위험 관리
            global_loss_rate: -10.0,
            use_rsi_filter: "false"
        },
        bunsan_water: {
            // 기본 설정
            target_stock_count: 5,
            split_buy_cnt: 3,

            // 매수 전략
            single_stock_strategy: "WATER",
            single_stock_rate: 1.5,

            // 매도 및 리스크
            take_profit_rate: 3.5,
            stop_loss_rate: -4.0,
            upper_limit_rate: 29.0,
            time_cut_minutes: 15,
            time_cut_profit: 0.5,

            // 고급 설정
            use_trailing_stop: "true",
            trailing_stop_activation_rate: 2.0,
            trailing_stop_callback_rate: 1.0,

            // 위험 관리
            global_loss_rate: -10.0,
            use_rsi_filter: "false"
        },
        bunsan_fire: {
            // 기본 설정
            target_stock_count: 5,
            split_buy_cnt: 3,

            // 매수 전략
            single_stock_strategy: "FIRE",
            single_stock_rate: 1.5,

            // 매도 및 리스크
            take_profit_rate: 4.0,
            stop_loss_rate: -4.0,
            upper_limit_rate: 29.0,
            time_cut_minutes: 20,
            time_cut_profit: 0.5,

            // 고급 설정
            use_trailing_stop: "true",
            trailing_stop_activation_rate: 2.5,
            trailing_stop_callback_rate: 1.2,

            // 위험 관리
            global_loss_rate: -10.0,
            use_rsi_filter: "false"
        }
    };

    const settings = presets[presetId];
    if (!settings) {
        showToast('프리셋을 찾을 수 없습니다', 'error');
        return;
    }

    // Apply settings to ALL form fields
    console.log(`🎯 프리셋 적용 시작: ${presetId}`);
    let successCount = 0;
    let failCount = 0;

    // 변경 내용 추적
    const changes = [];
    const fieldNames = {
        target_stock_count: '종목 수',
        split_buy_cnt: '분할 횟수',
        single_stock_strategy: '전략',
        single_stock_rate: '전략 기준',
        take_profit_rate: '익절',
        stop_loss_rate: '손절',
        upper_limit_rate: '상한가',
        time_cut_minutes: '타임컷',
        time_cut_profit: '타임컷 수익',
        use_trailing_stop: 'Trailing Stop',
        trailing_stop_activation_rate: 'TS 활성화',
        trailing_stop_callback_rate: 'TS 콜백',
        global_loss_rate: '글로벌 손실',
        use_rsi_filter: 'RSI 필터'
    };

    for (const [key, value] of Object.entries(settings)) {
        const el = document.getElementById(key);

        if (!el) {
            console.warn(`❌ 필드 없음: ${key}`);
            failCount++;
            continue;
        }

        // 현재 값 저장
        const oldValue = el.value;

        try {
            if (el.tagName === 'SELECT') {
                const valueStr = String(value);
                const optionExists = Array.from(el.options).some(opt => opt.value === valueStr);

                if (optionExists) {
                    el.value = valueStr;

                    // 변경 감지
                    if (oldValue !== valueStr) {
                        const fieldName = fieldNames[key] || key;
                        const oldText = el.options[Array.from(el.options).findIndex(o => o.value === oldValue)]?.text || oldValue;
                        const newText = el.options[el.selectedIndex].text;
                        changes.push(`${fieldName}: ${oldText} → ${newText}`);
                    }

                    console.log(`✅ ${key} = ${valueStr}`);
                    successCount++;
                } else {
                    console.warn(`⚠️ ${key}: Option '${valueStr}' 없음. 사용 가능:`, Array.from(el.options).map(o => o.value));
                    failCount++;
                }
            } else if (el.type === 'number') {
                el.value = value;
                if (oldValue !== String(value)) {
                    changes.push(`${fieldNames[key] || key}: ${oldValue} → ${value}`);
                }
                console.log(`✅ ${key} = ${value}`);
                successCount++;
            } else {
                el.value = value;
                if (oldValue !== String(value)) {
                    changes.push(`${fieldNames[key] || key}: ${oldValue} → ${value}`);
                }
                console.log(`✅ ${key} = ${value}`);
                successCount++;
            }

            // Visual feedback
            el.style.transition = 'background-color 0.3s';
            el.style.backgroundColor = '#fff3cd';
            setTimeout(() => { el.style.backgroundColor = ''; }, 1000);
        } catch (e) {
            console.error(`❌ ${key} 오류:`, e);
            failCount++;
        }
    }

    console.log(`📊 완료: 성공 ${successCount}, 실패 ${failCount}`);

    const presetNames = {
        molppang_water: "💧 몰빵 물타기",
        molppang_fire: "🔥 몰빵 불타기",
        bunsan_water: "💧 분산 물타기",
        bunsan_fire: "🔥 분산 불타기"
    };

    // 변경 내용 표시
    if (changes.length > 0) {
        const changeList = changes.join('\n');
        const message = `✅ ${presetNames[presetId]} 설정 적용 완료!\n\n【변경된 항목: ${changes.length}개】\n${changeList}\n\n⚠️ 반드시 '💾 설정 저장' 버튼을 눌러 저장하세요!`;

        alert(message);  // 다이얼로그로 표시
        addLog(`프리셋 ${presetNames[presetId]}: ${changes.length}개 변경`, 'success');
    } else {
        alert(`${presetNames[presetId]}\n\n변경 사항이 없습니다.\n(이미 같은 설정입니다)`);
    }
}

// ============ Bot Control ============

async function sendCommand(command) {
    try {
        const res = await fetch('/api/command', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command })
        });
        const result = await res.json();
        if (result.success) {
            addLog(`명령 실행: ${command}`, 'success');
        } else {
            addLog(`명령 실패: ${result.error}`, 'error');
        }
        return result;
    } catch (e) {
        addLog(`명령 오류: ${e.message}`, 'error');
        return { success: false, error: e.message };
    }
}

// ============ Logging ============

function addLog(message, type = '') {
    const container = document.getElementById('log-container');
    const entry = document.createElement('div');
    entry.className = 'log-entry ' + type;

    const now = new Date();
    const timeStr = now.toTimeString().split(' ')[0];
    entry.textContent = `[${timeStr}] ${message}`;

    // 로그 컨테이너에 추가 (최신순)
    container.insertBefore(entry, container.firstChild);

    // [Resumed] 알림 메시지 복원 (우측 상단 표시)
    showToast(message, type);

    // Keep only last 100 entries
    while (container.children.length > 100) {
        container.removeChild(container.lastChild);
    }
}

function clearLogs() {
    const container = document.getElementById('log-container');
    container.innerHTML = '';
    addLog('로그 초기화됨', 'success');
}

// ============ Toast Notifications ============

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return; // Safety check

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    // 아이콘 설정
    const icons = {
        success: '✅',
        error: '❌',
        warning: '⚠️',
        info: 'ℹ️'
    };

    toast.innerHTML = `<span>${icons[type] || icons.info}</span><span>${message}</span>`;
    // [Fix] 최신 알림이 위쪽에 뜨도록 변경 (prepend)
    container.prepend(toast);

    // 3초 후 제거
    setTimeout(() => {
        toast.remove();
    }, 3000);
}

// ============ Time Update ============

function updateTime() {
    const now = new Date();
    const timeStr = now.toLocaleString('ko-KR', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
    document.getElementById('current-time').textContent = timeStr;
}

// ============ Utilities ============

function formatNumber(num) {
    if (num === null || num === undefined) return '0';
    return parseInt(num).toLocaleString('ko-KR');
}

// ============ View Switching ============

function showView(viewId) {
    const views = document.querySelectorAll('.view');
    const navItems = document.querySelectorAll('.nav-item');
    const toggleSwitch = document.getElementById('btn-bot-toggle');
    const viewTitle = document.getElementById('view-title');

    views.forEach(v => v.classList.remove('active'));
    navItems.forEach(n => n.classList.remove('active'));
    toggleSwitch?.classList.remove('active');

    const activeView = document.getElementById(`view-${viewId}`);

    if (activeView) {
        activeView.classList.add('active');

        if (viewId === 'dashboard') {
            toggleSwitch?.classList.add('active');
            viewTitle.textContent = `💰 자산현황`;
        } else if (viewId === 'reports') {
            // [Sync Fix] 매매 보고서 클릭 시 즉시 동기화 및 '전체' 탭 초기화
            const allTab = document.querySelector('.tab-btn[data-tab="all"]');
            if (allTab) {
                document.querySelectorAll('.tab-btn').forEach(t => t.classList.remove('active'));
                allTab.classList.add('active');
            }
            renderFilteredLogs('all');
            loadTradingLog(true);
            const activeNav = document.querySelector(`.nav-item[data-view="${viewId}"]`);
            if (activeNav) {
                activeNav.classList.add('active');
                const navText = activeNav.querySelector('.nav-text').textContent;
                const navIcon = activeNav.querySelector('.nav-icon').textContent;
                viewTitle.textContent = `${navIcon} ${navText}`;
            }
        } else {
            const activeNav = document.querySelector(`.nav-item[data-view="${viewId}"]`);
            if (activeNav) {
                activeNav.classList.add('active');
                const navText = activeNav.querySelector('.nav-text').textContent;
                const navIcon = activeNav.querySelector('.nav-icon').textContent;
                viewTitle.textContent = `${navIcon} ${navText}`;
            }
        }

        // Persist View
        localStorage.setItem('activeView', viewId);
    }
}

// ============ Initialize ============

document.addEventListener('DOMContentLoaded', () => {
    // Connect WebSocket
    connectWebSocket();

    // --- Sidebar Navigation ---
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const viewId = item.dataset.view;
            showView(viewId);
        });
    });

    // Restore last view or default to dashboard
    const lastView = localStorage.getItem('activeView') || 'dashboard';
    showView(lastView);

    // --- Tab Switching Logic (Internal to Reports Page) ---
    const tabs = document.querySelectorAll('.tab-btn');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Active State
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            // Render
            const filterType = tab.dataset.tab;
            renderFilteredLogs(filterType);
        });
    });

    // Load initial data (즉시 로드하여 HTML 초기값 덮어쓰기)
    loadInitialStatus();
    loadSettings();
    loadTradingLog();

    // Update time every second
    updateTime();
    setInterval(updateTime, 1000);

    // Refresh data periodically
    setInterval(loadTradingLog, 5000);

    // -- Settings Management (단일 버튼 통합) --
    document.getElementById('save-settings')?.addEventListener('click', saveSettings);
    document.getElementById('save-credentials')?.addEventListener('click', saveSettings);
    document.getElementById('reload-settings')?.addEventListener('click', loadSettings);
    document.getElementById('clear-logs')?.addEventListener('click', clearLogs);

    // 매수 내역 삭제 버튼
    document.getElementById('clear-buy-log')?.addEventListener('click', async () => {
        if (confirm('매수 내역을 모두 삭제하시겠습니까?')) {
            const btn = document.getElementById('clear-buy-log');
            btn.classList.add('loading');
            btn.disabled = true;

            try {
                const res = await fetch('/api/buy-log', { method: 'DELETE' });
                const result = await res.json();
                if (result.success) {
                    showToast('매수 내역이 삭제되었습니다', 'success');
                    addLog('매수 내역 삭제 완료', 'success');
                    loadTradingLog();
                } else {
                    showToast('삭제 실패: ' + (result.error || '알 수 없는 오류'), 'error');
                    addLog('매수 내역 삭제 실패', 'error');
                }
            } catch (e) {
                showToast('삭제 오류: ' + e.message, 'error');
                addLog('매수 내역 삭제 오류: ' + e.message, 'error');
            } finally {
                btn.classList.remove('loading');
                btn.disabled = false;
            }
        }
    });

    // 매도 내역 삭제 버튼
    document.getElementById('clear-sell-log')?.addEventListener('click', async () => {
        if (confirm('매도 내역을 모두 삭제하시겠습니까?')) {
            const btn = document.getElementById('clear-sell-log');
            btn.classList.add('loading');
            btn.disabled = true;

            try {
                const res = await fetch('/api/sell-log', { method: 'DELETE' });
                const result = await res.json();
                if (result.success) {
                    showToast('매도 내역이 삭제되었습니다', 'success');
                    addLog('매도 내역 삭제 완료', 'success');
                    loadTradingLog();
                } else {
                    showToast('삭제 실패: ' + (result.error || '알 수 없는 오류'), 'error');
                    addLog('매도 내역 삭제 실패', 'error');
                }
            } catch (e) {
                showToast('삭제 오류: ' + e.message, 'error');
                addLog('매도 내역 삭제 오류: ' + e.message, 'error');
            } finally {
                btn.classList.remove('loading');
                btn.disabled = false;
            }
        }
    });

    // Bot Status Button Click
    document.getElementById('btn-bot-toggle')?.addEventListener('click', async (e) => {
        const btn = e.currentTarget;
        const currentState = btn.dataset.state; // 'running' or 'stopped'
        const command = currentState === 'running' ? 'stop' : 'start';

        // [Optimistic UI] 즉시 반응 (사용자 체감 개선)
        pendingBotToggleTime = Date.now();
        btn.classList.add('loading-process');

        // 버튼을 즉시 토글시켜 보여줌
        if (command === 'stop') {
            btn.innerHTML = '<span>▶</span> 시작 대기..';
            btn.dataset.state = 'stopped';
        } else {
            btn.innerHTML = '<span>⏹</span> 종료 대기..';
            btn.dataset.state = 'running';
        }
        btn.style.opacity = '0.7';

        // 명령 전송
        try {
            await sendCommand(command);

            // 토스트 알림
            const msg = command === 'start' ? '🚀 봇 시작 명령 전송됨' : '🛑 봇 종료 명령 전송됨';
            showToast(msg, 'info');

            // 명령 성공 후 텍스트 살짝 보정 (서버 상태 반영 전까지 자연스럽게 유지)
            setTimeout(() => {
                if (command === 'stop') btn.innerHTML = '<span>▶</span> 시작';
                else btn.innerHTML = '<span>⏹</span> 종료';
            }, 1000);

        } catch (err) {
            showToast('명령 전송 실패', 'error');
            pendingBotToggleTime = 0; // 즉시 동기화 허용
            btn.classList.remove('loading-process');
            btn.disabled = false;
            btn.style.opacity = '1';
            // 버튼 복구
            if (currentState === 'running') {
                btn.innerHTML = '<span>⏹</span> 종료';
                btn.dataset.state = 'running';
            } else {
                btn.innerHTML = '<span>▶</span> 시작';
                btn.dataset.state = 'stopped';
            }
        }
    });

    // Tab switching with delete button visibility
    document.querySelectorAll('.tab-btn').forEach(tab => {
        tab.addEventListener('click', () => {
            const tabType = tab.dataset.tab;

            // Update active tab
            document.querySelectorAll('.tab-btn').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            // Show/hide delete all & reset buttons
            const deleteAllBtn = document.getElementById('btn-delete-all-timecuts');
            const clearSellLogBtn = document.getElementById('clear-sell-log');
            const resetHiddenBtn = document.getElementById('btn-reset-hidden-timecuts');

            if (deleteAllBtn) {
                if (tabType === 'timecut') {
                    deleteAllBtn.style.display = 'block';
                    if (resetHiddenBtn) resetHiddenBtn.style.display = 'block';
                } else {
                    deleteAllBtn.style.display = 'none';
                    if (resetHiddenBtn) resetHiddenBtn.style.display = 'none';
                }
            }

            if (clearSellLogBtn) {
                if (tabType === 'sell' || tabType === 'all') {
                    clearSellLogBtn.style.display = 'block';
                } else {
                    clearSellLogBtn.style.display = 'none';
                }
            }

            // 매수 삭제 버튼 로직 추가
            const clearBuyLogBtn = document.getElementById('clear-buy-log');
            if (clearBuyLogBtn) {
                if (tabType === 'buy' || tabType === 'all') {
                    clearBuyLogBtn.style.display = 'block';
                } else {
                    clearBuyLogBtn.style.display = 'none';
                }
            }

            // Render filtered data
            renderFilteredLogs(tabType);
        });
    });

    // Bulk delete all timecuts - SESSION ONLY
    document.getElementById('btn-delete-all-timecuts')?.addEventListener('click', () => {
        const allSells = globalTradingLogs.sells || [];

        let deleteCount = 0;
        allSells.forEach(sell => {
            if (isTCFunc(sell)) {
                // Generate UID same as display logic
                const uid = getUID(sell);

                if (!deletedTimeCutIds.includes(uid)) {
                    deletedTimeCutIds.push(uid);
                    deleteCount++;
                }
            }
        });

        if (deleteCount === 0) {
            showToast('삭제할 새로운 타임컷이 없습니다', 'info');
            return;
        }

        saveDeletedIds();
        renderFilteredLogs('timecut');
        showToast(`${deleteCount}건의 타임컷이 화면에서 삭제되었습니다.`, 'success');
    });

    // Reset deleted timecuts
    document.getElementById('btn-reset-hidden-timecuts')?.addEventListener('click', () => {
        clearDeletedTimeCuts();
        showToast('삭제된 모든 타임컷이 복구되었습니다.', 'success');
    });

    // Close View Buttons - Return to Dashboard
    document.querySelectorAll('.btn-close-view').forEach(btn => {
        btn.addEventListener('click', () => {
            showView('dashboard');
        });
    });

    // ===== Preset Buttons =====
    document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const presetId = btn.dataset.preset;
            applyPreset(presetId);
        });
    });

    // ===== Auto-Preset Logic =====
    // 종목 수와 전략 변경 시 자동으로 팩터 업데이트
    const targetStockCount = document.getElementById('target_stock_count');
    const strategy = document.getElementById('single_stock_strategy');

    function applyAutoPreset() {
        const stockCount = targetStockCount.value;
        const strategyType = strategy.value;

        // 조합 결정: 몰빵(1) vs 분산(3 or 5), 물타기(WATER) vs 불타기(FIRE)
        const isMolppang = stockCount === '1';
        const isWater = strategyType === 'WATER';

        let presetValues = {};

        if (isMolppang && isWater) {
            // 몰빵 물타기
            presetValues = {
                split_buy_cnt: '4',
                single_stock_rate: '1.0',
                take_profit_rate: '2.5',
                stop_loss_rate: '-3.0',
                time_cut_minutes: '100',
                time_cut_profit: '0.3',
                use_trailing_stop: 'true',
                trailing_stop_activation_rate: '1.5',
                trailing_stop_callback_rate: '0.7'
            };
        } else if (isMolppang && !isWater) {
            // 몰빵 불타기
            presetValues = {
                split_buy_cnt: '4',
                single_stock_rate: '1.0',
                take_profit_rate: '3.0',
                stop_loss_rate: '-3.0',
                time_cut_minutes: '100',
                time_cut_profit: '0.3',
                use_trailing_stop: 'true',
                trailing_stop_activation_rate: '1.5',
                trailing_stop_callback_rate: '0.7'
            };
        } else if (!isMolppang && isWater) {
            // 분산 물타기
            presetValues = {
                split_buy_cnt: '3',
                single_stock_rate: '1.5',
                take_profit_rate: '3.5',
                stop_loss_rate: '-4.0',
                time_cut_minutes: '100',
                time_cut_profit: '0.5',
                use_trailing_stop: 'true',
                trailing_stop_activation_rate: '2.0',
                trailing_stop_callback_rate: '1.0'
            };
        } else {
            // 분산 불타기
            presetValues = {
                split_buy_cnt: '3',
                single_stock_rate: '1.5',
                take_profit_rate: '4.0',
                stop_loss_rate: '-4.0',
                time_cut_minutes: '100',
                time_cut_profit: '0.5',
                use_trailing_stop: 'true',
                trailing_stop_activation_rate: '2.5',
                trailing_stop_callback_rate: '1.2'
            };
        }

        // 팩터 자동 적용
        for (const [key, value] of Object.entries(presetValues)) {
            const el = document.getElementById(key);
            if (el && el.value !== value) {
                el.value = value;
                // Visual feedback
                el.style.transition = 'background-color 0.3s';
                el.style.backgroundColor = '#d1fae5';
                setTimeout(() => { el.style.backgroundColor = ''; }, 600);
            }
        }

        const modeName = isMolppang ? '몰빵' : '분산';
        const strategyName = isWater ? '물타기' : '불타기';
        console.log(`✅ 자동 적용: ${modeName} ${strategyName}`);
        addLog(`자동 적용: ${modeName} ${strategyName}`, 'success');
    }

    // 이벤트 리스너 등록
    targetStockCount?.addEventListener('change', applyAutoPreset);
    strategy?.addEventListener('change', applyAutoPreset);

    addLog('대시보드 초기화 완료');
    showToast('대시보드가 준비되었습니다', 'success');
});

// Cache bust: 20251221_1926_FINAL_REVISION
