// ==========================================================================
// TABS CORE PRESENTATION CONTROLLER (ARANY REFERENCIA-MINTA ALAPJÁN)
// ==========================================================================

window.TabsCore = {
    // 1. FELHASZNÁLÓK ÉS CSOPORTOK MODUL
    loadUsers: async function() {
        var tbody = document.getElementById('users_table_body') || document.getElementById('users_tbody') || document.querySelector('#users table tbody');
        try {
            var res = await fetch('/api/users');
            if (!res.ok) return;
            var data = await res.json();
            var list = data.users || data.data || [];

            // KPI számlálók frissítése
            var setTxt = function(id, v) { var e = document.getElementById(id); if (e) e.innerText = v; };
            setTxt('kpi_total_users', data.total_count || list.length);
            setTxt('kpi_active_users', data.active_count || list.filter(function(u){ return u.is_enabled; }).length);
            setTxt('kpi_disabled_users', data.disabled_count || list.filter(function(u){ return !u.is_enabled; }).length);

            if (tbody && list.length > 0) {
                tbody.innerHTML = list.slice(0, 100).map(function(u) {
                    var statusBadge = u.is_enabled ? 
                        '<span style="background:#dcfce7; color:#15803d; padding:2px 8px; border-radius:10px; font-weight:700; font-size:11px;">Aktív</span>' : 
                        '<span style="background:#fee2e2; color:#dc2626; padding:2px 8px; border-radius:10px; font-weight:700; font-size:11px;">Letiltva</span>';
                    
                    var groupsHtml = (u.groups || []).slice(0, 3).map(function(g) {
                        return '<span class="group-tag">' + g + '</span>';
                    }).join('') + ((u.groups && u.groups.length > 3) ? ' <small style="color:#64748b;">(+' + (u.groups.length - 3) + ')</small>' : '');

                    return '<tr>' +
                        '<td style="font-weight:700; color:#0f172a;">' + (u.display_name || '-') + '</td>' +
                        '<td style="font-family:monospace; color:#0284c7;">' + (u.sam_account_name || '-') + '</td>' +
                        '<td>' + (u.mail || '-') + '</td>' +
                        '<td>' + (u.title || '-') + '</td>' +
                        '<td>' + (u.department || '-') + '</td>' +
                        '<td>' + statusBadge + '</td>' +
                        '<td>' + (u.last_logon || '-') + '</td>' +
                        '<td>' + (groupsHtml || '-') + '</td>' +
                    '</tr>';
                }).join('');
            }
        } catch(e) {
            console.warn('TabsCore.loadUsers hiba:', e);
        }
    },

    // 2. SZINKRONIZÁLÁSI NAPLÓ MODUL
    loadSyncHistory: async function() {
        var tbody = document.getElementById('sync_history_tbody') || document.querySelector('#sync table tbody');
        try {
            var res = await fetch('/api/sync-history');
            if (!res.ok) return;
            var data = await res.json();
            var logs = data.logs || data.history || data.data || [];

            if (tbody && logs.length > 0) {
                tbody.innerHTML = logs.map(function(l) {
                    var isSucc = (l.status || '').toUpperCase().includes('SIKER') || (l.status || '').toUpperCase().includes('SUCC');
                    var badge = isSucc ? 
                        '<span style="background:#dcfce7; color:#15803d; padding:3px 8px; border-radius:10px; font-weight:700; font-size:11px;">Sikeres</span>' : 
                        '<span style="background:#fee2e2; color:#dc2626; padding:3px 8px; border-radius:10px; font-weight:700; font-size:11px;">Hiba</span>';

                    return '<tr>' +
                        '<td style="font-family:monospace;">' + (l.started_at || l.start_time || '-') + '</td>' +
                        '<td style="font-weight:600; color:#0f172a;">' + (l.source || '-') + '</td>' +
                        '<td>' + (l.duration || (l.duration_seconds + ' mp') || '-') + '</td>' +
                        '<td>' + (l.trigger || l.trigger_type || '-') + '</td>' +
                        '<td>' + badge + '</td>' +
                        '<td style="color:#475569;">' + (l.details || '-') + '</td>' +
                    '</tr>';
                }).join('');
            }
        } catch(e) {
            console.warn('TabsCore.loadSyncHistory hiba:', e);
        }
    },

    // 3. AD VÁLTOZÁSKÖVETŐ ANALITIKA MODUL
    loadAdAnalytics: async function() {
        try {
            var res = await fetch('/api/ad-analytics/summary');
            if (!res.ok) return;
            var data = await res.json();

            var counts = data.summary_counts || {};
            var setTxt = function(id, v) { var e = document.getElementById(id); if (e) e.innerText = v; };
            setTxt('kpi_ad_24h', counts.c_24h || 0);
            setTxt('kpi_ad_72h', counts.c_72h || 0);
            setTxt('kpi_ad_168h', counts.c_168h || 0);
            setTxt('kpi_ad_30d', counts.c_30d || 0);

            var tbody = document.getElementById('ad_daily_breakdown_tbody') || document.querySelector('#ad_analytics table tbody');
            var daily = data.daily_breakdown || [];
            if (tbody && daily.length > 0) {
                tbody.innerHTML = daily.map(function(d) {
                    return '<tr>' +
                        '<td style="font-weight:700;">' + (d.date || '-') + '</td>' +
                        '<td style="font-weight:800; color:#0284c7;">' + (d.total || 0) + '</td>' +
                        '<td style="color:#16a34a; font-weight:700;">+' + (d.added_to_group || 0) + '</td>' +
                        '<td style="color:#dc2626; font-weight:700;">-' + (d.removed_from_group || 0) + '</td>' +
                        '<td style="color:#7c3aed;">' + (d.user_lifecycle || 0) + '</td>' +
                        '<td style="font-size:11.5px; color:#64748b;">' + ((d.affected_users || []).slice(0, 3).join(', ') || '-') + '</td>' +
                    '</tr>';
                }).join('');
            }
        } catch(e) {
            console.warn('TabsCore.loadAdAnalytics hiba:', e);
        }
    },

    // 4. TELEMETRIA ÉS RENDSZERÁLLAPOT MODUL
    loadTelemetry: async function() {
        if (window.refreshTelemetryLive) {
            window.refreshTelemetryLive();
        }
    },

    init: function() {
        var self = this;
        // Minden fülváltásnál megbízhatóan betöltjük az adott modult
        document.querySelectorAll('.tab, .app-nav-btn').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var txt = (btn.innerText || '').toLowerCase();
                if (txt.includes('felhasználó') || txt.includes('csoport')) setTimeout(self.loadUsers, 50);
                if (txt.includes('szinkron')) setTimeout(self.loadSyncHistory, 50);
                if (txt.includes('ad változás') || txt.includes('elemző')) setTimeout(self.loadAdAnalytics, 50);
                if (txt.includes('telemetria') || txt.includes('rendszerállapot')) setTimeout(self.loadTelemetry, 50);
            });
        });

        // Kezdő futtatás
        setTimeout(function() {
            self.loadUsers();
            self.loadSyncHistory();
            self.loadAdAnalytics();
            self.loadTelemetry();
        }, 300);
    }
};

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() { window.TabsCore.init(); });
} else {
    window.TabsCore.init();
}
