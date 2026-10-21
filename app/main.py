from fastapi import FastAPI, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timezone
import threading

from database import engine, Base, get_db, SessionLocal
import models
from sync_engine import run_ad_sync
from config_manager import init_default_settings, get_setting, update_setting
from ldap_client import test_ad_connection
from auth import authenticate_ad_user, create_session_token, verify_session_token, COOKIE_NAME
from ai_assistant import fetch_ollama_models, ask_ollama
from github_sync import test_github_connection, push_code_to_github, get_github_commit_history

models.Base.metadata.create_all(bind=engine)
db_init = SessionLocal()
init_default_settings(db_init)
if not get_setting(db_init, "APP_VERSION"):
    update_setting(db_init, "APP_VERSION", "1.01")
db_init.close()

scheduler = BackgroundScheduler()
JOB_ID = "ad_sync_job"
sync_state = {"is_syncing": False, "last_run": None, "last_changes": 0}
sync_lock = threading.Lock()

def execute_sync_with_log(trigger_type: str):
    with sync_lock:
        if sync_state["is_syncing"]: return {"status": "ALREADY_RUNNING"}
        sync_state["is_syncing"] = True
    db = SessionLocal()
    log_entry = models.SyncHistory(trigger_type=trigger_type, status="FOLYAMATBAN")
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    start_time = datetime.now(timezone.utc)
    res = {}
    try:
        res = run_ad_sync(db)
        log_entry.status = "SIKERES"
        log_entry.changes_detected = res.get('detektalt_valtozasok', 0)
    except Exception as e:
        log_entry.status = "HIBA"
        log_entry.error_message = str(e)
        res = {"status": "ERROR", "message": str(e)}
    finally:
        end_time = datetime.now(timezone.utc)
        log_entry.ended_at = end_time
        log_entry.duration_seconds = int((end_time - start_time).total_seconds())
        db.commit()
        db.close()
        with sync_lock:
            sync_state["is_syncing"] = False
            sync_state["last_run"] = end_time
    return res

def scheduled_sync_job():
    execute_sync_with_log("Ütemezett")

@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    sync_minutes = int(get_setting(db, "SYNC_INTERVAL_MINUTES", "15"))
    db.close()
    if sync_minutes > 0:
        scheduler.add_job(scheduled_sync_job, 'interval', minutes=sync_minutes, id=JOB_ID)
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(title="AD Tracker", lifespan=lifespan)

def get_current_user(request: Request):
    return verify_session_token(request.cookies.get(COOKIE_NAME))

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: str = None):
    if get_current_user(request): return RedirectResponse(url="/", status_code=303)
    err_html = f'<div style="background:#fee2e2; color:#dc2626; padding:12px; border-radius:6px; margin-bottom:15px; font-size:14px;">{error}</div>' if error else ''
    return f"""
    <!DOCTYPE html>
    <html lang="hu"><head><meta charset="UTF-8"><title>Belépés</title><style>
        body{{font-family:sans-serif; background:#0f172a; display:flex; align-items:center; justify-content:center; height:100vh; margin:0;}}
        .card{{background:white; padding:35px; border-radius:12px; max-width:400px; width:100%; box-sizing:border-box;}}
        input{{width:100%; padding:10px; border:1px solid #cbd5e1; border-radius:6px; box-sizing:border-box; margin-bottom:15px;}}
        .btn{{width:100%; background:#0284c7; color:white; border:none; padding:12px; border-radius:6px; cursor:pointer; font-weight:bold;}}
    </style></head><body>
    <div class="card"><h2>AD Tracker Belépés</h2>{err_html}
    <form method="POST" action="/login">
        Felhasználó (@tspc.hu)<input type="text" name="username" required autofocus>
        Jelszó<input type="password" name="password" required>
        <button type="submit" class="btn">Bejelentkezés</button>
    </form></div></body></html>
    """

@app.post("/login")
def process_login(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    success, result = authenticate_ad_user(db, username, password)
    if not success: return RedirectResponse(url="/login?error=Hibas+adatok", status_code=303)
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(key=COOKIE_NAME, value=create_session_token(result), httponly=True, max_age=86400, samesite="lax")
    return response

@app.get("/logout")
def process_logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response

@app.get("/api/sync-status")
def get_sync_status(request: Request):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    return sync_state

@app.get("/api/sync-history")
def get_sync_history(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    logs = db.query(models.SyncHistory).order_by(desc(models.SyncHistory.started_at)).limit(50).all()
    return [{"id": l.id, "started": l.started_at.strftime("%Y-%m-%d %H:%M:%S") if l.started_at else "-", "ended": l.ended_at.strftime("%Y-%m-%d %H:%M:%S") if l.ended_at else "-", "duration": f"{l.duration_seconds} mp" if l.duration_seconds is not None else "-", "trigger": l.trigger_type, "status": l.status, "changes": l.changes_detected, "error": l.error_message or ""} for l in logs]

@app.get("/api/users")
def get_all_users(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    users = db.query(models.ADUser).all()
    return [{"sam": u.sam_account_name, "name": u.display_name or "-", "first_name": u.first_name or "-", "last_name": u.last_name or "-", "mail": u.mail or "-", "enabled": u.is_enabled, "phone": u.telephone_number or "-", "mobile": u.mobile or "-", "title": u.title or "-", "department": u.department or "-", "company": u.company or "-", "office": u.office or "-", "desc": u.description or "-", "sid": u.object_sid or "-", "created": u.when_created.strftime("%Y-%m-%d %H:%M") if u.when_created else "-", "changed": u.when_changed.strftime("%Y-%m-%d %H:%M") if u.when_changed else "-", "groups": [{"name": g.sam_account_name, "type": g.group_type or "Ismeretlen"} for g in u.groups]} for u in users]

@app.get("/api/groups")
def get_all_groups(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    groups = db.query(models.ADGroup).all()
    return [{"sam": g.sam_account_name, "desc": g.description or "-", "type": g.group_type or "Ismeretlen", "sid": g.object_sid or "-", "created": g.when_created.strftime("%Y-%m-%d %H:%M") if g.when_created else "-", "changed": g.when_changed.strftime("%Y-%m-%d %H:%M") if g.when_changed else "-", "members": [u.sam_account_name for u in g.members]} for g in groups]

@app.post("/api/sync")
def trigger_sync_manual(request: Request):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    threading.Thread(target=execute_sync_with_log, args=("Manuális",)).start()
    return {"status": "STARTED"}

# --- GitHub Végpontok ---
@app.post("/api/github/test")
async def api_gh_test(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    data = await request.json()
    repo = data.get("repo") or get_setting(db, "GH_REPO")
    token = data.get("token") or get_setting(db, "GH_TOKEN")
    
    if not repo or not token: 
        return {"status": "ERROR", "message": "Kérjük, adja meg a Repó nevét és a Tokent a teszteléshez!"}
    
    update_setting(db, "GH_REPO", repo)
    update_setting(db, "GH_TOKEN", token)
    if data.get("branch"): update_setting(db, "GH_BRANCH", data.get("branch"))
    
    ok, msg = test_github_connection(repo, token)
    return {"status": "SUCCESS" if ok else "ERROR", "message": msg}

@app.get("/api/github/history")
def api_gh_history(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    repo = get_setting(db, "GH_REPO")
    token = get_setting(db, "GH_TOKEN")
    branch = get_setting(db, "GH_BRANCH", "main")
    if not repo or not token: return {"status": "ERROR", "message": "Nincs beállítva GitHub azonosító."}
    ok, data = get_github_commit_history(repo, token, branch)
    return {"status": "SUCCESS" if ok else "ERROR", "data": data}

@app.post("/api/github/push")
async def api_gh_push(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): 
        return JSONResponse(status_code=401, content={"status": "ERROR", "message": "Munkamenet lejárt, kérjük jelentkezzen be újra!"})
    try:
        req_data = await request.json()
        custom_msg = req_data.get("message", "")
        repo = req_data.get("repo") or get_setting(db, "GH_REPO")
        token = req_data.get("token") or get_setting(db, "GH_TOKEN")
        branch = req_data.get("branch") or get_setting(db, "GH_BRANCH", "main")
        
        if not repo or not token: 
            return {"status": "ERROR", "message": "Hiányzó GitHub repó név vagy token!"}

        update_setting(db, "GH_REPO", repo)
        update_setting(db, "GH_TOKEN", token)
        update_setting(db, "GH_BRANCH", branch)

        raw_ver = str(get_setting(db, "APP_VERSION", "1.01")).replace("v", "").strip()
        try:
            current_ver = float(raw_ver)
        except ValueError:
            current_ver = 1.01

        new_ver = current_ver + 0.01
        new_ver_str = f"{new_ver:.2f}"

        ok, msg = push_code_to_github(repo, branch, token, new_ver_str, custom_msg)
        if ok:
            update_setting(db, "APP_VERSION", new_ver_str)
            return {"status": "SUCCESS", "message": msg, "new_version": new_ver_str}
        else:
            return {"status": "ERROR", "message": msg}
    except Exception as e:
        return {"status": "ERROR", "message": f"Szerveroldali hiba a feltöltés során: {str(e)}"}

# --- AI Végpontok ---
@app.get("/api/ai/models")
def get_ai_models(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    return {"models": fetch_ollama_models(db)}

@app.post("/api/ai/ask")
async def ask_ai_endpoint(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    data = await request.json()
    return ask_ollama(db, data.get("model"), data.get("prompt"))

@app.post("/api/settings")
async def save_settings(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    data = await request.json()
    update_setting(db, "AD_SERVER", data.get("AD_SERVER", ""))
    update_setting(db, "AD_USER", data.get("AD_USER", ""))
    if data.get("AD_PASSWORD"): update_setting(db, "AD_PASSWORD", data.get("AD_PASSWORD"))
    update_setting(db, "AD_SEARCH_BASE", data.get("AD_SEARCH_BASE", ""))
    update_setting(db, "OLLAMA_URL", data.get("OLLAMA_URL", "http://ollama:11434"))
    update_setting(db, "GH_REPO", data.get("GH_REPO", ""))
    update_setting(db, "GH_TOKEN", data.get("GH_TOKEN", ""))
    update_setting(db, "GH_BRANCH", data.get("GH_BRANCH", "main"))
    
    minutes = int(data.get("SYNC_INTERVAL_MINUTES", 15))
    update_setting(db, "SYNC_INTERVAL_MINUTES", str(minutes))
    if scheduler.get_job(JOB_ID): scheduler.remove_job(JOB_ID)
    if minutes > 0: scheduler.add_job(scheduled_sync_job, 'interval', minutes=minutes, id=JOB_ID)
    return {"status": "SUCCESS"}

@app.get("/", response_class=HTMLResponse)
def index_page(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request)
    if not current_user: return RedirectResponse(url="/login", status_code=303)

    logs = db.query(models.ADAuditLog).order_by(desc(models.ADAuditLog.timestamp)).limit(50).all()
    rows = ""
    for l in logs:
        badge = "#16a34a" if "ADDED" in l.change_type or "CREATED" in l.change_type else ("#dc2626" if "REMOVED" in l.change_type else "#2563eb")
        t = l.timestamp.strftime("%Y-%m-%d %H:%M") if l.timestamp else ""
        rows += f'<tr><td>{t}</td><td><b>{l.entity_name}</b></td><td><span style="background:{badge}; color:white; padding:3px 6px; border-radius:4px; font-size:11px;">{l.change_type}</span></td><td>{l.details}</td></tr>'

    ad_server = get_setting(db, "AD_SERVER")
    ad_user = get_setting(db, "AD_USER")
    ad_base = get_setting(db, "AD_SEARCH_BASE")
    ollama_url = get_setting(db, "OLLAMA_URL", "http://ollama:11434")
    
    gh_repo = get_setting(db, "GH_REPO")
    gh_token = get_setting(db, "GH_TOKEN")
    gh_branch = get_setting(db, "GH_BRANCH", "main")
    app_version = get_setting(db, "APP_VERSION", "1.01").replace("v", "")
    
    job = scheduler.get_job(JOB_ID)
    interval_min = int(job.trigger.interval.total_seconds() / 60) if job else 0

    return f"""<!DOCTYPE html>
<html lang="hu">
<head>
    <meta charset="UTF-8">
    <title>AD Tracker Admin</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f8fafc; margin:0; padding: 20px; }}
        .container {{ max-width: 1250px; margin: 0 auto; background: white; padding: 25px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .top-bar {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #e2e8f0; padding-bottom: 12px; margin-bottom: 15px; }}
        .tabs {{ border-bottom: 1px solid #e2e8f0; margin-bottom: 20px; display: flex; gap: 15px; }}
        .tab {{ padding: 10px 15px; cursor: pointer; font-weight: bold; color: #64748b; border-bottom: 3px solid transparent; }}
        .tab.active {{ color: #0284c7; border-bottom: 3px solid #0284c7; }}
        .content {{ display: none; }}
        .content.active {{ display: block; }}
        .btn {{ background: #0284c7; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-weight: bold; text-decoration: none; display: inline-block; }}
        .btn:disabled {{ background: #94a3b8; cursor: not-allowed; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 14px; }}
        th, td {{ text-align: left; padding: 10px; border-bottom: 1px solid #eee; }}
        th {{ background: #f1f5f9; }}
        tr:hover {{ background: #f8fafc; }}
        input, select, textarea {{ width: 100%; padding: 8px; border: 1px solid #cbd5e1; border-radius: 4px; margin-bottom: 12px; box-sizing: border-box; font-family: inherit; }}
        
        .sync-badge {{ background: #f59e0b; color: white; padding: 4px 12px; border-radius: 12px; font-size: 13px; font-weight: bold; display: none; animation: pulse 1.5s infinite; }}
        @keyframes pulse {{ 0% {{ opacity: 1; }} 50% {{ opacity: 0.5; }} 100% {{ opacity: 1; }} }}
        
        .gh-history-box {{ font-size: 13px; max-height: 200px; overflow-y: auto; background: #f8fafc; border: 1px solid #e2e8f0; padding: 10px; border-radius: 6px; margin-top: 10px; }}
        .gh-history-item {{ border-bottom: 1px solid #cbd5e1; padding: 6px 0; }}
        .gh-history-item:last-child {{ border-bottom: none; }}
        
        .modal {{ display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.6); overflow-y: auto; }}
        .modal-content {{ background-color: #fff; margin: 4% auto; padding: 30px; border-radius: 12px; width: 85%; max-width: 900px; box-shadow: 0 10px 25px rgba(0,0,0,0.3); position: relative; }}
        .close {{ color: #aaa; float: right; font-size: 28px; font-weight: bold; cursor: pointer; margin-top: -10px; }}
        .close:hover {{ color: #000; }}
        .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px; font-size: 14px; line-height: 1.6; }}
        .card-box {{ background: #f8fafc; padding: 15px; border-radius: 8px; border: 1px solid #e2e8f0; }}
        .card-box h4 {{ margin-top: 0; color: #0f172a; border-bottom: 2px solid #cbd5e1; padding-bottom: 5px; }}
        .data-row {{ display: flex; justify-content: space-between; border-bottom: 1px dashed #cbd5e1; padding: 4px 0; }}
        .data-row strong {{ color: #475569; }}
        .badge-active {{ background: #16a34a; color: white; padding: 4px 10px; border-radius: 12px; font-size: 13px; }}
        .badge-disabled {{ background: #dc2626; color: white; padding: 4px 10px; border-radius: 12px; font-size: 13px; }}
        .search-box {{ display: flex; gap: 10px; margin-bottom: 10px; align-items: center; }}
        .search-box input {{ margin: 0; flex: 1; max-width: 100%; padding: 10px; }}
        
        .group-tag {{ display: inline-block; background: #e0f2fe; color: #0369a1; padding: 4px 8px; border-radius: 4px; margin: 3px; font-size: 12px; border: 1px solid #bae6fd; cursor: pointer; transition: 0.2s; }}
        .group-tag:hover {{ background: #bae6fd; }}
        .group-tag.dist {{ background: #f3e8ff; color: #7e22ce; border-color: #e9d5ff; }}
        .group-tag.dist:hover {{ background: #e9d5ff; }}
        .user-tag {{ display: inline-block; background: #f1f5f9; color: #475569; padding: 4px 8px; border-radius: 4px; margin: 3px; font-size: 12px; border: 1px solid #cbd5e1; cursor: pointer; transition: 0.2s; }}
        .user-tag:hover {{ background: #e2e8f0; color: #0f172a; }}

        .ai-header {{ display: flex; gap: 15px; align-items: center; background: #f1f5f9; padding: 15px; border-radius: 6px; margin-bottom: 20px; }}
        .chat-box {{ height: 350px; border: 1px solid #e2e8f0; border-radius: 6px; padding: 15px; overflow-y: auto; background: #ffffff; display: flex; flex-direction: column; gap: 12px; margin-bottom: 15px; }}
        .msg {{ max-width: 80%; padding: 10px 14px; border-radius: 8px; font-size: 14px; line-height: 1.5; white-space: pre-wrap; }}
        .msg-user {{ align-self: flex-end; background: #0284c7; color: white; border-bottom-right-radius: 1px; }}
        .msg-ai {{ align-self: flex-start; background: #f8fafc; border: 1px solid #e2e8f0; color: #1e293b; border-bottom-left-radius: 1px; }}
        .quick-prompts {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }}
        .quick-btn {{ background: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd; padding: 6px 12px; border-radius: 15px; font-size: 12px; font-weight: 600; cursor: pointer; }}
        .quick-btn:hover {{ background: #bae6fd; }}
        .input-row {{ display: flex; gap: 10px; }}
        .input-row textarea {{ flex: 1; padding: 10px; border: 1px solid #cbd5e1; border-radius: 6px; resize: none; height: 45px; margin: 0; }}
    </style>
    <script>
        let allUsers = [];
        let allGroups = [];
        let isSyncing = false;

        function switchTab(tabId) {{
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.content').forEach(c => c.classList.remove('active'));
            const targetTab = document.getElementById('tab-' + tabId);
            const targetContent = document.getElementById('content-' + tabId);
            if (targetTab) targetTab.classList.add('active');
            if (targetContent) targetContent.classList.add('active');
            if (tabId === 'users' && allUsers.length === 0) loadUsersAndGroups();
            if (tabId === 'sync-history') loadSyncHistory();
            if (tabId === 'ai') loadModels();
            if (tabId === 'settings') loadGitHubHistory();
        }}

        async function checkSyncStatus() {{
            try {{
                const res = await fetch('/api/sync-status');
                const data = await res.json();
                const indicator = document.getElementById('syncIndicator');
                const syncBtn = document.getElementById('syncBtn');
                
                if (data.is_syncing) {{
                    if (indicator) indicator.style.display = 'inline-block';
                    if (syncBtn) {{ syncBtn.disabled = true; syncBtn.innerText = 'Szinkronizálás Folyamatban...'; }}
                    isSyncing = true;
                }} else {{
                    if (indicator) indicator.style.display = 'none';
                    if (syncBtn) {{ syncBtn.disabled = false; syncBtn.innerText = 'Azonnali Szinkronizálás'; }}
                    if (isSyncing) {{ window.location.reload(); }}
                }}
            }} catch (e) {{}}
        }}
        setInterval(checkSyncStatus, 5000);
        checkSyncStatus();

        async function doSync() {{
            const btn = document.getElementById('syncBtn');
            if (btn) btn.disabled = true;
            await fetch('/api/sync', {{ method: 'POST' }});
            checkSyncStatus();
        }}

        async function loadSyncHistory() {{
            const tbody = document.getElementById('syncHistoryBody');
            if (!tbody) return;
            tbody.innerHTML = '<tr><td colspan="6">Napló betöltése...</td></tr>';
            try {{
                const res = await fetch('/api/sync-history');
                const logs = await res.json();
                tbody.innerHTML = '';
                if (!logs || logs.length === 0) {{
                    tbody.innerHTML = '<tr><td colspan="6">Nincs rögzített szinkronizálási előzmény.</td></tr>';
                    return;
                }}
                logs.forEach(l => {{
                    let c = l.status === 'SIKERES' ? '#16a34a' : (l.status === 'HIBA' ? '#dc2626' : '#f59e0b');
                    tbody.innerHTML += `<tr><td><b>${{l.started}}</b></td><td>${{l.ended}}</td><td>${{l.duration}}</td><td>${{l.trigger}}</td><td><b style="color:${{c}}">${{l.status}}</b></td><td>${{l.changes}} db</td></tr>`;
                }});
            }} catch(e) {{
                tbody.innerHTML = '<tr><td colspan="6" style="color:#dc2626;">Hiba a napló betöltésekor.</td></tr>';
            }}
        }}

        async function loadUsersAndGroups() {{
            const tbody = document.getElementById('usersTableBody');
            if (tbody) tbody.innerHTML = '<tr><td colspan="6">Adatok letöltése az adatbázisból...</td></tr>';
            try {{
                const [uRes, gRes] = await Promise.all([fetch('/api/users'), fetch('/api/groups')]);
                allUsers = await uRes.json();
                allGroups = await gRes.json();
                renderUsers(allUsers);
            }} catch(e) {{
                if (tbody) tbody.innerHTML = '<tr><td colspan="6" style="color:#dc2626;">Hiba az adatok letöltésekor.</td></tr>';
            }}
        }}

        function renderUsers(usersList) {{
            const tbody = document.getElementById('usersTableBody');
            if (!tbody) return;
            tbody.innerHTML = '';
            const limited = usersList.slice(0, 150);
            limited.forEach(u => {{
                const tr = document.createElement('tr');
                tr.style.cursor = 'pointer';
                tr.onclick = () => openUserModal(u.sam);
                const st = u.enabled ? '<span style="color:#16a34a; font-weight:bold;">Aktív</span>' : '<span style="color:#dc2626; font-weight:bold;">Letiltva</span>';
                tr.innerHTML = `<td><b>${{u.name}}</b></td><td>${{u.sam}}</td><td>${{u.mail}}</td><td>${{u.title}}</td><td>${{st}}</td><td>${{u.changed}}</td>`;
                tbody.appendChild(tr);
            }});
            const countLabel = document.getElementById('userCountLabel');
            if (countLabel) countLabel.innerText = `Találat: ${{usersList.length}} fiók (150 megjelenítve)`;
        }}

        function filterUsers() {{
            const term = document.getElementById('userSearchBox').value.toLowerCase();
            if (!term) {{ renderUsers(allUsers); return; }}
            const filtered = allUsers.filter(u => 
                (u.name && u.name.toLowerCase().includes(term)) || 
                (u.sam && u.sam.toLowerCase().includes(term)) || 
                (u.mail && u.mail.toLowerCase().includes(term)) ||
                (u.department && u.department.toLowerCase().includes(term))
            );
            renderUsers(filtered);
        }}

        function openUserModal(sam) {{
            const u = allUsers.find(x => x.sam === sam);
            if(!u) return;
            document.getElementById('groupModal').style.display = 'none';
            document.getElementById('m-name').innerText = u.name;
            document.getElementById('m-status').innerHTML = u.enabled ? '<span class="badge-active">Aktív Fiók</span>' : '<span class="badge-disabled">Letiltott Fiók</span>';
            document.getElementById('m-sam').innerText = u.sam;
            document.getElementById('m-mail').innerText = u.mail;
            document.getElementById('m-fname').innerText = u.first_name;
            document.getElementById('m-lname').innerText = u.last_name;
            document.getElementById('m-desc').innerText = u.desc;
            document.getElementById('m-title').innerText = u.title;
            document.getElementById('m-dept').innerText = u.department;
            document.getElementById('m-company').innerText = u.company;
            document.getElementById('m-office').innerText = u.office;
            document.getElementById('m-phone').innerText = u.phone;
            document.getElementById('m-mobile').innerText = u.mobile;
            document.getElementById('m-sid').innerText = u.sid;
            document.getElementById('m-created').innerText = u.created;
            document.getElementById('m-changed').innerText = u.changed;
            
            let gHtml = '';
            if (u.groups && u.groups.length > 0) {{
                u.groups.forEach(g => {{
                    const cssClass = g.type.includes('Terjesztési') ? 'group-tag dist' : 'group-tag';
                    gHtml += `<span class="${{cssClass}}" onclick="event.stopPropagation(); openGroupModal('${{g.name}}')">${{g.name}}</span> `;
                }});
            }} else {{
                gHtml = '<span style="color:#64748b;">Nincs csoporttagság</span>';
            }}
            document.getElementById('m-groups').innerHTML = gHtml;
            document.getElementById('userModal').style.display = 'block';
        }}

        function openGroupModal(sam) {{
            const g = allGroups.find(x => x.sam === sam);
            if(!g) return;
            document.getElementById('userModal').style.display = 'none';
            document.getElementById('g-name').innerText = g.sam;
            document.getElementById('g-type').innerText = g.type;
            document.getElementById('g-desc').innerText = g.desc;
            document.getElementById('g-sid').innerText = g.sid;
            document.getElementById('g-created').innerText = g.created;
            document.getElementById('g-changed').innerText = g.changed;
            document.getElementById('g-count').innerText = (g.members ? g.members.length : 0) + " fő";
            
            let mHtml = '';
            if (g.members && g.members.length > 0) {{
                g.members.forEach(memberSam => {{
                    mHtml += `<span class="user-tag" onclick="event.stopPropagation(); openUserModal('${{memberSam}}')">👤 ${{memberSam}}</span> `;
                }});
            }} else {{
                mHtml = '<span style="color:#64748b;">A csoport üres.</span>';
            }}
            document.getElementById('g-members').innerHTML = mHtml;
            document.getElementById('groupModal').style.display = 'block';
        }}

        function closeAllModals() {{ 
            document.getElementById('userModal').style.display = 'none'; 
            document.getElementById('groupModal').style.display = 'none';
        }}
        window.onclick = function(event) {{ 
            if (event.target == document.getElementById('userModal') || event.target == document.getElementById('groupModal')) closeAllModals(); 
        }}

        // --- GITHUB FUNKCIÓK ---
        async function saveSettings() {{
            const data = {{
                AD_SERVER: document.getElementById('ad_server').value,
                AD_USER: document.getElementById('ad_user').value,
                AD_PASSWORD: document.getElementById('ad_password').value,
                AD_SEARCH_BASE: document.getElementById('ad_base').value,
                OLLAMA_URL: document.getElementById('ollama_url').value,
                SYNC_INTERVAL_MINUTES: document.getElementById('sync_interval').value,
                GH_REPO: document.getElementById('gh_repo').value,
                GH_TOKEN: document.getElementById('gh_token').value,
                GH_BRANCH: document.getElementById('gh_branch').value
            }};
            await fetch('/api/settings', {{ method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify(data) }});
            alert('Beállítások sikeresen mentve!');
            window.location.reload();
        }}

        async function testGitHub() {{
            const btn = document.getElementById('ghTestBtn');
            const repo = document.getElementById('gh_repo').value.trim();
            const token = document.getElementById('gh_token').value.trim();
            const branch = document.getElementById('gh_branch').value.trim();
            
            if(!repo || !token) {{
                alert("Kérjük, töltse ki a Repó nevét és a Tokent a teszteléshez!");
                return;
            }}
            
            btn.disabled = true; btn.innerText = "Tesztelés...";
            try {{
                const res = await fetch('/api/github/test', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{ repo: repo, token: token, branch: branch }})
                }});
                const data = await res.json();
                if (data.status === 'ERROR') {{
                    alert("Hiba történt:\\n\\n" + (data.message || data.detail));
                }} else {{
                    alert(data.message);
                }}
            }} catch(e) {{
                alert("Hálózati hiba a teszt során: " + e);
            }} finally {{
                btn.disabled = false; btn.innerText = "Kapcsolat Tesztelése";
                loadGitHubHistory();
            }}
        }}

        async function loadGitHubHistory() {{
            const box = document.getElementById('gh_history_list');
            if (!box) return;
            box.innerHTML = '<i>Verziótörténet betöltése folyamatban...</i>';
            try {{
                const res = await fetch('/api/github/history');
                const data = await res.json();
                if (data.status === 'SUCCESS' && Array.isArray(data.data)) {{
                    box.innerHTML = '';
                    if (data.data.length === 0) {{
                        box.innerHTML = '<i>Nincsenek elérhető commitok a megadott ágon.</i>';
                        return;
                    }}
                    data.data.forEach(item => {{
                        const d = new Date(item.date).toLocaleString('hu-HU');
                        box.innerHTML += `
                        <div class="gh-history-item">
                            <strong style="color:#0284c7;">${{item.message}}</strong><br/>
                            <span style="color:#64748b; font-size:11px;">${{d}} | Szerző: ${{item.author}} | Commit: <i>${{item.sha}}</i></span>
                        </div>`;
                    }});
                }} else {{
                    box.innerHTML = `<span style="color:#dc2626; font-weight:bold;">${{data.data || data.message || "Hiba"}}</span>`;
                }}
            }} catch(e) {{
                box.innerHTML = `<span style="color:#dc2626;">Nem sikerült betölteni a GitHub előzményeket.</span>`;
            }}
        }}

        async function pushToGitHub() {{
            const repo = document.getElementById('gh_repo').value.trim();
            const token = document.getElementById('gh_token').value.trim();
            const branch = document.getElementById('gh_branch').value.trim();
            const customMsg = document.getElementById('gh_custom_msg').value.trim();
            
            if(!repo || !token) {{
                alert("Kérjük, adja meg a Repó nevét és a Tokent a publikáláshoz!");
                return;
            }}
            if(!confirm("Biztosan feltölti a kódot a GitHub-ra? A verziószám 0.01-gyel nőni fog.")) return;
            
            const btn = document.getElementById('ghPushBtn');
            btn.disabled = true; btn.innerText = "Feltöltés...";
            try {{
                const res = await fetch('/api/github/push', {{ 
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{ repo: repo, token: token, branch: branch, message: customMsg }})
                }});
                const data = await res.json();
                if(res.status === 200 && data.status === 'SUCCESS') {{
                    alert(data.message);
                    document.getElementById('app_version_label').innerText = data.new_version;
                    document.getElementById('gh_custom_msg').value = '';
                    loadGitHubHistory();
                }} else {{
                    const hiba = data.message || data.detail || ("HTTP hiba: " + res.status);
                    alert("Hiba a feltöltésnél:\\n\\n" + hiba);
                }}
            }} catch(e) {{
                alert("Hálózati hiba: " + e);
            }} finally {{
                btn.disabled = false; btn.innerText = "Kód Publikálása (Push)";
            }}
        }}

        // --- AI FUNKCIÓK ---
        async function loadModels() {{
            const select = document.getElementById('modelSelect');
            if (!select || select.children.length > 1) return;
            try {{
                const res = await fetch('/api/ai/models');
                const data = await res.json();
                select.innerHTML = '';
                if (data.models && data.models.length > 0) {{
                    data.models.forEach(m => {{
                        const opt = document.createElement('option');
                        opt.value = m;
                        opt.innerText = m;
                        select.appendChild(opt);
                    }});
                }} else {{
                    select.innerHTML = '<option value="">Nem található modell az Ollamában!</option>';
                }}
            }} catch (e) {{
                select.innerHTML = '<option value="">Hiba az Ollama elérésekor</option>';
            }}
        }}

        function setPrompt(text) {{
            document.getElementById('userPrompt').value = text;
        }}

        async function sendAiQuestion() {{
            const model = document.getElementById('modelSelect').value;
            const promptBox = document.getElementById('userPrompt');
            const text = promptBox.value.trim();
            const sendBtn = document.getElementById('sendAiBtn');
            const chatBox = document.getElementById('chatBox');

            if (!model) {{ alert("Kérjük, válasszon ki egy modellt!"); return; }}
            if (!text) return;

            const uMsg = document.createElement('div');
            uMsg.className = 'msg msg-user';
            uMsg.innerText = text;
            chatBox.appendChild(uMsg);

            promptBox.value = '';
            sendBtn.disabled = true;
            sendBtn.innerText = 'Gondolkodik...';

            const aiMsg = document.createElement('div');
            aiMsg.className = 'msg msg-ai';
            aiMsg.innerText = '⏳ Adatbázis elemzése és válasz generálása...';
            chatBox.appendChild(aiMsg);
            chatBox.scrollTop = chatBox.scrollHeight;

            try {{
                const res = await fetch('/api/ai/ask', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ model: model, prompt: text }})
                }});
                const data = await res.json();
                if (data.status === 'SUCCESS') {{
                    aiMsg.innerText = data.response;
                }} else {{
                    aiMsg.innerText = 'Hiba történt: ' + (data.message || data.error);
                }}
            }} catch (err) {{
                aiMsg.innerText = 'Hálózati hiba: ' + err;
            }} finally {{
                sendBtn.disabled = false;
                sendBtn.innerText = 'Küldés';
                chatBox.scrollTop = chatBox.scrollHeight;
            }}
        }}
    </script>
</head>
<body>
    <div class="container">
        <div class="top-bar">
            <div style="display:flex; align-items:center; gap:20px;">
                <h2 style="margin:0;">AD Tracker Admin</h2>
                <span id="syncIndicator" class="sync-badge">⏳ Szinkronizálás Folyamatban...</span>
            </div>
            <span>Bejelentkezve: <b>{current_user}</b> <a href="/logout" class="btn" style="background:#ef4444; margin-left:10px;">Kijelentkezés</a></span>
        </div>
        
        <div class="tabs">
            <div id="tab-dashboard" class="tab active" onclick="switchTab('dashboard')">Jogosultság Változások</div>
            <div id="tab-users" class="tab" onclick="switchTab('users')">Felhasználók és Csoportok</div>
            <div id="tab-sync-history" class="tab" onclick="switchTab('sync-history')">Szinkronizálási Napló</div>
            <div id="tab-ai" class="tab" onclick="switchTab('ai')">AI Elemző & Asszisztens</div>
            <div id="tab-settings" class="tab" onclick="switchTab('settings')">Beállítások</div>
        </div>

        <!-- DASHBOARD -->
        <div id="content-dashboard" class="content active">
            <div style="margin-bottom: 15px; overflow: hidden;">
                <button id="syncBtn" class="btn" style="background:#16a34a; float:right;" onclick="doSync()">Azonnali Szinkronizálás</button>
            </div>
            <table>
                <thead><tr><th>Időpont</th><th>Érintett Fiók</th><th>Esemény</th><th>Részletek</th></tr></thead>
                <tbody>{rows if rows else '<tr><td colspan="4" style="text-align:center; color:#94a3b8; padding:20px;">Nincs naplózott változás.</td></tr>'}</tbody>
            </table>
        </div>

        <!-- FELHASZNÁLÓK -->
        <div id="content-users" class="content">
            <div class="search-box">
                <input type="text" id="userSearchBox" placeholder="Keresés név, email, azonosító vagy részleg alapján..." onkeyup="filterUsers()">
                <span id="userCountLabel" style="font-size:13px; color:#64748b; white-space:nowrap;"></span>
            </div>
            <table>
                <thead><tr><th>Név</th><th>Azonosító</th><th>Email</th><th>Titulus / Pozíció</th><th>Státusz</th><th>Utolsó módosítás</th></tr></thead>
                <tbody id="usersTableBody"></tbody>
            </table>
        </div>
        
        <!-- SZINKRONIZÁCIÓS NAPLÓ -->
        <div id="content-sync-history" class="content">
            <table>
                <thead><tr><th>Indítás ideje</th><th>Befejezés ideje</th><th>Időtartam</th><th>Kiváltó ok</th><th>Státusz</th><th>Észlelt Változások</th></tr></thead>
                <tbody id="syncHistoryBody"></tbody>
            </table>
        </div>

        <!-- AI ASSZISZTENS -->
        <div id="content-ai" class="content">
            <div class="ai-header">
                <div><b>Válasszon AI modellt:</b></div>
                <select id="modelSelect" style="max-width:300px; padding:6px; border-radius:4px; margin:0;">
                    <option value="">Modellek keresése az Ollamában...</option>
                </select>
                <span style="font-size:12px; color:#64748b; margin-left:auto;">Adatbázis-hozzáférés: 🟢 Csatlakoztatva</span>
            </div>

            <div class="quick-prompts">
                <button class="quick-btn" onclick="setPrompt('Készíts egy tömör biztonsági összefoglalót a legfrissebb AD változásokról!')">📊 Legfrissebb változások összefoglalása</button>
                <button class="quick-btn" onclick="setPrompt('Voltak-e csoporttagság-módosítások, különösen admin vagy kiemelt jogosultságú csoportoknál?')">🛡️ Kiemelt jogosultságok vizsgálata</button>
                <button class="quick-btn" onclick="setPrompt('Milyen fiók státusz változások vagy letiltások történtek az utóbbi időben?')">⚠️ Inaktivált / Módosított fiókok</button>
            </div>

            <div id="chatBox" class="chat-box">
                <div class="msg msg-ai">Üdvözlöm! Én vagyok a helyi AD Audit asszisztens. Közvetlen hozzáférésem van az exportált adatbázishoz és audit naplóhoz. Tegyen fel egy kérdést, vagy válasszon a fenti gyorsgombok közül!</div>
            </div>

            <div class="input-row">
                <textarea id="userPrompt" placeholder="Kérdezzen az AD eseményekről vagy fiókokról..." onkeydown="if(event.key==='Enter' && !event.shiftKey){{event.preventDefault(); sendAiQuestion();}}"></textarea>
                <button id="sendAiBtn" class="btn" onclick="sendAiQuestion()">Küldés</button>
            </div>
        </div>

        <!-- BEÁLLÍTÁSOK -->
        <div id="content-settings" class="content">
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                <!-- AD BEÁLLÍTÁSOK -->
                <div class="card-box">
                    <h4>Rendszer és AD Beállítások</h4>
                    <label>Active Directory Cím (Szerver:Port)</label><input type="text" id="ad_server" value="{ad_server}">
                    <label>Olvasó Felhasználó (Szerviz fiók)</label><input type="text" id="ad_user" value="{ad_user}">
                    <label>Jelszó (Hagyja üresen, ha nem változik)</label><input type="password" id="ad_password" placeholder="***">
                    <label>Keresési Bázis (Search Base)</label><input type="text" id="ad_base" value="{ad_base}">
                    <label>Ollama API Elérési Út</label><input type="text" id="ollama_url" value="{ollama_url}">
                    <label>Automatikus Szinkronizálás Gyakorisága</label>
                    <select id="sync_interval">
                        <option value="0" {"selected" if interval_min==0 else ""}>Kikapcsolva</option>
                        <option value="5" {"selected" if interval_min==5 else ""}>5 percenként</option>
                        <option value="15" {"selected" if interval_min==15 else ""}>15 percenként</option>
                        <option value="60" {"selected" if interval_min==60 else ""}>1 óra</option>
                        <option value="240" {"selected" if interval_min==240 else ""}>4 óra</option>
                        <option value="360" {"selected" if interval_min==360 else ""}>6 óra</option>
                        <option value="720" {"selected" if interval_min==720 else ""}>12 óra</option>
                        <option value="1440" {"selected" if interval_min==1440 else ""}>24 óra (1 nap)</option>
                        <option value="2880" {"selected" if interval_min==2880 else ""}>48 óra (2 nap)</option>
                    </select>
                    <button class="btn" style="width:100%; margin-top:10px;" onclick="saveSettings()">Beállítások Mentése</button>
                </div>

                <!-- GITHUB BEÁLLÍTÁSOK -->
                <div class="card-box">
                    <h4>GitHub Integráció & Publikáció</h4>
                    <label>Repó Neve (Szervezet/Repó)</label>
                    <input type="text" id="gh_repo" value="{gh_repo}" placeholder="pl. TSPC-Group/ad-tracker">
                    
                    <label>Personal Access Token (PAT)</label>
                    <input type="password" id="gh_token" value="{gh_token}" placeholder="ghp_xxxxxxxxxxxx...">
                    
                    <label>Cél ág (Branch)</label>
                    <input type="text" id="gh_branch" value="{gh_branch}" placeholder="pl. main">
                    
                    <label style="color:#0284c7; font-weight:bold; margin-top:5px;">Új verzió megjegyzése (Commit üzenet):</label>
                    <input type="text" id="gh_custom_msg" placeholder="Milyen új funkció vagy javítás készült? (Opcionális)" style="border-color:#0284c7; background:#f0f9ff;">
                    
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-top: 10px;">
                        <button id="ghTestBtn" class="btn" style="background:#475569;" onclick="testGitHub()">Kapcsolat Tesztelése</button>
                        <span style="font-size:14px; font-weight:bold;">Aktuális: <span style="color:#0284c7;">v<span id="app_version_label">{app_version}</span></span></span>
                        <button id="ghPushBtn" class="btn" style="background:#16a34a;" onclick="pushToGitHub()">Kód Publikálása (Push)</button>
                    </div>

                    <h5 style="margin:20px 0 5px 0; border-bottom:1px solid #cbd5e1; padding-bottom:5px; color:#475569;">Verziótörténet a GitHub-on</h5>
                    <div id="gh_history_list" class="gh-history-box">
                        Kattints a Beállítások fülre vagy a Tesztelés gombra a betöltéshez...
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- BŐVÍTETT USER MODAL -->
    <div id="userModal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeAllModals()">&times;</span>
            <h2 style="margin-top:0; color:#0f172a;"><span id="m-name"></span> <span id="m-status" style="margin-left:15px; vertical-align:middle;"></span></h2>
            
            <div class="grid">
                <div class="card-box">
                    <h4>Fiók és Személyes Adatok</h4>
                    <div class="data-row"><strong>Azonosító:</strong><span id="m-sam"></span></div>
                    <div class="data-row"><strong>Vezetéknév:</strong><span id="m-lname"></span></div>
                    <div class="data-row"><strong>Keresztnév:</strong><span id="m-fname"></span></div>
                    <div class="data-row"><strong>Leírás:</strong><span id="m-desc"></span></div>
                    <div class="data-row"><strong>Email cím:</strong><span id="m-mail"></span></div>
                </div>
                
                <div class="card-box">
                    <h4>Szervezeti Adatok</h4>
                    <div class="data-row"><strong>Cég:</strong><span id="m-company"></span></div>
                    <div class="data-row"><strong>Részleg:</strong><span id="m-dept"></span></div>
                    <div class="data-row"><strong>Titulus/Pozíció:</strong><span id="m-title"></span></div>
                    <div class="data-row"><strong>Iroda:</strong><span id="m-office"></span></div>
                </div>

                <div class="card-box">
                    <h4>Technikai és Rendszeradatok</h4>
                    <div class="data-row"><strong>SID azonosító:</strong><span id="m-sid" style="font-size:11px; word-break:break-all; text-align:right;"></span></div>
                    <div class="data-row"><strong>Létrehozva:</strong><span id="m-created"></span></div>
                    <div class="data-row"><strong>Módosítva:</strong><span id="m-changed"></span></div>
                    <div class="data-row"><strong>Asztali telefon:</strong><span id="m-phone"></span></div>
                    <div class="data-row"><strong>Mobiltelefon:</strong><span id="m-mobile"></span></div>
                </div>

                <div class="card-box">
                    <h4>Tagságok (Kattints egy csoportra a megnyitásához)</h4>
                    <div id="m-groups" style="line-height: 2;"></div>
                </div>
            </div>
        </div>
    </div>

    <!-- CSOPORT MODAL -->
    <div id="groupModal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeAllModals()">&times;</span>
            <h2 style="margin-top:0; color:#0f172a;">👥 <span id="g-name"></span></h2>
            
            <div class="grid">
                <div class="card-box">
                    <h4>Csoport Adatai</h4>
                    <div class="data-row"><strong>Típus:</strong><span id="g-type" style="font-weight:bold; color:#0369a1;"></span></div>
                    <div class="data-row"><strong>Leírás:</strong><span id="g-desc"></span></div>
                    <div class="data-row"><strong>Tagok száma:</strong><span id="g-count" style="font-weight:bold;"></span></div>
                    <div class="data-row"><strong>Létrehozva:</strong><span id="g-created"></span></div>
                    <div class="data-row"><strong>Módosítva:</strong><span id="g-changed"></span></div>
                    <div class="data-row"><strong>SID azonosító:</strong><span id="g-sid" style="font-size:11px; word-break:break-all; text-align:right;"></span></div>
                </div>
                
                <div class="card-box" style="grid-row: span 2;">
                    <h4>Csoport Tagjai (Kattints egy tagra)</h4>
                    <div id="g-members" style="line-height: 2; max-height:400px; overflow-y:auto; padding-right:10px;"></div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>"""
