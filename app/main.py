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
from github_sync import test_github_connection, push_code_to_github, get_github_commit_history
from backup_manager import create_backup, list_backups, restore_backup, delete_backup, BACKUP_DIR
from history_importer import scan_csv_directory, run_historical_replay, fast_backfill_extra_data

models.Base.metadata.create_all(bind=engine)

# Automatikus adatbázis oszlop-migráció meglévő adatok megtartásával
try:
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE ad_users ADD COLUMN IF NOT EXISTS last_logon_date TIMESTAMP WITH TIME ZONE;"))
        conn.execute(text("ALTER TABLE ad_users ADD COLUMN IF NOT EXISTS user_status VARCHAR(100);"))
        conn.execute(text("ALTER TABLE ad_users ADD COLUMN IF NOT EXISTS ou_path TEXT;"))
        conn.commit()
except Exception:
    pass

db_init = SessionLocal()
init_default_settings(db_init)
if not get_setting(db_init, "APP_VERSION"):
    update_setting(db_init, "APP_VERSION", "1.02")
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
            # Golyóálló lekérdezések a getattr használatával (ha egy oszlop véletlen hiányozna)
            u_status = getattr(u, "user_status", None)
            if not u_status:
                u_status = "Aktív normál user" if getattr(u, "is_enabled", True) else "Letiltva"
            
            last_logon_dt = getattr(u, "last_logon_date", None)
            if last_logon_dt and hasattr(last_logon_dt, "strftime"):
                last_logon_str = last_logon_dt.strftime("%Y-%m-%d %H:%M")
            else:
                last_logon_str = "-"

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
        import traceback
        traceback.print_exc()
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

# --- GitHub Végpontok ---
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
        
        raw_ver = str(get_setting(db, "APP_VERSION", "1.02")).replace("v", "").strip()
        try: current_ver = float(raw_ver)
        except ValueError: current_ver = 1.02
        new_ver_str = f"{current_ver + 0.01:.2f}"

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

    ad_server = get_setting(db, "AD_SERVER")
    ad_user = get_setting(db, "AD_USER")
    ad_base = get_setting(db, "AD_SEARCH_BASE")
    ollama_url = get_setting(db, "OLLAMA_URL", "http://ollama:11434")
    gh_repo = get_setting(db, "GH_REPO")
    gh_token = get_setting(db, "GH_TOKEN")
    gh_branch = get_setting(db, "GH_BRANCH", "main")
    app_version = get_setting(db, "APP_VERSION", "1.02").replace("v", "")
    
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
        
        .btn-restore {{ background: #ea580c; color: white; border: none; padding: 5px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; font-weight: bold; margin-right: 5px; }}
        .btn-download {{ background: #0284c7; color: white; border: none; padding: 5px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; font-weight: bold; text-decoration: none; margin-right: 5px; }}
        .btn-delete {{ background: #dc2626; color: white; border: none; padding: 5px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; font-weight: bold; }}
    </style>
    <script>
        const NL = String.fromCharCode(10);
        let allUsers = [];
        let allGroups = [];
        let isSyncing = false;
        let selectedLocalFiles = [];

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
            if (tabId === 'backups') loadBackups();
            if (tabId === 'history-import') autoScanServerFolder();
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
                    tbody.innerHTML += '<tr><td><b>' + l.started + '</b></td><td>' + l.ended + '</td><td>' + l.duration + '</td><td>' + l.trigger + '</td><td><b style="color:' + c + '">' + l.status + '</b></td><td>' + l.changes + ' db</td></tr>';
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

                let badgeColor = '#15803d', badgeBg = '#dcfce7';
                if (u.status === 'Külsös') {{ badgeColor = '#b45309'; badgeBg = '#fef3c7'; }}
                else if (u.status === 'Távozottak' || !u.enabled) {{ badgeColor = '#b91c1c'; badgeBg = '#fee2e2'; }}
                else if (u.status === 'Hosszútávúszabadság') {{ badgeColor = '#6d28d9'; badgeBg = '#ede9fe'; }}
                
                const stBadge = '<span style="background:' + badgeBg + '; color:' + badgeColor + '; padding:3px 8px; border-radius:10px; font-size:12px; font-weight:bold;">' + u.status + '</span>';

                tr.innerHTML = '<td><b>' + u.name + '</b></td><td>' + u.sam + '</td><td>' + u.mail + '</td><td>' + stBadge + '</td><td>' + u.title + '</td><td>' + u.last_logon + '</td>';
                tbody.appendChild(tr);
            }});
            const countLabel = document.getElementById('userCountLabel');
            if (countLabel) countLabel.innerText = 'Találat: ' + usersList.length + ' fiók (150 megjelenítve)';
        }}

        function filterUsers() {{
            const term = document.getElementById('userSearchBox').value.toLowerCase();
            if (!term) {{ renderUsers(allUsers); return; }}
            const filtered = allUsers.filter(u => 
                (u.name && u.name.toLowerCase().includes(term)) || 
                (u.sam && u.sam.toLowerCase().includes(term)) || 
                (u.mail && u.mail.toLowerCase().includes(term)) ||
                (u.department && u.department.toLowerCase().includes(term)) ||
                (u.status && u.status.toLowerCase().includes(term)) ||
                (u.ou && u.ou.toLowerCase().includes(term))
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
            document.getElementById('m-userstatus').innerText = u.status;
            document.getElementById('m-lastlogon').innerText = u.last_logon;
            document.getElementById('m-ou').innerText = u.ou;
            
            let gHtml = '';
            if (u.groups && u.groups.length > 0) {{
                u.groups.forEach(g => {{
                    const cssClass = g.type.includes('Terjesztési') ? 'group-tag dist' : 'group-tag';
                    gHtml += '<span class="' + cssClass + '" onclick="event.stopPropagation(); openGroupModal(\\'' + g.name + '\\')">' + g.name + '</span> ';
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
                    mHtml += '<span class="user-tag" onclick="event.stopPropagation(); openUserModal(\\'' + memberSam + '\\')">👤 ' + memberSam + '</span> ';
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

        function triggerClientFolderPicker() {{
            document.getElementById('client_folder_picker').click();
        }}

        function handleClientFolderSelect(input) {{
            const files = Array.from(input.files);
            if (!files || files.length === 0) return;

                        const timeRegex = /([0-9]{{8}}[-_][0-9]{{6}})/;
            const snapshotsMap = {{}};
            selectedLocalFiles = [];

            files.forEach(f => {{
                if (f.name.toLowerCase().endsWith('.csv')) {{
                    const match = timeRegex.exec(f.name);
                    if (match) {{
                        selectedLocalFiles.push(f);
                        const ts = match[1].replace('-', '_');
                        if (!snapshotsMap[ts]) {{
                            snapshotsMap[ts] = {{ ts: ts, filesCount: 0, hasGroups: false, hasAllUser: false }};
                        }}
                        snapshotsMap[ts].filesCount++;
                        const low = f.name.toLowerCase();
                        if (low.includes('group_') || low.startsWith('groups')) snapshotsMap[ts].hasGroups = true;
                        if (low.startsWith('alluser')) snapshotsMap[ts].hasAllUser = true;
                    }}
                }}
            }});

            const infoBox = document.getElementById('history_scan_info');
            const tbody = document.getElementById('historyTableBody');
            const startBtn = document.getElementById('startHistoryBtn');

            const sortedKeys = Object.keys(snapshotsMap).sort();
            if (sortedKeys.length === 0) {{
                infoBox.innerHTML = '<span style="color:#dc2626;">❌ Nem található a mintának megfelelő CSV fájl a kiválasztott mappában!</span>';
                tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:15px; color:#94a3b8;">A kiválasztott mappa nem tartalmazott felismerhető fájlokat.</td></tr>';
                startBtn.disabled = true;
                return;
            }}

            infoBox.innerHTML = '💻 <b>Kliens gép mappája kiválasztva:</b> Összesen <b>' + selectedLocalFiles.length + ' db releváns CSV fájl</b> találva, <b>' + sortedKeys.length + ' különböző mentési időponttal</b>!';
            tbody.innerHTML = '';
            sortedKeys.forEach(ts => {{
                const item = snapshotsMap[ts];
                const year = ts.substring(0, 4), mon = ts.substring(4, 6), day = ts.substring(6, 8);
                const hour = ts.substring(9, 11), min = ts.substring(11, 13), sec = ts.substring(13, 15);
                const dStr = year + '-' + mon + '-' + day + ' ' + hour + ':' + min + ':' + sec;

                tbody.innerHTML += '<tr><td><b>' + dStr + '</b></td><td><code>' + ts + '</code></td><td>' + item.filesCount + ' db fájl</td><td>' + (item.hasGroups ? '✅ Igen' : '❌ Nincs') + '</td><td>' + (item.hasAllUser ? '✅ Igen' : '⚪ Nem') + '</td></tr>';
            }});

            startBtn.disabled = false;
            startBtn.innerText = 'Feltöltés és Idővonal Feldolgozása (' + selectedLocalFiles.length + ' fájl)';
        }}

        function autoScanServerFolder() {{
            const f = document.getElementById('history_folder_input').value.trim();
            if (f && selectedLocalFiles.length === 0) scanServerFolder();
        }}

        async function scanServerFolder() {{
            const folder = document.getElementById('history_folder_input').value.trim();
            const btn = document.getElementById('scanHistoryBtn');
            const infoBox = document.getElementById('history_scan_info');
            const tbody = document.getElementById('historyTableBody');
            const startBtn = document.getElementById('startHistoryBtn');

            btn.disabled = true; btn.innerText = 'Felderítés...';
            tbody.innerHTML = '<tr><td colspan="5">Szerver mappa vizsgálata...</td></tr>';
            try {{
                const res = await fetch('/api/history/scan', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{ folder: folder }})
                }});
                const data = await res.json();
                if (data.status === 'SUCCESS') {{
                    infoBox.innerHTML = '🖥️ <b>Szerver mappa:</b> <b>' + data.total_snapshots + ' darab időpont-mentés</b> azonosítva a szerveren: <code>' + data.folder + '</code>';
                    tbody.innerHTML = '';
                    if (data.snapshots.length === 0) {{
                        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:15px; color:#94a3b8;">A szerver mappája üres. Tallózzon a kliens gépről a fenti kék gombbal!</td></tr>';
                        startBtn.disabled = true;
                    }} else {{
                        data.snapshots.forEach(s => {{
                            tbody.innerHTML += '<tr><td><b>' + s.datetime + '</b></td><td><code>' + s.timestamp + '</code></td><td>' + s.user_files_count + ' db fájl</td><td>' + (s.has_groups ? '✅ Igen' : '❌ Nincs') + '</td><td>' + (s.has_alluser ? '✅ Igen' : '⚪ Nem') + '</td></tr>';
                        }});
                        startBtn.disabled = false;
                        startBtn.innerText = 'Történeti Idővonal Újraépítése (Import)';
                    }}
                }} else {{
                    infoBox.innerHTML = '<span style="color:#dc2626;">❌ ' + data.message + '</span>';
                    tbody.innerHTML = '<tr><td colspan="5" style="color:#dc2626;">Hiba a mappa elérésekor.</td></tr>';
                    startBtn.disabled = true;
                }}
            }} catch(e) {{
                infoBox.innerHTML = '<span style="color:#dc2626;">Hálózati hiba: ' + e + '</span>';
            }} finally {{
                btn.disabled = false; btn.innerText = 'Szerver Mappa Felderítése';
            }}
        }}

        async function doQuickBackfill() {{
            const folder = document.getElementById('history_folder_input').value.trim();
            if (!confirm('Gyorsan frissíti a meglévő felhasználók adatait (Utolsó belépés, Besorolás, OU) a szerveren lévő CSV fájlok alapján?')) return;
            
            const btn = document.getElementById('backfillBtn');
            btn.disabled = true; btn.innerText = 'Frissítés folyamatban...';
            try {{
                const res = await fetch('/api/history/backfill', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{ folder: folder }})
                }});
                const data = await res.json();
                if (data.status === 'SUCCESS') {{
                    alert('✅ ' + data.message);
                    allUsers = [];
                    loadUsersAndGroups();
                }} else {{
                    alert('❌ Hiba: ' + data.message);
                }}
            }} catch(e) {{
                alert('Hálózati hiba: ' + e);
            }} finally {{
                btn.disabled = false; btn.innerText = '⚡ CSV Extra Adatok Frissítése (Backfill)';
            }}
        }}

        async function startHistoryImport() {{
            const btn = document.getElementById('startHistoryBtn');
            const progressBox = document.getElementById('import_progress_box');
            const progressBar = document.getElementById('import_bar');
            const statusText = document.getElementById('import_status_text');

            if (selectedLocalFiles.length > 0) {{
                if (!confirm('Biztosan feltölti és feldolgozza a kiválasztott ' + selectedLocalFiles.length + ' darab CSV fájlt a saját gépéről?')) return;
                
                btn.disabled = true;
                progressBox.style.display = 'block';
                progressBar.style.width = '10%';
                statusText.innerText = 'Fájlok feltöltése a szerverre...';

                const batchSize = 25;
                for (let i = 0; i < selectedLocalFiles.length; i += batchSize) {{
                    const batch = selectedLocalFiles.slice(i, i + batchSize);
                    const formData = new FormData();
                    batch.forEach(f => formData.append('files', f));

                    const uploadPct = Math.round(((i + batch.length) / selectedLocalFiles.length) * 40);
                    progressBar.style.width = uploadPct + '%';
                    statusText.innerText = 'Fájlok feltöltése folyamatban: ' + (i + batch.length) + ' / ' + selectedLocalFiles.length + ' db...';

                    const upRes = await fetch('/api/history/upload-files', {{
                        method: 'POST',
                        body: formData
                    }});
                    if (!upRes.ok) {{
                        alert('Hiba történt a fájlok feltöltése közben!');
                        btn.disabled = false;
                        return;
                    }}
                }}
            }} else {{
                if (!confirm('Biztosan elindítja a szerveren lévő CSV fájlok időrendi feldolgozását?')) return;
                btn.disabled = true;
                progressBox.style.display = 'block';
            }}

            progressBar.style.width = '45%';
            statusText.innerText = 'Idővonal felépítése és eseménynapló generálása...';

            try {{
                await fetch('/api/history/import', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{ folder: 'csv_imports' }})
                }});
                trackHistoryProgress();
            }} catch(e) {{
                alert('Nem sikerült elindítani a feldolgozást: ' + e);
                btn.disabled = false;
            }}
        }}

        async function trackHistoryProgress() {{
            const interval = setInterval(async () => {{
                try {{
                    const res = await fetch('/api/history/progress');
                    const data = await res.json();
                    
                    if (data.is_running) {{
                        const pct = data.total_steps > 0 ? 40 + Math.round((data.current_step / data.total_steps) * 60) : 50;
                        document.getElementById('import_bar').style.width = pct + '%';
                        document.getElementById('import_status_text').innerText = 'Mentés feldolgozása: ' + data.current_step + ' / ' + data.total_steps + ' (' + pct + '%) -> Mentési időpont: ' + data.current_time;
                    }} else {{
                        clearInterval(interval);
                        document.getElementById('import_bar').style.width = '100%';
                        if (data.result && data.result.status === 'SUCCESS') {{
                            document.getElementById('import_status_text').innerHTML = 
                                '<b style="color:#16a34a;">✅ Sikeres Történeti Import!</b><br/>' +
                                'Feldolgozott időpontok: <b>' + data.result.processed_snapshots + ' db</b> | Generált audit események: <b>' + data.result.total_events_logged + ' db</b><br/>' +
                                'Időszak: <code>' + data.result.first_snapshot + '</code> &rarr; <code>' + data.result.last_snapshot + '</code>';
                            alert('A történeti importálás és diff-képzés sikeresen befejeződött!');
                        }} else {{
                            const errMsg = (data.result && data.result.message) ? data.result.message : 'Ismeretlen hiba';
                            document.getElementById('import_status_text').innerHTML = '<b style="color:#dc2626;">Hiba történt: ' + errMsg + '</b>';
                        }}
                        document.getElementById('startHistoryBtn').disabled = false;
                        document.getElementById('startHistoryBtn').innerText = 'Újraindítás / Feldolgozás';
                    }}
                }} catch(e) {{
                    clearInterval(interval);
                }}
            }}, 2000);
        }}

        // --- BIZTONSÁGI MENTÉSEK KEZELÉSE ---
        async function loadBackups() {{
            const tbody = document.getElementById('backupsTableBody');
            if (!tbody) return;
            tbody.innerHTML = '<tr><td colspan="7">Mentések keresése...</td></tr>';
            try {{
                const res = await fetch('/api/backups');
                const data = await res.json();
                tbody.innerHTML = '';
                if (!data.backups || data.backups.length === 0) {{
                    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:#94a3b8; padding:20px;">Még nem készült biztonsági mentés.</td></tr>';
                    return;
                }}
                data.backups.forEach(b => {{
                    tbody.innerHTML += '<tr><td><b>' + b.created_at + '</b></td><td><span style="background:#e0f2fe; color:#0369a1; padding:3px 8px; border-radius:4px; font-weight:bold;">' + b.version + '</span></td><td><span style="font-family:monospace; font-size:12px;">' + b.filename + '</span></td><td>' + b.size + '</td><td>' + b.comment + '</td><td><small style="color:#64748b;">' + b.author + '</small></td><td style="white-space:nowrap;"><button class="btn-restore" onclick="restoreBackup(\\'' + b.filename + '\\')">Visszaállítás</button><a class="btn-download" href="/api/backups/download/' + b.filename + '">Letöltés</a><button class="btn-delete" onclick="deleteBackup(\\'' + b.filename + '\\')">Törlés</button></td></tr>';
                }});
            }} catch(e) {{
                tbody.innerHTML = '<tr><td colspan="7" style="color:#dc2626;">Hiba a mentések betöltésekor: ' + e + '</td></tr>';
            }}
        }}

        async function createNewBackup() {{
            const commentInput = document.getElementById('backup_comment');
            const comment = commentInput.value.trim();
            const btn = document.getElementById('createBackupBtn');

            btn.disabled = true; btn.innerText = 'Mentés készítése...';
            try {{
                const res = await fetch('/api/backups/create', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{ comment: comment }})
                }});
                const data = await res.json();
                if (data.status === 'SUCCESS') {{
                    alert('✅ Teljes mentés sikeresen elkészült!' + NL + NL + 'Fájl: ' + data.filename + NL + 'Méret: ' + data.size);
                    commentInput.value = '';
                    loadBackups();
                }} else {{
                    alert('❌ Hiba történt: ' + (data.message || 'Ismeretlen hiba'));
                }}
            }} catch(e) {{
                alert('Hálózati hiba: ' + e);
            }} finally {{
                btn.disabled = false; btn.innerText = 'Teljes Mentés Készítése';
            }}
        }}

        async function restoreBackup(filename) {{
            if (!confirm('⚠️ FIGYELEM! A visszaállítás felülírja a jelenlegi adatbázist és a futó kódot a mentett állapotra!' + NL + NL + 'Biztosan folytatja a(z) ' + filename + ' visszaállítását?')) return;
            try {{
                const res = await fetch('/api/backups/restore', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{ filename: filename }})
                }});
                const data = await res.json();
                if (data.status === 'SUCCESS') {{
                    alert('✅ ' + data.message + NL + NL + 'Az oldal most újratöltődik.');
                    window.location.reload();
                }} else {{
                    alert('❌ Hiba a visszaállításkor:' + NL + NL + data.message);
                }}
            }} catch(e) {{
                alert('Hálózati hiba: ' + e);
            }}
        }}

        async function deleteBackup(filename) {{
            if (!confirm('Biztosan törölni szeretné ezt a mentést: ' + filename + '?')) return;
            try {{
                const res = await fetch('/api/backups/' + encodeURIComponent(filename), {{ method: 'DELETE' }});
                const data = await res.json();
                if (data.status === 'SUCCESS') loadBackups();
                else alert('Hiba a törlésnél: ' + data.message);
            }} catch(e) {{
                alert('Hálózati hiba: ' + e);
            }}
        }}

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
            if(!repo || !token) {{ alert("Kérjük, töltse ki a mezőket!"); return; }}
            
            btn.disabled = true; btn.innerText = "Tesztelés...";
            try {{
                const res = await fetch('/api/github/test', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{ repo: repo, token: token, branch: branch }})
                }});
                const data = await res.json();
                alert(data.status === 'ERROR' ? ("Hiba:" + NL + NL + data.message) : data.message);
            }} catch(e) {{
                alert("Hiba: " + e);
            }} finally {{
                btn.disabled = false; btn.innerText = "Kapcsolat Tesztelése";
                loadGitHubHistory();
            }}
        }}

        async function loadGitHubHistory() {{
            const box = document.getElementById('gh_history_list');
            if (!box) return;
            box.innerHTML = '<i>Verziótörténet betöltése...</i>';
            try {{
                const res = await fetch('/api/github/history');
                const data = await res.json();
                if (data.status === 'SUCCESS' && Array.isArray(data.data)) {{
                    box.innerHTML = '';
                    data.data.forEach(item => {{
                        const d = new Date(item.date).toLocaleString('hu-HU');
                        box.innerHTML += '<div class="gh-history-item"><strong style="color:#0284c7;">' + item.message + '</strong><br/><span style="color:#64748b; font-size:11px;">' + d + ' | Szerző: ' + item.author + ' | Commit: <i>' + item.sha + '</i></span></div>';
                    }});
                }} else {{
                    box.innerHTML = '<span style="color:#dc2626;">' + (data.data || data.message || "Hiba") + '</span>';
                }}
            }} catch(e) {{
                box.innerHTML = '<span style="color:#dc2626;">Hiba a betöltéskor.</span>';
            }}
        }}

        async function pushToGitHub() {{
            const repo = document.getElementById('gh_repo').value.trim();
            const token = document.getElementById('gh_token').value.trim();
            const branch = document.getElementById('gh_branch').value.trim();
            const customMsg = document.getElementById('gh_custom_msg').value.trim();
            
            if(!confirm("Feltölti a kódot a GitHub-ra? A verziószám 0.01-gyel nő.")) return;
            const btn = document.getElementById('ghPushBtn');
            btn.disabled = true; btn.innerText = "Feltöltés...";
            try {{
                const res = await fetch('/api/github/push', {{ 
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{ repo: repo, token: token, branch: branch, message: customMsg }})
                }});
                const data = await res.json();
                if(data.status === 'SUCCESS') {{
                    alert(data.message);
                    document.getElementById('app_version_label').innerText = data.new_version;
                    document.getElementById('gh_custom_msg').value = '';
                    loadGitHubHistory();
                }} else {{
                    alert("Hiba:" + NL + NL + data.message);
                }}
            }} catch(e) {{
                alert("Hálózati hiba: " + e);
            }} finally {{
                btn.disabled = false; btn.innerText = "Kód Publikálása (Push)";
            }}
        }}

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
                        opt.value = m; opt.innerText = m;
                        select.appendChild(opt);
                    }});
                }} else {{
                    select.innerHTML = '<option value="">Nem található modell!</option>';
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
            sendBtn.disabled = true; sendBtn.innerText = 'Gondolkodik...';

            const aiMsg = document.createElement('div');
            aiMsg.className = 'msg msg-ai';
            aiMsg.innerText = '⏳ Elemzés és válasz generálása...';
            chatBox.appendChild(aiMsg);
            chatBox.scrollTop = chatBox.scrollHeight;

            try {{
                const res = await fetch('/api/ai/ask', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ model: model, prompt: text }})
                }});
                const data = await res.json();
                aiMsg.innerText = (data.status === 'SUCCESS') ? data.response : ('Hiba: ' + (data.message || data.error));
            }} catch (err) {{
                aiMsg.innerText = 'Hálózati hiba: ' + err;
            }} finally {{
                sendBtn.disabled = false; sendBtn.innerText = 'Küldés';
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
            <div id="tab-history-import" class="tab" onclick="switchTab('history-import')">Történeti Időgép (CSV Import)</div>
            <div id="tab-backups" class="tab" onclick="switchTab('backups')">Mentések & Verziók</div>
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
                <input type="text" id="userSearchBox" placeholder="Keresés név, email, azonosító, státusz (pl. Külsős) vagy OU alapján..." onkeyup="filterUsers()">
                <span id="userCountLabel" style="font-size:13px; color:#64748b; white-space:nowrap;"></span>
            </div>
            <table>
                <thead><tr><th>Név</th><th>Azonosító</th><th>Email</th><th>Besorolás / Státusz</th><th>Titulus / Pozíció</th><th>Utolsó belépés</th></tr></thead>
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
                <button class="quick-btn" onclick="setPrompt('Kik a távozott vagy külsős státuszú fiókok, és van-e aktív csoporttagságuk?')">🛡️ Külsős és távozott fiókok ellenőrzése</button>
                <button class="quick-btn" onclick="setPrompt('Ki az a felhasználó, aki több mint 90 napja nem lépett be az AD-be?')">⚠️ Régen bejelentkezett (inaktív) fiókok</button>
                <button class="quick-btn" onclick="setPrompt('Elemezd a szervezeti egységek (OU) szerinti megoszlást és a csoporttagságokat!')">⏳ Szervezeti egységek és fluktuáció</button>
            </div>

            <div id="chatBox" class="chat-box">
                <div class="msg msg-ai">Üdvözlöm! Én vagyok a helyi AD Audit asszisztens. Közvetlen hozzáférésem van az exportált adatbázishoz, a történeti audit naplóhoz, a bejelentkezési dátumokhoz és a szervezeti besorolásokhoz.</div>
            </div>

            <div class="input-row">
                <textarea id="userPrompt" placeholder="Kérdezzen a fiókokról vagy változásokról..." onkeydown="if(event.key==='Enter' && !event.shiftKey){{event.preventDefault(); sendAiQuestion();}}"></textarea>
                <button id="sendAiBtn" class="btn" onclick="sendAiQuestion()">Küldés</button>
            </div>
        </div>

        <!-- TÖRTÉNETI IMPORT (IDŐGÉP) FÜL -->
        <div id="content-history-import" class="content">
            <div class="card-box" style="margin-bottom: 20px;">
                <h4 style="margin-top:0;">PowerShell CSV Mentések Betöltése és Visszamenőleges Frissítés</h4>
                <p style="font-size:13px; color:#64748b; margin-top:0;">
                    Válassza ki a saját számítógépén azt a mappát (pl. <code>C:\\1</code>), amely a korábbi exportfájlokat tartalmazza.
                </p>

                <input type="file" id="client_folder_picker" webkitdirectory directory multiple style="display:none;" onchange="handleClientFolderSelect(this)">

                <div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin-bottom:15px;">
                    <button class="btn" style="background:#0284c7; padding:10px 18px;" onclick="triggerClientFolderPicker()">📁 Mappa Kiválasztása a Saját Gépemen (Tallózás)</button>
                    <span style="font-size:13px; color:#64748b;">vagy szerver mappa:</span>
                    <input type="text" id="history_folder_input" value="csv_imports" placeholder="Szerver mappa neve" style="margin:0; width:150px;">
                    <button id="scanHistoryBtn" class="btn" style="background:#475569;" onclick="scanServerFolder()">Szerver Mappa Felderítése</button>
                    <button id="backfillBtn" class="btn" style="background:#d97706;" onclick="doQuickBackfill()">⚡ Meglévő Adatok Frissítése (Backfill)</button>
                    <button id="startHistoryBtn" class="btn" style="background:#16a34a; margin-left:auto;" disabled onclick="startHistoryImport()">Történeti Idővonal Újraépítése (Import)</button>
                </div>
                <div id="history_scan_info" style="font-size:13px; padding:8px 12px; background:#f1f5f9; border-radius:6px;">
                    Válasszon egy mappát a számítógépéről a fenti kék gombbal a mentések felderítéséhez.
                </div>
            </div>

            <div id="import_progress_box" class="card-box" style="display:none; margin-bottom: 20px; border-left: 4px solid #0284c7;">
                <h4 style="margin-top:0;">Feldolgozás Folyamatban...</h4>
                <div style="background:#e2e8f0; border-radius:8px; height:18px; width:100%; overflow:hidden; margin-bottom:8px;">
                    <div id="import_bar" style="background:#0284c7; width:0%; height:100%; transition: width 0.3s;"></div>
                </div>
                <div id="import_status_text" style="font-size:13px; color:#334155;">Előkészítés...</div>
            </div>

            <h4 style="color:#0f172a; margin-bottom:10px;">Felismert Időpontok és Mentési Csomagok</h4>
            <table>
                <thead>
                    <tr>
                        <th>Időpont (Dátum)</th>
                        <th>Időbélyeg (Név minta)</th>
                        <th>User CSV-k száma</th>
                        <th>Csoport fájl (Groups)</th>
                        <th>AllUser fájl</th>
                    </tr>
                </thead>
                <tbody id="historyTableBody">
                    <tr><td colspan="5" style="text-align:center; color:#94a3b8; padding:20px;">Válasszon ki egy mappát a saját gépén a mentések megtekintéséhez.</td></tr>
                </tbody>
            </table>
        </div>

        <!-- MENTÉSEK ÉS VERZIÓK FÜL -->
        <div id="content-backups" class="content">
            <div class="card-box" style="margin-bottom: 25px;">
                <h4 style="margin-top:0;">Új Helyi Teljes Mentés Készítése</h4>
                <p style="font-size:13px; color:#64748b; margin-top:0;">
                    A mentés egyetlen tömörített <b>.zip</b> archívumba csomagolja a forráskódot (<code>kod/</code>), a konfigurációkat (<code>konfig/</code>) és a PostgreSQL adatbázis teljes tartalmát (<code>adatbazis/dump.sql</code> és <code>data.json</code>).
                </p>
                <div style="display:flex; gap:12px; align-items:center;">
                    <input type="text" id="backup_comment" placeholder="Mentés megjegyzése..." style="margin:0; flex:1;">
                    <button id="createBackupBtn" class="btn" style="background:#16a34a; white-space:nowrap;" onclick="createNewBackup()">Teljes Mentés Készítése</button>
                </div>
            </div>

            <h4 style="color:#0f172a; margin-bottom:10px;">Elérhető Biztonsági Mentések</h4>
            <table>
                <thead>
                    <tr>
                        <th>Létrehozva</th>
                        <th>Verzió</th>
                        <th>Fájlnév</th>
                        <th>Méret</th>
                        <th>Megjegyzés</th>
                        <th>Készítette</th>
                        <th style="text-align:right;">Műveletek</th>
                    </tr>
                </thead>
                <tbody id="backupsTableBody"></tbody>
            </table>
        </div>

        <!-- BEÁLLÍTÁSOK -->
        <div id="content-settings" class="content">
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
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
                    </select>
                    <button class="btn" style="width:100%; margin-top:10px;" onclick="saveSettings()">Beállítások Mentése</button>
                </div>

                <div class="card-box">
                    <h4>GitHub Integráció & Publikáció</h4>
                    <label>Repó Neve (Szervezet/Repó)</label>
                    <input type="text" id="gh_repo" value="{gh_repo}">
                    <label>Personal Access Token (PAT)</label>
                    <input type="password" id="gh_token" value="{gh_token}">
                    <label>Cél ág (Branch)</label>
                    <input type="text" id="gh_branch" value="{gh_branch}">
                    <label style="color:#0284c7; font-weight:bold; margin-top:5px;">Új verzió megjegyzése:</label>
                    <input type="text" id="gh_custom_msg" placeholder="Milyen javítás készült? (Opcionális)" style="border-color:#0284c7; background:#f0f9ff;">
                    
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-top: 10px;">
                        <button id="ghTestBtn" class="btn" style="background:#475569;" onclick="testGitHub()">Kapcsolat Tesztelése</button>
                        <span style="font-size:14px; font-weight:bold;">Aktuális: <span style="color:#0284c7;">v<span id="app_version_label">{app_version}</span></span></span>
                        <button id="ghPushBtn" class="btn" style="background:#16a34a;" onclick="pushToGitHub()">Kód Publikálása (Push)</button>
                    </div>

                    <h5 style="margin:20px 0 5px 0; border-bottom:1px solid #cbd5e1; padding-bottom:5px; color:#475569;">Verziótörténet a GitHub-on</h5>
                    <div id="gh_history_list" class="gh-history-box">Kattints a fülre a betöltéshez...</div>
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
                    <h4>Szervezeti és Státusz Adatok</h4>
                    <div class="data-row"><strong>Besorolás / Státusz:</strong><span id="m-userstatus" style="font-weight:bold; color:#0284c7;"></span></div>
                    <div class="data-row"><strong>Utolsó bejelentkezés:</strong><span id="m-lastlogon" style="font-weight:bold;"></span></div>
                    <div class="data-row"><strong>Szervezeti egység (OU):</strong><span id="m-ou" style="font-size:12px;"></span></div>
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
