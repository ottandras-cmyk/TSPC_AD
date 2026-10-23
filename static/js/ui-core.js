const NL = String.fromCharCode(10);
let allUsers = [];
let allGroups = [];
let currentUsersSubView = 'users';

let chartCpu = null, chartRam = null, chartStorage = null, chartLlm = null;
let chartAdChanges = null;
let telemetryInterval = null;
let adAnalyticsData = null;
let activeWindowKey = 'w_24h';

let currentDayEvents = [];
let activeDayFilterType = 'ALL';
let activeDayDate = '';
let daySortCol = 'timestamp';
let daySortDir = 'desc';

let rawChartLabels = [];
let rawChartTotal = [];
let rawChartAdded = [];
let rawChartRemoved = [];
let rawChartLifecycle = [];
let currentFilteredLabels = [];

let currentAiModelsData = null;
let modelUpdatesData = {};
let updatePollTimer = null;

function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function escapeJs(str) {
    if (!str) return '';
    return String(str).replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

function switchTab(tabId) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.content').forEach(c => c.classList.remove('active'));
    const targetTab = document.getElementById('tab-' + tabId);
    const targetContent = document.getElementById('content-' + tabId);
    if (targetTab) targetTab.classList.add('active');
    if (targetContent) targetContent.classList.add('active');
    
    if (tabId === 'users' && allUsers.length === 0) loadUsersAndGroups();
    if (tabId === 'sync-history') loadSyncHistory();
    if (tabId === 'ad-changes') loadAdAnalytics();
    if (tabId === 'ai') loadAiModels('modelSelect');
    if (tabId === 'backups') loadBackups();
    if (tabId === 'history-import') autoScanServerFolder();
    if (tabId === 'settings') loadGitHubHistory();
    if (tabId === 'telemetry') {
        loadSessionsData();
        loadTelemetryLive();
        loadTelemetryHistory();
        loadWebAccessLogs();
        loadHostIpHistory();
        if (!telemetryInterval) telemetryInterval = setInterval(() => { loadTelemetryLive(); loadSessionsData(); }, 10000);
    } else {
        if (telemetryInterval) { clearInterval(telemetryInterval); telemetryInterval = null; }
    }
}

async function fetchLiveGitHubVersion() {
    try {
        const res = await fetch('/api/github/version');
        const data = await res.json();
        if (data.version) {
            const el = document.getElementById('app_version_label');
            if (el) el.innerText = data.version;
        }
    } catch(e) {}
}
fetchLiveGitHubVersion();

// --- FELHASZNÁLÓK ÉS CSOPORTOK KEZELÉSE ---
async function loadUsersAndGroups() {
    const tbodyU = document.getElementById('usersTableBody');
    if (tbodyU) tbodyU.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:15px; color:#64748b;">Felhasználók és csoportok betöltése...</td></tr>';
    try {
        const [uRes, gRes] = await Promise.all([fetch('/api/users'), fetch('/api/groups')]);
        allUsers = await uRes.json();
        allGroups = await gRes.json();

        const badgeU = document.getElementById('userCountBadge');
        if (badgeU) badgeU.innerText = allUsers.length;
        const badgeG = document.getElementById('groupCountBadge');
        if (badgeG) badgeG.innerText = allGroups.length;

        renderUsers(allUsers);
        renderGroups(allGroups);
    } catch(e) {
        if (tbodyU) tbodyU.innerHTML = `<tr><td colspan="7" style="color:#dc2626; padding:15px;">Hiba: ${e}</td></tr>`;
    }
}

function switchUsersSubTab(view) {
    currentUsersSubView = view;
    const btnU = document.getElementById('btnSubUsers');
    const btnG = document.getElementById('btnSubGroups');
    const boxU = document.getElementById('viewUsersBox');
    const boxG = document.getElementById('viewGroupsBox');
    
    if (view === 'users') {
        if (btnU) { btnU.style.background = '#0284c7'; btnU.style.color = 'white'; }
        if (btnG) { btnG.style.background = '#f1f5f9'; btnG.style.color = '#334155'; }
        if (boxU) boxU.style.display = 'block';
        if (boxG) boxG.style.display = 'none';
    } else {
        if (btnU) { btnU.style.background = '#f1f5f9'; btnU.style.color = '#334155'; }
        if (btnG) { btnG.style.background = '#0284c7'; btnG.style.color = 'white'; }
        if (boxU) boxU.style.display = 'none';
        if (boxG) boxG.style.display = 'block';
    }
    filterUsersAndGroups();
}

function renderUsers(usersList) {
    const tbody = document.getElementById('usersTableBody');
    if (!tbody) return;
    tbody.innerHTML = '';
    
    if (!usersList || usersList.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:15px; color:#94a3b8;">Nincs találat a keresési feltételekre.</td></tr>';
        return;
    }

    usersList.slice(0, 150).forEach(u => {
        const tr = document.createElement('tr');
        tr.style.cursor = 'pointer';
        tr.onclick = (e) => { e.stopPropagation(); openUserModal(u.sam); };

        let badgeColor = '#15803d', badgeBg = '#dcfce7';
        if (u.status === 'Külsös') { badgeColor = '#b45309'; badgeBg = '#fef3c7'; }
        else if (u.status === 'Távozottak' || !u.enabled) { badgeColor = '#b91c1c'; badgeBg = '#fee2e2'; }
        else if (u.status === 'Hosszútávúszabadság') { badgeColor = '#6d28d9'; badgeBg = '#ede9fe'; }
        
        const stBadge = `<span style="background:${badgeBg}; color:${badgeColor}; padding:3px 8px; border-radius:10px; font-size:12px; font-weight:bold;">${escapeHtml(u.status)}</span>`;
        const srcBadge = `<span style="background:#f1f5f9; color:#475569; padding:2px 6px; border-radius:4px; font-size:10px; font-family:monospace;">${escapeHtml(u.source_ref || 'AD')}</span>`;

        tr.innerHTML = `
            <td><b style="color:#0284c7; text-decoration:underline;">${escapeHtml(u.name)}</b> ${srcBadge}</td>
            <td><code>${escapeHtml(u.sam)}</code></td>
            <td>${escapeHtml(u.mail)}</td>
            <td>${stBadge}</td>
            <td>${escapeHtml(u.title)}</td>
            <td>${escapeHtml(u.last_logon)}</td>
            <td style="text-align:right;">
                <button class="btn" style="padding:4px 10px; font-size:11.5px; background:#0284c7;" onclick="event.stopPropagation(); openUserModal('${escapeJs(u.sam)}')">
                    🔍 Adatlap
                </button>
            </td>
        `;
        tbody.appendChild(tr);
    });
    
    const countLbl = document.getElementById('userCountLabel');
    if (countLbl) countLbl.innerText = `Találat: ${usersList.length} fiók (max. 150 megjelenítve)`;
}

function renderGroups(groupsList) {
    const tbody = document.getElementById('groupsTableBody');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (!groupsList || groupsList.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:15px; color:#94a3b8;">Nincs találat a keresési feltételekre.</td></tr>';
        return;
    }

    groupsList.slice(0, 150).forEach(g => {
        const tr = document.createElement('tr');
        tr.style.cursor = 'pointer';
        tr.onclick = (e) => { e.stopPropagation(); openGroupModal(g.sam); };

        const memberCount = g.members ? g.members.length : 0;
        const countBadge = `<span style="background:#e0f2fe; color:#0369a1; padding:2px 8px; border-radius:10px; font-weight:bold; font-size:11.5px;">👥 ${memberCount} fő</span>`;

        tr.innerHTML = `
            <td><b style="color:#0369a1; text-decoration:underline;">${escapeHtml(g.sam)}</b></td>
            <td><span style="background:#f1f5f9; padding:2px 6px; border-radius:4px; font-size:11.5px;">${escapeHtml(g.type)}</span></td>
            <td>${escapeHtml(g.desc)}</td>
            <td>${countBadge}</td>
            <td>${escapeHtml(g.created)}</td>
            <td style="text-align:right;">
                <button class="btn" style="padding:4px 10px; font-size:11.5px; background:#0369a1;" onclick="event.stopPropagation(); openGroupModal('${escapeJs(g.sam)}')">
                    👥 Tagok / Adatlap
                </button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function filterUsersAndGroups() {
    const term = (document.getElementById('userSearchBox')?.value || '').toLowerCase().trim();
    if (currentUsersSubView === 'users') {
        if (!term) { renderUsers(allUsers); return; }
        const filtered = allUsers.filter(u => 
            (u.name && u.name.toLowerCase().includes(term)) ||
            (u.sam && u.sam.toLowerCase().includes(term)) ||
            (u.mail && u.mail.toLowerCase().includes(term)) ||
            (u.department && u.department.toLowerCase().includes(term)) ||
            (u.status && u.status.toLowerCase().includes(term)) ||
            (u.ou && u.ou.toLowerCase().includes(term)) ||
            (u.source_ref && u.source_ref.toLowerCase().includes(term))
        );
        renderUsers(filtered);
    } else {
        if (!term) { renderGroups(allGroups); return; }
        const filtered = allGroups.filter(g => 
            (g.sam && g.sam.toLowerCase().includes(term)) ||
            (g.desc && g.desc.toLowerCase().includes(term)) ||
            (g.type && g.type.toLowerCase().includes(term))
        );
        renderGroups(filtered);
    }
}

function findUserByIdentifier(identifier) {
    if (!identifier) return null;
    const idStr = String(identifier).trim().toLowerCase();
    let u = allUsers.find(x => String(x.sam || '').trim().toLowerCase() === idStr);
    if (u) return u;
    u = allUsers.find(x => String(x.name || '').trim().toLowerCase() === idStr);
    if (u) return u;
    const prefix = idStr.split('@')[0];
    u = allUsers.find(x => String(x.sam || '').trim().toLowerCase() === prefix);
    if (u) return u;
    u = allUsers.find(x => String(x.mail || '').trim().toLowerCase() === idStr);
    if (u) return u;
    return null;
}

function safeSetText(id, val) {
    const el = document.getElementById(id);
    if (el) el.innerText = (val !== null && val !== undefined && val !== '') ? val : '-';
}

function safeSetHtml(id, val) {
    const el = document.getElementById(id);
    if (el) el.innerHTML = (val !== null && val !== undefined && val !== '') ? val : '-';
}

function openUserModal(identifier) {
    const u = findUserByIdentifier(identifier);
    if (!u) {
        alert(`Nem található felhasználói rekord ehhez az azonosítóhoz: ${identifier}`);
        return;
    }
    const gModal = document.getElementById('groupModal');
    if (gModal) gModal.style.display = 'none';

    safeSetText('m-name', u.name);
    const stBadge = u.enabled 
        ? '<span style="background:#16a34a; color:white; padding:4px 10px; border-radius:12px; font-size:12px; font-weight:bold;">Aktív</span>' 
        : '<span style="background:#dc2626; color:white; padding:4px 10px; border-radius:12px; font-size:12px; font-weight:bold;">Letiltva</span>';
    safeSetHtml('m-status', stBadge);

    safeSetText('m-sam', u.sam);
    safeSetText('m-mail', u.mail);
    safeSetText('m-fname', u.first_name);
    safeSetText('m-lname', u.last_name);
    safeSetText('m-desc', u.desc);
    safeSetText('m-title', u.title);
    safeSetText('m-dept', u.department);
    safeSetText('m-company', u.company);
    safeSetText('m-office', u.office);
    safeSetText('m-phone', u.phone);
    safeSetText('m-mobile', u.mobile);
    safeSetText('m-sid', u.sid);
    safeSetText('m-created', u.created);
    safeSetText('m-changed', u.changed);
    safeSetText('m-userstatus', u.status);
    safeSetText('m-sourceref', `${u.source_ref || 'AD'} (${u.source_type || 'AD_SYNC'})`);
    safeSetText('m-lastlogon', u.last_logon);
    safeSetText('m-ou', u.ou);

    let gHtml = '';
    if (u.groups && u.groups.length > 0) {
        u.groups.forEach(g => {
            const gName = g.name || g;
            gHtml += `<span class="group-tag" onclick="event.stopPropagation(); openGroupModal('${escapeJs(gName)}')">👥 ${escapeHtml(gName)}</span> `;
        });
    } else {
        gHtml = '<span style="color:#64748b; font-style:italic;">Nincs rögzített csoporttagság.</span>';
    }
    safeSetHtml('m-groups', gHtml);

    const histBox = document.getElementById('m-history');
    if (histBox) {
        histBox.innerHTML = 'Előzmények keresése az audit naplóban...';
        fetch('/api/users/' + encodeURIComponent(u.sam) + '/history')
            .then(r => r.json())
            .then(data => {
                if (!data || data.length === 0) {
                    histBox.innerHTML = '<div style="padding:10px; color:#94a3b8; font-style:italic;">Nincs rögzített változás ennél a fióknál.</div>';
                    return;
                }
                let hHtml = '<table style="margin:0; width:100%; font-size:12px;"><tbody>';
                data.forEach(item => {
                    const sRef = item.source_ref ? `<code style="font-size:10px; background:#f1f5f9; padding:2px 4px; border-radius:3px; margin-left:6px;">${escapeHtml(item.source_ref)}</code>` : '';
                    let badgeBg = '#e2e8f0', badgeColor = '#334155';
                    if (item.change_type === 'ADDED_TO_GROUP') { badgeBg = '#dcfce7'; badgeColor = '#15803d'; }
                    else if (item.change_type === 'REMOVED_FROM_GROUP') { badgeBg = '#fee2e2'; badgeColor = '#b91c1c'; }
                    
                    hHtml += `<tr>
                        <td style="width:140px; color:#64748b;">${escapeHtml(item.timestamp)}</td>
                        <td><span style="background:${badgeBg}; color:${badgeColor}; padding:2px 6px; border-radius:4px; font-weight:bold; font-size:11px;">${escapeHtml(item.change_type)}</span>${sRef}</td>
                        <td>${escapeHtml(item.details)}</td>
                    </tr>`;
                });
                hHtml += '</tbody></table>';
                histBox.innerHTML = hHtml;
            })
            .catch(() => {
                histBox.innerHTML = '<div style="padding:10px; color:#94a3b8; font-style:italic;">Nem érhető el előzmény.</div>';
            });
    }

    const uModal = document.getElementById('userModal');
    if (uModal) uModal.style.display = 'block';
}

function openGroupModal(sam) {
    const g = allGroups.find(x => String(x.sam || '').trim().toLowerCase() === String(sam || '').trim().toLowerCase());
    if (!g) {
        alert(`Nem található csoport rekord ehhez a névhez: ${sam}`);
        return;
    }
    const uModal = document.getElementById('userModal');
    if (uModal) uModal.style.display = 'none';

    safeSetText('g-name', g.sam);
    safeSetText('g-type', g.type);
    safeSetText('g-desc', g.desc);
    safeSetText('g-sid', g.sid);
    safeSetText('g-created', g.created);
    safeSetText('g-count', (g.members ? g.members.length : 0) + ' fő');

    let mHtml = '';
    if (g.members && g.members.length > 0) {
        g.members.forEach(m => {
            mHtml += `<span class="user-tag" onclick="event.stopPropagation(); openUserModal('${escapeJs(m)}')">👤 ${escapeHtml(m)}</span> `;
        });
    } else {
        mHtml = '<span style="color:#64748b; font-style:italic;">A csoport üres.</span>';
    }
    safeSetHtml('g-members', mHtml);

    const gModal = document.getElementById('groupModal');
    if (gModal) gModal.style.display = 'block';
}

function closeAllModals() {
    ['userModal', 'groupModal', 'dayDetailModal'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = 'none';
    });
}

window.onclick = function(e) {
    ['userModal', 'groupModal', 'dayDetailModal'].forEach(id => {
        const el = document.getElementById(id);
        if (el && e.target === el) el.style.display = 'none';
    });
};

// --- AD VÁLTOZÁS ELEMZŐ FUNKCIÓK ---
async function loadAdAnalytics() {
    loadAiModels('adChangesModelSelect');
    try {
        const res = await fetch('/api/ad-analytics/summary');
        adAnalyticsData = await res.json();
        
        document.getElementById('card_val_24h').innerText = adAnalyticsData.summary_counts.c_24h + ' db';
        document.getElementById('card_val_72h').innerText = adAnalyticsData.summary_counts.c_72h + ' db';
        document.getElementById('card_val_168h').innerText = adAnalyticsData.summary_counts.c_168h + ' db';
        document.getElementById('card_val_30d').innerText = adAnalyticsData.summary_counts.c_30d + ' db';

        rawChartLabels = adAnalyticsData.chart_data.labels || [];
        rawChartTotal = adAnalyticsData.chart_data.total || [];
        rawChartAdded = adAnalyticsData.chart_data.added || [];
        rawChartRemoved = adAnalyticsData.chart_data.removed || [];
        rawChartLifecycle = adAnalyticsData.chart_data.lifecycle || [];

        if (rawChartLabels.length > 0) {
            document.getElementById('ad_chart_from').value = rawChartLabels[0];
            document.getElementById('ad_chart_to').value = rawChartLabels[rawChartLabels.length - 1];
        }

        renderAdChangesLineChart(rawChartLabels, rawChartTotal, rawChartAdded, rawChartRemoved, rawChartLifecycle);
        renderDailyBreakdownTable(adAnalyticsData.daily_breakdown);
        selectTimeWindow(activeWindowKey);
    } catch(e) {}
}

function renderAdChangesLineChart(labels, totalData, addedData, removedData, lifecycleData) {
    currentFilteredLabels = labels;
    updateChartKpiSummary(labels, totalData);

    if (chartAdChanges) chartAdChanges.destroy();
    const ctx = document.getElementById('chartAdDailyChanges')?.getContext('2d');
    if (!ctx) return;
    
    chartAdChanges = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                { label: '🔷 Összes Változás', data: totalData, borderColor: '#0284c7', backgroundColor: 'rgba(2, 132, 199, 0.08)', borderWidth: 3, pointRadius: 4, pointHoverRadius: 7, pointBackgroundColor: '#0284c7', tension: 0.25, fill: true },
                { label: '➕ Csoporttagság Hozzáadás', data: addedData, borderColor: '#16a34a', backgroundColor: 'transparent', borderWidth: 2, pointRadius: 4, pointHoverRadius: 7, pointBackgroundColor: '#16a34a', tension: 0.25 },
                { label: '➖ Csoporttagság Elvétel', data: removedData, borderColor: '#dc2626', backgroundColor: 'transparent', borderWidth: 2, pointRadius: 4, pointHoverRadius: 7, pointBackgroundColor: '#dc2626', tension: 0.25 },
                { label: '👤 Fiók / Státusz Változás', data: lifecycleData, borderColor: '#8b5cf6', backgroundColor: 'transparent', borderWidth: 1.5, borderDash: [4, 4], pointRadius: 3, pointHoverRadius: 6, pointBackgroundColor: '#8b5cf6', tension: 0.25 }
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            onClick: (evt, activeEls) => {
                if (activeEls && activeEls.length > 0) {
                    const idx = activeEls[0].index;
                    const selectedDate = currentFilteredLabels[idx];
                    if (selectedDate) openDayDetailModal(selectedDate, 'ALL');
                }
            },
            plugins: {
                tooltip: { mode: 'index', intersect: false, padding: 10 },
                zoom: { pan: { enabled: true, mode: 'x' }, zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'x' } }
            },
            scales: {
                x: { title: { display: true, text: 'Időtengely (Dátum)' }, grid: { color: '#f1f5f9' } },
                y: { beginAtZero: true, title: { display: true, text: 'Változások száma (db)' }, grid: { color: '#e2e8f0' } }
            }
        }
    });
}

function updateChartKpiSummary(labels, totals) {
    if (!labels || labels.length === 0) return;
    let maxVal = -1, maxIdx = -1, minVal = 999999, minIdx = -1, sum = 0;
    totals.forEach((v, idx) => {
        sum += v;
        if (v > maxVal) { maxVal = v; maxIdx = idx; }
        if (v < minVal) { minVal = v; minIdx = idx; }
    });
    const avg = (sum / totals.length).toFixed(1);
    const pEl = document.getElementById('ad_chart_peak'); if (pEl) pEl.innerText = `${labels[maxIdx]} (${maxVal} db)`;
    const mEl = document.getElementById('ad_chart_min'); if (mEl) mEl.innerText = `${labels[minIdx]} (${minVal} db)`;
    const aEl = document.getElementById('ad_chart_avg'); if (aEl) aEl.innerText = `${avg} db / nap`;
}

function resetAdChartZoom() { if (chartAdChanges) chartAdChanges.resetZoom(); }

function applyAdChartDateFilter() {
    const fVal = document.getElementById('ad_chart_from').value;
    const tVal = document.getElementById('ad_chart_to').value;
    if (!fVal || !tVal) return;
    const fIdx = rawChartLabels.findIndex(d => d >= fVal);
    let tIdx = -1;
    for (let i = rawChartLabels.length - 1; i >= 0; i--) {
        if (rawChartLabels[i] <= tVal) { tIdx = i; break; }
    }
    if (fIdx === -1 || tIdx === -1 || fIdx > tIdx) { alert('Nincs adat ebben az intervallumban.'); return; }
    renderAdChangesLineChart(rawChartLabels.slice(fIdx, tIdx + 1), rawChartTotal.slice(fIdx, tIdx + 1), rawChartAdded.slice(fIdx, tIdx + 1), rawChartRemoved.slice(fIdx, tIdx + 1), rawChartLifecycle.slice(fIdx, tIdx + 1));
}

function setAdChartRange(days) {
    if (rawChartLabels.length === 0) return;
    if (days === 'all') {
        document.getElementById('ad_chart_from').value = rawChartLabels[0];
        document.getElementById('ad_chart_to').value = rawChartLabels[rawChartLabels.length - 1];
        renderAdChangesLineChart(rawChartLabels, rawChartTotal, rawChartAdded, rawChartRemoved, rawChartLifecycle);
        return;
    }
    const count = Math.min(days, rawChartLabels.length);
    const startIdx = rawChartLabels.length - count;
    document.getElementById('ad_chart_from').value = rawChartLabels[startIdx];
    document.getElementById('ad_chart_to').value = rawChartLabels[rawChartLabels.length - 1];
    renderAdChangesLineChart(rawChartLabels.slice(startIdx), rawChartTotal.slice(startIdx), rawChartAdded.slice(startIdx), rawChartRemoved.slice(startIdx), rawChartLifecycle.slice(startIdx));
}

async function openDayDetailModal(dateStr, filterType = 'ALL') {
    activeDayDate = dateStr;
    activeDayFilterType = filterType;
    daySortCol = 'timestamp';
    daySortDir = 'desc';
    safeSetText('ddm_date', dateStr);
    resetDayModalFilterInputs();
    const dModal = document.getElementById('dayDetailModal');
    if (dModal) dModal.style.display = 'block';
    safeSetHtml('ddm_events_body', '<tr><td colspan="6" style="text-align:center; padding:15px; color:#64748b;">Betöltés...</td></tr>');
    
    try {
        const res = await fetch(`/api/ad-analytics/day-events?date=${encodeURIComponent(dateStr)}&type=ALL`);
        const data = await res.json();
        currentDayEvents = data.events || [];
        populateDayModalDropdowns(currentDayEvents);
        updateDayModalCounters();
        updateSortHeaders();
        filterDayModalEvents();
    } catch(err) {
        safeSetHtml('ddm_events_body', `<tr><td colspan="6" style="color:#dc2626; padding:15px;">Hiba: ${err}</td></tr>`);
    }
}

function populateDayModalDropdowns(events) {
    const selAction = document.getElementById('col_filter_action');
    if (selAction) {
        selAction.innerHTML = '<option value="">Mind (Művelet)</option>';
        Array.from(new Set(events.map(e => e.change_type).filter(Boolean))).sort().forEach(act => {
            let label = act;
            if (act === 'ADDED_TO_GROUP') label = '➕ Hozzáadás';
            else if (act === 'REMOVED_FROM_GROUP') label = '➖ Elvétel';
            else if (act === 'USER_DISABLED') label = '🚫 Letiltva';
            else if (act === 'USER_ENABLED') label = '✅ Aktiválva';
            else if (act === 'STATUS_CHANGED') label = '🔄 Besorolás';
            else if (act === 'USER_CREATED') label = '👤 Új fiók';
            selAction.innerHTML += `<option value="${act}">${label}</option>`;
        });
    }
    const selGroup = document.getElementById('col_filter_group');
    if (selGroup) {
        selGroup.innerHTML = '<option value="">Mind (Csoport)</option>';
        Array.from(new Set(events.map(e => e.group_name).filter(Boolean))).sort().forEach(grp => {
            selGroup.innerHTML += `<option value="${grp}">${grp}</option>`;
        });
    }
    const selSource = document.getElementById('col_filter_source');
    if (selSource) {
        selSource.innerHTML = '<option value="">Mind (Forrás)</option>';
        Array.from(new Set(events.map(e => e.source_ref).filter(Boolean))).sort().forEach(src => {
            selSource.innerHTML += `<option value="${src}">${src}</option>`;
        });
    }
}

function resetDayModalFilterInputs() {
    ['ddm_search', 'col_filter_time', 'col_filter_user', 'col_filter_action', 'col_filter_group', 'col_filter_details', 'col_filter_source'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
}

function resetDayModalFilters() {
    resetDayModalFilterInputs();
    activeDayFilterType = 'ALL';
    daySortCol = 'timestamp';
    daySortDir = 'desc';
    updateSortHeaders();
    filterDayModalEvents();
}

function sortDayModal(col) {
    if (daySortCol === col) daySortDir = daySortDir === 'asc' ? 'desc' : 'asc';
    else { daySortCol = col; daySortDir = 'asc'; }
    updateSortHeaders();
    filterDayModalEvents();
}

function updateSortHeaders() {
    ['timestamp', 'entity_name', 'change_type', 'group_name', 'details', 'source_ref'].forEach(c => {
        const el = document.getElementById('sort_icon_' + c);
        if (el) {
            if (daySortCol === c) { el.innerText = daySortDir === 'asc' ? ' ▲' : ' ▼'; el.style.color = '#0284c7'; }
            else { el.innerText = ' ↕'; el.style.color = '#94a3b8'; }
        }
    });
}

function updateDayModalCounters() {
    const total = currentDayEvents.length;
    const added = currentDayEvents.filter(e => e.change_type === 'ADDED_TO_GROUP').length;
    const removed = currentDayEvents.filter(e => e.change_type === 'REMOVED_FROM_GROUP').length;
    const lifecycle = total - added - removed;

    safeSetText('btn_ddm_all', `Mind (${total})`);
    safeSetText('btn_ddm_add', `➕ Csak Hozzáadások (+${added})`);
    safeSetText('btn_ddm_rem', `➖ Csak Elvételek (-${removed})`);
    safeSetText('btn_ddm_life', `👤 Fiók / Státusz (${lifecycle})`);
    safeSetText('ddm_total_title', `${total} db`);
}

function setDayModalFilterType(type) { activeDayFilterType = type; filterDayModalEvents(); }

function filterDayModalEvents() {
    ['ALL', 'ADDED', 'REMOVED', 'LIFECYCLE'].forEach(t => {
        const btn = document.getElementById('btn_ddm_' + (t === 'ALL' ? 'all' : (t === 'ADDED' ? 'add' : (t === 'REMOVED' ? 'rem' : 'life'))));
        if (btn) {
            btn.style.background = activeDayFilterType === t ? '#0284c7' : '#e2e8f0';
            btn.style.color = activeDayFilterType === t ? 'white' : '#334155';
        }
    });

    const searchVal = (document.getElementById('ddm_search')?.value || '').toLowerCase().trim();
    const fTime = (document.getElementById('col_filter_time')?.value || '').toLowerCase().trim();
    const fUser = (document.getElementById('col_filter_user')?.value || '').toLowerCase().trim();
    const fAction = (document.getElementById('col_filter_action')?.value || '').trim();
    const fGroup = (document.getElementById('col_filter_group')?.value || '').toLowerCase().trim();
    const fDetails = (document.getElementById('col_filter_details')?.value || '').toLowerCase().trim();
    const fSource = (document.getElementById('col_filter_source')?.value || '').trim();

    const tbody = document.getElementById('ddm_events_body');
    if (!tbody) return;
    tbody.innerHTML = '';

    let filtered = currentDayEvents;

    if (activeDayFilterType === 'ADDED') filtered = filtered.filter(e => e.change_type === 'ADDED_TO_GROUP');
    else if (activeDayFilterType === 'REMOVED') filtered = filtered.filter(e => e.change_type === 'REMOVED_FROM_GROUP');
    else if (activeDayFilterType === 'LIFECYCLE') filtered = filtered.filter(e => e.change_type !== 'ADDED_TO_GROUP' && e.change_type !== 'REMOVED_FROM_GROUP');

    if (searchVal) {
        filtered = filtered.filter(e => (e.entity_name && e.entity_name.toLowerCase().includes(searchVal)) || (e.group_name && e.group_name.toLowerCase().includes(searchVal)) || (e.details && e.details.toLowerCase().includes(searchVal)) || (e.source_ref && e.source_ref.toLowerCase().includes(searchVal)));
    }
    if (fTime) filtered = filtered.filter(e => e.timestamp && e.timestamp.toLowerCase().includes(fTime));
    if (fUser) filtered = filtered.filter(e => e.entity_name && e.entity_name.toLowerCase().includes(fUser));
    if (fAction) filtered = filtered.filter(e => e.change_type === fAction);
    if (fGroup) filtered = filtered.filter(e => e.group_name && e.group_name.toLowerCase() === fGroup);
    if (fDetails) filtered = filtered.filter(e => e.details && e.details.toLowerCase().includes(fDetails));
    if (fSource) filtered = filtered.filter(e => e.source_ref === fSource);

    filtered.sort((a, b) => {
        let vA = (a[daySortCol] || '').toString().toLowerCase();
        let vB = (b[daySortCol] || '').toString().toLowerCase();
        if (vA < vB) return daySortDir === 'asc' ? -1 : 1;
        if (vA > vB) return daySortDir === 'asc' ? 1 : -1;
        return 0;
    });

    safeSetText('ddm_visible_count', `${filtered.length} / ${currentDayEvents.length} esemény`);
    if (filtered.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:18px; color:#94a3b8;">Nincs találat a megadott szűrésre.</td></tr>';
        return;
    }

    filtered.forEach(e => {
        let badgeBg = '#2563eb', badgeColor = '#ffffff', actionLabel = e.change_type;
        if (e.change_type === 'ADDED_TO_GROUP') { badgeBg = '#dcfce7'; badgeColor = '#15803d'; actionLabel = '➕ Hozzáadva'; }
        else if (e.change_type === 'REMOVED_FROM_GROUP') { badgeBg = '#fee2e2'; badgeColor = '#b91c1c'; actionLabel = '➖ Eltávolítva'; }
        else if (e.change_type === 'USER_DISABLED') { badgeBg = '#fef2f2'; badgeColor = '#991b1b'; actionLabel = '🚫 Letiltva'; }
        else if (e.change_type === 'USER_ENABLED') { badgeBg = '#f0fdf4'; badgeColor = '#166534'; actionLabel = '✅ Aktiválva'; }
        else if (e.change_type === 'STATUS_CHANGED') { badgeBg = '#fef3c7'; badgeColor = '#b45309'; actionLabel = '🔄 Besorolás'; }
        else if (e.change_type === 'USER_CREATED') { badgeBg = '#e0f2fe'; badgeColor = '#0369a1'; actionLabel = '👤 Létrehozva'; }

        const grpBadge = e.group_name ? `<span class="group-tag" onclick="event.stopPropagation(); closeAllModals(); openGroupModal('${escapeJs(e.group_name)}')">👥 ${escapeHtml(e.group_name)}</span>` : '-';
        const userBadge = `<span class="user-tag" onclick="event.stopPropagation(); closeAllModals(); openUserModal('${escapeJs(e.entity_name)}')">👤 ${escapeHtml(e.entity_name)}</span>`;
        const srcBadge = `<code style="background:#f1f5f9; padding:2px 5px; border-radius:4px; font-size:11px;">${escapeHtml(e.source_ref)}</code>`;

        tbody.innerHTML += `<tr>
            <td style="white-space:nowrap; color:#64748b;">${escapeHtml(e.timestamp)}</td>
            <td>${userBadge}</td>
            <td><span style="background:${badgeBg}; color:${badgeColor}; padding:3px 8px; border-radius:10px; font-weight:bold; font-size:11px;">${actionLabel}</span></td>
            <td>${grpBadge}</td>
            <td>${escapeHtml(e.details)}</td>
            <td>${srcBadge}</td>
        </tr>`;
    });
}

function renderDailyBreakdownTable(dailyList) {
    const tbody = document.getElementById('dailyBreakdownBody');
    if (!tbody) return;
    tbody.innerHTML = '';
    if (!dailyList || dailyList.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:#94a3b8; padding:15px;">Nincs elérhető adat.</td></tr>';
        return;
    }
    dailyList.forEach(d => {
        let uTags = d.affected_users.slice(0, 4).map(u => `<span class="user-tag" onclick="openUserModal('${escapeJs(u)}')">👤 ${escapeHtml(u)}</span>`).join(' ');
        if (d.affected_users.length > 4) uTags += ` <small style="color:#64748b;">+${d.affected_users.length - 4} fő</small>`;
        let gTags = d.affected_groups.slice(0, 3).map(g => `<span class="group-tag" onclick="openGroupModal('${escapeJs(g)}')">👥 ${escapeHtml(g)}</span>`).join(' ');
        if (d.affected_groups.length > 3) gTags += ` <small style="color:#64748b;">+${d.affected_groups.length - 3} db</small>`;

        tbody.innerHTML += `<tr>
            <td><b>${escapeHtml(d.date)}</b></td>
            <td><span class="click-num click-num-total" onclick="openDayDetailModal('${escapeJs(d.date)}', 'ALL')">${d.total} db</span></td>
            <td><span class="click-num click-num-add" onclick="openDayDetailModal('${escapeJs(d.date)}', 'ADDED')">+${d.added_to_group}</span></td>
            <td><span class="click-num click-num-rem" onclick="openDayDetailModal('${escapeJs(d.date)}', 'REMOVED')">-${d.removed_from_group}</span></td>
            <td><span class="click-num click-num-life" onclick="openDayDetailModal('${escapeJs(d.date)}', 'LIFECYCLE')">${d.user_lifecycle}</span></td>
            <td>${uTags || '<span style="color:#94a3b8;">-</span>'}</td>
            <td>${gTags || '<span style="color:#94a3b8;">-</span>'}</td>
        </tr>`;
    });
}

function selectTimeWindow(winKey) {
    activeWindowKey = winKey;
    document.querySelectorAll('.window-card').forEach(c => c.classList.remove('active'));
    const cardEl = document.getElementById('card_' + winKey);
    if (cardEl) cardEl.classList.add('active');

    const tbody = document.getElementById('timeWindowEventsBody');
    if (!tbody || !adAnalyticsData) return;
    tbody.innerHTML = '';
    const events = adAnalyticsData.windows[winKey] || [];
    if (events.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:#94a3b8; padding:15px;">Nincs esemény ebben az ablakban.</td></tr>';
        return;
    }
    events.forEach(e => {
        let badgeBg = '#2563eb', badgeColor = '#ffffff', actionLabel = e.change_type;
        if (e.change_type === 'ADDED_TO_GROUP') { badgeBg = '#dcfce7'; badgeColor = '#15803d'; actionLabel = '➕ Hozzáadva'; }
        else if (e.change_type === 'REMOVED_FROM_GROUP') { badgeBg = '#fee2e2'; badgeColor = '#b91c1c'; actionLabel = '➖ Eltávolítva'; }
        else if (e.change_type === 'USER_DISABLED') { badgeBg = '#fef2f2'; badgeColor = '#991b1b'; actionLabel = '🚫 Letiltva'; }
        else if (e.change_type === 'USER_ENABLED') { badgeBg = '#f0fdf4'; badgeColor = '#166534'; actionLabel = '✅ Aktiválva'; }
        else if (e.change_type === 'STATUS_CHANGED') { badgeBg = '#fef3c7'; badgeColor = '#b45309'; actionLabel = '🔄 Besorolás'; }
        else if (e.change_type === 'USER_CREATED') { badgeBg = '#e0f2fe'; badgeColor = '#0369a1'; actionLabel = '👤 Létrehozva'; }

        const grpBadge = e.group_name ? `<span class="group-tag" onclick="openGroupModal('${escapeJs(e.group_name)}')">👥 ${escapeHtml(e.group_name)}</span>` : '-';
        const srcBadge = `<code style="background:#f1f5f9; padding:2px 5px; border-radius:4px; font-size:11px;">${escapeHtml(e.source_ref)}</code>`;

        tbody.innerHTML += `<tr>
            <td style="white-space:nowrap; color:#64748b;">${escapeHtml(e.timestamp)}</td>
            <td><b style="color:#0f172a; cursor:pointer; text-decoration:underline;" onclick="openUserModal('${escapeJs(e.entity_name)}')">👤 ${escapeHtml(e.entity_name)}</b></td>
            <td><span style="background:${badgeBg}; color:${badgeColor}; padding:3px 8px; border-radius:10px; font-weight:bold; font-size:11px;">${actionLabel}</span></td>
            <td>${grpBadge}</td>
            <td>${escapeHtml(e.details)}</td>
            <td>${srcBadge}</td>
        </tr>`;
    });
}

function setAdPrompt(txt) { document.getElementById('adChangesUserPrompt').value = txt; }

async function sendAdChangesAiQuestion() {
    const model = document.getElementById('adChangesModelSelect').value;
    const promptBox = document.getElementById('adChangesUserPrompt');
    const txt = promptBox.value.trim();
    if (!model || !txt) return;

    const chatBox = document.getElementById('adChangesChatBox');
    chatBox.innerHTML += `<div style="align-self:flex-end; background:#0284c7; color:white; padding:8px 12px; border-radius:8px; margin:4px 0; max-width:80%; font-size:13px;">${escapeHtml(txt)}</div>`;
    promptBox.value = '';

    const aiDiv = document.createElement('div');
    aiDiv.style = 'align-self:flex-start; background:#f1f5f9; padding:8px 12px; border-radius:8px; margin:4px 0; max-width:80%; font-size:13px;';
    aiDiv.innerText = '🔍 Elemzés folyamatban...';
    chatBox.appendChild(aiDiv);
    chatBox.scrollTop = chatBox.scrollHeight;

    try {
        const res = await fetch('/api/ad-analytics/ask', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ model: model, prompt: txt })
        });
        const d = await res.json();
        aiDiv.innerText = d.status === 'SUCCESS' ? d.response : ('Hiba: ' + d.message);
    } catch(err) { aiDiv.innerText = 'Hiba: ' + err; }
}

// --- TELEMETRIA ÉS MUNKAMENETEK ---
async function loadSessionsData() {
    try {
        const res = await fetch('/api/telemetry/sessions');
        const d = await res.json();
        if (d.current_session) {
            const c = d.current_session;
            safeSetText('cur_sess_user', c.username);
            safeSetText('cur_sess_login', `${c.login_time} (${c.active_duration})`);
            safeSetText('cur_sess_ip', `${c.client_ip} — ${c.location}`);
            safeSetText('cur_sess_device', `${c.device_type} | ${c.browser} | ${c.os_name}`);
        }
        const tbody = document.getElementById('otherSessionsBody');
        if (tbody) {
            tbody.innerHTML = '';
            const others = d.other_sessions || [];
            if (others.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:#94a3b8; padding:12px;">Nincs más aktív belépő.</td></tr>';
            } else {
                others.forEach(o => {
                    tbody.innerHTML += `<tr>
                        <td><b style="color:#0284c7;">${escapeHtml(o.username)}</b></td>
                        <td><code>${escapeHtml(o.client_ip)}</code><br/><small style="color:#64748b;">${escapeHtml(o.location)}</small></td>
                        <td>${escapeHtml(o.browser)} (${escapeHtml(o.os_name)})</td>
                        <td>${escapeHtml(o.login_time)}<br/><small style="color:#64748b;">${escapeHtml(o.active_duration)}</small></td>
                        <td><span style="background:#dcfce7; color:#15803d; padding:2px 8px; border-radius:10px; font-weight:bold; font-size:11px;">🟢 ${escapeHtml(o.last_activity)}</span></td>
                    </tr>`;
                });
            }
        }
    } catch(e) {}
}

async function loadTelemetryLive() {
    try {
        const res = await fetch('/api/telemetry/live');
        const d = await res.json();
        safeSetText('tel_host_ip', d.host.current_ip);
        safeSetText('tel_host_sub', `${d.host.hostname} | ${d.host.uptime}`);

        safeSetText('tel_cpu_pct', `${d.cpu.percent} %`);
        safeSetText('tel_cpu_sub', `${d.cpu.temp_c ? '🌡️ ' + d.cpu.temp_c + ' °C | ' : ''}${d.cpu.cores} mag`);
        const cpuBar = document.getElementById('tel_cpu_bar');
        if (cpuBar) {
            cpuBar.style.width = Math.min(100, d.cpu.percent) + '%';
            cpuBar.style.backgroundColor = d.cpu.percent > 85 ? '#dc2626' : (d.cpu.percent > 60 ? '#f59e0b' : '#0284c7');
        }

        safeSetText('tel_ram_val', `${(d.ram.used_mb / 1024).toFixed(2)} GB`);
        safeSetText('tel_ram_sub', `${d.ram.percent}% (${(d.ram.total_mb / 1024).toFixed(1)} GB)`);
        const ramBar = document.getElementById('tel_ram_bar');
        if (ramBar) ramBar.style.width = Math.min(100, d.ram.percent) + '%';

        safeSetText('tel_disk_val', `${d.disk.free_gb} GB szabad`);
        safeSetText('tel_disk_sub', `Használt: ${d.disk.used_gb} GB | DB: ${d.db.size_mb} MB`);
        const diskBar = document.getElementById('tel_disk_bar');
        if (diskBar) diskBar.style.width = Math.min(100, d.disk.percent) + '%';

        if (d.gpu && d.gpu.detected) {
            safeSetText('tel_gpu_val', `${d.gpu.util_pct} %`);
            let gpuSub = d.gpu.name;
            if (d.gpu.temp_c) gpuSub += ' | 🌡️ ' + d.gpu.temp_c + ' °C';
            if (d.gpu.power_w) gpuSub += ' | ⚡ ' + d.gpu.power_w + ' W';
            if (d.gpu.mem_used_mb) gpuSub += ' | VRAM: ' + Math.round(d.gpu.mem_used_mb) + ' / ' + Math.round(d.gpu.mem_total_mb) + ' MB';
            safeSetText('tel_gpu_sub', gpuSub);
            const gpuBar = document.getElementById('tel_gpu_bar');
            if (gpuBar) {
                gpuBar.style.width = Math.min(100, d.gpu.util_pct) + '%';
                gpuBar.style.backgroundColor = '#10b981';
            }
        } else {
            safeSetText('tel_gpu_val', 'Nem észlelve');
            safeSetText('tel_gpu_sub', 'NVIDIA GPU nem érhető el');
            const gpuBar = document.getElementById('tel_gpu_bar');
            if (gpuBar) gpuBar.style.width = '0%';
        }
        safeSetText('tel_llm_val', `${(d.llm.total_tokens || 0).toLocaleString()} db`);
        safeSetText('tel_llm_sub', `Prompt: ${(d.llm.prompt_tokens || 0).toLocaleString()} | Válasz: ${(d.llm.eval_tokens || 0).toLocaleString()}`);
    } catch(e) {}
}

async function triggerTelemetryCollect() {
    const btn = document.getElementById('collectTelBtn');
    if (btn) { btn.disabled = true; btn.innerText = 'Rögzítés...'; }
    try {
        await fetch('/api/telemetry/collect', { method: 'POST' });
        await loadSessionsData();
        await loadTelemetryLive();
        await loadTelemetryHistory();
        await loadWebAccessLogs();
        await loadHostIpHistory();
    } catch(e) { alert('Hiba: ' + e); }
    finally { if (btn) { btn.disabled = false; btn.innerText = '⚡ Azonnali Mérés Rögzítése'; } }
}

async function loadTelemetryHistory() {
    try {
        const res = await fetch('/api/telemetry/history');
        const data = await res.json();
        const list = data.history || [];
        renderCharts(
            list.map(x => x.timestamp),
            list.map(x => x.cpu_percent),
            list.map(x => x.cpu_temp_c),
            list.map(x => x.ram_used_mb),
            list.map(x => x.gpu_util_percent),
            list.map(x => x.disk_free_gb),
            list.map(x => x.db_size_mb),
            list.map(x => x.llm_tokens_total)
        );
        renderTelemetryTable(list);
    } catch(e) {}
}

function renderCharts(labels, cpuData, cpuTemp, ramData, gpuData, diskFree, dbSize, llmTokens) {
    if (chartCpu) chartCpu.destroy();
    const ctxCpu = document.getElementById('chartCpuGpu')?.getContext('2d');
    if (ctxCpu) {
        chartCpu = new Chart(ctxCpu, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    { label: 'CPU Terhelés (%)', data: cpuData, borderColor: '#0284c7', backgroundColor: 'rgba(2, 132, 199, 0.1)', tension: 0.3, fill: true },
                    { label: 'GPU Terhelés (%)', data: gpuData, borderColor: '#10b981', borderDash: [4, 4], tension: 0.3 },
                    { label: 'CPU Hőfok (°C)', data: cpuTemp, borderColor: '#ef4444', yAxisID: 'yTemp', tension: 0.3 }
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                scales: {
                    y: { min: 0, max: 100, title: { display: true, text: 'Kihasználtság (%)' } },
                    yTemp: { position: 'right', min: 20, max: 100, grid: { drawOnChartArea: false }, title: { display: true, text: 'Hőfok (°C)' } }
                }
            }
        });
    }

    if (chartRam) chartRam.destroy();
    const ctxRam = document.getElementById('chartMemory')?.getContext('2d');
    if (ctxRam) {
        chartRam = new Chart(ctxRam, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{ label: 'RAM Használat (MB)', data: ramData, borderColor: '#8b5cf6', backgroundColor: 'rgba(139, 92, 246, 0.1)', tension: 0.3, fill: true }]
            },
            options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true, title: { display: true, text: 'MB' } } } }
        });
    }

    if (chartStorage) chartStorage.destroy();
    const ctxStorage = document.getElementById('chartStorage')?.getContext('2d');
    if (ctxStorage) {
        chartStorage = new Chart(ctxStorage, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    { label: 'Szabad Lemez (GB)', data: diskFree, borderColor: '#059669', yAxisID: 'yDisk', tension: 0.3 },
                    { label: 'PostgreSQL DB (MB)', data: dbSize, borderColor: '#d97706', yAxisID: 'yDb', tension: 0.3 }
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                scales: {
                    yDisk: { position: 'left', title: { display: true, text: 'Lemez (GB)' } },
                    yDb: { position: 'right', grid: { drawOnChartArea: false }, title: { display: true, text: 'Adatbázis (MB)' } }
                }
            }
        });
    }

    if (chartLlm) chartLlm.destroy();
    const ctxLlm = document.getElementById('chartLlm')?.getContext('2d');
    if (ctxLlm) {
        chartLlm = new Chart(ctxLlm, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{ label: 'Összesített Tokenek', data: llmTokens, borderColor: '#f59e0b', backgroundColor: 'rgba(245, 158, 11, 0.1)', tension: 0.3, fill: true }]
            },
            options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true, title: { display: true, text: 'Tokenek' } } } }
        });
    }
}

function renderTelemetryTable(list) {
    const tbody = document.getElementById('telemetryTableBody');
    if (!tbody) return;
    tbody.innerHTML = '';
    if (!list || list.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:#94a3b8; padding:15px;">Még nincs rögzített adat.</td></tr>';
        return;
    }
    [...list].reverse().slice(0, 30).forEach(r => {
        tbody.innerHTML += `<tr>
            <td><b>${escapeHtml(r.timestamp)}</b></td>
            <td>${r.cpu_percent} % ${r.cpu_temp_c ? ` (${r.cpu_temp_c} °C)` : ''}</td>
            <td>${Math.round(r.ram_used_mb)} MB (${r.ram_percent}%)</td>
            <td>${r.disk_free_gb} GB</td>
            <td><b>${r.db_size_mb} MB</b></td>
            <td>${r.gpu_name !== 'N/A' ? `${r.gpu_util_percent}% | ${Math.round(r.gpu_mem_used_mb)}MB` : '-'}</td>
            <td>${(r.llm_tokens_total || 0).toLocaleString()} db</td>
        </tr>`;
    });
}

async function loadWebAccessLogs() {
    const tbody = document.getElementById('webAccessLogBody');
    if (!tbody) return;
    try {
        const res = await fetch('/api/telemetry/web-logs');
        const data = await res.json();
        tbody.innerHTML = '';
        const logs = data.logs || [];
        if (logs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:#94a3b8; padding:15px;">Még nincs rögzített webes tevékenység.</td></tr>';
            return;
        }
        logs.forEach(l => {
            const stColor = l.status === 'SIKERES' ? '#16a34a' : '#dc2626';
            const stBg = l.status === 'SIKERES' ? '#dcfce7' : '#fee2e2';

            let devIcon = '💻';
            if (l.device_type === 'Mobiltelefon') devIcon = '📱';
            else if (l.device_type && l.device_type.includes('Tablet')) devIcon = '📟';

            const clientInfo = `<span style="background:#f1f5f9; color:#334155; padding:2px 6px; border-radius:4px; font-weight:600; font-size:11px;">${devIcon} ${escapeHtml(l.browser)}</span> <span style="background:#e0f2fe; color:#0369a1; padding:2px 6px; border-radius:4px; font-size:11px;">${escapeHtml(l.os_name)}</span>`;
            const ipInfo = `<code style="background:#f8fafc; border:1px solid #e2e8f0; padding:2px 5px; border-radius:4px; font-weight:bold;">${escapeHtml(l.client_ip)}</code><br/><small style="color:#64748b;">📍 ${escapeHtml(l.location)}</small>`;

            tbody.innerHTML += `<tr>
                <td style="white-space:nowrap; color:#64748b;">${escapeHtml(l.timestamp)}</td>
                <td><b>${escapeHtml(l.username)}</b></td>
                <td>${ipInfo}</td>
                <td>${clientInfo}</td>
                <td><b>${escapeHtml(l.action)}</b></td>
                <td>${escapeHtml(l.details)}</td>
                <td><span style="background:${stBg}; color:${stColor}; padding:3px 8px; border-radius:10px; font-weight:bold; font-size:11px;">${escapeHtml(l.status)}</span></td>
            </tr>`;
        });
    } catch(e) {}
}

async function loadHostIpHistory() {
    const tbody = document.getElementById('hostIpHistoryBody');
    if (!tbody) return;
    try {
        const res = await fetch('/api/telemetry/host-ip-history');
        const data = await res.json();
        tbody.innerHTML = '';
        const history = data.history || [];
        if (history.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; color:#94a3b8; padding:15px;">Még nincs rögzített IP változás.</td></tr>';
            return;
        }
        history.forEach(h => {
            tbody.innerHTML += `<tr><td>${escapeHtml(h.timestamp)}</td><td><code style="font-weight:bold; color:#0369a1;">${escapeHtml(h.ip_address)}</code></td><td>${escapeHtml(h.hostname)}</td><td>${escapeHtml(h.details)}</td></tr>`;
        });
    } catch(e) {}
}

// --- MENTÉSEK KEZELÉSE ---
async function loadBackups() {
    const tbody = document.getElementById('backupsTableBody');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="7">Mentések keresése...</td></tr>';
    try {
        const res = await fetch('/api/backups');
        const data = await res.json();
        tbody.innerHTML = '';
        if (!data.backups || data.backups.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:#94a3b8; padding:20px;">Még nem készült biztonsági mentés.</td></tr>';
            return;
        }
        data.backups.forEach(b => {
            tbody.innerHTML += `<tr>
                <td><b>${escapeHtml(b.created_at)}</b></td>
                <td><span style="background:#e0f2fe; color:#0369a1; padding:3px 8px; border-radius:4px; font-weight:bold;">${escapeHtml(b.version)}</span></td>
                <td><code style="font-size:12px;">${escapeHtml(b.filename)}</code></td>
                <td>${escapeHtml(b.size)}</td>
                <td>${escapeHtml(b.comment)}</td>
                <td><small style="color:#64748b;">${escapeHtml(b.author)}</small></td>
                <td style="white-space:nowrap; text-align:right;">
                    <button class="btn-restore" onclick="restoreBackup('${escapeJs(b.filename)}')">Visszaállítás</button>
                    <a class="btn-download" href="/api/backups/download/${encodeURIComponent(b.filename)}">Letöltés</a>
                    <button class="btn-delete" onclick="deleteBackup('${escapeJs(b.filename)}')">Törlés</button>
                </td>
            </tr>`;
        });
    } catch(e) { tbody.innerHTML = `<tr><td colspan="7" style="color:#dc2626;">Hiba: ${e}</td></tr>`; }
}

async function createNewBackup() {
    const btn = document.getElementById('createBackupBtn');
    const commentInput = document.getElementById('backup_comment');
    if (btn) { btn.disabled = true; btn.innerText = 'Mentés készítése...'; }
    try {
        const res = await fetch('/api/backups/create', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ comment: commentInput.value.trim() })
        });
        const d = await res.json();
        if(d.status === 'SUCCESS') {
            alert('✅ Teljes mentés elkészült!' + NL + 'Fájl: ' + d.filename);
            commentInput.value = '';
            loadBackups();
        } else alert('Hiba: ' + d.message);
    } catch(e) { alert(e); }
    finally { if (btn) { btn.disabled = false; btn.innerText = 'Teljes Mentés Készítése'; } }
}

async function restoreBackup(filename) {
    if (!confirm('⚠️ FIGYELEM! A visszaállítás felülírja a jelenlegi adatbázist a mentett állapotra!' + NL + NL + 'Biztosan folytatja a(z) ' + filename + ' visszaállítását?')) return;
    try {
        const res = await fetch('/api/backups/restore', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ filename: filename })
        });
        const data = await res.json();
        if (data.status === 'SUCCESS') {
            alert('✅ ' + data.message + NL + 'Az oldal most újratöltődik.');
            window.location.reload();
        } else alert('❌ Hiba a visszaállításkor: ' + data.message);
    } catch(e) { alert('Hálózati hiba: ' + e); }
}

async function deleteBackup(filename) {
    if (!confirm('Biztosan törölni szeretné ezt a mentést: ' + filename + '?')) return;
    try {
        const res = await fetch('/api/backups/' + encodeURIComponent(filename), { method: 'DELETE' });
        const data = await res.json();
        if (data.status === 'SUCCESS') loadBackups();
        else alert('Hiba a törlésnél: ' + data.message);
    } catch(e) { alert('Hálózati hiba: ' + e); }
}

// --- AI MODELLEK, VRAM ÉS FRISSÍTÉSEK ---
async function loadAiModels(elementId) {
    const select = document.getElementById(elementId);
    if (!select) return;
    try {
        const res = await fetch('/api/ai/models');
        const data = await res.json();
        currentAiModelsData = data;
        const modelsList = data.models || [];
        const activeModel = data.active_loaded_model || (data.running_models && data.running_models[0]) || '';
        
        select.innerHTML = '';
        
        const devGroup = document.createElement('optgroup');
        devGroup.label = '🛠️ Fejlesztői funkció (Teljes Kódbázis & Séma)';
        
        const genGroup = document.createElement('optgroup');
        genGroup.label = '🤖 Általános Rendszer Asszisztensek';
        
        modelsList.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m.name;
            const isLoaded = (m.name === activeModel);
            const activeMark = isLoaded ? ' [🟢 VRAM-ban]' : '';
            const sizeStr = m.size_gb ? ` (${m.size_gb} GB)` : '';
            opt.innerText = m.name + sizeStr + (m.is_developer ? ' [Fejlesztői]' : '') + activeMark;
            if (m.is_developer) devGroup.appendChild(opt);
            else genGroup.appendChild(opt);
        });
        
        if (devGroup.children.length > 0) select.appendChild(devGroup);
        if (genGroup.children.length > 0) select.appendChild(genGroup);
        
        if (activeModel && Array.from(select.options).some(o => o.value === activeModel)) {
            select.value = activeModel;
        }
        
        updateVramStatusBadge(activeModel);
        onAiModelChanged();
        renderInstalledModelsTable();
    } catch(e) {}
}

function updateVramStatusBadge(activeModel) {
    const badge = document.getElementById('vramStatusBadge');
    if (!badge) return;
    if (activeModel) {
        badge.innerHTML = `🟢 Betöltve a VRAM-ban (1/1): <b>${escapeHtml(activeModel)}</b>`;
        badge.style.background = '#dcfce7';
        badge.style.color = '#15803d';
    } else {
        badge.innerHTML = `⚪ Nincs modell betöltve a VRAM-ban`;
        badge.style.background = '#f1f5f9';
        badge.style.color = '#64748b';
    }
}

function onAiModelChanged() {
    const select = document.getElementById('modelSelect');
    if (!select) return;
    const model = select.value.toLowerCase();
    const isDev = model.includes('coder') || model.includes('code') || model.includes('dev') || model.includes('qwen') || model.includes('deepseek');
    
    const notice = document.getElementById('devModeNotice');
    if (notice) notice.style.display = isDev ? 'block' : 'none';
    
    const devPrompts = document.getElementById('devPromptButtons');
    if (devPrompts) devPrompts.style.display = isDev ? 'flex' : 'none';
    
    const genPrompts = document.getElementById('genPromptButtons');
    if (genPrompts) genPrompts.style.display = isDev ? 'none' : 'flex';
}

async function triggerModelSwitch() {
    const select = document.getElementById('modelSelect');
    if (!select || !select.value) return;
    const model = select.value;
    const badge = document.getElementById('vramStatusBadge');
    if (badge) badge.innerText = '⏳ Modell váltása és VRAM ürítése...';
    
    try {
        const res = await fetch('/api/ai/switch-model', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ model: model })
        });
        const data = await res.json();
        if (data.status === 'SUCCESS' || data.active_model) {
            updateVramStatusBadge(model);
            alert(`✅ ${model} sikeresen betöltve a memóriába! Minden más modell kisöpörve a VRAM-ból.`);
            loadAiModels('modelSelect');
        } else {
            alert('Hiba a váltáskor: ' + (data.error || 'Ismeretlen hiba'));
        }
    } catch(err) {
        alert('Hálózati hiba: ' + err);
    }
}

async function triggerModelPull() {
    const input = document.getElementById('pullModelInput');
    if (!input || !input.value.trim()) {
        alert('Kérjük, adja meg a letöltendő modell nevét (pl. llama3:8b)!');
        return;
    }
    const modelName = input.value.trim();
    if (!confirm(`Elindítja a(z) ${modelName} letöltését a háttérben futó Ollamába?`)) return;
    
    try {
        const res = await fetch('/api/ai/update-model', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ model: modelName })
        });
        const data = await res.json();
        alert(data.message || 'Letöltés elindítva!');
        input.value = '';
        startPollingModelTasks();
    } catch(err) {
        alert('Hiba a letöltés indításakor: ' + err);
    }
}

async function checkAllModelUpdates() {
    const btn = document.getElementById('checkUpdatesBtn');
    if (btn) { btn.disabled = true; btn.innerText = '🔍 Ellenőrzés a registry-ben...'; }
    
    try {
        const res = await fetch('/api/ai/check-updates');
        const data = await res.json();
        (data.updates || []).forEach(u => {
            modelUpdatesData[u.name] = u;
        });
        renderInstalledModelsTable();
    } catch(err) {
        alert('Nem sikerült ellenőrizni a frissítéseket: ' + err);
    } finally {
        if (btn) { btn.disabled = false; btn.innerText = '🔍 Frissítések Keresése Most'; }
    }
}

function renderInstalledModelsTable() {
    const tbody = document.getElementById('installedModelsTableBody');
    if (!tbody || !currentAiModelsData) return;
    tbody.innerHTML = '';
    
    const modelsList = currentAiModelsData.models || [];
    const activeModel = currentAiModelsData.active_loaded_model || '';

    if (modelsList.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:15px; color:#94a3b8;">Nincs telepített modell az Ollamában.</td></tr>';
        return;
    }

    modelsList.forEach(m => {
        const isLoaded = (m.name === activeModel);
        const vramBadge = isLoaded 
            ? '<span style="background:#dcfce7; color:#15803d; font-weight:bold; padding:2px 8px; border-radius:10px; font-size:11px;">🟢 Betöltve</span>'
            : '<span style="background:#f1f5f9; color:#64748b; padding:2px 8px; border-radius:10px; font-size:11px;">⚪ Inaktív</span>';

        const typeBadge = m.is_developer
            ? '<span style="background:#e0f2fe; color:#0369a1; font-weight:bold; padding:2px 8px; border-radius:6px; font-size:11px;">🛠️ Fejlesztői</span>'
            : '<span style="background:#f1f5f9; color:#475569; padding:2px 6px; border-radius:6px; font-size:11px;">🤖 Általános</span>';

        const uInfo = modelUpdatesData[m.name];
        let statusBadge = '<span style="color:#94a3b8; font-size:11.5px;">⚪ Nincs ellenőrizve</span>';
        let updateBtnDisabled = false;

        if (m.update_task && m.update_task.status === 'RUNNING') {
            statusBadge = '<span style="background:#fef3c7; color:#b45309; padding:2px 8px; border-radius:10px; font-size:11px; font-weight:bold;">⏳ Frissítés folyamatban...</span>';
            updateBtnDisabled = true;
        } else if (uInfo) {
            if (uInfo.status === 'UP_TO_DATE') {
                statusBadge = '<span style="background:#dcfce7; color:#15803d; padding:2px 8px; border-radius:10px; font-size:11px; font-weight:bold;">🟢 Naprakész</span>';
            } else if (uInfo.status === 'UPDATE_AVAILABLE') {
                statusBadge = '<span style="background:#fef3c7; color:#b45309; padding:2px 8px; border-radius:10px; font-size:11px; font-weight:bold;">🟡 Új verzió érhető el!</span>';
            } else {
                statusBadge = '<span style="background:#f1f5f9; color:#64748b; padding:2px 8px; border-radius:10px; font-size:11px;">⚪ Ismeretlen</span>';
            }
        }

        tbody.innerHTML += `<tr>
            <td><b>${escapeHtml(m.name)}</b></td>
            <td>${m.size_gb ? m.size_gb + ' GB' : '-'}</td>
            <td>${typeBadge}</td>
            <td>${vramBadge}</td>
            <td>${statusBadge}</td>
            <td style="white-space:nowrap; text-align:right;">
                <button class="btn" style="padding:4px 8px; font-size:11px; background:#16a34a; margin-right:4px;" ${updateBtnDisabled ? 'disabled' : ''} onclick="triggerSingleModelUpdate('${escapeJs(m.name)}')">🔄 Frissítés</button>
                <button class="btn" style="padding:4px 8px; font-size:11px; background:#0284c7;" onclick="switchSpecificModel('${escapeJs(m.name)}')">⚡ VRAM-ba</button>
            </td>
        </tr>`;
    });
}

async function switchSpecificModel(modelName) {
    const select = document.getElementById('modelSelect');
    if (select) select.value = modelName;
    await triggerModelSwitch();
}

async function triggerSingleModelUpdate(modelName) {
    if (!confirm(`Biztosan frissíteni szeretné a(z) ${modelName} modellt a legfrissebb távoli változatra?`)) return;
    
    try {
        const res = await fetch('/api/ai/update-model', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ model: modelName })
        });
        const data = await res.json();
        alert(data.message || 'Frissítés elindítva!');
        startPollingModelTasks();
    } catch(err) {
        alert('Hiba a frissítés indításakor: ' + err);
    }
}

function startPollingModelTasks() {
    if (updatePollTimer) clearInterval(updatePollTimer);
    updatePollTimer = setInterval(async () => {
        try {
            const res = await fetch('/api/ai/update-tasks');
            const data = await res.json();
            const tasks = data.tasks || {};
            let isAnyRunning = false;
            
            for (let name in tasks) {
                if (tasks[name].status === 'RUNNING') isAnyRunning = true;
            }
            
            await loadAiModels('modelSelect');
            
            if (!isAnyRunning) {
                clearInterval(updatePollTimer);
                updatePollTimer = null;
            }
        } catch(e) {}
    }, 4000);
}

function setPrompt(txt) { document.getElementById('userPrompt').value = txt; }

async function sendAiQuestion() {
    const model = document.getElementById('modelSelect').value;
    const promptBox = document.getElementById('userPrompt');
    const txt = promptBox.value.trim();
    if (!model || !txt) return;

    const chatBox = document.getElementById('chatBox');
    chatBox.innerHTML += `<div style="align-self:flex-end; background:#0284c7; color:white; padding:8px 12px; border-radius:8px; margin:4px 0; max-width:80%; font-size:13px;">${escapeHtml(txt)}</div>`;
    promptBox.value = '';

    const aiDiv = document.createElement('div');
    aiDiv.style = 'align-self:flex-start; background:#f1f5f9; padding:8px 12px; border-radius:8px; margin:4px 0; max-width:80%; font-size:13px;';
    aiDiv.innerText = '🔍 Helyi adatbázis és kontextus elemzése...';
    chatBox.appendChild(aiDiv);
    chatBox.scrollTop = chatBox.scrollHeight;

    try {
        const res = await fetch('/api/ai/ask', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ model: model, prompt: txt })
        });
        const d = await res.json();
        aiDiv.innerText = d.status === 'SUCCESS' ? d.response : ('Hiba: ' + d.message);
    } catch(err) { aiDiv.innerText = 'Hiba: ' + err; }
}

// --- TÖRTÉNETI CSV ÉS GITHUB SEGÉDFÜGGVÉNYEK ---
function triggerClientFolderPicker() { document.getElementById('client_folder_picker').click(); }

function handleClientFolderSelect(input) {
    const files = Array.from(input.files);
    selectedLocalFiles = files.filter(f => f.name.toLowerCase().endsWith('.csv'));
    document.getElementById('history_scan_info').innerHTML = '📁 <b>' + selectedLocalFiles.length + ' db CSV fájl</b> kiválasztva.';
    document.getElementById('startHistoryBtn').disabled = selectedLocalFiles.length === 0;
}

function autoScanServerFolder() { scanServerFolder(); }

async function scanServerFolder() {
    const folder = document.getElementById('history_folder_input').value.trim();
    try {
        const res = await fetch('/api/history/scan', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ folder: folder })
        });
        const data = await res.json();
        const tbody = document.getElementById('historyTableBody');
        if (data.status === 'SUCCESS') {
            document.getElementById('history_scan_info').innerHTML = '🖥️ <b>' + data.total_snapshots + ' db mentési csomag</b> a szerveren.';
            tbody.innerHTML = '';
            (data.snapshots || []).forEach(s => {
                tbody.innerHTML += `<tr><td><b>${escapeHtml(s.datetime)}</b></td><td><code>${escapeHtml(s.timestamp)}</code></td><td>${s.user_files_count} db fájl</td><td>${s.has_groups ? '✅ Igen' : '❌ Nincs'}</td></tr>`;
            });
            document.getElementById('startHistoryBtn').disabled = false;
        }
    } catch(e) {}
}

async function doQuickBackfill() {
    const folder = document.getElementById('history_folder_input').value.trim();
    if(!confirm('Frissíti a meglévő adatokat a CSV-k alapján?')) return;
    try {
        const res = await fetch('/api/history/backfill', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ folder: folder })
        });
        const d = await res.json();
        alert(d.message);
        allUsers = [];
        loadUsersAndGroups();
    } catch(e) { alert(e); }
}

async function startHistoryImport() {
    if(!confirm('Elindítja a történeti idővonal visszajátszását?')) return;
    try {
        await fetch('/api/history/import', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ folder: 'csv_imports' })
        });
        alert('Importálás elindult a háttérben!');
    } catch(e) { alert(e); }
}

async function loadGitHubHistory() {
    const box = document.getElementById('gh_history_list');
    if (!box) return;
    try {
        const res = await fetch('/api/github/history');
        const data = await res.json();
        if (data.status === 'SUCCESS' && Array.isArray(data.data)) {
            box.innerHTML = '';
            data.data.forEach(item => {
                box.innerHTML += `<div style="border-bottom:1px solid #cbd5e1; padding:5px 0;"><strong>${escapeHtml(item.message)}</strong><br/><small style="color:#64748b;">${escapeHtml(item.date)} | ${escapeHtml(item.author)}</small></div>`;
            });
        }
    } catch(e) {}
}

async function pushToGitHub() {
    const customMsg = document.getElementById('gh_custom_msg').value.trim();
    if(!confirm('Feltölti a kódot a GitHub-ra?')) return;
    const btn = document.getElementById('ghPushBtn');
    if (btn) { btn.disabled = true; btn.innerText = 'Feltöltés...'; }
    try {
        const res = await fetch('/api/github/push', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ message: customMsg })
        });
        const d = await res.json();
        alert(d.message);
        if(d.status === 'SUCCESS') {
            document.getElementById('app_version_label').innerText = d.new_version;
            loadGitHubHistory();
        }
    } catch(e) { alert(e); }
    finally { if (btn) { btn.disabled = false; btn.innerText = 'Kód Publikálása (Push)'; } }
}

async function saveSettings() {
    const data = {
        AD_SERVER: document.getElementById('ad_server').value,
        AD_USER: document.getElementById('ad_user').value,
        AD_PASSWORD: document.getElementById('ad_password').value,
        AD_SEARCH_BASE: document.getElementById('ad_base').value,
        OLLAMA_URL: document.getElementById('ollama_url').value,
        SYNC_INTERVAL_MINUTES: document.getElementById('sync_interval').value,
        GH_REPO: document.getElementById('gh_repo').value,
        GH_TOKEN: document.getElementById('gh_token').value,
        GH_BRANCH: document.getElementById('gh_branch').value
    };
    await fetch('/api/settings', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data) });
    alert('Beállítások elmentve!');
    window.location.reload();
}

// --- BIZTONSÁGOS ADATBÁZIS OPTIMALIZÁLÁS ---
async function optimizeDatabase() {
    const btn = document.getElementById('optDbBtn');
    const statusBox = document.getElementById('dbOptStatusBox');
    
    if (!confirm('Elindítja az adatbázis indexeinek újraépítését és a táblák analizálását?\n\nA művelet biztonságos, egyetlen adatot sem töröl.')) return;
    
    if (btn) { btn.disabled = true; btn.innerText = '⏳ Karbantartás és indexelés folyamatban...'; }
    if (statusBox) {
        statusBox.style.display = 'block';
        statusBox.style.background = '#fef3c7';
        statusBox.style.borderColor = '#fde047';
        statusBox.style.color = '#854d0e';
        statusBox.innerHTML = '⏳ <b>PostgreSQL karbantartás fut...</b> Indexek újraépítése (REINDEX) és táblák analizálása (VACUUM ANALYZE). Kérjük, várjon pár másodpercet...';
    }

    try {
        const res = await fetch('/api/settings/database/optimize', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'}
        });
        const data = await res.json();
        
        if (data.status === 'SUCCESS') {
            if (statusBox) {
                statusBox.style.background = '#f0fdf4';
                statusBox.style.borderColor = '#86efac';
                statusBox.style.color = '#166534';
                statusBox.innerHTML = `✅ <b>Karbantartás kész (${data.duration_sec} mp alatt)!</b> Adatbázis méret: ${data.size_before_mb} MB &rarr; <b>${data.size_after_mb} MB</b>. Indexek és statisztikák frissítve.`;
            }
            alert(data.message);
        } else {
            alert('Hiba a karbantartás során: ' + (data.message || 'Ismeretlen hiba'));
        }
    } catch(err) {
        alert('Hálózati hiba történt: ' + err);
    } finally {
        if (btn) { btn.disabled = false; btn.innerText = '⚡ Adatbázis Optimalizálása és Indexelése'; }
    }
}

// --- BEÁLLÍTÁSOK AL-FÜLEK ÉS VEZÉRLÉS ---
let currentSettingsSubTab = 'conn';
let systemAppSettings = {};

function switchSettingsSubTab(subTab) {
    currentSettingsSubTab = subTab;
    const tabs = ['conn', 'maint', 'ui'];
    tabs.forEach(t => {
        const btn = document.getElementById('btnSetTab' + t.charAt(0).toUpperCase() + t.slice(1));
        const box = document.getElementById('setBox' + t.charAt(0).toUpperCase() + t.slice(1));
        if (btn) {
            btn.style.background = (t === subTab) ? '#0284c7' : '#f1f5f9';
            btn.style.color = (t === subTab) ? 'white' : '#334155';
        }
        if (box) box.style.display = (t === subTab) ? 'block' : 'none';
    });
}

async function loadUnifiedSettings() {
    try {
        const res = await fetch('/api/settings/all');
        const data = await res.json();
        systemAppSettings = data;

        // Mezők feltöltése
        const setVal = (id, val) => { const el = document.getElementById(id); if (el && val !== undefined) el.value = val; };
        setVal('cfg_ad_server', data.AD_SERVER);
        setVal('cfg_ad_user', data.AD_USER);
        setVal('cfg_ad_base', data.AD_SEARCH_BASE);
        setVal('cfg_sync_interval', data.SYNC_INTERVAL_MINUTES);
        setVal('cfg_ollama_url', data.OLLAMA_URL);
        setVal('cfg_gh_repo', data.GH_REPO);
        setVal('cfg_gh_branch', data.GH_BRANCH);

        setVal('cfg_default_tab', data.DEFAULT_TAB);
        setVal('cfg_table_density', data.UI_TABLE_DENSITY);
        setVal('cfg_page_size', data.UI_PAGE_SIZE);
        setVal('cfg_telemetry_refresh', data.UI_TELEMETRY_REFRESH_SEC);

        setVal('cfg_ret_logs', data.RETENTION_DAYS_LOGS);
        setVal('cfg_ret_telemetry', data.RETENTION_DAYS_TELEMETRY);

        applyClientUiPreferences(data);
    } catch(e) {}
}

function applyClientUiPreferences(settings) {
    // 1. Táblázat sűrűség (Kompakt mód)
    if (settings.UI_TABLE_DENSITY === 'compact') {
        document.body.classList.add('compact-mode');
    } else {
        document.body.classList.remove('compact-mode');
    }

    // 2. Telemetria frissítési frekvencia alkalmazása
    const refreshSec = parseInt(settings.UI_TELEMETRY_REFRESH_SEC || '10');
    if (telemetryInterval) { clearInterval(telemetryInterval); telemetryInterval = null; }
    if (refreshSec > 0) {
        telemetryInterval = setInterval(() => {
            const activeTab = document.querySelector('.tab.active');
            if (activeTab && activeTab.id === 'tab-telemetry') {
                loadTelemetryLive();
                loadSessionsData();
            }
        }, refreshSec * 1000);
    }
}

async function saveUnifiedSettings() {
    const payload = {
        AD_SERVER: document.getElementById('cfg_ad_server')?.value,
        AD_USER: document.getElementById('cfg_ad_user')?.value,
        AD_PASSWORD: document.getElementById('cfg_ad_password')?.value,
        AD_SEARCH_BASE: document.getElementById('cfg_ad_base')?.value,
        SYNC_INTERVAL_MINUTES: document.getElementById('cfg_sync_interval')?.value,
        OLLAMA_URL: document.getElementById('cfg_ollama_url')?.value,
        GH_REPO: document.getElementById('cfg_gh_repo')?.value,
        GH_TOKEN: document.getElementById('cfg_gh_token')?.value,
        GH_BRANCH: document.getElementById('cfg_gh_branch')?.value,

        DEFAULT_TAB: document.getElementById('cfg_default_tab')?.value,
        UI_TABLE_DENSITY: document.getElementById('cfg_table_density')?.value,
        UI_PAGE_SIZE: document.getElementById('cfg_page_size')?.value,
        UI_TELEMETRY_REFRESH_SEC: document.getElementById('cfg_telemetry_refresh')?.value,

        RETENTION_DAYS_LOGS: document.getElementById('cfg_ret_logs')?.value,
        RETENTION_DAYS_TELEMETRY: document.getElementById('cfg_ret_telemetry')?.value
    };

    try {
        const res = await fetch('/api/settings/save', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.status === 'SUCCESS') {
            alert('✅ Beállítások sikeresen mentve és alkalmazva a rendszeren!');
            applyClientUiPreferences(payload);
        } else {
            alert('Hiba a mentéskor: ' + (data.message || 'Ismeretlen hiba'));
        }
    } catch(err) {
        alert('Hálózati hiba: ' + err);
    }
}

// Tesztek
async function testAdConnection() {
    alert('AD kapcsolat tesztelése folyamatban...');
    try {
        const res = await fetch('/api/settings/test/ad', { method: 'POST' });
        const d = await res.json();
        alert((d.status === 'SUCCESS' ? '✅ ' : '❌ ') + d.message);
    } catch(e) { alert('Hiba: ' + e); }
}

async function testOllamaConnection() {
    try {
        const res = await fetch('/api/settings/test/ollama', { method: 'POST' });
        const d = await res.json();
        alert((d.status === 'SUCCESS' ? '✅ ' : '❌ ') + d.message);
    } catch(e) { alert('Hiba: ' + e); }
}

// Öndiagnosztika
async function runSystemHealthCheck() {
    const box = document.getElementById('healthCheckResultsBox');
    if (box) box.innerHTML = '⏳ <i>Komponensek diagnosztikája fut...</i>';
    try {
        const res = await fetch('/api/settings/diagnostics/health');
        const data = await res.json();
        if (box && data.results) {
            box.innerHTML = '';
            data.results.forEach(item => {
                const badge = item.status === 'OK' 
                    ? '<span style="background:#dcfce7; color:#15803d; padding:2px 8px; border-radius:10px; font-weight:bold; font-size:11px;">🟢 OK</span>'
                    : '<span style="background:#fee2e2; color:#dc2626; padding:2px 8px; border-radius:10px; font-weight:bold; font-size:11px;">⚠️ Figyelem</span>';
                box.innerHTML += `<div style="display:flex; justify-content:space-between; border-bottom:1px solid #f1f5f9; padding:5px 0;">
                    <span><b>${item.name}:</b> ${item.detail}</span>
                    <span>${badge}</span>
                </div>`;
            });
            box.innerHTML += `<small style="display:block; margin-top:8px; color:#64748b;">Mérés időpontja: ${data.timestamp}</small>`;
        }
    } catch(e) {
        if (box) box.innerHTML = `<span style="color:#dc2626;">Hiba a diagnosztika során: ${e}</span>`;
    }
}

// Elavult adatok törlése
async function runLogRetentionCleanup() {
    if (!confirm('Biztosan törölni szeretné a megadott megőrzési időnél régebbi telemetriai és webes naplókat?\n\n(Az AD audit napló érintetlen marad!)')) return;
    try {
        const res = await fetch('/api/settings/maintenance/cleanup-history', { method: 'POST' });
        const d = await res.json();
        alert(d.message);
    } catch(e) { alert('Hiba: ' + e); }
}

// A Beállítások fülre váltáskor töltsük be az értékeket
const prevSwitchTab = switchTab;
switchTab = function(tabId) {
    prevSwitchTab(tabId);
    if (tabId === 'settings') {
        loadUnifiedSettings();
    }
};

// Oldal betöltésekor érvényesítsük a mentett kezdőfület és a stílust
window.addEventListener('DOMContentLoaded', async () => {
    try {
        const res = await fetch('/api/settings/all');
        const data = await res.json();
        applyClientUiPreferences(data);
        if (data.DEFAULT_TAB && data.DEFAULT_TAB !== 'dashboard') {
            switchTab(data.DEFAULT_TAB);
        }
    } catch(e) {}
});

// --- DOKUMENTÁCIÓ, SÉMA ÉS LLM SKILL PROMPT ÚJRAÉPÍTÉSE ---
async function rebuildSystemDocs() {
    const btn = document.getElementById('rebuildDocsBtn');
    const statusBox = document.getElementById('docsRebuildStatusBox');
    
    if (btn) { btn.disabled = true; btn.innerText = '⏳ Generálás folyamatban...'; }
    if (statusBox) {
        statusBox.style.display = 'block';
        statusBox.style.background = '#e0f2fe';
        statusBox.style.borderColor = '#bae6fd';
        statusBox.style.color = '#0369a1';
        statusBox.innerHTML = '⏳ <b>Dokumentáció és sémák generálása folyamatban...</b> Kérjük, várjon pár másodpercet...';
    }

    try {
        const res = await fetch('/api/settings/docs/rebuild', { method: 'POST' });
        const data = await res.json();
        
        if (data.status === 'SUCCESS') {
            const filesList = (data.generated_files || []).map(f => `<code>${f}</code>`).join(', ');
            if (statusBox) {
                statusBox.style.background = '#f0fdf4';
                statusBox.style.borderColor = '#86efac';
                statusBox.style.color = '#15803d';
                statusBox.innerHTML = `✅ <b>${data.message}</b><br/>Generált állományok: ${filesList} (${data.timestamp})`;
            }
            alert(`✅ ${data.message}\nGenerált fájlok:\n- ` + (data.generated_files || []).join('\n- '));
        } else {
            alert('Hiba a dokumentáció újraépítésekor: ' + (data.message || 'Ismeretlen hiba'));
        }
    } catch(err) {
        alert('Hálózati hiba: ' + err);
    } finally {
        if (btn) { btn.disabled = false; btn.innerText = '📚 Dokumentáció & LLM Prompt Újraépítése'; }
    }
}

// --- JELSZÓ ÉS TOKEN FELFEDÉSE / ELREJTÉSE ---
function togglePasswordVisibility(inputId, btn) {
    const input = document.getElementById(inputId);
    if (!input) return;
    if (input.type === 'password') {
        input.type = 'text';
        btn.innerText = '🔒';
        btn.title = 'Elrejtés';
    } else {
        input.type = 'password';
        btn.innerText = '👁️';
        btn.title = 'Felfedés';
    }
}

// --- GITHUB KAPCSOLAT TESZTELÉSE ---
async function testGitHub() {
    const repo = document.getElementById('cfg_gh_repo')?.value;
    const token = document.getElementById('cfg_gh_token')?.value;
    alert('GitHub kapcsolat tesztelése folyamatban...');
    try {
        const res = await fetch('/api/settings/test/git', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ repo: repo, token: token })
        });
        const contentType = res.headers.get("content-type") || "";
        if (!contentType.includes("application/json")) {
            const errText = await res.text();
            alert('Hiba a teszt során (Szerver válasz): ' + errText);
            return;
        }
        const d = await res.json();
        alert((d.status === 'SUCCESS' ? '✅ ' : '❌ ') + d.message);
    } catch(e) {
        alert('Hálózati hiba: ' + e);
    }
}

// Felülírjuk az AD tesztet hibabiztos JSON kezeléssel
testAdConnection = async function() {
    alert('AD kapcsolat tesztelése folyamatban...');
    try {
        const payload = {
            server: document.getElementById('cfg_ad_server')?.value,
            user: document.getElementById('cfg_ad_user')?.value,
            password: document.getElementById('cfg_ad_password')?.value,
            base: document.getElementById('cfg_ad_base')?.value
        };
        const res = await fetch('/api/settings/test/ad', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        const contentType = res.headers.get("content-type") || "";
        if (!contentType.includes("application/json")) {
            const errText = await res.text();
            alert('Hiba az AD teszt során: ' + errText);
            return;
        }
        const d = await res.json();
        alert((d.status === 'SUCCESS' ? '✅ ' : '❌ ') + d.message);
    } catch(e) {
        alert('Hiba: ' + e);
    }
};

// Felülírjuk a mentéskészítőt hibabiztos JSON kezeléssel
createNewBackup = async function() {
    const btn = document.getElementById('createBackupBtn');
    const commentInput = document.getElementById('backup_comment');
    if (btn) { btn.disabled = true; btn.innerText = 'Mentés készítése...'; }
    try {
        const res = await fetch('/api/backups/create', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ comment: commentInput ? commentInput.value.trim() : '' })
        });
        const contentType = res.headers.get("content-type") || "";
        if (!contentType.includes("application/json")) {
            const errText = await res.text();
            alert('Szerverhiba a mentés során: ' + errText);
            return;
        }
        const d = await res.json();
        if (d.status === 'SUCCESS') {
            alert('✅ Teljes mentés sikeresen elkészült!\nFájl: ' + d.filename + '\nMéret: ' + d.size);
            if (commentInput) commentInput.value = '';
            loadBackups();
        } else {
            alert('Hiba a mentésnél: ' + d.message);
        }
    } catch(e) {
        alert('Hálózati hiba: ' + e);
    } finally {
        if (btn) { btn.disabled = false; btn.innerText = '📦 Teljes Mentés Készítése'; }
    }
};

// Frissítjük a beállítások betöltését, hogy beállítsa a jelszó és token mezők értékeit
const baseLoadUnifiedSettings = loadUnifiedSettings;
loadUnifiedSettings = async function() {
    try {
        const res = await fetch('/api/settings/all');
        const data = await res.json();
        systemAppSettings = data;

        const setVal = (id, val) => { const el = document.getElementById(id); if (el && val !== undefined) el.value = val; };
        setVal('cfg_ad_server', data.AD_SERVER);
        setVal('cfg_ad_user', data.AD_USER);
        setVal('cfg_ad_password', data.AD_PASSWORD);
        setVal('cfg_ad_base', data.AD_SEARCH_BASE);
        setVal('cfg_sync_interval', data.SYNC_INTERVAL_MINUTES);
        setVal('cfg_ollama_url', data.OLLAMA_URL);
        setVal('cfg_gh_repo', data.GH_REPO);
        setVal('cfg_gh_token', data.GH_TOKEN);
        setVal('cfg_gh_branch', data.GH_BRANCH);

        setVal('cfg_default_tab', data.DEFAULT_TAB);
        setVal('cfg_table_density', data.UI_TABLE_DENSITY);
        setVal('cfg_page_size', data.UI_PAGE_SIZE);
        setVal('cfg_telemetry_refresh', data.UI_TELEMETRY_REFRESH_SEC);

        setVal('cfg_ret_logs', data.RETENTION_DAYS_LOGS);
        setVal('cfg_ret_telemetry', data.RETENTION_DAYS_TELEMETRY);

        applyClientUiPreferences(data);
    } catch(e) {}
};

// --- SZINKRONIZÁLÁSI NAPLÓ ÉS VEZÉRLÉS ---
async function loadSyncHistory() {
    const tbody = document.getElementById('syncHistoryBody');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:15px; color:#64748b;">Szinkronizálási napló lekérdezése az adatbázisból...</td></tr>';
    
    try {
        const [hRes, sRes] = await Promise.all([
            fetch('/api/sync-history'),
            fetch('/api/sync-status')
        ]);
        const historyData = await hRes.json();
        const statusData = await sRes.json();
        
        const stBadge = document.getElementById('syncStatusIndicator');
        if (stBadge) {
            if (statusData.is_syncing) {
                stBadge.innerHTML = '⏳ <b>Szinkronizáció folyamatban...</b>';
                stBadge.style.background = '#fef3c7';
                stBadge.style.color = '#b45309';
            } else {
                const lastRunTxt = statusData.last_run ? ` (Utolsó futás: ${statusData.last_run.slice(0, 19).replace('T', ' ')})` : '';
                stBadge.innerHTML = '🟢 <b>Készenlétben</b>' + lastRunTxt;
                stBadge.style.background = '#dcfce7';
                stBadge.style.color = '#15803d';
            }
        }

        tbody.innerHTML = '';
        if (!historyData || historyData.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:25px; color:#94a3b8;">Még nincs rögzített szinkronizálási naplóbejegyzés. Kattintson a jobb felső <b>Azonnali AD Szinkronizálás</b> gombra!</td></tr>';
            return;
        }

        historyData.forEach(l => {
            let stBg = '#dcfce7', stColor = '#15803d', stText = 'SIKERES';
            if (l.status === 'HIBA') { stBg = '#fee2e2'; stColor = '#b91c1c'; stText = 'HIBA'; }
            else if (l.status === 'FOLYAMATBAN') { stBg = '#fef3c7'; stColor = '#b45309'; stText = 'FOLYAMATBAN'; }

            const errHtml = l.error ? `<br/><small style="color:#b91c1c; font-family:monospace;">${escapeHtml(l.error)}</small>` : '';
            const chHtml = (l.changes > 0) 
                ? `<span style="background:#e0f2fe; color:#0369a1; padding:2px 8px; border-radius:10px; font-weight:bold; font-size:11.5px;">+${l.changes} változás</span>`
                : `<span style="color:#64748b;">0 db</span>`;

            tbody.innerHTML += `<tr>
                <td style="white-space:nowrap; color:#64748b;">${escapeHtml(l.started)}</td>
                <td style="white-space:nowrap; color:#64748b;">${escapeHtml(l.ended)}</td>
                <td><b>${escapeHtml(l.duration)}</b></td>
                <td><span style="background:#f1f5f9; padding:2px 6px; border-radius:4px; font-weight:600; font-size:11.5px;">${escapeHtml(l.trigger)}</span></td>
                <td><span style="background:${stBg}; color:${stColor}; padding:3px 8px; border-radius:10px; font-weight:bold; font-size:11px;">${stText}</span>${errHtml}</td>
                <td>${chHtml}</td>
            </tr>`;
        });
    } catch(err) {
        tbody.innerHTML = `<tr><td colspan="6" style="color:#dc2626; padding:15px;">Hiba a napló betöltésekor: ${err}</td></tr>`;
    }
}

async function triggerManualSync() {
    if (!confirm('Elindítja az azonnali manuális szinkronizálást az Active Directory-ból?')) return;
    try {
        const res = await fetch('/api/sync', { method: 'POST' });
        const d = await res.json();
        alert('Szinkronizáció elindítva a háttérben!');
        setTimeout(loadSyncHistory, 1200);
    } catch(e) {
        alert('Hiba az indításkor: ' + e);
    }
}

// Felülírjuk a mentéskészítőt részletes tételes adattartalom visszaigazolással
createNewBackup = async function() {
    const btn = document.getElementById('createBackupBtn');
    const commentInput = document.getElementById('backup_comment');
    if (btn) { btn.disabled = true; btn.innerText = 'Mentés készítése...'; }
    try {
        const res = await fetch('/api/backups/create', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ comment: commentInput ? commentInput.value.trim() : '' })
        });
        const contentType = res.headers.get("content-type") || "";
        if (!contentType.includes("application/json")) {
            const errText = await res.text();
            alert('Szerverhiba a mentés során: ' + errText);
            return;
        }
        const d = await res.json();
        if (d.status === 'SUCCESS') {
            const st = d.stats || {};
            const infoMsg = [
                `✅ Teljes mentés sikeresen elkészült!`,
                `Fájl: ${d.filename} (${d.size})`,
                ``,
                `Garantáltan elmentett rekordok a csomagban:`,
                `  • AD Felhasználók: ${st.ad_users || 0} db`,
                `  • AD Csoportok: ${st.ad_groups || 0} db`,
                `  • Csoporttagsági kötések: ${st.ad_group_members || 0} db`,
                `  • Változás- és Auditnapló: ${st.ad_audit_log || 0} esemény`,
                `  • Szinkronizálási történet: ${st.sync_history || 0} bejegyzés`,
                `  • Rendszernaplók: ${(st.system_telemetry || 0) + (st.web_access_log || 0)} mérés`,
                `  • Teljes kódbázis (Python, HTML, CSS, JS)`,
                `  • Dokumentáció és Konfiguráció`
            ].join('\n');
            alert(infoMsg);
            if (commentInput) commentInput.value = '';
            loadBackups();
        } else {
            alert('Hiba a mentésnél: ' + d.message);
        }
    } catch(e) {
        alert('Hálózati hiba: ' + e);
    } finally {
        if (btn) { btn.disabled = false; btn.innerText = '📦 Teljes Mentés Készítése'; }
    }
};

// --- GITHUB VERZIÓ ÉS PUSH VEZÉRLÉS ---
async function fetchLiveGitHubVersion() {
    try {
        const res = await fetch('/api/github/version');
        const data = await res.json();
        if (data.version) {
            document.querySelectorAll('#app_version_label, .app-version-val').forEach(el => el.innerText = data.version);
        }
    } catch(e) {}
}

async function loadGitHubHistory() {
    const box = document.getElementById('gh_history_list');
    if (!box) return;
    box.innerHTML = '<span style="color:#64748b;">Előzmények lekérése a GitHub API-ról...</span>';
    try {
        const res = await fetch('/api/github/history');
        const data = await res.json();
        if (data.status === 'SUCCESS' && Array.isArray(data.data) && data.data.length > 0) {
            box.innerHTML = '';
            data.data.forEach(item => {
                box.innerHTML += `<div style="border-bottom:1px solid #e2e8f0; padding:4px 0;">
                    <span style="background:#e0f2fe; color:#0369a1; padding:1px 5px; border-radius:3px; font-size:10px; font-family:monospace;">${escapeHtml(item.sha)}</span>
                    <strong>${escapeHtml(item.message)}</strong><br/>
                    <small style="color:#64748b;">${escapeHtml(item.date)} | ${escapeHtml(item.author)}</small>
                </div>`;
            });
        } else {
            box.innerHTML = '<span style="color:#94a3b8;">Nincs megjeleníthető commit előzmény.</span>';
        }
    } catch(e) {
        box.innerHTML = `<span style="color:#dc2626;">Hiba a lekéréskor: ${e}</span>`;
    }
}

async function pushToGitHub() {
    const msgInput = document.getElementById('gh_custom_msg');
    const customMsg = msgInput ? msgInput.value.trim() : '';
    if (!confirm('Biztosan közzéteszi a jelenlegi forráskódot a GitHub repóban? A rendszer automatikusan lépteti a verziószámot és rögzíti a commitot!')) return;

    const btn = document.getElementById('ghPushBtn');
    if (btn) { btn.disabled = true; btn.innerText = '⏳ Kód feltöltése és verzió növelése...'; }

    try {
        const res = await fetch('/api/github/push', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ message: customMsg })
        });
        const d = await res.json();
        if (d.status === 'SUCCESS') {
            alert(`✅ ${d.message}`);
            if (msgInput) msgInput.value = '';
            await fetchLiveGitHubVersion();
            await loadGitHubHistory();
        } else {
            alert(`❌ Hiba a publikáláskor: ${d.message}`);
        }
    } catch(err) {
        alert('Hálózati hiba: ' + err);
    } finally {
        if (btn) { btn.disabled = false; btn.innerText = '🚀 Kód Publikálása (Push & Verzió Növelés)'; }
    }
}

// Beállítások fülre lépéskor azonnal betöltjük az előzményeket és a verziót
const originalSwitchSettingsSubTab = switchSettingsSubTab;
switchSettingsSubTab = function(subTab) {
    originalSwitchSettingsSubTab(subTab);
    if (subTab === 'conn') {
        fetchLiveGitHubVersion();
        loadGitHubHistory();
    }
};
