from fastapi import FastAPI, Depends, Request, Form, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, text
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timezone
from typing import List
import threading
import os
import shutil

from database import engine, Base, get_db, SessionLocal
import models
from sync_engine import run_ad_sync
from config_manager import init_default_settings, get_setting, update_setting
from ldap_client import test_ad_connection
from auth import authenticate_ad_user, create_session_token, verify_session_token, COOKIE_NAME
from ai_assistant import fetch_ollama_models, ask_ollama
from github_sync import test_github_connection, push_code_to_github, get_github_commit_history, get_latest_github_version
from backup_manager import create_backup, list_backups, restore_backup, delete_backup, BACKUP_DIR
from history_importer import scan_csv_directory, run_historical_replay, fast_backfill_extra_data

models.Base.metadata.create_all(bind=engine)

# Automatikus adatbázis oszlop-migráció
try:
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE ad_users ADD COLUMN IF NOT EXISTS last_logon_date TIMESTAMP WITH TIME ZONE;"))
        conn.execute(text("ALTER TABLE ad_users ADD COLUMN IF NOT EXISTS user_status VARCHAR(100);"))
        conn.execute(text("ALTER TABLE ad_users ADD COLUMN IF NOT EXISTS ou_path TEXT;"))
        conn.execute(text("ALTER TABLE ad_audit_log ALTER COLUMN raw_diff TYPE TEXT USING raw_diff::text;"))
        conn.commit()
except Exception:
    pass

db_init = SessionLocal()
init_default_settings(db_init)
db_init.close()

scheduler = BackgroundScheduler()
JOB_ID = "ad_sync_job"
sync_state = {"is_syncing": False, "last_run": None, "last_changes": 0}
sync_lock = threading.Lock()

import_progress = {
    "is_running": False,
    "current_step": 0,
    "total_steps": 0,
    "current_time": "",
    "result": None
}

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
    return f"""<!DOCTYPE html>
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
</form></div></body></html>"""

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
    try:
        logs = db.query(models.SyncHistory).order_by(desc(models.SyncHistory.started_at)).limit(50).all()
        return [{"id": l.id, "started": l.started_at.strftime("%Y-%m-%d %H:%M:%S") if l.started_at else "-", "ended": l.ended_at.strftime("%Y-%m-%d %H:%M:%S") if l.ended_at else "-", "duration": f"{l.duration_seconds} mp" if l.duration_seconds is not None else "-", "trigger": l.trigger_type, "status": l.status, "changes": l.changes_detected, "error": l.error_message or ""} for l in logs]
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/users")
def get_all_users(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    try:
        users = db.query(models.ADUser).all()
        result = []
        for u in users:
            u_status = getattr(u, "user_status", None)
            if not u_status:
                u_status = "Aktív normál user" if getattr(u, "is_enabled", True) else "Letiltva"
            
            last_logon_dt = getattr(u, "last_logon_date", None)
            last_logon_str = last_logon_dt.strftime("%Y-%m-%d %H:%M") if last_logon_dt and hasattr(last_logon_dt, "strftime") else "-"
            ou_path = getattr(u, "ou_path", None) or "-"
            w_created = getattr(u, "when_created", None)
            w_changed = getattr(u, "when_changed", None)

            result.append({
                "sam": getattr(u, "sam_account_name", "-"),
                "name": getattr(u, "display_name", None) or "-",
                "first_name": getattr(u, "first_name", None) or "-",
                "last_name": getattr(u, "last_name", None) or "-",
                "mail": getattr(u, "mail", None) or "-",
                "enabled": getattr(u, "is_enabled", True),
                "status": u_status,
                "last_logon": last_logon_str,
                "ou": ou_path,
                "phone": getattr(u, "telephone_number", None) or "-",
                "mobile": getattr(u, "mobile", None) or "-",
                "title": getattr(u, "title", None) or "-",
                "department": getattr(u, "department", None) or "-",
                "company": getattr(u, "company", None) or "-",
                "office": getattr(u, "office", None) or "-",
                "desc": getattr(u, "description", None) or "-",
                "sid": getattr(u, "object_sid", None) or "-",
                "created": w_created.strftime("%Y-%m-%d %H:%M") if w_created else "-",
                "changed": w_changed.strftime("%Y-%m-%d %H:%M") if w_changed else "-",
                "groups": [{"name": getattr(g, "sam_account_name", "-"), "type": getattr(g, "group_type", None) or "Ismeretlen"} for g in getattr(u, "groups", [])]
            })
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/users/{sam}/history")
def get_user_history(sam: str, request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    try:
        logs = db.query(models.ADAuditLog)\
            .filter(models.ADAuditLog.entity_name.ilike(sam))\
            .order_by(desc(models.ADAuditLog.timestamp))\
            .all()
        return [{
            "timestamp": l.timestamp.strftime("%Y-%m-%d %H:%M:%S") if l.timestamp else "-",
            "change_type": l.change_type,
            "details": l.details or ""
        } for l in logs]
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/groups")
def get_all_groups(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    try:
        groups = db.query(models.ADGroup).all()
        return [{"sam": g.sam_account_name, "desc": g.description or "-", "type": g.group_type or "Ismeretlen", "sid": g.object_sid or "-", "created": g.when_created.strftime("%Y-%m-%d %H:%M") if g.when_created else "-", "changed": g.when_changed.strftime("%Y-%m-%d %H:%M") if g.when_changed else "-", "members": [u.sam_account_name for u in g.members]} for g in groups]
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/sync")
def trigger_sync_manual(request: Request):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    threading.Thread(target=execute_sync_with_log, args=("Manuális",)).start()
    return {"status": "STARTED"}

# --- TÖRTÉNETI CSV IMPORT ÉS GYORS BACKFILL ---
@app.post("/api/history/upload-files")
async def api_history_upload_files(request: Request, files: List[UploadFile] = File(...)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    app_dir = os.path.dirname(os.path.abspath(__file__))
    upload_dir = os.path.join(app_dir, "csv_imports")
    os.makedirs(upload_dir, exist_ok=True)

    saved_count = 0
    for file in files:
        fname = os.path.basename(file.filename)
        if fname.lower().endswith(".csv"):
            dest_path = os.path.join(upload_dir, fname)
            with open(dest_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            saved_count += 1
    return {"status": "SUCCESS", "saved_files": saved_count}

@app.post("/api/history/scan")
async def api_history_scan(request: Request):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    data = await request.json()
    folder = data.get("folder", "csv_imports")
    return scan_csv_directory(folder)

@app.post("/api/history/backfill")
async def api_history_backfill(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    data = await request.json()
    folder = data.get("folder", "csv_imports")
    return fast_backfill_extra_data(db, folder)

def async_import_worker(folder: str):
    global import_progress
    import_progress["is_running"] = True
    import_progress["result"] = None
    def on_progress(cur, total, ts_str):
        import_progress["current_step"] = cur
        import_progress["total_steps"] = total
        import_progress["current_time"] = ts_str
    db = SessionLocal()
    try:
        res = run_historical_replay(db, folder, progress_callback=on_progress)
        import_progress["result"] = res
    except Exception as e:
        import_progress["result"] = {"status": "ERROR", "message": str(e)}
    finally:
        db.close()
        import_progress["is_running"] = False

@app.post("/api/history/import")
async def api_history_import(request: Request):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    if import_progress["is_running"]: return {"status": "ERROR", "message": "Importálás folyamatban!"}
    data = await request.json()
    folder = data.get("folder", "csv_imports")
    threading.Thread(target=async_import_worker, args=(folder,)).start()
    return {"status": "STARTED"}

@app.get("/api/history/progress")
def api_history_progress(request: Request):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    return import_progress

# --- BIZTONSÁGI MENTÉSEK ---
@app.get("/api/backups")
def get_backups_list(request: Request):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    return {"backups": list_backups()}

@app.post("/api/backups/create")
async def create_backup_endpoint(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return JSONResponse(status_code=401, content={})
    data = await request.json()
    return create_backup(db, comment=data.get("comment", ""), user=user)

@app.post("/api/backups/restore")
async def restore_backup_endpoint(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    data = await request.json()
    return restore_backup(db, filename=data.get("filename", ""))

@app.get("/api/backups/download/{filename}")
def download_backup_endpoint(filename: str, request: Request):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    safe_name = os.path.basename(filename)
    fpath = os.path.join(BACKUP_DIR, safe_name)
    if not os.path.isfile(fpath): return JSONResponse(status_code=404, content={"error": "Fájl nem található"})
    return FileResponse(fpath, filename=safe_name, media_type="application/zip")

@app.delete("/api/backups/{filename}")
def delete_backup_endpoint(filename: str, request: Request):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    return delete_backup(filename)

# --- GitHub Végpontok (Élő GitHub verzióval) ---
@app.get("/api/github/version")
def api_gh_get_version(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    repo = get_setting(db, "GH_REPO")
    token = get_setting(db, "GH_TOKEN")
    branch = get_setting(db, "GH_BRANCH", "main")
    if not repo or not token:
        local_ver = get_setting(db, "APP_VERSION", "1.00").replace("v", "")
        return {"version": local_ver, "source": "local"}
    
    gh_version = get_latest_github_version(repo, token, branch)
    update_setting(db, "APP_VERSION", gh_version)
    return {"version": gh_version, "source": "github"}

@app.post("/api/github/test")
async def api_gh_test(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    data = await request.json()
    repo = data.get("repo") or get_setting(db, "GH_REPO")
    token = data.get("token") or get_setting(db, "GH_TOKEN")
    if not repo or not token: return {"status": "ERROR", "message": "Hiányzó adatok!"}
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
    if not repo or not token: return {"status": "ERROR", "message": "Nincs beállítva GitHub."}
    ok, data = get_github_commit_history(repo, token, branch)
    return {"status": "SUCCESS" if ok else "ERROR", "data": data}

@app.post("/api/github/push")
async def api_gh_push(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={"status": "ERROR", "message": "Munkamenet lejárt!"})
    try:
        req_data = await request.json()
        custom_msg = req_data.get("message", "")
        repo = req_data.get("repo") or get_setting(db, "GH_REPO")
        token = req_data.get("token") or get_setting(db, "GH_TOKEN")
        branch = req_data.get("branch") or get_setting(db, "GH_BRANCH", "main")
        
        current_gh_ver = get_latest_github_version(repo, token, branch)
        try:
            curr_float = float(current_gh_ver)
        except ValueError:
            curr_float = 1.00

        new_ver = curr_float + 0.01
        new_ver_str = f"{new_ver:.2f}"

        ok, msg = push_code_to_github(repo, branch, token, new_ver_str, custom_msg)
        if ok:
            update_setting(db, "APP_VERSION", new_ver_str)
            return {"status": "SUCCESS", "message": msg, "new_version": new_ver_str}
        return {"status": "ERROR", "message": msg}
    except Exception as e:
        return {"status": "ERROR", "message": f"Hiba: {str(e)}"}

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

# --- FŐOLDAL BETÖLTÉSE A SABLONBÓL ---
HTML_TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "index.html")

@app.get("/", response_class=HTMLResponse)
def index_page(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request)
    if not current_user: return RedirectResponse(url="/login", status_code=303)

    logs = db.query(models.ADAuditLog).order_by(desc(models.ADAuditLog.timestamp)).limit(50).all()
    rows = ""
    for l in logs:
        badge = "#16a34a" if "ADDED" in l.change_type or "CREATED" in l.change_type else ("#dc2626" if "REMOVED" in l.change_type or "DISABLED" in l.change_type else "#2563eb")
        t = l.timestamp.strftime("%Y-%m-%d %H:%M") if l.timestamp else ""
        rows += f'<tr><td>{t}</td><td><b>{l.entity_name}</b></td><td><span style="background:{badge}; color:white; padding:3px 6px; border-radius:4px; font-size:11px;">{l.change_type}</span></td><td>{l.details}</td></tr>'

    if not rows:
        rows = '<tr><td colspan="4" style="text-align:center; color:#94a3b8; padding:20px;">Nincs naplózott változás.</td></tr>'

    job = scheduler.get_job(JOB_ID)
    interval_min = int(job.trigger.interval.total_seconds() / 60) if job else 0

    opts = [
        (0, "Kikapcsolva"), (5, "5 percenként"), (15, "15 percenként"),
        (60, "1 óra"), (240, "4 óra"), (360, "6 óra"),
        (720, "12 óra"), (1440, "24 óra (1 nap)"), (2880, "48 óra (2 nap)")
    ]
    interval_options = "\n".join([f'<option value="{m}" {"selected" if interval_min==m else ""}>{lbl}</option>' for m, lbl in opts])

    with open(HTML_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    html = html.replace("{{CURRENT_USER}}", current_user)\
               .replace("{{ROWS}}", rows)\
               .replace("{{AD_SERVER}}", get_setting(db, "AD_SERVER", ""))\
               .replace("{{AD_USER}}", get_setting(db, "AD_USER", ""))\
               .replace("{{AD_BASE}}", get_setting(db, "AD_SEARCH_BASE", ""))\
               .replace("{{OLLAMA_URL}}", get_setting(db, "OLLAMA_URL", "http://ollama:11434"))\
               .replace("{{GH_REPO}}", get_setting(db, "GH_REPO", ""))\
               .replace("{{GH_TOKEN}}", get_setting(db, "GH_TOKEN", ""))\
               .replace("{{GH_BRANCH}}", get_setting(db, "GH_BRANCH", "main"))\
               .replace("{{INTERVAL_SELECT}}", interval_options)

    return HTMLResponse(content=html)
