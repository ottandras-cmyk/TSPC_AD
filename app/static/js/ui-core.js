// ==========================================================================
// AD TRACKER & RENDSZERKÖZPONT - TELJES EGYSÉGES MOTOR (ALL TABS + HELPDESK)
// ==========================================================================

function safeSetText(id, txt) {
    var el = document.getElementById(id);
    if (el) el.innerText = (txt !== null && txt !== undefined && String(txt).trim() !== '') ? txt : '-';
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

// --------------------------------------------------------------------------
// 1. UNIVERZÁLIS FÜLVÁLTÓ MOTOR (MIND A 11 FÜL HIÁNYTALAN KEZELÉSE)
// --------------------------------------------------------------------------
window.switchTab = function(tabId) {
    if (!tabId) return;

    // Normalizáljuk az azonosítót: kezeli az 'audit' és 'pane-audit' formátumot is!
    var shortId = String(tabId).replace(/^pane-/, '');
    var realPaneId = 'pane-' + shortId;

    // 1. Gombok stílusának frissítése (minden switchTab gombot tisztít, és csak az aktívat színezi)
    document.querySelectorAll('[onclick*="switchTab"]').forEach(function(btn) {
        var clk = btn.getAttribute('onclick') || '';
        var isMatch = clk.includes("'" + shortId + "'") || 
                      clk.includes('"' + shortId + '"') ||
                      clk.includes("'" + realPaneId + "'") || 
                      clk.includes('"' + realPaneId + '"');

        if (isMatch) {
            btn.classList.add('active');
            btn.style.setProperty('background', '#0284c7', 'important');
            btn.style.setProperty('color', '#ffffff', 'important');
        } else {
            btn.classList.remove('active');
            btn.style.removeProperty('background');
            btn.style.removeProperty('color');
        }
    });

    // 2. Lapok (pane-ek) megjelenítése és elrejtése
    var allPanes = document.querySelectorAll('.app-tab-pane, [id^="pane-"], [id^="tab-"]');
    allPanes.forEach(function(pane) {
        var isCurrent = (pane.id === realPaneId || pane.id === shortId || pane.id === tabId);
        if (isCurrent) {
            pane.classList.add('active');
            pane.style.setProperty('display', 'block', 'important');
        } else {
            pane.classList.remove('active');
            pane.style.setProperty('display', 'none', 'important');
        }
    });

    // 3. Adatbetöltők indítása a megfelelő fül aktiválásakor
    if (shortId === 'audit' && window.loadAuditEvents) loadAuditEvents();
    else if (shortId === 'users' && window.loadUsersAndGroups) {
        loadUsersAndGroups();
        if (window.refreshDataTableLayoutForVisibleTab) window.refreshDataTableLayoutForVisibleTab();
    }
    else if (shortId === 'easyproject' && window.loadEpTasks) loadEpTasks();
    else if (shortId === 'helpdesk' && window.loadHelpdeskTickets) loadHelpdeskTickets();
    else if (shortId === 'backups' && window.loadBackups) { loadBackups(); loadGitLog(); }
};

// --------------------------------------------------------------------------
// 2. JOGOSULTSÁG VÁLTOZÁSOK (AUDIT ESEMÉNYEK)
// --------------------------------------------------------------------------
var allAuditEventsMaster = [];
window.loadAuditEvents = async function() {
    var tbody = document.getElementById('auditTableBody');
    try {
        var res = await fetch('/api/audit/events');
        if (res.ok) {
            var data = await res.json();
            allAuditEventsMaster = data.events || data || [];
            renderAuditRows();
        }
    } catch(err) {
        if (tbody) tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding:20px; color:#ef4444;">Hiba az események betöltésekor.</td></tr>';
    }
};

function renderAuditRows() {
    var tbody = document.getElementById('auditTableBody');
    if (!tbody) return;
    if (allAuditEventsMaster.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding:20px; color:#94a3b8;">Nincs megjeleníthető esemény.</td></tr>';
        return;
    }
    tbody.innerHTML = allAuditEventsMaster.slice(0, 50).map(function(e) {
        return `<tr>
            <td style="font-size:12px; color:#64748b; white-space:nowrap;">${escapeHtml(e.timestamp || e.created_at || '-')}</td>
            <td><b>${escapeHtml(e.target_user || e.username || '-')}</b></td>
            <td><span style="background:#e0f2fe; color:#0369a1; padding:2px 8px; border-radius:10px; font-size:11px; font-weight:bold;">${escapeHtml(e.event_type || e.action || '-')}</span></td>
            <td style="font-size:12px;">${escapeHtml(e.details || e.description || '-')}</td>
        </tr>`;
    }).join('');
}

// --------------------------------------------------------------------------
// 3. FELHASZNÁLÓK ÉS CSOPORTOK
// --------------------------------------------------------------------------
var allUsersMaster = [];
var allGroupsMaster = [];
window.loadUsersAndGroups = async function() {
    try {
        var res = await fetch('/api/users/all');
        if (res.ok) {
            var data = await res.json();
            allUsersMaster = data.users || [];
            allGroupsMaster = data.groups || [];
            renderUserRows();
        }
    } catch(err) {}
};


function renderUserRows() {
    var tbody = document.getElementById('usersTableBody');
    if (!tbody) return;
    
    var usersToDisplay = (window.filteredUsersMaster || allUsersMaster);
    if (!usersToDisplay || usersToDisplay.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:30px; color:#64748b;">Nincs megjeleníthető munkatárs.</td></tr>';
        return;
    }

    tbody.innerHTML = usersToDisplay.slice(0, 100).map(function(u) {
        var sName = u.display_name || u.displayName || u.name || u.sam_account_name || u.sAMAccountName || '-';
        var sUser = u.sam_account_name || u.sAMAccountName || u.username || '-';
        var sMail = u.mail || u.email || '-';
        var sDept = u.department || u.dept || '-';
        var sTitle = u.title || '-';
        var sLogon = u.last_logon || u.last_logon_date || u.last_logon_timestamp || '-';
        if (typeof sLogon === 'string' && sLogon.length > 16) sLogon = sLogon.substring(0, 16);
        
        var isAct = (u.is_enabled !== false && u.enabled !== false);
        var badge = isAct 
            ? '<span style="background:#dcfce7; color:#15803d; padding:2px 7px; border-radius:10px; font-size:10.5px; font-weight:700; margin-left:6px;">Aktív</span>'
            : '<span style="background:#fee2e2; color:#b91c1c; padding:2px 7px; border-radius:10px; font-size:10.5px; font-weight:700; margin-left:6px;">Letiltott</span>';

        var initial = sName ? sName.trim().charAt(0).toUpperCase() : 'U';

        return `<tr style="border-bottom:1px solid #f1f5f9; font-size:13px; cursor:pointer;" onclick="openUserModal('${escapeHtml(sUser)}')">
            <td style="padding:10px 14px; font-weight:700; color:#0f172a; display:flex; align-items:center; gap:8px;">
                <span style="background:#e0f2fe; color:#0284c7; width:28px; height:28px; border-radius:50%; display:inline-flex; align-items:center; justify-content:center; font-size:11.5px; font-weight:800; flex-shrink:0;">${initial}</span>
                <div>${escapeHtml(sName)}${badge}</div>
            </td>
            <td style="padding:10px 14px; font-family:monospace; color:#475569; font-weight:600;">${escapeHtml(sUser)}</td>
            <td style="padding:10px 14px; color:#0284c7;">${sMail !== '-' ? '<a href="mailto:' + escapeHtml(sMail) + '" style="color:#0284c7; text-decoration:none;">' + escapeHtml(sMail) + '</a>' : '<span style="color:#94a3b8;">-</span>'}</td>
            <td style="padding:10px 14px;"><span style="background:#f1f5f9; color:#334155; padding:3px 8px; border-radius:4px; font-weight:600; font-size:11.5px;">${escapeHtml(sDept)}</span></td>
            <td style="padding:10px 14px; color:#475569;">${escapeHtml(sTitle)}</td>
            <td style="padding:10px 14px; color:#64748b; font-size:12px;">${escapeHtml(sLogon)}</td>
            <td style="padding:10px 14px; text-align:right;">
                <button class="btn" style="background:#0284c7; color:white; border:none; padding:4px 10px; border-radius:4px; font-size:11.5px; font-weight:600; cursor:pointer;" onclick="event.stopPropagation(); openUserModal('${escapeHtml(sUser)}')">👁️ Részletek</button>
            </td>
        </tr>`;
    }).join('');
}

window.filterAndSortUsers = function() {
    var query = (document.getElementById('userGlobalSearch')?.value || '').toLowerCase().trim();
    if (!query) {
        window.filteredUsersMaster = allUsersMaster;
    } else {
        window.filteredUsersMaster = allUsersMaster.filter(function(u) {
            var n = (u.display_name || u.displayName || '').toLowerCase();
            var s = (u.sam_account_name || u.sAMAccountName || '').toLowerCase();
            var m = (u.mail || u.email || '').toLowerCase();
            var d = (u.department || '').toLowerCase();
            var t = (u.title || '').toLowerCase();
            return n.includes(query) || s.includes(query) || m.includes(query) || d.includes(query) || t.includes(query);
        });
    }
    renderUserRows();
};

window.sortUsersBy = function(field) {
    if (!allUsersMaster) return;
    window.userSortAsc = !window.userSortAsc;
    var list = window.filteredUsersMaster || allUsersMaster;
    list.sort(function(a, b) {
        var va = (a[field] || a['sam_account_name'] || '').toString().toLowerCase();
        var vb = (b[field] || b['sam_account_name'] || '').toString().toLowerCase();
        return window.userSortAsc ? va.localeCompare(vb, 'hu') : vb.localeCompare(va, 'hu');
    });
    renderUserRows();
};

window.openUserModal = function(uName) {
    if (!uName || uName === 'undefined') return;
    var u = allUsersMaster.find(function(x) { 
        return (x.sam_account_name === uName || x.sAMAccountName === uName || x.username === uName); 
    });
    if (!u) return;

    var overlay = document.getElementById('userModalOverlay') || document.getElementById('userModal');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'userModalOverlay';
        overlay.style.cssText = 'position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(15,23,42,0.6); z-index:999999; display:flex; align-items:center; justify-content:center; padding:16px;';
        document.body.appendChild(overlay);
    }

    var isAct = (u.is_enabled !== false && u.enabled !== false);
    var sName = u.display_name || u.displayName || u.sam_account_name;

    overlay.style.display = 'flex';
    overlay.innerHTML = `
    <div style="background:white; border-radius:10px; width:100%; max-width:560px; box-shadow:0 20px 40px rgba(0,0,0,0.3); overflow:hidden;">
        <div style="background:#0284c7; color:white; padding:16px 20px; display:flex; justify-content:space-between; align-items:center;">
            <div style="font-weight:800; font-size:16px; display:flex; align-items:center; gap:8px;">
                <span>👤</span> ${escapeHtml(sName)}
            </div>
            <button onclick="document.getElementById('userModalOverlay').style.display='none'" style="background:transparent; border:none; color:white; font-size:20px; font-weight:bold; cursor:pointer;">✕</button>
        </div>
        <div style="padding:20px; display:flex; flex-direction:column; gap:12px; font-size:13px; max-height:75vh; overflow-y:auto;">
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; background:#f8fafc; padding:14px; border-radius:8px; border:1px solid #e2e8f0;">
                <div><span style="color:#64748b; font-size:11.5px; display:block;">Felhasználónév (SAM):</span><b>${escapeHtml(u.sam_account_name || u.sAMAccountName || '-')}</b></div>
                <div><span style="color:#64748b; font-size:11.5px; display:block;">Fiók állapota:</span><b style="color:${isAct ? '#15803d' : '#b91c1c'};">${isAct ? '✅ Aktív munkatárs' : '⛔ Letiltott fiók'}</b></div>
                <div><span style="color:#64748b; font-size:11.5px; display:block;">E-mail cím:</span><b>${escapeHtml(u.mail || u.email || '-')}</b></div>
                <div><span style="color:#64748b; font-size:11.5px; display:block;">Részleg / Osztály:</span><b>${escapeHtml(u.department || '-')}</b></div>
                <div><span style="color:#64748b; font-size:11.5px; display:block;">Beosztás (Title):</span><b>${escapeHtml(u.title || '-')}</b></div>
                <div><span style="color:#64748b; font-size:11.5px; display:block;">Telefonszám:</span><b>${escapeHtml(u.telephone_number || '-')}</b></div>
                <div style="grid-column: span 2;"><span style="color:#64748b; font-size:11.5px; display:block;">Utolsó belépés:</span><b>${escapeHtml(u.last_logon || '-')}</b></div>
            </div>
        </div>
        <div style="background:#f1f5f9; padding:12px 20px; text-align:right; border-top:1px solid #e2e8f0;">
            <button onclick="document.getElementById('userModalOverlay').style.display='none'" style="background:#64748b; color:white; border:none; padding:6px 14px; border-radius:5px; cursor:pointer; font-weight:600;">Bezárás</button>
        </div>
    </div>`;
};

window.closeUserModal = function() {
    var o = document.getElementById('userModalOverlay');
    if (o) o.style.display = 'none';
};

// --------------------------------------------------------------------------
// 4. EASY PROJECT TASKS (3380 FELADAT)
// --------------------------------------------------------------------------
var allEpTasksMaster = [];
window.loadEpTasks = async function() {
    try {
        var res = await fetch('/api/easyproject/tasks');
        if (res.ok) {
            var data = await res.json();
            allEpTasksMaster = data.tasks || [];
            var tbody = document.getElementById('epTasksTableBody');
            if (tbody) {
                tbody.innerHTML = allEpTasksMaster.slice(0, 50).map(function(t) {
                    return `<tr>
                        <td><b>#${t.id}</b></td>
                        <td>${escapeHtml(t.subject)}</td>
                        <td>${escapeHtml(t.status_name || '-')}</td>
                        <td>${escapeHtml(t.assigned_to_name || '-')}</td>
                    </tr>`;
                }).join('');
            }
        }
    } catch(err) {}
};

// ==========================================================================
// 5. EP HIBAJEGYKEZELŐ + (SZŰRÉS, RENDEZÉS, SZÁMLÁLÓK, MODÁL & TELEGRAM)
// ==========================================================================
var allHelpdeskTicketsMaster = [];
var filteredHelpdeskTickets = [];
var hdPage = 1, hdPageSize = 50;
var hdSortCol = 'default', hdSortDir = 'asc';
var activeModalTicketId = null;
var activeHdKpi = 'ALL';

var hdInvCounts = {};
var hdAuthorCounts = {};
var hdLocCounts = {};
var hdStatusCounts = {};
var hdPriorityCounts = {};

function getStatusRank(statusName) {
    if (!statusName) return 99;
    var s = String(statusName).toLowerCase().trim();
    if (s.includes('új') || s.includes('uj') || s.includes('kioszt') || s === 'new' || s.includes('1.0')) return 0;
    if (s.includes('elhalaszt') || s.includes('folyamat') || s.includes('vizsgá') || s.includes('vizsga') || s.includes('kívül') || s.includes('kivul') || s.includes('nyitott') || s.includes('open') || s.includes('3.1') || s.includes('3.2') || s.includes('4.1')) return 1;
    if (s.includes('megoldva') || s.includes('lezárt') || s.includes('lezart') || s.includes('elutasít') || s.includes('zárva') || s.includes('zarva') || s.includes('closed') || s.includes('resolved') || s.includes('4.2') || s.includes('4.3')) return 2;
    return 1;
}

// KPI KÁRTYÁKRA KATTINTÁS (ÖSSZES, NYITOTT, MEGOLDOTT SZŰRÉS)
window.filterHdByKpi = function(kpiType) {
    activeHdKpi = (activeHdKpi === kpiType && kpiType !== 'ALL') ? 'ALL' : kpiType;

    var cardTotal = document.getElementById('hd_kpi_card_total');
    var cardOpen = document.getElementById('hd_kpi_card_open');
    var cardClosed = document.getElementById('hd_kpi_card_closed');

    if (cardTotal) cardTotal.style.boxShadow = (activeHdKpi === 'ALL') ? '0 0 0 2px #0284c7' : '';
    if (cardOpen) cardOpen.style.boxShadow = (activeHdKpi === 'OPEN') ? '0 0 0 3px #16a34a' : '';
    if (cardClosed) cardClosed.style.boxShadow = (activeHdKpi === 'CLOSED') ? '0 0 0 3px #64748b' : '';

    var selStatus = document.getElementById('hdFilterStatus');
    if (selStatus) {
        if (activeHdKpi === 'OPEN') selStatus.value = 'OPEN';
        else if (activeHdKpi === 'CLOSED') selStatus.value = 'CLOSED';
        else selStatus.value = 'ALL';
    }

    hdPage = 1;
    filterAndSortHelpdesk();
};

window.onHdDropdownFilterChange = function(which) {
    if (which === 'status') {
        var el = document.getElementById('hdFilterStatus');
        var val = el ? el.value : 'ALL';
        activeHdKpi = (val === 'OPEN' || val === 'CLOSED') ? val : 'ALL';
        var cardTotal = document.getElementById('hd_kpi_card_total');
        var cardOpen = document.getElementById('hd_kpi_card_open');
        var cardClosed = document.getElementById('hd_kpi_card_closed');
        if (cardTotal) cardTotal.style.boxShadow = (activeHdKpi === 'ALL') ? '0 0 0 2px #0284c7' : '';
        if (cardOpen) cardOpen.style.boxShadow = (activeHdKpi === 'OPEN') ? '0 0 0 3px #16a34a' : '';
        if (cardClosed) cardClosed.style.boxShadow = (activeHdKpi === 'CLOSED') ? '0 0 0 3px #64748b' : '';
    }
    hdPage = 1;
    filterAndSortHelpdesk();
};

window.setHdFilter = function(filterType, value) {
    var el = document.getElementById('hdFilter' + filterType.charAt(0).toUpperCase() + filterType.slice(1));
    if (el) el.value = value;
    hdPage = 1;
    filterAndSortHelpdesk();
};

window.resetHdFilters = function() {
    var s = document.getElementById('hdGlobalSearch'); if (s) s.value = '';
    var st = document.getElementById('hdFilterStatus'); if (st) st.value = 'ALL';
    var pr = document.getElementById('hdFilterPriority'); if (pr) pr.value = 'ALL';
    var inv = document.getElementById('hdFilterInventory'); if (inv) inv.value = 'ALL';
    var aut = document.getElementById('hdFilterAuthor'); if (aut) aut.value = 'ALL';
    var loc = document.getElementById('hdFilterLocation'); if (loc) loc.value = 'ALL';

    activeHdKpi = 'ALL';
    var cardTotal = document.getElementById('hd_kpi_card_total');
    var cardOpen = document.getElementById('hd_kpi_card_open');
    var cardClosed = document.getElementById('hd_kpi_card_closed');
    if (cardTotal) cardTotal.style.boxShadow = '0 0 0 2px #0284c7';
    if (cardOpen) cardOpen.style.boxShadow = '';
    if (cardClosed) cardClosed.style.boxShadow = '';

    hdSortCol = 'default';
    hdSortDir = 'asc';
    document.querySelectorAll('[id^="hd_sort_"]').forEach(function(el) { el.innerText = '⇅'; el.style.color = '#94a3b8'; });
    var cur = document.getElementById('hd_sort_id');
    if (cur) { cur.innerText = '▼'; cur.style.color = '#0284c7'; }

    hdPage = 1;
    filterAndSortHelpdesk();
};

window.populateHdFilterDropdowns = function() {
    hdInvCounts = {};
    hdAuthorCounts = {};
    hdLocCounts = {};
    hdStatusCounts = {};
    hdPriorityCounts = {};

    allHelpdeskTicketsMaster.forEach(function(t) {
        var inv = t.inventory_number || t.custom_field_499;
        if (inv && inv !== '-' && inv !== 'None') hdInvCounts[inv] = (hdInvCounts[inv] || 0) + 1;

        var aut = t.author_name || t.author;
        if (aut && aut !== '-' && aut !== 'None') hdAuthorCounts[aut] = (hdAuthorCounts[aut] || 0) + 1;

        var loc = t.location || t.custom_field_503;
        if (loc && loc !== '-' && loc !== 'None') hdLocCounts[loc] = (hdLocCounts[loc] || 0) + 1;

        var st = t.status_name || t.status;
        if (st && st !== '-' && st !== 'None') hdStatusCounts[st] = (hdStatusCounts[st] || 0) + 1;

        var pr = t.priority_name || t.priority || 'Normál';
        hdPriorityCounts[pr] = (hdPriorityCounts[pr] || 0) + 1;
    });

    var inventories = Object.keys(hdInvCounts).sort(function(a, b) { return a.localeCompare(b, 'hu', { numeric: true }); });
    var authors = Object.keys(hdAuthorCounts).sort(function(a, b) { return a.localeCompare(b, 'hu'); });
    var locations = Object.keys(hdLocCounts).sort(function(a, b) { return a.localeCompare(b, 'hu'); });

    var fillDropdown = function(elemId, items, counts, defaultLabel) {
        var sel = document.getElementById(elemId);
        if (!sel) return;
        var cur = sel.value;
        sel.innerHTML = '<option value="ALL">' + defaultLabel + '</option>';
        items.forEach(function(it) {
            var opt = document.createElement('option');
            opt.value = it;
            opt.innerText = it + ' (' + (counts[it] || 0) + ' db)';
            sel.appendChild(opt);
        });
        if (cur && items.includes(cur)) sel.value = cur;
    };

    fillDropdown('hdFilterInventory', inventories, hdInvCounts, '💻 Minden leltári szám (' + inventories.length + ' gép)');
    fillDropdown('hdFilterAuthor', authors, hdAuthorCounts, '👤 Minden bejelentő (' + authors.length + ' fő)');
    fillDropdown('hdFilterLocation', locations, hdLocCounts, '📍 Minden helyszín (' + locations.length + ' hely)');

    // 1. STÁTUSZ SZŰRŐ FELTÖLTÉSE
    var selStatus = document.getElementById('hdFilterStatus');
    if (selStatus) {
        var curVal = selStatus.value;
        var openCnt = allHelpdeskTicketsMaster.filter(function(t){ return getStatusRank(t.status_name) < 2; }).length;
        var closedCnt = allHelpdeskTicketsMaster.length - openCnt;

        var statuses = Object.keys(hdStatusCounts).sort(function(a, b) {
            var rankDiff = getStatusRank(a) - getStatusRank(b);
            if (rankDiff !== 0) return rankDiff;
            return a.localeCompare(b, 'hu');
        });

        selStatus.innerHTML = '<option value="ALL">Minden státusz (' + allHelpdeskTicketsMaster.length + ' db)</option>' +
                              '<option value="OPEN">🟢 Csak nyitott / folyamatban (' + openCnt + ' db)</option>' +
                              '<option value="CLOSED">⚪ Csak megoldott / lezárt (' + closedCnt + ' db)</option>';
        statuses.forEach(function(st) {
            var cnt = hdStatusCounts[st] || 0;
            var opt = document.createElement('option');
            opt.value = st;
            var icon = (getStatusRank(st) < 2) ? '🟢 ' : '⚪ ';
            opt.innerText = icon + st + ' (' + cnt + ' db)';
            selStatus.appendChild(opt);
        });
        if (curVal) selStatus.value = curVal;
    }

    // 2. PRIORITÁS SZŰRŐ FELTÖLTÉSE
    var selPriority = document.getElementById('hdFilterPriority');
    if (selPriority) {
        var curPrio = selPriority.value;
        var prioOrder = ['Azonnali', 'Sürgős', 'Magas', 'Normál', 'Alacsony'];
        var allPrios = Array.from(new Set(prioOrder.concat(Object.keys(hdPriorityCounts))));

        selPriority.innerHTML = '<option value="ALL">⚡ Minden prioritás (' + allHelpdeskTicketsMaster.length + ' db)</option>';
        allPrios.forEach(function(pr) {
            var cnt = hdPriorityCounts[pr] || 0;
            if (cnt > 0) {
                var opt = document.createElement('option');
                opt.value = pr;
                opt.innerText = pr + ' (' + cnt + ' db)';
                selPriority.appendChild(opt);
            }
        });
        if (curPrio) selPriority.value = curPrio;
    }
};

window.loadHelpdeskTickets = async function() {
    try {
        var res = await fetch('/api/easyproject/helpdesk/tickets');
        if (res.ok) {
            var data = await res.json();
            allHelpdeskTicketsMaster = data.tickets || [];
            var s = data.summary || {};

            var openCnt = allHelpdeskTicketsMaster.filter(function(t){ return getStatusRank(t.status_name) < 2; }).length;
            var closedCnt = allHelpdeskTicketsMaster.length - openCnt;

            safeSetText('hd_stat_total', `${s.total_count || allHelpdeskTicketsMaster.length} db`);
            safeSetText('hd_stat_open', `${openCnt} db`);
            safeSetText('hd_stat_closed', `${closedCnt} db`);
            safeSetText('hd_stat_last_sync', s.last_sync || 'Ma 15:34');

            populateHdFilterDropdowns();
            filterAndSortHelpdesk();
        }
    } catch(err) {
        console.error('Helpdesk betöltési hiba:', err);
    }
};

window.filterAndSortHelpdesk = function() {
    var qGlobal = (document.getElementById('hdGlobalSearch') ? document.getElementById('hdGlobalSearch').value : '').toLowerCase().trim();
    var fStatus = document.getElementById('hdFilterStatus') ? document.getElementById('hdFilterStatus').value : 'ALL';
    var fPriority = document.getElementById('hdFilterPriority') ? document.getElementById('hdFilterPriority').value : 'ALL';
    var fInventory = document.getElementById('hdFilterInventory') ? document.getElementById('hdFilterInventory').value : 'ALL';
    var fAuthor = document.getElementById('hdFilterAuthor') ? document.getElementById('hdFilterAuthor').value : 'ALL';
    var fLocation = document.getElementById('hdFilterLocation') ? document.getElementById('hdFilterLocation').value : 'ALL';

    var res = allHelpdeskTicketsMaster.filter(function(t) {
        var rank = getStatusRank(t.status_name);

        if (fStatus === 'OPEN' && rank >= 2) return false;
        if (fStatus === 'CLOSED' && rank < 2) return false;
        if (fStatus !== 'ALL' && fStatus !== 'OPEN' && fStatus !== 'CLOSED' && (t.status_name || t.status) !== fStatus) return false;

        if (fPriority !== 'ALL' && (t.priority_name || t.priority || 'Normál') !== fPriority) return false;

        if (fInventory !== 'ALL' && (t.inventory_number || t.custom_field_499 || '-') !== fInventory) return false;
        if (fAuthor !== 'ALL' && (t.author_name || t.author || '-') !== fAuthor) return false;
        if (fLocation !== 'ALL' && (t.location || t.custom_field_503 || '-') !== fLocation) return false;

        if (qGlobal) {
            var rowStr = [
                t.id, t.hd_serial, t.custom_field_545, t.created_on,
                t.inventory_number, t.custom_field_499,
                t.author_name, t.author, t.phone, t.custom_field_500,
                t.location, t.custom_field_503,
                t.status_name, t.priority_name, t.subject,
                t.description, t.custom_field_530, t.custom_field_498
            ].join(' ').toLowerCase();
            if (!rowStr.includes(qGlobal)) return false;
        }
        return true;
    });

    res.sort(function(a, b) {
        if (hdSortCol === 'default') {
            var rankA = getStatusRank(a.status_name);
            var rankB = getStatusRank(b.status_name);
            if (rankA !== rankB) return rankA - rankB;
            return (Number(b.id) || 0) - (Number(a.id) || 0);
        }

        if (hdSortCol === 'status_name') {
            var rankA = getStatusRank(a.status_name);
            var rankB = getStatusRank(b.status_name);
            if (rankA !== rankB) {
                return (hdSortDir === 'desc') ? (rankB - rankA) : (rankA - rankB);
            }
            return (hdSortDir === 'desc') 
                ? String(b.status_name || '').localeCompare(String(a.status_name || ''), 'hu')
                : String(a.status_name || '').localeCompare(String(b.status_name || ''), 'hu');
        }

        var valA = a[hdSortCol] || '';
        var valB = b[hdSortCol] || '';

        if (hdSortCol === 'id' || hdSortCol === 'hd_serial') {
            var numA = Number(valA) || 0;
            var numB = Number(valB) || 0;
            return (hdSortDir === 'desc') ? (numB - numA) : (numA - numB);
        }

        var comp = String(valA).localeCompare(String(valB), 'hu', { numeric: true, sensitivity: 'base' });
        return (hdSortDir === 'desc') ? -comp : comp;
    });

    filteredHelpdeskTickets = res;
    renderHelpdeskRows();
};

window.sortHdBy = function(col) {
    if (hdSortCol === col) {
        hdSortDir = (hdSortDir === 'desc') ? 'asc' : 'desc';
    } else {
        hdSortCol = col;
        hdSortDir = (col === 'id' || col === 'hd_serial' || col === 'created_on') ? 'desc' : 'asc';
    }

    document.querySelectorAll('[id^="hd_sort_"]').forEach(function(el) {
        el.innerText = '⇅';
        el.style.color = '#94a3b8';
    });
    var cur = document.getElementById('hd_sort_' + col);
    if (cur) {
        cur.innerText = (hdSortDir === 'desc') ? '▼' : '▲';
        cur.style.color = '#0284c7';
    }

    filterAndSortHelpdesk();
};

function renderHelpdeskRows() {
    var tbody = document.getElementById('hdTicketsTableBody');
    if (!tbody) return;

    var total = filteredHelpdeskTickets.length;
    var totalPages = Math.ceil(total / hdPageSize) || 1;
    if (hdPage > totalPages) hdPage = totalPages;
    if (hdPage < 1) hdPage = 1;

    var start = (hdPage - 1) * hdPageSize;
    var end = Math.min(start + hdPageSize, total);

    var pagHtml = `
        <div style="display:flex; justify-content:space-between; align-items:center; width:100%; font-size:12px;">
            <span>Megjelenítve: <b>${total > 0 ? start + 1 : 0} - ${end}</b> / <b>${total}</b> jegy</span>
            <div style="display:flex; gap:5px;">
                <button class="btn" onclick="hdPage=1; renderHelpdeskRows();" ${hdPage <= 1 ? 'disabled style="opacity:0.4"' : ''}>« Első</button>
                <button class="btn" onclick="hdPage--; renderHelpdeskRows();" ${hdPage <= 1 ? 'disabled style="opacity:0.4"' : ''}>‹ Előző</button>
                <span style="padding:2px 8px; font-weight:bold;">Oldal: ${hdPage} / ${totalPages}</span>
                <button class="btn" onclick="hdPage++; renderHelpdeskRows();" ${hdPage >= totalPages ? 'disabled style="opacity:0.4"' : ''}>Következő ›</button>
                <button class="btn" onclick="hdPage=${totalPages}; renderHelpdeskRows();" ${hdPage >= totalPages ? 'disabled style="opacity:0.4"' : ''}>Utolsó »</button>
            </div>
        </div>
    `;

    var pTop = document.getElementById('hdPaginationTop');
    var pBtm = document.getElementById('hdPaginationBottom');
    if (pTop) pTop.innerHTML = pagHtml;
    if (pBtm) pBtm.innerHTML = pagHtml;

    if (total === 0) {
        tbody.innerHTML = '<tr><td colspan="11" style="text-align:center; padding:20px; color:#94a3b8;">Nincs a szűrési feltételeknek megfelelő hibajegy.</td></tr>';
        return;
    }

    var slice = filteredHelpdeskTickets.slice(start, end);
    tbody.innerHTML = slice.map(function(t) {
        var rank = getStatusRank(t.status_name);
        var stBadgeStyle = (rank === 0) 
            ? 'background:#fef3c7; color:#b45309; border:1px solid #fde68a;' 
            : ((rank === 1) ? 'background:#dcfce7; color:#15803d; border:1px solid #bbf7d0;' : 'background:#e0f2fe; color:#0369a1;');

        var inv = t.inventory_number || t.custom_field_499;
        var invCnt = (inv && hdInvCounts[inv]) ? hdInvCounts[inv] : 0;

        var auth = t.author_name || t.author;
        var authCnt = (auth && hdAuthorCounts[auth]) ? hdAuthorCounts[auth] : 0;

        var serial = t.hd_serial || t.custom_field_545 || t.id;

        var invText = (inv && inv !== '-') 
            ? `<span style="cursor:pointer; display:inline-flex; align-items:center; gap:4px;" onclick="setHdFilter('inventory', '${escapeHtml(inv)}')" title="Szűrés erre a leltári számra (Összesen ${invCnt} db jegy)">
                <b style="color:#0284c7;">${escapeHtml(inv)}</b>
                <span style="background:#e0f2fe; color:#0369a1; padding:1px 5px; border-radius:8px; font-size:10px; font-weight:bold;">${invCnt} db</span>
               </span>`
            : '<span style="color:#94a3b8;">-</span>';

        var authText = (auth && auth !== '-')
            ? `<span style="cursor:pointer; display:inline-flex; align-items:center; gap:4px;" onclick="setHdFilter('author', '${escapeHtml(auth)}')" title="Szűrés erre a bejelentőre (Összesen ${authCnt} db jegy)">
                <b style="color:#0f172a;">${escapeHtml(auth)}</b>
                <span style="background:#f1f5f9; color:#475569; padding:1px 5px; border-radius:8px; font-size:10px; font-weight:bold;">${authCnt} db</span>
               </span>`
            : '<span style="color:#94a3b8;">-</span>';

        return `
        <tr>
            <td><b>#${escapeHtml(t.id)}</b></td>
            <td><code style="color:#0284c7; font-weight:bold;">${escapeHtml(serial)}</code></td>
            <td style="white-space:nowrap; font-size:12px; color:#64748b;">${escapeHtml(t.created_on || '-')}</td>
            <td style="font-size:12px;">${invText}</td>
            <td>${authText}</td>
            <td style="font-size:12px;">${escapeHtml(t.phone || t.custom_field_500 || '-')}</td>
            <td style="font-size:12px; color:#475569;">${escapeHtml(t.location || t.custom_field_503 || '-')}</td>
            <td><span style="${stBadgeStyle} font-weight:bold; padding:2px 7px; border-radius:10px; font-size:11px;">${escapeHtml(t.status_name || '-')}</span></td>
            <td><span style="background:#f1f5f9; padding:2px 6px; border-radius:4px; font-size:11px;">${escapeHtml(t.priority_name || 'Normál')}</span></td>
            <td style="font-size:12px;">${escapeHtml(t.subject || '-')}</td>
            <td style="text-align:right; white-space:nowrap;">
                <button class="btn" style="background:#0284c7; color:white; padding:3px 8px; font-size:11px; border-radius:4px; font-weight:bold; cursor:pointer;" onclick="openTicketModal('${t.id}')">👁️ Részletek</button>
                <button class="btn" style="background:#2563eb; color:white; padding:3px 8px; font-size:11px; border-radius:4px; margin-left:3px; font-weight:bold; cursor:pointer;" title="Azonnali küldés a Telegram csoportba" onclick="event.stopPropagation(); sendTicketToTelegramDirect('${t.id}')">📲 TG</button>
            </td>
        </tr>`;
    }).join('');
}

window.openTicketModal = function(id) {
    activeModalTicketId = id;
    var t = allHelpdeskTicketsMaster.find(function(x) { return String(x.id) === String(id); });
    if (!t) return;
    var overlay = document.getElementById('ticketModalOverlay');
    if (overlay) {
        var sorszam = t.custom_field_545 || t.hd_serial || t.id;
        safeSetText('mdl_t_title_text', `Helpdesk Jegy #${t.id} (${sorszam})`);
        safeSetText('mdl_t_serial', sorszam);
        safeSetText('mdl_t_created', t.created_on || '-');
        safeSetText('mdl_t_author', t.author_name || t.author || '-');
        safeSetText('mdl_t_phone', t.custom_field_500 || t.phone || '-');
        safeSetText('mdl_t_inventory', t.custom_field_499 || t.inventory_number || '-');
        safeSetText('mdl_t_location', t.custom_field_503 || t.location || '-');
        safeSetText('mdl_t_category', t.custom_field_498 || t.it_category || '-');
        safeSetText('mdl_t_status', t.status_name || '-');
        safeSetText('mdl_t_priority', t.priority_name || 'Normál');
        safeSetText('mdl_t_subject', t.subject || '-');

        var descBox = document.getElementById('mdl_t_description');
        var descContent = t.custom_field_530 || t.description || '';
        if (descBox) {
            if (descContent && descContent.trim() && descContent.trim() !== '-') {
                if (/<[a-z][\s\S]*>/i.test(descContent)) {
                    descBox.innerHTML = descContent;
                } else {
                    descBox.innerHTML = descContent.replace(/\n/g, '<br>');
                }
            } else {
                descBox.innerHTML = '<i style="color:#94a3b8;">Nincs külön leírás rögzítve a hibajegyhez.</i>';
            }
        }

        overlay.style.setProperty('display', 'flex', 'important');
        overlay.style.setProperty('pointer-events', 'auto', 'important');
    }
};

window.closeTicketModal = function() {
    var overlay = document.getElementById('ticketModalOverlay');
    if (overlay) {
        overlay.style.setProperty('display', 'none', 'important');
        overlay.style.setProperty('pointer-events', 'none', 'important');
    }
};

window.sendCurrentModalTicketToTelegram = function() {
    if (!activeModalTicketId) {
        alert('Nincs kiválasztva hibajegy!');
        return;
    }
    sendTicketToTelegramDirect(activeModalTicketId);
};

window.sendTicketToTelegramDirect = async function(ticketId) {
    if (!ticketId) return;
    var t = allHelpdeskTicketsMaster.find(function(x) { return String(x.id) === String(ticketId); });
    var ok = confirm(`Valóban elküldi a #${ticketId} számú hibajegyet a Telegram csoportba?`);
    if (!ok) return;

    try {
        var res = await fetch(`/api/easyproject/helpdesk/ticket/${encodeURIComponent(ticketId)}/send-telegram`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(t || {})
        });
        var data = {};
        try {
            data = await res.json();
        } catch(e) {
            data = { message: 'HTTP ' + res.status + ' válasz' };
        }

        if (res.ok && data.status === 'SUCCESS') {
            alert(`✅ ${data.message || 'Üzenet sikeresen elküldve!'}`);
        } else {
            var errMsg = data.message || data.detail || ('HTTP ' + res.status);
            alert(`❌ Hiba a küldés során: ${errMsg}`);
        }
    } catch(err) {
        alert(`❌ Hálózati hiba: ${err.message || err}`);
    }
};

// Automatikus kezdő fül aktiválás induláskor (ha még nincs aktív)
function initActiveTab() {
    if (window.initializeDataTableLayouts) window.initializeDataTableLayouts();
    var activePane = document.querySelector('.app-tab-pane.active') || document.querySelector('[id^="pane-"].active');
    if (activePane && activePane.id) {
        switchTab(activePane.id);
    } else {
        switchTab('audit');
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initActiveTab);
} else {
    initActiveTab();
}


// ==========================================================================
// 6. MENTÉSEK ÉS GIT VERZIÓKEZELÉS MOTOR
// ==========================================================================
// ==========================================================================
// MENTÉSEK, GIT ELŐZMÉNYEK, KÉPERNYŐKÉPEK ÉS FELSŐ GOMBOK MOTORJA
// ==========================================================================
// ==========================================================================
// MENTÉSEK & VERZIÓK - TELJES, MŰKÖDŐ VEZÉRLŐ ÉS GOMB MOTOR
// ==========================================================================
window.loadBackups = async function() {
    var tbody = document.getElementById('backupsTableBody');
    if (tbody) tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:15px; color:#64748b;">⏳ Mentések betöltése...</td></tr>';
    try {
        var res = await fetch('/api/backups/list');
        var data = await res.json();
        var list = data.backups || [];

        safeSetText('bk_stat_count', (data.count || list.length) + ' db');
        safeSetText('bk_stat_last', data.last_backup || '-');
        safeSetText('bk_stat_version', 'main (' + (data.git_version || 'v1.09') + ')');
        safeSetText('bk_stat_size', (data.total_size_mb || 0) + ' MB');

        if (!tbody) return;
        if (list.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:20px; color:#94a3b8;">Nincs mentés.</td></tr>';
            return;
        }

        tbody.innerHTML = list.map(function(b) {
            return '<tr style="border-bottom:1px solid #f1f5f9;">' +
                '<td style="padding:10px;"><b style="color:#0f172a; font-family:monospace; font-size:12px;">' + escapeHtml(b.filename) + '</b></td>' +
                '<td style="padding:10px; font-size:12px; color:#64748b;">' + escapeHtml(b.created_at) + '</td>' +
                '<td style="padding:10px; font-size:12px;"><span style="background:#e0f2fe; color:#0369a1; padding:2px 8px; border-radius:10px; font-weight:bold; font-size:11px;">' + b.size_mb + ' MB</span></td>' +
                '<td style="padding:10px; font-size:12px; color:#334155;">' + escapeHtml(b.comment) + '</td>' +
                '<td style="padding:10px; text-align:right; white-space:nowrap;">' +
                    '<a href="/api/backups/download/' + encodeURIComponent(b.filename) + '" class="btn" style="background:#0284c7; color:white; padding:4px 10px; font-size:11px; text-decoration:none; border-radius:4px; font-weight:bold; margin-right:6px;" download>📥 Letöltés</a>' +
                    '<button class="btn" style="background:#ef4444; color:white; padding:4px 8px; font-size:11px; border-radius:4px; border:none; cursor:pointer;" onclick="deleteBackupFile(\'' + escapeHtml(b.filename) + '\')">🗑️</button>' +
                '</td>' +
            '</tr>';
        }).join('');
    } catch(err) {
        if (tbody) tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:20px; color:#ef4444;">Hiba: ' + err.message + '</td></tr>';
    }
};

window.loadGitCommits = async function() {
    var tbody = document.getElementById('gitLogTableBody');
    if (tbody) tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:15px; color:#64748b;">⏳ Git napló betöltése...</td></tr>';
    try {
        var res = await fetch('/api/backups/git-log');
        var data = await res.json();
        var commits = data.commits || [];

        if (!tbody) return;
        if (commits.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:20px; color:#94a3b8;">Nincs megjeleníthető Git előzmény.</td></tr>';
            return;
        }

        tbody.innerHTML = commits.map(function(c) {
            var isTag = c.status && c.status.includes('🏷️');
            var isHead = c.status && c.status.includes('HEAD');
            var badgeStyle = isTag 
                ? 'background:#fef3c7; color:#b45309; border:1px solid #fde68a;' 
                : (isHead ? 'background:#dcfce7; color:#15803d; border:1px solid #bbf7d0;' : 'background:#f1f5f9; color:#475569;');

            return '<tr style="border-bottom:1px solid #f1f5f9;">' +
                '<td style="padding:10px;"><code style="background:#f1f5f9; padding:2px 6px; border-radius:4px; font-weight:bold; color:#0284c7; font-size:12px;">' + escapeHtml(c.hash) + '</code></td>' +
                '<td style="padding:10px; font-size:12px; color:#64748b; white-space:nowrap;">' + escapeHtml(c.date) + '</td>' +
                '<td style="padding:10px; font-size:12px; font-weight:600; color:#334155;">' + escapeHtml(c.author) + '</td>' +
                '<td style="padding:10px; font-size:12px; color:#0f172a;">' + escapeHtml(c.message) + '</td>' +
                '<td style="padding:10px; text-align:center;"><span style="' + badgeStyle + ' font-weight:bold; padding:2px 8px; border-radius:10px; font-size:11px;">' + escapeHtml(c.status) + '</span></td>' +
            '</tr>';
        }).join('');
    } catch(err) {
        if (tbody) tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:20px; color:#ef4444;">Hiba a Git naplónál: ' + err.message + '</td></tr>';
    }
};
window.loadGitLog = window.loadGitCommits;

window.loadScreenshots = async function() {
    var grid = document.getElementById('screenshotsGrid');
    if (grid) grid.innerHTML = '<div style="grid-column: 1 / -1; padding:20px; text-align:center; color:#64748b;">⏳ Képek betöltése...</div>';
    try {
        var res = await fetch('/api/backups/screenshots');
        var data = await res.json();
        var list = data.screenshots || [];

        if (!grid) return;
        if (list.length === 0) {
            grid.innerHTML = '<div style="grid-column: 1 / -1; padding:20px; text-align:center; color:#94a3b8;">Nincsenek képek.</div>';
            return;
        }

        grid.innerHTML = list.map(function(s) {
            return '<div style="border:1px solid #e2e8f0; border-radius:8px; overflow:hidden; background:white; box-shadow:0 1px 3px rgba(0,0,0,0.05);">' +
                '<a href="' + s.url + '" target="_blank" title="Kattintson a teljes méretű megnyitáshoz">' +
                    '<img src="' + s.url + '" alt="' + escapeHtml(s.title) + '" style="width:100%; height:130px; object-fit:cover; border-bottom:1px solid #e2e8f0; background:#0f172a;">' +
                '</a>' +
                '<div style="padding:10px 12px;">' +
                    '<div style="font-weight:700; font-size:12px; color:#0f172a; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">' + escapeHtml(s.title) + '</div>' +
                    '<div style="display:flex; justify-content:space-between; align-items:center; margin-top:5px; font-size:11px; color:#64748b;">' +
                        '<span>' + s.size_kb + ' KB</span>' +
                        '<span>' + escapeHtml(s.created_at.split(' ')[0]) + '</span>' +
                    '</div>' +
                '</div>' +
            '</div>';
        }).join('');
    } catch(err) {
        if (grid) grid.innerHTML = '<div style="grid-column: 1 / -1; padding:20px; text-align:center; color:#ef4444;">Hiba: ' + err.message + '</div>';
    }
};

// Gombok pontos bekötése
window.refreshBackups = function() {
    loadBackups();
    loadGitCommits();
    loadScreenshots();
};

window.generateSystemDoc = async function() {
    alert('📄 Rendszerleírás & AI adatforrás generálása folyamatban...');
    try {
        var res = await fetch('/api/backups/generate-doc', { method: 'POST' });
        var d = await res.json();
        alert('✅ ' + (d.message || 'Sikeres generálás!'));
    } catch(e) { alert('❌ Hiba: ' + e.message); }
};
window.generateDoc = window.generateSystemDoc;

window.takeAllScreenshots = async function() {
    alert('📸 Képernyőképek rögzítése folyamatban (mind a 10 fül rögzítése)...');
    try {
        var res = await fetch('/api/backups/screenshots/capture', { method: 'POST' });
        var d = await res.json();
        alert('✅ ' + (d.message || 'Mind a 10 fül képernyőképe sikeresen elkészült!'));
        loadScreenshots();
    } catch(e) { alert('❌ Hiba: ' + e.message); }
};
window.takeScreenshots = window.takeAllScreenshots;

window.createManualBackup = async function() {
    alert('➕ Új helyi mentés készítése folyamatban...');
    try {
        var res = await fetch('/api/backups/create', { method: 'POST' });
        var d = await res.json();
        alert('✅ ' + (d.message || 'Új mentés elkészült!'));
        loadBackups();
    } catch(e) { alert('❌ Hiba: ' + e.message); }
};
window.createNewBackup = window.createManualBackup;

window.commitGitVersion = async function() {
    var ok = confirm('Valóban készít új Git verziókiadást (+0.01 verziószám léptetés)?');
    if (!ok) return;
    try {
        var res = await fetch('/api/backups/git-version', { method: 'POST' });
        var d = await res.json();
        alert('✅ ' + (d.message || 'Sikeres verziókiadás!'));
        loadBackups();
        loadGitCommits();
    } catch(e) { alert('❌ Hiba: ' + e.message); }
};
window.commitGitVersionPrompt = window.commitGitVersion;

window.deleteBackupFile = async function(fn) {
    if (!confirm('Biztosan törli a(z) ' + fn + ' mentést?')) return;
    try {
        await fetch('/api/backups/delete/' + encodeURIComponent(fn), { method: 'DELETE' });
        loadBackups();
    } catch(e) { alert('❌ Hiba: ' + e.message); }
};


// --------------------------------------------------------------------------
// MENTÉSI MODÁL ÉS TESTRESZABHATÓ MENTÉS VEZÉRLŐ
// --------------------------------------------------------------------------
window.openNewBackupModal = function() {
    var m = document.getElementById('backupConfigModal');
    if (m) {
        m.style.setProperty('display', 'flex', 'important');
        var st = document.getElementById('bk_modal_status');
        if (st) st.style.display = 'none';
        var btn = document.getElementById('btn_start_backup_exec');
        if (btn) { btn.disabled = false; btn.innerText = '💾 Mentés Indítása'; }
    }
};

window.closeNewBackupModal = function() {
    var m = document.getElementById('backupConfigModal');
    if (m) m.style.setProperty('display', 'none', 'important');
};

window.toggleAllBackupOptions = function(checked) {
    document.querySelectorAll('.bk-sub-opt').forEach(function(cb) {
        cb.checked = checked;
    });
};

window.createManualBackup = function() {
    openNewBackupModal();
};
window.createNewBackup = function() {
    openNewBackupModal();
};

window.executeConfiguredBackup = async function() {
    var comment = (document.getElementById('bk_custom_comment')?.value || '').trim();
    var incDb = document.getElementById('bk_opt_db')?.checked || false;
    var incCode = document.getElementById('bk_opt_code')?.checked || false;
    var incConfig = document.getElementById('bk_opt_config')?.checked || false;
    var incShots = document.getElementById('bk_opt_shots')?.checked || false;

    if (!incDb && !incCode && !incConfig && !incShots) {
        alert('Legalább egy komponenst jelöljön ki a mentéshez!');
        return;
    }

    var btn = document.getElementById('btn_start_backup_exec');
    var st = document.getElementById('bk_modal_status');
    if (btn) { btn.disabled = true; btn.innerText = '⏳ Mentés folyamatban...'; }
    if (st) {
        st.style.display = 'block';
        st.style.background = '#e0f2fe';
        st.style.color = '#0369a1';
        st.innerText = 'Archívum készítése és tömörítése folyamatban, kérjük várjon...';
    }

    try {
        var res = await fetch('/api/backups/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                comment: comment,
                include_db: incDb,
                include_code: incCode,
                include_config: incConfig,
                include_screenshots: incShots
            })
        });

        var d = await res.json();
        if (res.ok && d.status === 'SUCCESS') {
            if (st) {
                st.style.background = '#dcfce7';
                st.style.color = '#15803d';
                st.innerText = '✅ ' + (d.message || 'Mentés sikeresen elkészült!');
            }
            setTimeout(function() {
                closeNewBackupModal();
                loadBackups();
            }, 1200);
        } else {
            throw new Error(d.message || d.detail || 'Hiba a mentés során');
        }
    } catch(err) {
        if (st) {
            st.style.background = '#fee2e2';
            st.style.color = '#b91c1c';
            st.innerText = '❌ Hiba: ' + err.message;
        }
        if (btn) { btn.disabled = false; btn.innerText = 'Újrapróbálás'; }
    }
};


// ==========================================================================
// BEÁLLÍTÁSOK FÜL ÉS AL-FÜLEK VEZÉRLŐ MOTOR
// ==========================================================================
// ==========================================================================
// BEÁLLÍTÁSOK FÜL ÉS AL-FÜLEK VEZÉRLŐ MOTOR
// ==========================================================================
window.switchSettingsSubTab = function(subTabId) {
    var tabs = ['connections', 'telegram', 'git', 'debug'];
    tabs.forEach(function(t) {
        var btn = document.getElementById('btn_subtab_' + t);
        var sec = document.getElementById('sec_settings_' + t);
        if (t === subTabId) {
            if (btn) {
                btn.classList.add('active');
                btn.style.setProperty('background', '#0284c7', 'important');
                btn.style.setProperty('color', '#ffffff', 'important');
                btn.style.setProperty('border', 'none', 'important');
            }
            if (sec) sec.style.setProperty('display', 'block', 'important');
        } else {
            if (btn) {
                btn.classList.remove('active');
                btn.style.setProperty('background', '#ffffff', 'important');
                btn.style.setProperty('color', '#475569', 'important');
                btn.style.setProperty('border', '1px solid #cbd5e1', 'important');
            }
            if (sec) sec.style.setProperty('display', 'none', 'important');
        }
    });
};

window.toggleSecretVisibility = function(inputId, btn) {
    var inp = document.getElementById(inputId);
    if (!inp) return;
    if (inp.type === 'password') {
        inp.type = 'text';
        if (btn) btn.innerText = '🙈';
    } else {
        inp.type = 'password';
        if (btn) btn.innerText = '👁️';
    }
};

window.loadSettings = async function() {
    try {
        var res = await fetch('/api/settings');
        if (!res.ok) return;
        var data = await res.json();

        var ep = data.easyproject || {};
        var ad = data.ad || {};
        var tg = data.telegram || {};
        var gh = data.github || {};

        var setVal = function(id, val) {
            var el = document.getElementById(id);
            if (el && val !== undefined && val !== null) el.value = val;
        };
        var setChk = function(id, val) {
            var el = document.getElementById(id);
            if (el) el.checked = Boolean(val);
        };

        // 1. Kapcsolatok
        setVal('cfg_ep_url', ep.url || '');
        setVal('cfg_ep_api_key', ep.api_key || '');
        setVal('cfg_ad_server', ad.server || '');
        setVal('cfg_ad_base_dn', ad.base_dn || '');
        setVal('cfg_ad_user', ad.bind_user || '');
        setVal('cfg_ad_password', ad.bind_password || '');

        // 2. Telegram
        setVal('cfg_tg_token', tg.bot_token || '');
        setVal('cfg_tg_chat_id', tg.chat_id || '');
        setChk('cfg_tg_notify_hd', tg.notify_helpdesk !== false);
        setChk('cfg_tg_notify_audit', tg.notify_audit !== false);

        // 3. Git
        setVal('cfg_git_repo', gh.repo_url || '');
        setVal('cfg_git_token', gh.token || '');
        setVal('cfg_git_branch', gh.branch || 'copilot/ad-tracker-v1.27-20261030');

    } catch(err) {
        console.error('Hiba a beállítások betöltésekor:', err);
    }
};

function showSettingsMsg(elemId, msg, isSuccess) {
    var el = document.getElementById(elemId);
    if (!el) return;
    el.style.display = 'block';
    el.style.background = isSuccess ? '#dcfce7' : '#fee2e2';
    el.style.color = isSuccess ? '#15803d' : '#b91c1c';
    el.style.border = isSuccess ? '1px solid #bbf7d0' : '1px solid #fecaca';
    el.style.padding = '10px 14px';
    el.style.borderRadius = '6px';
    el.style.fontSize = '12px';
    el.style.fontWeight = '600';
    el.style.marginBottom = '14px';
    el.innerText = msg;
}

window.saveConnectionsSettings = async function() {
    var payload = {
        easyproject: {
            url: document.getElementById('cfg_ep_url')?.value || '',
            api_key: document.getElementById('cfg_ep_api_key')?.value || ''
        },
        ad: {
            server: document.getElementById('cfg_ad_server')?.value || '',
            base_dn: document.getElementById('cfg_ad_base_dn')?.value || '',
            bind_user: document.getElementById('cfg_ad_user')?.value || '',
            bind_password: document.getElementById('cfg_ad_password')?.value || ''
        }
    };
    try {
        var res = await fetch('/api/settings/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        var d = await res.json();
        showSettingsMsg('status_connections', '✅ ' + (d.message || 'Kapcsolati beállítások mentve!'), true);
    } catch(e) {
        showSettingsMsg('status_connections', '❌ Hiba a mentés során: ' + e.message, false);
    }
};

window.testEpConnection = async function() {
    var btn = document.getElementById('btn_test_ep');
    if (btn) btn.innerText = '⏳ EasyProject tesztelése...';
    try {
        var res = await fetch('/api/settings/test-ep', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url: document.getElementById('cfg_ep_url')?.value || '',
                api_key: document.getElementById('cfg_ep_api_key')?.value || ''
            })
        });
        var d = await res.json();
        showSettingsMsg('status_connections', (d.status === 'SUCCESS' ? '✅ ' : '❌ ') + d.message, d.status === 'SUCCESS');
    } catch(e) {
        showSettingsMsg('status_connections', '❌ Hálózati hiba: ' + e.message, false);
    } finally {
        if (btn) btn.innerText = '🔌 Easy Project Tesztelése';
    }
};

window.testAdConnection = async function() {
    var btn = document.getElementById('btn_test_ad');
    if (btn) btn.innerText = '⏳ AD tesztelése...';
    try {
        var res = await fetch('/api/settings/test-ad', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                server: document.getElementById('cfg_ad_server')?.value || '',
                base_dn: document.getElementById('cfg_ad_base_dn')?.value || '',
                bind_user: document.getElementById('cfg_ad_user')?.value || '',
                bind_password: document.getElementById('cfg_ad_password')?.value || ''
            })
        });
        var d = await res.json();
        showSettingsMsg('status_connections', (d.status === 'SUCCESS' ? '✅ ' : '❌ ') + d.message, d.status === 'SUCCESS');
    } catch(e) {
        showSettingsMsg('status_connections', '❌ Hálózati hiba: ' + e.message, false);
    } finally {
        if (btn) btn.innerText = '🔌 AD Kapcsolat Tesztelése';
    }
};

window.saveTelegramSettings = async function() {
    var payload = {
        telegram: {
            bot_token: document.getElementById('cfg_tg_token')?.value || '',
            chat_id: document.getElementById('cfg_tg_chat_id')?.value || '',
            notify_helpdesk: document.getElementById('cfg_tg_notify_hd')?.checked ?? true,
            notify_audit: document.getElementById('cfg_tg_notify_audit')?.checked ?? true
        }
    };
    try {
        var res = await fetch('/api/settings/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        var d = await res.json();
        showSettingsMsg('status_telegram', '✅ ' + (d.message || 'Telegram beállítások elmentve!'), true);
    } catch(e) {
        showSettingsMsg('status_telegram', '❌ Hiba: ' + e.message, false);
    }
};

window.testTelegramMessage = async function() {
    var btn = document.getElementById('btn_test_tg');
    if (btn) btn.innerText = '⏳ Üzenet küldése...';
    try {
        var res = await fetch('/api/settings/test-telegram', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                bot_token: document.getElementById('cfg_tg_token')?.value || '',
                chat_id: document.getElementById('cfg_tg_chat_id')?.value || ''
            })
        });
        var d = await res.json();
        showSettingsMsg('status_telegram', (d.status === 'SUCCESS' ? '✅ ' : '❌ ') + d.message, d.status === 'SUCCESS');
    } catch(e) {
        showSettingsMsg('status_telegram', '❌ Hiba: ' + e.message, false);
    } finally {
        if (btn) btn.innerText = '📲 Teszt Üzenet Küldése';
    }
};

window.saveGitSettings = async function() {
    var payload = {
        github: {
            repo_url: document.getElementById('cfg_git_repo')?.value || '',
            token: document.getElementById('cfg_git_token')?.value || '',
            branch: document.getElementById('cfg_git_branch')?.value || 'copilot/ad-tracker-v1.27-20261030'
        }
    };
    try {
        var res = await fetch('/api/settings/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        var d = await res.json();
        showSettingsMsg('status_git', '✅ ' + (d.message || 'Git beállítások elmentve!'), true);
    } catch(e) {
        showSettingsMsg('status_git', '❌ Hiba: ' + e.message, false);
    }
};

window.testGitConnection = async function() {
    var btn = document.getElementById('btn_test_git');
    if (btn) btn.innerText = '⏳ Ellenőrzés...';
    try {
        var res = await fetch('/api/settings/test-git', { method: 'POST' });
        var d = await res.json();
        showSettingsMsg('status_git', (d.status === 'SUCCESS' ? '✅ ' : '❌ ') + d.message, d.status === 'SUCCESS');
    } catch(e) {
        showSettingsMsg('status_git', '❌ Hiba: ' + e.message, false);
    } finally {
        if (btn) btn.innerText = '🚀 Git Kapcsolat Tesztelése';
    }
};

window.runDebugCommand = async function(cmd) {
    var inputEl = document.getElementById('debug_cmd_input');
    var term = document.getElementById('debug_terminal_output');
    var commandToRun = cmd || (inputEl ? inputEl.value : '');
    if (!commandToRun) return;

    if (term) term.innerText += '\n$ ' + commandToRun + '\n⏳ Végrehajtás...';
    try {
        var res = await fetch('/api/settings/debug-exec', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command: commandToRun })
        });
        var d = await res.json();
        if (term) {
            term.innerText += '\n' + (d.output || d.message || '') + '\n';
            term.scrollTop = term.scrollHeight;
        }
    } catch(e) {
        if (term) term.innerText += '\n❌ Hiba: ' + e.message + '\n';
    }
};


// ==========================================
// EP HIBAJEGYEK STÍLUSÚ FELHASZNÁLÓI VEZÉRLŐ
// ==========================================
window.userState = {
    page: 1,
    pageSize: 50,
    sortField: 'display_name',
    sortAsc: true,
    search: '',
    status: 'ALL',
    department: 'ALL',
    title: 'ALL',
    searchTimer: null
};

window.allUsersMaster = window.allUsersMaster || [];
window.filteredUsersList = [];

// Kezdeti adatbetöltés és szűrők felépítése
window.loadUsersAndGroups = async function() {
    window.groupListState.loading = true;
    var results = await Promise.allSettled([
        fetch('/api/users/all'),
        fetch('/api/groups/all')
    ]);

    if (results[0].status === 'fulfilled' && results[0].value.ok) {
        var usersData = await results[0].value.json();
        window.allUsersMaster = usersData.users || [];

        var total = window.allUsersMaster.length;
        var active = window.allUsersMaster.filter(function(u) { return u.is_enabled !== false && u.enabled !== false; }).length;
        var disabled = total - active;

        if (document.getElementById('u_kpi_total')) document.getElementById('u_kpi_total').innerText = total + ' fő';
        if (document.getElementById('u_kpi_active')) document.getElementById('u_kpi_active').innerText = active + ' fő';
        if (document.getElementById('u_kpi_disabled')) document.getElementById('u_kpi_disabled').innerText = disabled + ' fő';
        if (document.getElementById('u_badge_cnt')) document.getElementById('u_badge_cnt').innerText = total;

        populateUserDropdownFilters();
        filterAndSortUsers();
    } else {
        var usersError = results[0].status === 'rejected'
            ? results[0].reason.message
            : 'HTTP ' + results[0].value.status;
        console.error('Hiba a felhasználók betöltésekor:', usersError);
    }

    if (results[1].status === 'fulfilled' && results[1].value.ok) {
        var groupsData = await results[1].value.json();
        window.allGroupsMaster = groupsData.groups || groupsData.data || [];
        window.groupListState.loaded = true;
        window.groupListState.error = '';
        window.updateGroupCount(window.allGroupsMaster.length);
        window.renderGroupsList();
    } else {
        var groupsError = results[1].status === 'rejected'
            ? results[1].reason.message
            : 'HTTP ' + results[1].value.status;
        window.groupListState.error = 'A csoportok betöltése sikertelen (' + groupsError + ').';
        console.error(window.groupListState.error);
        window.renderGroupsList();
    }
    window.groupListState.loading = false;
};

window.groupListState = {
    loaded: false,
    loading: false,
    error: '',
    search: '',
    sortField: 'sam_account_name',
    sortOrder: 'asc'
};
window.allGroupsMaster = window.allGroupsMaster || [];

window.dataTableLayoutDefaults = {
    users: [230, 160, 230, 180, 170, 170, 100],
    groups: [240, 160, 170, 110, 420, 120]
};
window.dataTableLayouts = JSON.parse(JSON.stringify(window.dataTableLayoutDefaults));
window.dataTableLayoutInitPromise = null;
window.dataTableLayoutSaveTimers = {};

window.initializeDataTableLayouts = function() {
    if (window.dataTableLayoutInitPromise) return window.dataTableLayoutInitPromise;
    window.dataTableLayoutInitPromise = (async function() {
        try {
            var response = await fetch('/api/users/table-layout');
            if (!response.ok) throw new Error('HTTP ' + response.status);
            var data = await response.json();
            Object.keys(window.dataTableLayoutDefaults).forEach(function(tableName) {
                var widths = data.layouts && data.layouts[tableName];
                if (Array.isArray(widths) && widths.length === window.dataTableLayoutDefaults[tableName].length &&
                    widths.every(function(width) { return Number.isInteger(width) && width >= 60 && width <= 1200; })) {
                    window.dataTableLayouts[tableName] = widths.slice();
                }
            });
        } catch (error) {
            console.error('A táblázat-oszlopszélességek betöltése nem sikerült:', error);
            window.setDataTableLayoutStatus('A mentett oszlopszélességek betöltése nem sikerült.');
        }
        Object.keys(window.dataTableLayoutDefaults).forEach(function(tableName) {
            window.applyDataTableLayout(tableName);
            window.setupDataTableResizers(tableName);
            window.setupDataTableScrollbars(tableName);
        });
    })();
    return window.dataTableLayoutInitPromise;
};

window.setDataTableLayoutStatus = function(message) {
    document.querySelectorAll('[data-table-layout-status]').forEach(function(element) {
        element.textContent = message;
    });
};

window.applyDataTableLayout = function(tableName) {
    var table = document.getElementById(tableName === 'users' ? 'usersDataTable' : 'groupsDataTable');
    if (!table) return;
    var cols = table.querySelectorAll('colgroup col');
    var widths = window.dataTableLayouts[tableName];
    widths.forEach(function(width, index) {
        if (cols[index]) cols[index].style.width = width + 'px';
    });
    table.style.width = widths.reduce(function(total, width) { return total + width; }, 0) + 'px';
    window.updateDataTableScrollbars(tableName);
};

window.setupDataTableScrollbars = function(tableName) {
    var scrollbars = document.querySelectorAll('[data-table-scroll="' + tableName + '"]');
    var viewport = document.querySelector('.data-table-scroll[data-table-scroll="' + tableName + '"]');
    if (!viewport) return;
    scrollbars.forEach(function(scrollbar) {
        if (scrollbar.dataset.syncBound === 'true') return;
        scrollbar.dataset.syncBound = 'true';
        scrollbar.addEventListener('scroll', function() {
            scrollbars.forEach(function(other) {
                if (other !== scrollbar) other.scrollLeft = scrollbar.scrollLeft;
            });
        });
    });
    if (!window.dataTableScrollResizeObserver && window.ResizeObserver) {
        window.dataTableScrollResizeObserver = new ResizeObserver(function() {
            Object.keys(window.dataTableLayoutDefaults).forEach(window.updateDataTableScrollbars);
        });
    }
    if (window.dataTableScrollResizeObserver) window.dataTableScrollResizeObserver.observe(viewport);
    window.updateDataTableScrollbars(tableName);
};

window.updateDataTableScrollbars = function(tableName) {
    var table = document.getElementById(tableName === 'users' ? 'usersDataTable' : 'groupsDataTable');
    var viewport = document.querySelector('.data-table-scroll[data-table-scroll="' + tableName + '"]');
    if (!table || !viewport) return;
    document.querySelectorAll('.table-scroll-mirror[data-table-scroll="' + tableName + '"] > div').forEach(function(inner) {
        inner.style.width = Math.max(table.scrollWidth, viewport.clientWidth) + 'px';
    });
};

window.setupDataTableResizers = function(tableName) {
    var table = document.getElementById(tableName === 'users' ? 'usersDataTable' : 'groupsDataTable');
    if (!table) return;
    var headers = table.querySelectorAll('thead th');
    headers.forEach(function(header, index) {
        if (header.querySelector('.table-column-resizer')) return;
        var handle = document.createElement('span');
        handle.className = 'table-column-resizer';
        handle.setAttribute('role', 'separator');
        handle.setAttribute('aria-orientation', 'vertical');
        handle.setAttribute('aria-label', 'Oszlopszélesség módosítása');
        header.appendChild(handle);
        handle.addEventListener('click', function(event) {
            event.preventDefault();
            event.stopPropagation();
        });
        handle.addEventListener('pointerdown', function(event) {
            event.preventDefault();
            event.stopPropagation();
            var startX = event.clientX;
            var startWidth = window.dataTableLayouts[tableName][index];
            handle.classList.add('is-resizing');
            function move(moveEvent) {
                var nextWidth = Math.max(60, Math.min(1200, Math.round(startWidth + moveEvent.clientX - startX)));
                window.dataTableLayouts[tableName][index] = nextWidth;
                window.applyDataTableLayout(tableName);
            }
            function finish() {
                handle.classList.remove('is-resizing');
                document.removeEventListener('pointermove', move);
                document.removeEventListener('pointerup', finish);
                window.persistDataTableLayout(tableName);
            }
            document.addEventListener('pointermove', move);
            document.addEventListener('pointerup', finish, { once: true });
        });
    });
};

window.persistDataTableLayout = function(tableName) {
    clearTimeout(window.dataTableLayoutSaveTimers[tableName]);
    window.dataTableLayoutSaveTimers[tableName] = setTimeout(async function() {
        try {
            var response = await fetch('/api/users/table-layout', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ layouts: { [tableName]: window.dataTableLayouts[tableName] } })
            });
            var data = await response.json();
            if (!response.ok || data.status !== 'SUCCESS') {
                throw new Error(data.detail || data.message || ('HTTP ' + response.status));
            }
            window.setDataTableLayoutStatus('Oszlopszélességek helyben elmentve.');
        } catch (error) {
            console.error('Az oszlopszélességek mentése nem sikerült:', error);
            window.setDataTableLayoutStatus('Az oszlopszélességek mentése nem sikerült: ' + error.message);
        }
    }, 250);
};

window.resetDataTableWidths = function(tableName) {
    var defaults = window.dataTableLayoutDefaults[tableName];
    if (!defaults) return;
    window.dataTableLayouts[tableName] = defaults.slice();
    window.applyDataTableLayout(tableName);
    window.persistDataTableLayout(tableName);
};

window.refreshDataTableLayoutForVisibleTab = function() {
    var tableName = document.getElementById('viewGroupsContainer')?.style.display === 'none'
        ? 'users'
        : 'groups';
    if (!window.dataTableLayoutInitPromise) {
        window.initializeDataTableLayouts().then(function() {
            window.refreshDataTableLayoutForVisibleTab();
        });
        return;
    }
    window.applyDataTableLayout(tableName);
    window.setupDataTableScrollbars(tableName);
    window.requestAnimationFrame(function() {
        window.updateDataTableScrollbars(tableName);
    });
};

window.updateGroupCount = function(count) {
    ['u_kpi_groups', 'g_badge_cnt'].forEach(function(id) {
        var element = document.getElementById(id);
        if (element) element.innerText = id === 'u_kpi_groups' ? count + ' db' : count;
    });
};

window.switchUsersSubTab = function(tab) {
    var showGroups = tab === 'groups';
    var usersView = document.getElementById('viewUsersContainer');
    var groupsView = document.getElementById('viewGroupsContainer');
    var usersButton = document.getElementById('btnSubUsers');
    var groupsButton = document.getElementById('btnSubGroups');

    if (usersView) usersView.style.display = showGroups ? 'none' : 'block';
    if (groupsView) groupsView.style.display = showGroups ? 'block' : 'none';
    if (usersButton) {
        usersButton.style.background = showGroups ? '#f1f5f9' : '#0284c7';
        usersButton.style.color = showGroups ? '#334155' : 'white';
    }
    if (groupsButton) {
        groupsButton.style.background = showGroups ? '#6366f1' : '#f1f5f9';
        groupsButton.style.color = showGroups ? 'white' : '#334155';
    }
    window.refreshDataTableLayoutForVisibleTab();

    if (showGroups && !window.groupListState.loaded && !window.groupListState.loading) {
        window.loadUsersAndGroups();
    } else if (showGroups) {
        window.renderGroupsList();
    }
};

window.filterAndSortGroups = function() {
    window.groupListState.search = (document.getElementById('groupGlobalSearch')?.value || '')
        .trim()
        .toLocaleLowerCase('hu');
    window.renderGroupsList();
};

window.sortGroupsBy = function(field) {
    var state = window.groupListState;
    if (state.sortField === field) {
        state.sortOrder = state.sortOrder === 'asc' ? 'desc' : 'asc';
    } else {
        state.sortField = field;
        state.sortOrder = 'asc';
    }
    window.renderGroupsList();
};

window.renderGroupsList = function() {
    var tbody = document.getElementById('groupsTableBody');
    if (!tbody) return;
    var state = window.groupListState;
    if (state.error) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:24px; color:#b91c1c;">' + escapeHtml(state.error) + '</td></tr>';
        return;
    }

    var query = state.search;
    var groups = (window.allGroupsMaster || []).filter(function(group) {
        return !query || (group.sam_account_name || '').toLocaleLowerCase('hu').includes(query)
            || (group.description || '').toLocaleLowerCase('hu').includes(query);
    }).slice();
    groups.sort(function(a, b) {
        var left = a[state.sortField] || '';
        var right = b[state.sortField] || '';
        if (state.sortField === 'members_count') {
            left = Number(a.members_count || 0);
            right = Number(b.members_count || 0);
            return state.sortOrder === 'asc' ? left - right : right - left;
        }
        if (state.sortField === 'when_created') {
            left = left ? new Date(left).getTime() : 0;
            right = right ? new Date(right).getTime() : 0;
            return state.sortOrder === 'asc' ? left - right : right - left;
        }
        var comparison = String(left).localeCompare(String(right), 'hu', { sensitivity: 'base' });
        return state.sortOrder === 'asc' ? comparison : -comparison;
    });

    if (!groups.length) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:24px; color:#64748b;">' +
            (query ? 'Nincs a keresésnek megfelelő csoport.' : 'Nincs megjeleníthető csoport.') + '</td></tr>';
    } else {
        tbody.innerHTML = groups.map(function(group) {
            var created = group.when_created ? new Date(group.when_created) : null;
            var createdText = created && !Number.isNaN(created.getTime())
                ? created.toLocaleDateString('hu-HU')
                : '-';
            var sam = group.sam_account_name || '-';
            return '<tr style="border-bottom:1px solid #f1f5f9;">' +
                '<td style="padding:10px 14px; font-weight:700; color:#0f172a;">' + escapeHtml(sam) + '</td>' +
                '<td style="padding:10px 14px; white-space:nowrap; color:#475569;">' + escapeHtml(createdText) + '</td>' +
                '<td style="padding:10px 14px; color:#475569;">' + escapeHtml(group.group_type || 'AD-csoport') + '</td>' +
                '<td style="padding:10px 14px; white-space:nowrap; color:#475569; font-variant-numeric:tabular-nums;">' + Number(group.members_count || 0) + '</td>' +
                '<td style="padding:10px 14px; color:#475569;">' + escapeHtml(group.description || '-') + '</td>' +
                '<td style="padding:8px 14px; text-align:right;"><button type="button" class="btn" style="background:#6366f1; color:white; padding:5px 11px;" data-group-details="' + escapeHtml(sam) + '">Részletek</button></td>' +
                '</tr>';
        }).join('');
        tbody.querySelectorAll('[data-group-details]').forEach(function(button) {
            button.addEventListener('click', function() {
                window.openGroupMembersModal(button.dataset.groupDetails);
            });
        });
    }

    var countText = query
        ? groups.length + ' találat / ' + (window.allGroupsMaster || []).length + ' csoport'
        : groups.length + ' csoport';
    ['groupPaginationTop', 'groupPaginationBottom'].forEach(function(id) {
        var element = document.getElementById(id);
        if (element) element.innerText = countText;
    });
    ['sam_account_name', 'when_created', 'group_type', 'members_count', 'description'].forEach(function(field) {
        var indicator = document.getElementById('g_sort_' + field);
        if (indicator) indicator.innerText = state.sortField === field
            ? (state.sortOrder === 'asc' ? '▲' : '▼')
            : '⇅';
    });
};

function populateUserDropdownFilters() {
    var deptCounts = {};
    var titleCounts = {};

    allUsersMaster.forEach(function(u) {
        var d = (u.department || '').trim();
        if (d && d !== '-') deptCounts[d] = (deptCounts[d] || 0) + 1;

        var t = (u.title || '').trim();
        if (t && t !== '-') titleCounts[t] = (titleCounts[t] || 0) + 1;
    });

    var deptSel = document.getElementById('userFilterDept');
    if (deptSel) {
        var dOpts = '<option value="ALL">🏢 Minden részleg (' + Object.keys(deptCounts).length + ' db)</option>';
        Object.keys(deptCounts).sort(function(a, b) { return a.localeCompare(b, 'hu'); }).forEach(function(d) {
            dOpts += '<option value="' + escapeHtml(d) + '">' + escapeHtml(d) + ' (' + deptCounts[d] + ' fő)</option>';
        });
        deptSel.innerHTML = dOpts;
    }

    var titleSel = document.getElementById('userFilterTitle');
    if (titleSel) {
        var tOpts = '<option value="ALL">💼 Minden beosztás (' + Object.keys(titleCounts).length + ' db)</option>';
        Object.keys(titleCounts).sort(function(a, b) { return a.localeCompare(b, 'hu'); }).forEach(function(t) {
            tOpts += '<option value="' + escapeHtml(t) + '">' + escapeHtml(t) + ' (' + titleCounts[t] + ' fő)</option>';
        });
        titleSel.innerHTML = tOpts;
    }
}

window.onUserSearchInput = function() {
    clearTimeout(userState.searchTimer);
    userState.searchTimer = setTimeout(function() {
        userState.search = (document.getElementById('userGlobalSearch')?.value || '').toLowerCase().trim();
        userState.page = 1;
        filterAndSortUsers();
    }, 180);
};

window.onUserFilterChange = function() {
    userState.status = document.getElementById('userFilterStatus')?.value || 'ALL';
    userState.department = document.getElementById('userFilterDept')?.value || 'ALL';
    userState.title = document.getElementById('userFilterTitle')?.value || 'ALL';
    userState.page = 1;
    filterAndSortUsers();
};

window.resetUserFilters = function() {
    userState.search = '';
    userState.status = 'ALL';
    userState.department = 'ALL';
    userState.title = 'ALL';
    userState.page = 1;

    if (document.getElementById('userGlobalSearch')) document.getElementById('userGlobalSearch').value = '';
    if (document.getElementById('userFilterStatus')) document.getElementById('userFilterStatus').value = 'ALL';
    if (document.getElementById('userFilterDept')) document.getElementById('userFilterDept').value = 'ALL';
    if (document.getElementById('userFilterTitle')) document.getElementById('userFilterTitle').value = 'ALL';

    filterAndSortUsers();
};

window.sortUsersBy = function(field) {
    if (userState.sortField === field) {
        userState.sortAsc = !userState.sortAsc;
    } else {
        userState.sortField = field;
        userState.sortAsc = true;
    }
    filterAndSortUsers();
};

window.filterAndSortUsers = function() {
    if (!allUsersMaster || allUsersMaster.length === 0) return;

    // 1. SZŰRÉS
    var filtered = allUsersMaster.filter(function(u) {
        // Keresőszó
        if (userState.search) {
            var q = userState.search;
            var n = (u.display_name || u.displayName || '').toLowerCase();
            var s = (u.sam_account_name || u.sAMAccountName || '').toLowerCase();
            var m = (u.mail || u.email || '').toLowerCase();
            var d = (u.department || '').toLowerCase();
            var t = (u.title || '').toLowerCase();
            var p = (u.telephone_number || '').toLowerCase();
            if (!n.includes(q) && !s.includes(q) && !m.includes(q) && !d.includes(q) && !t.includes(q) && !p.includes(q)) {
                return false;
            }
        }

        // Állapot szűrő
        var isAct = (u.is_enabled !== false && u.enabled !== false);
        if (userState.status === 'active' && !isAct) return false;
        if (userState.status === 'disabled' && isAct) return false;

        // Részleg szűrő
        if (userState.department !== 'ALL' && (u.department || '').trim() !== userState.department) return false;

        // Beosztás szűrő
        if (userState.title !== 'ALL' && (u.title || '').trim() !== userState.title) return false;

        return true;
    });

    // 2. RENDEZÉS
    var f = userState.sortField;
    filtered.sort(function(a, b) {
        var va = (a[f] || a['display_name'] || a['sam_account_name'] || '').toString().toLowerCase();
        var vb = (b[f] || b['display_name'] || b['sam_account_name'] || '').toString().toLowerCase();
        return userState.sortAsc ? va.localeCompare(vb, 'hu') : vb.localeCompare(va, 'hu');
    });

    window.filteredUsersList = filtered;

    // 3. RENDEZÉSI NYILAK FRISSÍTÉSE A FEJLÉCBEN
    ['display_name', 'sam_account_name', 'mail', 'department', 'title', 'last_logon'].forEach(function(col) {
        var el = document.getElementById('u_sort_' + col);
        if (el) {
            if (col === userState.sortField) {
                el.innerText = userState.sortAsc ? '▲' : '▼';
                el.style.color = '#0284c7';
            } else {
                el.innerText = '⇅';
                el.style.color = '#94a3b8';
            }
        }
    });

    // 4. LAPOZÓ SZÁMÍTÁSA ÉS RENDERELÉS
    var total = filtered.length;
    var totalPages = Math.ceil(total / userState.pageSize) || 1;
    if (userState.page > totalPages) userState.page = totalPages;
    if (userState.page < 1) userState.page = 1;

    var startIdx = (userState.page - 1) * userState.pageSize;
    var pageItems = filtered.slice(startIdx, startIdx + userState.pageSize);

    renderUsersTablePage(pageItems);
    renderUserPaginationBars(total, totalPages);
};

function renderUsersTablePage(items) {
    var tbody = document.getElementById('usersTableBody');
    if (!tbody) return;

    if (items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:35px; color:#64748b; font-size:13.5px;">🔍 Nem található a szűrésnek megfelelő munkatárs.</td></tr>';
        return;
    }

    tbody.innerHTML = items.map(function(u) {
        var sName = u.display_name || u.displayName || u.sam_account_name || '-';
        var sUser = u.sam_account_name || u.sAMAccountName || u.username || '-';
        var sMail = u.mail || u.email || '-';
        var sDept = u.department || '-';
        var sTitle = u.title || '-';
        var sLogon = u.last_logon || u.last_logon_date || '-';
        if (typeof sLogon === 'string' && sLogon.length > 16) sLogon = sLogon.substring(0, 16);

        var isAct = (u.is_enabled !== false && u.enabled !== false);
        var badge = isAct 
            ? '<span style="background:#dcfce7; color:#15803d; padding:2px 7px; border-radius:10px; font-size:10.5px; font-weight:700; margin-left:6px;">Aktív</span>'
            : '<span style="background:#fee2e2; color:#b91c1c; padding:2px 7px; border-radius:10px; font-size:10.5px; font-weight:700; margin-left:6px;">Letiltott</span>';

        var initial = sName ? sName.trim().charAt(0).toUpperCase() : 'U';

        return `<tr style="border-bottom:1px solid #f1f5f9; font-size:13px; cursor:pointer;" onclick="openUserModal('${escapeHtml(sUser)}')">
            <td style="padding:10px 14px; font-weight:700; color:#0f172a; display:flex; align-items:center; gap:8px;">
                <span style="background:#e0f2fe; color:#0284c7; width:28px; height:28px; border-radius:50%; display:inline-flex; align-items:center; justify-content:center; font-size:11.5px; font-weight:800; flex-shrink:0;">${initial}</span>
                <div>${escapeHtml(sName)}${badge}</div>
            </td>
            <td style="padding:10px 14px; font-family:monospace; color:#475569; font-weight:600;">${escapeHtml(sUser)}</td>
            <td style="padding:10px 14px; color:#0284c7;">${sMail !== '-' ? '<a href="mailto:' + escapeHtml(sMail) + '" style="color:#0284c7; text-decoration:none;">' + escapeHtml(sMail) + '</a>' : '<span style="color:#94a3b8;">-</span>'}</td>
            <td style="padding:10px 14px;"><span style="background:#f1f5f9; color:#334155; padding:3px 8px; border-radius:4px; font-weight:600; font-size:11.5px;">${escapeHtml(sDept)}</span></td>
            <td style="padding:10px 14px; color:#475569;">${escapeHtml(sTitle)}</td>
            <td style="padding:10px 14px; color:#64748b; font-size:12px;">${escapeHtml(sLogon)}</td>
            <td style="padding:10px 14px; text-align:right;">
                <button class="btn" style="background:#0284c7; color:white; border:none; padding:5px 12px; border-radius:4px; font-size:12px; font-weight:600; cursor:pointer;" onclick="event.stopPropagation(); openUserModal('${escapeHtml(sUser)}')">👁️ Részletek</button>
            </td>
        </tr>`;
    }).join('');
}

// EP stílusú lapozó sáv mind felülre, mind alulra
function renderUserPaginationBars(total, totalPages) {
    var p = userState.page;
    var start = total > 0 ? ((p - 1) * userState.pageSize) + 1 : 0;
    var end = Math.min(p * userState.pageSize, total);

    var html = `
        <div style="font-size:12.5px; color:#475569;">
            Megjelenítve: <b>${start} - ${end}</b> / <b>${total}</b> felhasználó
        </div>
        <div style="display:flex; align-items:center; gap:5px;">
            <button ${p <= 1 ? 'disabled' : ''} onclick="changeUserPage(1)" style="padding:4px 10px; border-radius:5px; border:1px solid #cbd5e1; background:${p <= 1 ? '#f1f5f9' : '#ffffff'}; color:${p <= 1 ? '#94a3b8' : '#334155'}; font-size:12px; cursor:${p <= 1 ? 'default' : 'pointer'}; font-weight:600;">« Első</button>
            <button ${p <= 1 ? 'disabled' : ''} onclick="changeUserPage(${p - 1})" style="padding:4px 10px; border-radius:5px; border:1px solid #cbd5e1; background:${p <= 1 ? '#f1f5f9' : '#ffffff'}; color:${p <= 1 ? '#94a3b8' : '#334155'}; font-size:12px; cursor:${p <= 1 ? 'default' : 'pointer'}; font-weight:600;">‹ Előző</button>
            <span style="font-size:12.5px; font-weight:700; color:#0f172a; padding:0 6px;">Oldal: ${p} / ${totalPages}</span>
            <button ${p >= totalPages ? 'disabled' : ''} onclick="changeUserPage(${p + 1})" style="padding:4px 10px; border-radius:5px; border:1px solid #cbd5e1; background:${p >= totalPages ? '#f1f5f9' : '#ffffff'}; color:${p >= totalPages ? '#94a3b8' : '#334155'}; font-size:12px; cursor:${p >= totalPages ? 'default' : 'pointer'}; font-weight:700;">Következő ›</button>
            <button ${p >= totalPages ? 'disabled' : ''} onclick="changeUserPage(${totalPages})" style="padding:4px 10px; border-radius:5px; border:1px solid #cbd5e1; background:${p >= totalPages ? '#f1f5f9' : '#ffffff'}; color:${p >= totalPages ? '#94a3b8' : '#334155'}; font-size:12px; cursor:${p >= totalPages ? 'default' : 'pointer'}; font-weight:700;">Utolsó »</button>
        </div>
    `;

    if (document.getElementById('userPaginationTop')) document.getElementById('userPaginationTop').innerHTML = html;
    if (document.getElementById('userPaginationBottom')) document.getElementById('userPaginationBottom').innerHTML = html;
}

window.changeUserPage = function(newPage) {
    userState.page = newPage;
    filterAndSortUsers();
};

// ==========================================
// RÉSZLETES MUNKATÁRSI ADATLAP (MODAL POPUP)
// ==========================================
window.openUserModal = async function(samName) {
    if (!samName || samName === 'undefined') return;

    // Megkeressük az alap adatokat a memóriából
    var u = allUsersMaster.find(function(x) {
        return (x.sam_account_name === samName || x.sAMAccountName === samName || x.username === samName);
    });

    var modal = document.getElementById('adUserFloatingModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'adUserFloatingModal';
        modal.style.cssText = 'position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(15,23,42,0.65); z-index:999999; display:flex; align-items:center; justify-content:center; padding:16px; backdrop-filter:blur(2px);';
        document.body.appendChild(modal);
    }

    modal.style.display = 'flex';
    modal.innerHTML = '<div style="background:white; padding:24px; border-radius:8px; font-weight:700; color:#0284c7;">⏳ Adatlap betöltése...</div>';

    var detailData = null;
    var groupsHtml = '<span style="color:#64748b;">⏳ Csoporttagságok betöltése...</span>';
    try {
        var gRes = await fetch('/api/users/' + encodeURIComponent(samName) + '/detail');
        if (!gRes.ok) {
            throw new Error('HTTP ' + gRes.status);
        }
        detailData = await gRes.json();
        var grps = Array.isArray(detailData.groups) ? detailData.groups : [];
        if (grps.length > 0) {
            groupsHtml = grps.map(function(g) {
                var gn = typeof g === 'object' ? (g.name || g.sam_account_name || '-') : g;
                var isDistributionList = typeof g === 'object' && g.membership_type === 'distribution_list';
                var typeLabel = isDistributionList
                    ? 'Terjesztési lista'
                    : (typeof g === 'object' && g.membership_type === 'security_group' ? 'Biztonsági csoport' : 'AD-csoport');
                var colors = isDistributionList
                    ? 'background:#f3e8ff; color:#7e22ce;'
                    : 'background:#e0f2fe; color:#0369a1;';
                return '<button type="button" data-group-name="' + escapeHtml(gn) + '" title="Kattintson a csoport tagjainak megtekintéséhez" style="' + colors + ' padding:4px 9px; border:0; border-radius:5px; font-size:12px; font-weight:600; margin:3px; display:inline-block; cursor:pointer;">' + (isDistributionList ? '📧 ' : '🏢 ') + escapeHtml(gn) + ' <small>(' + typeLabel + ')</small></button>';
            }).join('');
        } else {
            groupsHtml = '<span style="color:#64748b;">Nincs szinkronizált csoporttagság.</span>';
        }
    } catch(e) {
        groupsHtml = '<span style="color:#b91c1c;">A csoporttagságok betöltése sikertelen (' + escapeHtml(e.message) + '). Frissítse az adatokat, vagy ellenőrizze a szinkronizálást.</span>';
    }

    var userData = detailData && detailData.user ? detailData.user : (u || {});
    var isAct = userData.is_enabled !== false;
    var dName = userData.display_name || u?.display_name || u?.displayName || samName;
    var knownLabels = {
        object_guid: 'AD objektum GUID',
        sam_account_name: 'Felhasználónév (SAM)',
        display_name: 'Megjelenítendő név',
        mail: 'E-mail cím',
        is_enabled: 'Fiók engedélyezve',
        distinguished_name: 'Distinguished Name',
        first_name: 'Keresztnév',
        last_name: 'Vezetéknév',
        description: 'Leírás',
        office: 'Iroda',
        title: 'Beosztás',
        department: 'Részleg / osztály',
        company: 'Cég',
        telephone_number: 'Telefonszám',
        mobile: 'Mobiltelefon',
        object_sid: 'SID',
        last_logon_date: 'Utolsó bejelentkezés',
        user_status: 'Felhasználói státusz',
        ou_path: 'Szervezeti egység útvonala',
        source_type: 'Adatforrás típusa',
        source_ref: 'Adatforrás hivatkozása',
        user_principal_name: 'Bejelentkezési név (UPN)',
        user_account_control: 'AD fiókvezérlő érték',
        pwd_last_set: 'Jelszó utolsó beállítása',
        last_logon_timestamp: 'AD utolsó bejelentkezési időbélyeg',
        first_seen_at: 'Első észlelés',
        last_seen_at: 'Utolsó észlelés',
        when_created: 'AD létrehozás dátuma',
        when_changed: 'AD módosítás dátuma',
        last_synced_at: 'Utolsó adatbázis-szinkron'
    };
    var userAttributes = Object.entries(userData).filter(function(entry) {
        return entry[1] !== null && entry[1] !== undefined && entry[1] !== '';
    });
    var sid = userData.object_sid;
    var userAttributesHtml = userAttributes.map(function(entry) {
        var key = entry[0];
        var value = entry[1];
        if (key === 'object_sid') return '';
        if (typeof value === 'boolean' && key === 'is_enabled') value = value ? 'Igen' : 'Nem';
        if (typeof value === 'string' && /(_at|_date|_set)$/.test(key)) {
            var parsedDate = new Date(value);
            if (!Number.isNaN(parsedDate.getTime())) value = parsedDate.toLocaleString('hu-HU');
        }
        var label = knownLabels[key] || key.replace(/_/g, ' ').replace(/\b\w/g, function(letter) { return letter.toUpperCase(); });
        return '<div style="min-width:0; padding:9px 11px; background:white; border:1px solid #e2e8f0; border-radius:6px;"><small style="display:block; color:#64748b; font-size:10.5px;">' + escapeHtml(label) + '</small><b style="display:block; margin-top:3px; color:#0f172a; font-size:12px; overflow-wrap:anywhere;">' + escapeHtml(value) + '</b></div>';
    }).join('');

    modal.innerHTML = `
    <div style="background:white; border-radius:12px; width:100%; max-width:900px; box-shadow:0 25px 50px -12px rgba(0,0,0,0.35); overflow:hidden; animation:fadeIn 0.15s ease-out;">
        <div style="background:#0284c7; color:white; padding:16px 22px; display:flex; justify-content:space-between; align-items:center;">
            <div style="font-weight:800; font-size:17px; display:flex; align-items:center; gap:10px;">
                <span style="font-size:22px;">👤</span> ${escapeHtml(dName)}
            </div>
            <button onclick="document.getElementById('adUserFloatingModal').style.display='none'" style="background:transparent; border:none; color:white; font-size:22px; font-weight:bold; cursor:pointer;">✕</button>
        </div>
        <div style="padding:22px; display:flex; flex-direction:column; gap:14px; font-size:13.5px; max-height:75vh; overflow-y:auto;">
            ${sid ? '<div style="padding:13px 15px; background:#eff6ff; border:2px solid #60a5fa; border-radius:8px;"><span style="display:block; color:#1e40af; font-size:11px; font-weight:700;">🔐 AD SECURITY IDENTIFIER (SID)</span><code style="display:block; margin-top:5px; color:#0f172a; font-size:14px; font-weight:800; overflow-wrap:anywhere;">' + escapeHtml(sid) + '</code></div>' : '<div style="padding:10px 12px; background:#fff7ed; border:1px solid #fdba74; border-radius:7px; color:#9a3412;">Ehhez a felhasználóhoz nincs SID eltárolva az adatbázisban.</div>'}
            <section>
                <span style="font-weight:700; color:#0f172a; display:block; margin-bottom:8px;">Az adatbázisban tárolt felhasználói adatok (${userAttributes.length} mező)</span>
                <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:8px; padding:12px; background:#f8fafc; border-radius:8px; border:1px solid #e2e8f0;">
                    ${userAttributesHtml || '<span style="color:#64748b;">Nincs elérhető adat.</span>'}
                </div>
            </section>
            <div>
                <span style="font-weight:700; color:#0f172a; display:block; margin-bottom:8px;">👥 Active Directory Csoporttagságok:</span>
                <div style="display:flex; flex-wrap:wrap; gap:4px; max-height:160px; overflow-y:auto; padding:4px; background:#fafafa; border-radius:6px; border:1px solid #f1f5f9;">
                    ${groupsHtml}
                </div>
            </div>
        </div>
        <div style="background:#f1f5f9; padding:12px 22px; text-align:right; border-top:1px solid #e2e8f0;">
            <button onclick="document.getElementById('adUserFloatingModal').style.display='none'" style="background:#64748b; color:white; border:none; padding:8px 18px; border-radius:6px; cursor:pointer; font-weight:600; font-size:13px;">Bezárás</button>
        </div>
    </div>`;
    modal.querySelectorAll('[data-group-name]').forEach(function(button) {
        button.addEventListener('click', function(event) {
            event.preventDefault();
            event.stopPropagation();
            window.openGroupMembersModal(button.dataset.groupName);
        });
    });
};

window.openGroupMembersModal = function(groupName) {
    if (!groupName) return;

    var overlay = document.getElementById('adGroupMembersOverlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'adGroupMembersOverlay';
        overlay.style.cssText = 'position:fixed; inset:0; z-index:1000000; display:flex; align-items:center; justify-content:center; padding:16px; background:rgba(15,23,42,0.68); backdrop-filter:blur(2px);';
        document.body.appendChild(overlay);
    }
    overlay.style.display = 'flex';

    window.groupMembersState = {
        groupName: groupName,
        groupPath: [groupName],
        group: null,
        members: [],
        selectedIdentity: null,
        offset: 0,
        nextOffset: 0,
        filteredCount: 0,
        memberCount: 0,
        query: '',
        sortField: 'display_name',
        sortOrder: 'asc',
        requestId: 0,
        error: ''
    };

    overlay.innerHTML = `
        <section style="background:white; width:min(1100px,100%); max-height:92vh; display:flex; flex-direction:column; border-radius:12px; box-shadow:0 25px 60px rgba(0,0,0,.35); overflow:hidden;">
            <header style="display:flex; justify-content:space-between; align-items:center; gap:12px; padding:16px 20px; color:white; background:#4338ca;">
                <div><small style="opacity:.85;">Active Directory csoport / terjesztési lista</small><h2 id="groupMembersTitle" style="margin:3px 0 0; font-size:19px;">${escapeHtml(groupName)}</h2></div>
                <button type="button" onclick="document.getElementById('adGroupMembersOverlay').style.display='none'" aria-label="Bezárás" style="border:0; background:transparent; color:white; font-size:26px; cursor:pointer;">✕</button>
            </header>
            <div id="groupMembersBody" style="padding:16px; overflow:auto;">
                <div style="padding:26px; text-align:center; color:#64748b;">⏳ A csoport és a tagok adatainak betöltése...</div>
            </div>
        </section>`;
    overlay.onclick = function(event) {
        if (event.target === overlay) overlay.style.display = 'none';
    };
    window.loadGroupMembersPage(true);
};

window.loadGroupMembersPage = async function(reset) {
    var state = window.groupMembersState;
    var body = document.getElementById('groupMembersBody');
    if (!state || !body) return;
    if (reset) {
        state.members = [];
        state.offset = 0;
        state.nextOffset = 0;
        state.selectedIdentity = null;
        state.error = '';
    }

    var requestId = ++state.requestId;
    var params = new URLSearchParams({
        limit: '100',
        offset: String(reset ? 0 : state.nextOffset),
        q: state.query,
        sort_by: state.sortField,
        sort_order: state.sortOrder
    });
    try {
        var currentGroup = state.groupPath[state.groupPath.length - 1];
        var response = await fetch('/api/groups/' + encodeURIComponent(currentGroup) + '/detail?' + params.toString());
        if (!response.ok) throw new Error('HTTP ' + response.status);
        var data = await response.json();
        if (requestId !== state.requestId) return;
        state.group = data.group;
        state.memberCount = data.member_count || 0;
        state.filteredCount = data.filtered_count || 0;
        state.nextOffset = data.next_offset;
        state.members = reset ? (data.members || []) : state.members.concat(data.members || []);
        if (!state.selectedIdentity && state.members.length) {
            state.selectedIdentity = state.members[0].entity_type + ':' + state.members[0].guid;
        }
        state.error = '';
        window.renderGroupMembersModal();
    } catch (error) {
        if (requestId !== state.requestId) return;
        state.error = 'A csoporttagok lekérése nem sikerült: ' + error.message;
        window.renderGroupMembersModal();
    }
};

window.searchGroupMembers = function() {
    var input = document.getElementById('groupMemberSearch');
    if (!window.groupMembersState || !input) return;
    window.groupMembersState.query = input.value.trim();
    window.loadGroupMembersPage(true);
};

window.sortGroupMembersBy = function(field) {
    var state = window.groupMembersState;
    if (!state) return;
    if (state.sortField === field) {
        state.sortOrder = state.sortOrder === 'asc' ? 'desc' : 'asc';
    } else {
        state.sortField = field;
        state.sortOrder = 'asc';
    }
    window.loadGroupMembersPage(true);
};

window.openNestedGroupMembers = function(groupName) {
    var state = window.groupMembersState;
    if (!state || !groupName) return;
    state.groupPath.push(groupName);
    state.groupName = groupName;
    state.group = null;
    state.query = '';
    window.loadGroupMembersPage(true);
};

window.navigateGroupMembersPath = function(index) {
    var state = window.groupMembersState;
    if (!state || index < 0 || index >= state.groupPath.length) return;
    state.groupPath = state.groupPath.slice(0, index + 1);
    state.groupName = state.groupPath[index];
    state.group = null;
    state.query = '';
    window.loadGroupMembersPage(true);
};

window.selectGroupMember = function(entityType, guid) {
    if (!window.groupMembersState) return;
    window.groupMembersState.selectedIdentity = entityType + ':' + guid;
    window.renderGroupMembersModal();
};

window.renderGroupMembersModal = function() {
    var state = window.groupMembersState;
    var body = document.getElementById('groupMembersBody');
    if (!state || !body) return;

    var group = state.group || {};
    var selected = state.members.find(function(member) {
        return member.entity_type + ':' + member.guid === state.selectedIdentity;
    });
    var profileFields = selected ? (selected.entity_type === 'group' ? [
        ['Csoport neve', selected.display_name],
        ['Csoport típusa', selected.group_type],
        ['Csoport SAM-azonosítója', selected.sam_account_name],
        ['SID', selected.object_sid],
        ['Leírás', selected.description],
        ['Distinguished Name', selected.distinguished_name],
        ['Létrehozva', selected.when_created],
        ['Módosítva', selected.when_changed],
        ['Csoporttagság kezdete', selected.assigned_at],
        ['Utolsó szinkron', selected.last_synced_at]
    ] : [
        ['Megjelenítendő név', selected.display_name],
        ['Felhasználónév (SAM)', selected.sam_account_name],
        ['SID', selected.object_sid],
        ['Email cím', selected.mail],
        ['Bejelentkezési név', selected.user_principal_name],
        ['Fiók állapota', selected.is_enabled ? (selected.user_status || 'Aktív') : 'Letiltva'],
        ['Beosztás', selected.title],
        ['Részleg', selected.department],
        ['Cég', selected.company],
        ['Iroda', selected.office],
        ['Telefonszám', selected.telephone_number],
        ['Mobil', selected.mobile],
        ['Utolsó bejelentkezés', selected.last_logon_date],
        ['Létrehozva', selected.when_created],
        ['Módosítva', selected.when_changed],
        ['Csoporttagság kezdete', selected.assigned_at],
        ['AD útvonal', selected.ou_path],
        ['Leírás', selected.description],
        ['Distinguished Name', selected.distinguished_name],
        ['Utolsó szinkron', selected.last_synced_at]
    ]).filter(function(field) { return field[1] !== null && field[1] !== undefined && String(field[1]).trim() !== ''; }) : [];

    var profileHtml = selected
        ? '<div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:9px;">' + profileFields.map(function(field) {
            var value = field[1];
            if (['Utolsó bejelentkezés', 'Létrehozva', 'Módosítva', 'Csoporttagság kezdete', 'Utolsó szinkron'].includes(field[0])) {
                var parsed = new Date(value);
                if (!Number.isNaN(parsed.getTime())) value = parsed.toLocaleString('hu-HU');
            }
            return '<div style="min-width:0; padding:8px 10px; background:white; border:1px solid #e2e8f0; border-radius:6px;"><small style="display:block; color:#64748b; font-size:10.5px;">' + escapeHtml(field[0]) + '</small><b style="display:block; margin-top:3px; color:#0f172a; font-size:12px; overflow-wrap:anywhere;">' + escapeHtml(value) + '</b></div>';
        }).join('') + '</div>'
        : '<div style="padding:16px; color:#64748b; background:#f8fafc; border-radius:6px;">' + (state.members.length ? 'Válasszon egy tagot a listából a részletes adatok megjelenítéséhez.' : 'Nincs megjeleníthető tag.') + '</div>';

    var memberRows = state.members.map(function(member) {
        var identity = member.entity_type + ':' + member.guid;
        var active = identity === state.selectedIdentity;
        var assignedAt = member.assigned_at ? new Date(member.assigned_at) : null;
        var assignedLabel = assignedAt && !Number.isNaN(assignedAt.getTime()) ? assignedAt.toLocaleString('hu-HU') : '-';
        var entityLabel = member.entity_type === 'group' ? 'Csoport · ' + (member.group_type || 'AD-csoport') : 'Felhasználó';
        var status = member.entity_type === 'group' ? '—' : (member.is_enabled ? 'Aktív' : 'Letiltva');
        var statusColor = member.entity_type === 'group' ? '#64748b' : (member.is_enabled ? '#15803d' : '#b91c1c');
        var handler = member.entity_type === 'group'
            ? 'data-nested-group="' + escapeHtml(member.sam_account_name) + '"'
            : 'data-member-guid="' + escapeHtml(member.guid) + '"';
        return '<button type="button" ' + handler + ' style="width:100%; display:grid; grid-template-columns:minmax(130px,1.05fr) minmax(155px,1.2fr) minmax(120px,.9fr) minmax(150px,1.2fr) minmax(90px,.65fr) minmax(145px,1fr); gap:10px; align-items:center; text-align:left; border:0; border-bottom:1px solid #e2e8f0; padding:10px 12px; cursor:pointer; background:' + (active ? '#eef2ff' : 'white') + '; color:#0f172a;"><span style="color:' + (member.entity_type === 'group' ? '#6d28d9' : '#475569') + '; font-size:11px; font-weight:700;">' + (member.entity_type === 'group' ? '📂 ' : '👤 ') + escapeHtml(entityLabel) + (member.entity_type === 'group' ? ' →' : '') + '</span><b>' + escapeHtml(member.display_name || member.sam_account_name) + '</b><span style="font-family:monospace; color:#475569;">' + escapeHtml(member.sam_account_name || '-') + '</span><span style="color:#0369a1; overflow-wrap:anywhere;">' + escapeHtml(member.mail || '-') + '</span><span style="color:' + statusColor + ';">' + status + '</span><span style="color:#475569;">' + escapeHtml(assignedLabel) + '</span></button>';
    }).join('');

    var headers = [
        ['entity_type', 'Entitás típusa'],
        ['display_name', 'Megjelenítendő név'],
        ['sam_account_name', 'SAM fiók'],
        ['mail', 'Email'],
        ['is_enabled', 'Állapot'],
        ['assigned_at', 'Tagság kezdete']
    ];
    var headerHtml = headers.map(function(header) {
        var active = state.sortField === header[0];
        var direction = active ? (state.sortOrder === 'asc' ? '▲' : '▼') : '↕';
        return '<button type="button" onclick="window.sortGroupMembersBy(\'' + header[0] + '\')" aria-label="Rendezés: ' + escapeHtml(header[1]) + '" aria-sort="' + (active ? (state.sortOrder === 'asc' ? 'ascending' : 'descending') : 'none') + '" style="border:0; padding:0; background:transparent; color:' + (active ? '#3730a1' : '#475569') + '; font-size:11px; font-weight:700; text-align:left; cursor:pointer;">' + escapeHtml(header[1]) + ' <span aria-hidden="true">' + direction + '</span></button>';
    }).join('');

    var breadcrumbsHtml = state.groupPath.length > 1
        ? '<nav aria-label="Csoport útvonal" style="display:flex; flex-wrap:wrap; gap:5px; margin-bottom:10px; font-size:12px;">' + state.groupPath.map(function(pathGroup, index) {
            return (index ? '<span style="color:#94a3b8;">›</span>' : '') + '<button type="button" data-group-path-index="' + index + '" style="border:0; padding:2px 4px; background:transparent; color:' + (index === state.groupPath.length - 1 ? '#312e81' : '#4338ca') + '; font-weight:' + (index === state.groupPath.length - 1 ? '700' : '500') + '; cursor:pointer;">' + escapeHtml(pathGroup) + '</button>';
        }).join('') + '</nav>'
        : '';

    body.innerHTML = `
        ${breadcrumbsHtml}
        <div style="display:flex; flex-wrap:wrap; gap:14px; align-items:start; justify-content:space-between; margin-bottom:14px; padding:12px 14px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px;">
            <div style="min-width:260px; flex:1;"><b style="font-size:13px;">${escapeHtml(group.sam_account_name || state.groupPath[state.groupPath.length - 1] || '')} · ${escapeHtml(group.group_type || 'AD-csoport')}</b><div style="margin-top:5px; color:#475569; font-size:12px;">${escapeHtml(group.description || 'Nincs leírás')}</div><small style="display:block; margin-top:5px; color:#64748b; overflow-wrap:anywhere;">${escapeHtml(group.distinguished_name || '')}</small></div>
            <div style="font-size:13px; font-weight:700; color:#4338ca;">${state.memberCount} tag</div>
        </div>
        ${state.error ? '<div role="alert" style="padding:12px; margin-bottom:12px; color:#b91c1c; background:#fef2f2; border-radius:6px;">' + escapeHtml(state.error) + '</div>' : ''}
        <div style="display:flex; gap:8px; margin-bottom:10px;">
            <input id="groupMemberSearch" type="search" value="${escapeHtml(state.query)}" placeholder="Keresés név, SAM, email vagy SID alapján..." onkeydown="if(event.key==='Enter') window.searchGroupMembers()" style="flex:1; min-width:150px; margin:0; padding:8px 10px;">
            <button type="button" onclick="window.searchGroupMembers()" style="border:0; border-radius:5px; padding:7px 13px; background:#4338ca; color:white; cursor:pointer;">Keresés</button>
        </div>
        <div style="display:grid; grid-template-columns:minmax(130px,1.05fr) minmax(155px,1.2fr) minmax(120px,.9fr) minmax(150px,1.2fr) minmax(90px,.65fr) minmax(145px,1fr); gap:10px; padding:8px 12px; color:#475569; background:#f1f5f9; font-size:11px; font-weight:700;">${headerHtml}</div>
        <div style="max-height:34vh; overflow:auto; border:1px solid #e2e8f0; border-top:0; border-radius:0 0 7px 7px; margin-bottom:14px;">
            ${memberRows || '<div style="padding:18px; text-align:center; color:#64748b;">Nincs a keresésnek megfelelő csoporttag.</div>'}
        </div>
        <section style="padding:12px; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:8px;">
            <div style="margin-bottom:9px; font-weight:700; color:#0f172a;">👤 Kijelölt tag részletes AD-adatai</div>
            ${profileHtml}
        </section>
        <div style="display:flex; justify-content:space-between; align-items:center; gap:8px; padding-top:10px; color:#64748b; font-size:12px;">
            <span>Találat: ${state.filteredCount} / ${state.memberCount}</span>
            ${state.nextOffset !== null && state.nextOffset !== undefined ? '<button type="button" onclick="window.loadGroupMembersPage(false)" style="border:1px solid #cbd5e1; border-radius:5px; padding:6px 12px; background:white; cursor:pointer;">További tagok betöltése</button>' : ''}
        </div>`;
    body.querySelectorAll('[data-member-guid]').forEach(function(button) {
        button.addEventListener('click', function() {
            window.selectGroupMember('user', button.dataset.memberGuid);
        });
    });
    body.querySelectorAll('[data-nested-group]').forEach(function(button) {
        button.addEventListener('click', function() {
            window.openNestedGroupMembers(button.dataset.nestedGroup);
        });
    });
    body.querySelectorAll('[data-group-path-index]').forEach(function(button) {
        button.addEventListener('click', function() {
            window.navigateGroupMembersPath(Number(button.dataset.groupPathIndex));
        });
    });
};
