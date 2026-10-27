
// ==========================================================================
// AD TRACKER - BEÁLLÍTÁSOK KÁRTYÁK MŰVELETI MOTORJA
// ==========================================================================

window.toggleSecretVisibility = function(id, btn) {
    var el = document.getElementById(id);
    if (!el) return;
    if (el.type === 'password') {
        el.type = 'text';
        if (btn) btn.innerText = '🙈';
    } else {
        el.type = 'password';
        if (btn) btn.innerText = '👁️';
    }
};

window.showCardStatus = function(elemId, msg, isSuccess) {
    var el = document.getElementById(elemId);
    if (!el) return;
    el.style.display = 'block';
    el.style.background = isSuccess ? '#dcfce7' : '#fee2e2';
    el.style.color = isSuccess ? '#15803d' : '#b91c1c';
    el.style.border = isSuccess ? '1px solid #bbf7d0' : '1px solid #fecaca';
    el.innerHTML = msg;
};

window.loadUnifiedSettings = async function() {
    try {
        var res = await fetch('/api/settings');
        if (!res.ok) return;
        var d = await res.json();

        var ad = d.ad || {};
        var ep = d.easyproject || {};
        var tg = d.telegram || {};
        var gh = d.github || {};

        var setVal = function(id, v) { var el = document.getElementById(id); if (el && v !== undefined && v !== null) el.value = v; };
        var setChk = function(id, v) { var el = document.getElementById(id); if (el) el.checked = Boolean(v); };

        setVal('cfg_ad_server', ad.server || 'dc1.tspc.hu:389');
        setVal('cfg_ad_base_dn', ad.base_dn || 'DC=tspc,DC=hu');
        setVal('cfg_ad_user', ad.bind_user || 'tadmin@tspc.hu');
        setVal('cfg_ad_password', ad.bind_password || '');
        setVal('cfg_ad_interval', String(ad.sync_interval_minutes || 15));

        setVal('cfg_ep_url', ep.url || 'https://ep.tspc.hu/');
        setVal('cfg_ep_project', ep.project_id || '2403');
        setVal('cfg_ep_api_key', ep.api_key || '');
        setVal('cfg_ep_interval', String(ep.sync_interval_minutes || 15));

        setVal('cfg_tg_token', tg.bot_token || '');
        setVal('cfg_tg_chat_id', tg.chat_id || '229087988');
        setChk('cfg_tg_notify_hd', tg.notify_helpdesk !== false);
        setChk('cfg_tg_notify_audit', tg.notify_audit !== false);

        setVal('cfg_git_repo', gh.repo_url || 'https://github.com/tspcit/ad-tracker.git');
        setVal('cfg_git_token', gh.token || '');
        setVal('cfg_git_branch', gh.branch || 'main');

        if (window.testGitCard) {
            window.testGitCard(true);
        }
    } catch(e) {
        console.error('Hiba a kártyák betöltésekor:', e);
    }
};

window.saveAdCard = async function() {
    var btn = document.getElementById('btn_save_ad');
    if (btn) btn.innerText = '⏳ Mentés...';
    var payload = {
        ad: {
            server: document.getElementById('cfg_ad_server')?.value || '',
            base_dn: document.getElementById('cfg_ad_base_dn')?.value || '',
            bind_user: document.getElementById('cfg_ad_user')?.value || '',
            bind_password: document.getElementById('cfg_ad_password')?.value || '',
            sync_interval_minutes: parseInt(document.getElementById('cfg_ad_interval')?.value || '15')
        }
    };
    try {
        var res = await fetch('/api/settings/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        var d = await res.json();
        window.showCardStatus('status_ad_card', '✅ ' + (d.message || 'AD beállítások elmentve!'), true);
    } catch(e) {
        window.showCardStatus('status_ad_card', '❌ Hiba a mentéskor: ' + e.message, false);
    } finally {
        if (btn) btn.innerText = '💾 Mentés';
    }
};

window.testAdCard = async function() {
    var btn = document.getElementById('btn_test_ad');
    if (btn) btn.innerText = '⏳ Tesztelés...';
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
        window.showCardStatus('status_ad_card', (d.status === 'SUCCESS' ? '✅ ' : '❌ ') + d.message, d.status === 'SUCCESS');
    } catch(e) {
        window.showCardStatus('status_ad_card', '❌ Hiba: ' + e.message, false);
    } finally {
        if (btn) btn.innerText = '🔌 Tesztelés';
    }
};

window.syncAdNow = async function() {
    var btn = document.getElementById('btn_sync_ad');
    if (btn) { btn.innerText = '⏳ Kinyerés...'; btn.disabled = true; }
    window.showCardStatus('status_ad_card', '⏳ AD adatkinyerés folyamatban van a szerveren...', true);
    try {
        var res = await fetch('/api/settings/sync-ad-now', { method: 'POST' });
        var d = await res.json();
        if (d.status === 'SUCCESS') {
            window.showCardStatus('status_ad_card', d.html || d.message, true);
        } else {
            window.showCardStatus('status_ad_card', d.html || d.message || 'Hiba a kinyeréskor', false);
        }
    } catch(e) {
        window.showCardStatus('status_ad_card', '❌ Hálózati hiba: ' + e.message, false);
    } finally {
        if (btn) {
            btn.innerText = '🔄 Kinyerés Most';
            btn.disabled = false;
        }
    }
};

window.saveEpCard = async function() {
    var btn = document.getElementById('btn_save_ep');
    if (btn) btn.innerText = '⏳ Mentés...';
    var payload = {
        easyproject: {
            url: document.getElementById('cfg_ep_url')?.value || '',
            api_key: document.getElementById('cfg_ep_api_key')?.value || '',
            project_id: document.getElementById('cfg_ep_project')?.value || '2403',
            sync_interval_minutes: parseInt(document.getElementById('cfg_ep_interval')?.value || '15')
        }
    };
    try {
        var res = await fetch('/api/settings/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        var d = await res.json();
        window.showCardStatus('status_ep_card', '✅ ' + (d.message || 'Easy Project beállítások elmentve!'), true);
    } catch(e) {
        window.showCardStatus('status_ep_card', '❌ Hiba a mentéskor: ' + e.message, false);
    } finally {
        if (btn) btn.innerText = '💾 Mentés';
    }
};

window.testEpCard = async function() {
    var btn = document.getElementById('btn_test_ep');
    if (btn) btn.innerText = '⏳ Tesztelés...';
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
        window.showCardStatus('status_ep_card', (d.status === 'SUCCESS' ? '✅ ' : '❌ ') + d.message, d.status === 'SUCCESS');
    } catch(e) {
        window.showCardStatus('status_ep_card', '❌ Hiba: ' + e.message, false);
    } finally {
        if (btn) btn.innerText = '🔌 Tesztelés';
    }
};

window.syncEpNow = async function() {
    var btn = document.getElementById('btn_sync_ep');
    if (btn) { btn.innerText = '⏳ Szinkron...'; btn.disabled = true; }
    window.showCardStatus('status_ep_card', '⏳ Easy Project szinkronizálás folyamatban van a szerveren...', true);
    try {
        var res = await fetch('/api/settings/sync-ep-now', { method: 'POST' });
        var d = await res.json();
        if (d.status === 'SUCCESS') {
            window.showCardStatus('status_ep_card', d.html || d.message, true);
        } else {
            window.showCardStatus('status_ep_card', d.html || d.message || 'Hiba a szinkronizáláskor', false);
        }
    } catch(e) {
        window.showCardStatus('status_ep_card', '❌ Hálózati hiba: ' + e.message, false);
    } finally {
        if (btn) {
            btn.innerText = '🔄 Szinkronizálás Most';
            btn.disabled = false;
        }
    }
};

window.saveTgCard = async function() {
    var btn = document.getElementById('btn_save_tg');
    if (btn) btn.innerText = '⏳ Mentés...';
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
        window.showCardStatus('status_tg_card', '✅ Telegram beállítások elmentve!', true);
    } catch(e) {
        window.showCardStatus('status_tg_card', '❌ Hiba: ' + e.message, false);
    } finally {
        if (btn) btn.innerText = '💾 Mentés';
    }
};

window.testTgCard = async function() {
    var btn = document.getElementById('btn_test_tg');
    if (btn) btn.innerText = '⏳ Küldés...';
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
        window.showCardStatus('status_tg_card', (d.status === 'SUCCESS' ? '✅ ' : '❌ ') + d.message, d.status === 'SUCCESS');
    } catch(e) {
        window.showCardStatus('status_tg_card', '❌ Hiba: ' + e.message, false);
    } finally {
        if (btn) btn.innerText = '📲 Teszt Ping';
    }
};

window.saveGitCard = async function() {
    var btn = document.getElementById('btn_save_git');
    if (btn) btn.innerText = '⏳ Mentés...';
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
        window.showCardStatus('status_git_card', '✅ Git beállítások és token elmentve!', true);
    } catch(e) {
        window.showCardStatus('status_git_card', '❌ Hiba: ' + e.message, false);
    } finally {
        if (btn) btn.innerText = '💾 Mentés';
    }
};

window.testGitCard = async function(isSilent) {
    var btn = document.getElementById('btn_test_git');
    if (btn && !isSilent) btn.innerText = '⏳ Lekérdezés...';
    try {
        var res = await fetch('/api/settings/test-git', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                repo_url: document.getElementById('cfg_git_repo')?.value || '',
                token: document.getElementById('cfg_git_token')?.value || ''
            })
        });
        var d = await res.json();

        var setTxt = function(id, v) { var el = document.getElementById(id); if (el) el.innerText = v || '-'; };
        setTxt('git_info_tag', d.version || 'v1.10');
        setTxt('git_info_name', d.name || 'Release');
        setTxt('git_info_date', d.date || '-');
        setTxt('git_info_commit', d.commit || '-');
        setTxt('git_info_source', d.source || 'GitHub API');

        if (!isSilent) {
            window.showCardStatus('status_git_card', '✅ ' + d.message, true);
        }
    } catch(e) {
        if (!isSilent) {
            window.showCardStatus('status_git_card', '❌ Hiba a GitHub lekérdezésekor: ' + e.message, false);
        }
    } finally {
        if (btn && !isSilent) btn.innerText = '🚀 Git Tesztelése';
    }
};

window.pushGitCard = async function() {
    var btn = document.getElementById('btn_push_git');
    var repoUrl = document.getElementById('cfg_git_repo')?.value || '';
    var token = document.getElementById('cfg_git_token')?.value || '';
    var branch = document.getElementById('cfg_git_branch')?.value || 'main';
    var comment = document.getElementById('cfg_git_comment')?.value || '';

    if (!token) {
        window.showCardStatus('status_git_card', '❌ Kérjük írja be a Personal Access Token-t (PAT) a push indítása előtt!', false);
        return;
    }

    if (btn) {
        btn.innerText = '⏳ Push (+0.01)...';
        btn.disabled = true;
    }
    window.showCardStatus('status_git_card', '⏳ Verziószám növelése, commit, tag címkézés és GitHub Push folyamatban...', true);

    try {
        var res = await fetch('/api/settings/github-push', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ repo_url: repoUrl, token: token, branch: branch, comment: comment })
        });
        var d = await res.json();
        if (d.status === 'SUCCESS') {
            window.showCardStatus('status_git_card', '✅ ' + d.message, true);

            var setTxt = function(id, v) { var el = document.getElementById(id); if (el) el.innerText = v || '-'; };
            setTxt('git_info_tag', d.version);
            setTxt('git_info_name', d.name);
            setTxt('git_info_date', d.date);
            setTxt('git_info_commit', d.commit || '-');
            setTxt('git_info_source', 'GitHub Távoli Tároló (Frissítve)');

            var commentEl = document.getElementById('cfg_git_comment');
            if (commentEl) commentEl.value = '';
        } else {
            window.showCardStatus('status_git_card', '❌ ' + d.message, false);
        }
    } catch(e) {
        window.showCardStatus('status_git_card', '❌ Hálózati hiba a push során: ' + e.message, false);
    } finally {
        if (btn) {
            btn.innerText = '⬆️ GitHub Push (+0.01)';
            btn.disabled = false;
        }
    }
};

window.runDebugCmd = async function(cmd) {
    var inputEl = document.getElementById('unified_debug_input');
    var term = document.getElementById('unified_debug_output');
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

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', window.loadUnifiedSettings);
} else {
    window.loadUnifiedSettings();
}
