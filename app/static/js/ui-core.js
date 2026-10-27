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
    else if (shortId === 'users' && window.loadUsersAndGroups) loadUsersAndGroups();
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
    tbody.innerHTML = allUsersMaster.slice(0, 50).map(function(u) {
        return `<tr>
            <td><b>${escapeHtml(u.sAMAccountName || u.username)}</b></td>
            <td>${escapeHtml(u.displayName || u.name || '-')}</td>
            <td>${escapeHtml(u.mail || u.email || '-')}</td>
            <td><span style="font-size:11px;">${escapeHtml(u.department || '-')}</span></td>
            <td><button class="btn" style="padding:2px 8px; font-size:11px;" onclick="openUserModal('${u.sAMAccountName}')">Részletek</button></td>
        </tr>`;
    }).join('');
}

window.openUserModal = function(uName) {
    var u = allUsersMaster.find(function(x) { return x.sAMAccountName === uName; });
    if (!u) return;
    safeSetText('mdl_u_sam', u.sAMAccountName);
    safeSetText('mdl_u_name', u.displayName);
    safeSetText('mdl_u_mail', u.mail);
    var o = document.getElementById('userModalOverlay');
    if (o) o.style.display = 'flex';
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
        setVal('cfg_git_branch', gh.branch || 'main');

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
            branch: document.getElementById('cfg_git_branch')?.value || 'main'
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
