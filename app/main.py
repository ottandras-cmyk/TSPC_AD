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
from telemetry import (
    collect_and_save_telemetry, get_live_telemetry, get_telemetry_history,
    log_web_activity, get_web_access_logs, get_host_ip_history,
    register_active_session, update_active_session, close_active_session, get_active_sessions_info
)
from ad_analytics import get_ad_analytics_summary, ask_ad_changes_ai

models.Base.metadata.create_all(bind=engine)

migration_statements = [
    "ALTER TABLE ad_users ADD COLUMN IF NOT EXISTS last_logon_date TIMESTAMP WITH TIME ZONE;",
    "ALTER TABLE ad_users ADD COLUMN IF NOT EXISTS user_status VARCHAR(100);",
    "ALTER TABLE ad_users ADD COLUMN IF NOT EXISTS ou_path TEXT;",
    "ALTER TABLE ad_users ADD COLUMN IF NOT EXISTS source_type VARCHAR(50) DEFAULT 'AD_SYNC';",
    "ALTER TABLE ad_users ADD COLUMN IF NOT EXISTS source_ref VARCHAR(255) DEFAULT 'LIVE_AD';",
    "ALTER TABLE ad_groups ADD COLUMN IF NOT EXISTS source_type VARCHAR(50) DEFAULT 'AD_SYNC';",
    "ALTER TABLE ad_groups ADD COLUMN IF NOT EXISTS source_ref VARCHAR(255) DEFAULT 'LIVE_AD';",
    "ALTER TABLE ad_audit_log ADD COLUMN IF NOT EXISTS source_type VARCHAR(50) DEFAULT 'AD_SYNC';",
    "ALTER TABLE ad_audit_log ADD COLUMN IF NOT EXISTS source_ref VARCHAR(255) DEFAULT 'LIVE_AD';",
    "ALTER TABLE ad_audit_log ALTER COLUMN raw_diff TYPE TEXT USING raw_diff::text;",
    """CREATE TABLE IF NOT EXISTS system_telemetry (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        cpu_percent FLOAT DEFAULT 0.0,
        cpu_temp_c FLOAT,
        ram_total_mb FLOAT DEFAULT 0.0,
        ram_used_mb FLOAT DEFAULT 0.0,
        ram_percent FLOAT DEFAULT 0.0,
        disk_total_gb FLOAT DEFAULT 0.0,
        disk_used_gb FLOAT DEFAULT 0.0,
        disk_free_gb FLOAT DEFAULT 0.0,
        db_size_mb FLOAT DEFAULT 0.0,
        gpu_name VARCHAR(100),
        gpu_util_percent FLOAT,
        gpu_mem_used_mb FLOAT,
        gpu_mem_total_mb FLOAT,
        gpu_temp_c FLOAT,
        gpu_power_w FLOAT,
        llm_tokens_prompt INTEGER DEFAULT 0,
        llm_tokens_eval INTEGER DEFAULT 0,
        llm_tokens_total INTEGER DEFAULT 0
    );""",
    """CREATE TABLE IF NOT EXISTS web_access_log (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        username VARCHAR(255) NOT NULL,
        client_ip VARCHAR(100) NOT NULL,
        browser VARCHAR(100),
        os_name VARCHAR(100),
        device_type VARCHAR(50),
        location VARCHAR(255),
        user_agent TEXT,
        action VARCHAR(100) NOT NULL,
        details TEXT,
        status VARCHAR(50) DEFAULT 'SIKERES'
    );""",
    "ALTER TABLE web_access_log ADD COLUMN IF NOT EXISTS browser VARCHAR(100);",
    "ALTER TABLE web_access_log ADD COLUMN IF NOT EXISTS os_name VARCHAR(100);",
    "ALTER TABLE web_access_log ADD COLUMN IF NOT EXISTS device_type VARCHAR(50);",
    "ALTER TABLE web_access_log ADD COLUMN IF NOT EXISTS location VARCHAR(255);",
    "ALTER TABLE web_access_log ADD COLUMN IF NOT EXISTS user_agent TEXT;",
    """CREATE TABLE IF NOT EXISTS host_ip_history (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        ip_address VARCHAR(100) NOT NULL,
        hostname VARCHAR(255),
        details TEXT
    );""",
    """CREATE TABLE IF NOT EXISTS active_web_sessions (
        session_id VARCHAR(100) PRIMARY KEY,
        username VARCHAR(255) NOT NULL,
        login_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        last_activity TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        client_ip VARCHAR(100),
        browser VARCHAR(100),
        os_name VARCHAR(100),
        device_type VARCHAR(50),
        location VARCHAR(255),
        user_agent TEXT
    );"""
]

for stmt in migration_statements:
    try:
        with engine.connect() as conn:
            conn.execute(text(stmt))
            conn.commit()
    except Exception:
        pass

# Korábbi hamis "USER_CREATED" és "GROUP_CREATED" rekordok letisztázása az adatbázisban
try:
    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE ad_audit_log
            SET change_type = 'SCOPE_ADOPTED',
                details = 'Korábban létező AD fiók beemelve a hatókörbe (hatókör-különbség korrigálva)'
            WHERE change_type = 'USER_CREATED'
              AND id IN (
                  SELECT l.id
                  FROM ad_audit_log l
                  JOIN ad_users u ON lower(l.entity_name) = lower(u.sam_account_name)
                  WHERE u.when_created IS NOT NULL
                    AND u.when_created < (l.timestamp - INTERVAL '3 days')
              );
        """))
        conn.execute(text("""
            UPDATE ad_audit_log
            SET change_type = 'SCOPE_ADOPTED',
                details = 'Korábban létező AD csoport beemelve a hatókörbe (hatókör-különbség korrigálva)'
            WHERE change_type = 'GROUP_CREATED'
              AND id IN (
                  SELECT l.id
                  FROM ad_audit_log l
                  JOIN ad_groups g ON lower(l.entity_name) = lower(g.sam_account_name)
                  WHERE g.when_created IS NOT NULL
                    AND g.when_created < (l.timestamp - INTERVAL '3 days')
              );
        """))
        conn.commit()
except Exception:
    pass

db_init = SessionLocal()
init_default_settings(db_init)
db_init.close()

scheduler = BackgroundScheduler()
JOB_ID = "ad_sync_job"
TELEMETRY_JOB_ID = "telemetry_job"
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

def scheduled_telemetry_job():
    db = SessionLocal()
    try:
        collect_and_save_telemetry(db)
    except Exception:
        pass
    finally:
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    sync_minutes = int(get_setting(db, "SYNC_INTERVAL_MINUTES", "15"))
    db.close()
    if sync_minutes > 0:
        scheduler.add_job(scheduled_sync_job, 'interval', minutes=sync_minutes, id=JOB_ID)
    scheduler.add_job(scheduled_telemetry_job, 'interval', minutes=15, id=TELEMETRY_JOB_ID)
    scheduler.start()
    
    def startup_worker():
        init_db = SessionLocal()
        try:
            collect_and_save_telemetry(init_db)
            log_web_activity(init_db, None, "SYSTEM", "RENDSZER_INDULÁS", "AD Tracker szerver és telemetria sikeresen elindult", "SIKERES")
        except Exception:
            pass
        finally:
            init_db.close()
            
    threading.Thread(target=startup_worker).start()
    yield
    scheduler.shutdown()

app = FastAPI(title="AD Tracker", lifespan=lifespan)

def get_current_session(request: Request):
    return verify_session_token(request.cookies.get(COOKIE_NAME))

def get_current_user(request: Request):
    user, _ = get_current_session(request)
    return user

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
def process_login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    success, result = authenticate_ad_user(db, username, password)
    if not success:
        log_web_activity(db, request, username, "BEJELENTKEZÉS", "Hibás felhasználónév vagy jelszó", "SIKERTELEN")
        return RedirectResponse(url="/login?error=Hibas+adatok", status_code=303)
    
    token, session_id = create_session_token(result)
    register_active_session(db, request, session_id, result)
    log_web_activity(db, request, result, "BEJELENTKEZÉS", f"Sikeres belépés (Munkamenet: {session_id[:8]})", "SIKERES")
    
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(key=COOKIE_NAME, value=token, httponly=True, max_age=86400 * 7, samesite="lax")
    return response

@app.get("/logout")
def process_logout(request: Request, db: Session = Depends(get_db)):
    user, session_id = get_current_session(request)
    if user:
        close_active_session(db, session_id)
        log_web_activity(db, request, user, "KIJELENTKEZÉS", f"Kijelentkezés (Munkamenet: {session_id[:8] if session_id else '-'})", "SIKERES")
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
            u_status = getattr(u, "user_status", None) or ("Aktív normál user" if getattr(u, "is_enabled", True) else "Letiltva")
            last_logon_dt = getattr(u, "last_logon_date", None)
            last_logon_str = last_logon_dt.strftime("%Y-%m-%d %H:%M") if last_logon_dt and hasattr(last_logon_dt, "strftime") else "-"
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
                "ou": getattr(u, "ou_path", None) or "-",
                "phone": getattr(u, "telephone_number", None) or "-",
                "mobile": getattr(u, "mobile", None) or "-",
                "title": getattr(u, "title", None) or "-",
                "department": getattr(u, "department", None) or "-",
                "company": getattr(u, "company", None) or "-",
                "office": getattr(u, "office", None) or "-",
                "desc": getattr(u, "description", None) or "-",
                "sid": getattr(u, "object_sid", None) or "-",
                "source_type": getattr(u, "source_type", "AD_SYNC") or "AD_SYNC",
                "source_ref": getattr(u, "source_ref", "LIVE_AD") or "LIVE_AD",
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
            "details": l.details or "",
            "source_type": getattr(l, "source_type", "AD_SYNC") or "AD_SYNC",
            "source_ref": getattr(l, "source_ref", "LIVE_AD") or "LIVE_AD"
        } for l in logs]
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/groups")
def get_all_groups(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    try:
        groups = db.query(models.ADGroup).all()
        return [{
            "sam": g.sam_account_name,
            "desc": g.description or "-",
            "type": g.group_type or "Ismeretlen",
            "sid": g.object_sid or "-",
            "source_type": getattr(g, "source_type", "AD_SYNC") or "AD_SYNC",
            "source_ref": getattr(g, "source_ref", "LIVE_AD") or "LIVE_AD",
            "created": g.when_created.strftime("%Y-%m-%d %H:%M") if g.when_created else "-",
            "changed": g.when_changed.strftime("%Y-%m-%d %H:%M") if g.when_changed else "-",
            "members": [u.sam_account_name for u in g.members]
        } for g in groups]
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/sync")
def trigger_sync_manual(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return JSONResponse(status_code=401, content={})
    log_web_activity(db, request, user, "AD_SZINKRON", "Manuális szinkronizálás indítva", "SIKERES")
    threading.Thread(target=execute_sync_with_log, args=("Manuális",)).start()
    return {"status": "STARTED"}

# --- AD VÁLTOZÁS ELEMZŐ VÉGPONTOK ---
@app.get("/api/ad-analytics/day-events")
def api_ad_analytics_day_events(date: str, type: str = "ALL", request: Request = None, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    from ad_analytics import get_day_detailed_events
    return get_day_detailed_events(db, date_str=date, event_type=type)

@app.get("/api/ad-analytics/summary")
def api_ad_analytics_summary(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    return get_ad_analytics_summary(db)

@app.post("/api/ad-analytics/ask")
async def api_ad_analytics_ask(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return JSONResponse(status_code=401, content={})
    data = await request.json()
    res = ask_ad_changes_ai(db, data.get("model"), data.get("prompt"))
    log_web_activity(db, request, user, "AD_VÁLTOZÁS_AI_KÉRDÉS", f"Modell: {data.get('model')}", "SIKERES" if res.get("status") == "SUCCESS" else "HIBA")
    return res

# --- TELEMETRIA, MUNKAMENETEK ÉS WEB AUDIT ---
@app.get("/api/telemetry/live")
def api_telemetry_live(request: Request, db: Session = Depends(get_db)):
    user, session_id = get_current_session(request)
    if not user: return JSONResponse(status_code=401, content={})
    update_active_session(db, session_id)
    return get_live_telemetry(db)

@app.get("/api/telemetry/sessions")
def api_telemetry_sessions(request: Request, db: Session = Depends(get_db)):
    user, session_id = get_current_session(request)
    if not user: return JSONResponse(status_code=401, content={})
    update_active_session(db, session_id)
    return get_active_sessions_info(db, session_id)

@app.get("/api/telemetry/history")
def api_telemetry_history(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    return {"history": get_telemetry_history(db, limit=96)}

@app.get("/api/telemetry/web-logs")
def api_telemetry_web_logs(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    return {"logs": get_web_access_logs(db, limit=100)}

@app.get("/api/telemetry/host-ip-history")
def api_telemetry_host_ip_history(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    return {"history": get_host_ip_history(db, limit=50)}

@app.post("/api/telemetry/collect")
def api_telemetry_collect(request: Request, db: Session = Depends(get_db)):
    user, session_id = get_current_session(request)
    if not user: return JSONResponse(status_code=401, content={})
    update_active_session(db, session_id)
    rec = collect_and_save_telemetry(db)
    log_web_activity(db, request, user, "MÉRÉS_RÖGZÍTÉS", f"Azonnali telemetria mérés azonosító: #{rec.id}", "SIKERES")
    return {"status": "SUCCESS", "id": rec.id, "timestamp": rec.timestamp.strftime("%Y-%m-%d %H:%M:%S")}

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
    user = get_current_user(request)
    if not user: return JSONResponse(status_code=401, content={})
    data = await request.json()
    folder = data.get("folder", "csv_imports")
    log_web_activity(db, request, user, "CSV_BACKFILL", f"Mappa: {folder}", "SIKERES")
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
async def api_history_import(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return JSONResponse(status_code=401, content={})
    if import_progress["is_running"]: return {"status": "ERROR", "message": "Importálás folyamatban!"}
    data = await request.json()
    folder = data.get("folder", "csv_imports")
    log_web_activity(db, request, user, "CSV_IMPORT_INDÍTÁS", f"Mappa: {folder}", "SIKERES")
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
    comment = data.get("comment", "")
    res = create_backup(db, comment=comment, user=user)
    if res.get("status") == "SUCCESS":
        log_web_activity(db, request, user, "MENTÉS_LÉTREHOZÁS", f"Fájl: {res.get('filename')}, Megjegyzés: {comment}", "SIKERES")
    return res

@app.post("/api/backups/restore")
async def restore_backup_endpoint(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return JSONResponse(status_code=401, content={})
    data = await request.json()
    filename = data.get("filename", "")
    res = restore_backup(db, filename=filename)
    st = "SIKERES" if res.get("status") == "SUCCESS" else "HIBA"
    log_web_activity(db, request, user, "MENTÉS_VISSZAÁLLÍTÁS", f"Fájl: {filename}", st)
    return res

@app.get("/api/backups/download/{filename}")
def download_backup_endpoint(filename: str, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return JSONResponse(status_code=401, content={})
    safe_name = os.path.basename(filename)
    fpath = os.path.join(BACKUP_DIR, safe_name)
    if not os.path.isfile(fpath): return JSONResponse(status_code=404, content={"error": "Fájl nem található"})
    log_web_activity(db, request, user, "MENTÉS_LETÖLTÉS", f"Fájl: {safe_name}", "SIKERES")
    return FileResponse(fpath, filename=safe_name, media_type="application/zip")

@app.delete("/api/backups/{filename}")
def delete_backup_endpoint(filename: str, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return JSONResponse(status_code=401, content={})
    res = delete_backup(filename)
    log_web_activity(db, request, user, "MENTÉS_TÖRLÉS", f"Fájl: {filename}", "SIKERES")
    return res

# --- GITHUB INTEGRÁCIÓ ---
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
    user = get_current_user(request)
    if not user: return JSONResponse(status_code=401, content={"status": "ERROR", "message": "Munkamenet lejárt!"})
    try:
        from doc_generator import build_all_docs
        build_all_docs(db)
    except Exception:
        pass
    try:
        req_data = await request.json()
        custom_msg = req_data.get("message", "")
        repo = req_data.get("repo") or get_setting(db, "GH_REPO")
        token = req_data.get("token") or get_setting(db, "GH_TOKEN")
        branch = req_data.get("branch") or get_setting(db, "GH_BRANCH", "main")
        
        current_gh_ver = get_latest_github_version(repo, token, branch)
        try: curr_float = float(current_gh_ver)
        except ValueError: curr_float = 1.00
        new_ver_str = f"{curr_float + 0.01:.2f}"

        ok, msg = push_code_to_github(repo, branch, token, new_ver_str, custom_msg)
        if ok:
            update_setting(db, "APP_VERSION", new_ver_str)
            log_web_activity(db, request, user, "GITHUB_PUSH", f"Verzió: v{new_ver_str}, Megjegyzés: {custom_msg}", "SIKERES")
            return {"status": "SUCCESS", "message": msg, "new_version": new_ver_str}
        
        log_web_activity(db, request, user, "GITHUB_PUSH", f"Sikertelen push: {msg}", "HIBA")
        return {"status": "ERROR", "message": msg}
    except Exception as e:
        return {"status": "ERROR", "message": f"Hiba: {str(e)}"}

@app.get("/api/ai/models")
def get_ai_models(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    return {"models": fetch_ollama_models(db)}

@app.post("/api/ai/ask")
async def ask_ai_endpoint(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return JSONResponse(status_code=401, content={})
    data = await request.json()
    res = ask_ollama(db, data.get("model"), data.get("prompt"))
    log_web_activity(db, request, user, "AI_LEKÉRDEZÉS", f"Modell: {data.get('model')}", "SIKERES" if res.get("status") == "SUCCESS" else "HIBA")
    return res

@app.post("/api/settings")
async def save_settings(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return JSONResponse(status_code=401, content={})
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
    
    log_web_activity(db, request, user, "BEÁLLÍTÁS_MENTÉS", "Rendszer és AD konfigurációk frissítve", "SIKERES")
    return {"status": "SUCCESS"}

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
        src = getattr(l, "source_ref", "AD") or "AD"
        src_badge = f'<span style="background:#f1f5f9; color:#475569; padding:2px 6px; border-radius:4px; font-size:10px; font-family:monospace; margin-left:6px;">{src}</span>'
        rows += f'<tr><td>{t}</td><td><b>{l.entity_name}</b> {src_badge}</td><td><span style="background:{badge}; color:white; padding:3px 6px; border-radius:4px; font-size:11px;">{l.change_type}</span></td><td>{l.details}</td></tr>'

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
