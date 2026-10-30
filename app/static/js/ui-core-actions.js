
// ==========================================================================
// VISSZAJELZŐ ADATKINYERÉSEK ÉS GITHUB PUSH MOTOR
// ==========================================================================

window.syncAdNow = async function() {
    var btn = document.getElementById('btn_sync_ad');
    if (btn) {
        btn.innerText = '⏳ Kinyerés folyamatban...';
        btn.disabled = true;
    }
    window.showCardStatus('status_ad_card', '⏳ AD adatkinyerés folyamatban van a szerveren...', true);
    try {
        var res = await fetch('/api/settings/sync-ad-now', { method: 'POST' });
        var d = await res.json();
        if (d.status === 'SUCCESS') {
            window.showCardStatus('status_ad_card', '✅ ' + d.message, true);
        } else {
            window.showCardStatus('status_ad_card', '❌ ' + (d.message || 'Hiba történt a kinyeréskor'), false);
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

window.syncEpNow = async function() {
    var btn = document.getElementById('btn_sync_ep');
    if (btn) {
        btn.innerText = '⏳ Szinkronizálás folyamatban...';
        btn.disabled = true;
    }
    window.showCardStatus('status_ep_card', '⏳ Easy Project szinkronizálás folyamatban van a szerveren...', true);
    try {
        var res = await fetch('/api/settings/sync-ep-now', { method: 'POST' });
        var d = await res.json();
        if (d.status === 'SUCCESS') {
            window.showCardStatus('status_ep_card', '✅ ' + d.message, true);
        } else {
            window.showCardStatus('status_ep_card', '❌ ' + (d.message || 'Hiba történt a szinkronizáláskor'), false);
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

window.pushGitCard = async function() {
    var btn = document.getElementById('btn_push_git');
    var repoUrl = document.getElementById('cfg_git_repo')?.value || '';
    var token = document.getElementById('cfg_git_token')?.value || '';
    var branch = document.getElementById('cfg_git_branch')?.value || 'copilot/ad-tracker-v1.27-20261030';

    if (!token) {
        window.showCardStatus('status_git_card', '❌ Kérjük írja be a Personal Access Token-t (PAT) a push indítása előtt!', false);
        return;
    }

    if (btn) {
        btn.innerText = '⏳ Push (+0.01) folyamatban...';
        btn.disabled = true;
    }
    window.showCardStatus('status_git_card', '⏳ Verziószám növelése, commit, tag címkézés és GitHub Push folyamatban...', true);

    try {
        var res = await fetch('/api/settings/github-push', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ repo_url: repoUrl, token: token, branch: branch })
        });
        var d = await res.json();
        if (d.status === 'SUCCESS') {
            window.showCardStatus('status_git_card', '✅ ' + d.message, true);

            // Frissítjük a kártyán lévő információs blokkot az új verzióval
            var setTxt = function(id, v) { var el = document.getElementById(id); if (el) el.innerText = v || '-'; };
            setTxt('git_info_tag', d.version);
            setTxt('git_info_name', d.name);
            setTxt('git_info_date', d.date);
            setTxt('git_info_source', 'GitHub Távoli Tároló (Frissítve)');
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
