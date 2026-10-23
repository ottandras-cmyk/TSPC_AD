import time
import socket
import shutil
import urllib.request
import json
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db, engine
import models
from auth import verify_session_token, COOKIE_NAME
from config_manager import get_setting, update_setting
from telemetry import log_web_activity

router = APIRouter(prefix="/api/settings", tags=["settings"])

def get_current_user(request: Request):
    user, _ = verify_session_token(request.cookies.get(COOKIE_NAME))
    return user

@router.get("/all")
def get_all_settings(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    return {
        "AD_SERVER": get_setting(db, "AD_SERVER", ""),
        "AD_USER": get_setting(db, "AD_USER", ""),
        "AD_PASSWORD": get_setting(db, "AD_PASSWORD", ""),
        "AD_SEARCH_BASE": get_setting(db, "AD_SEARCH_BASE", ""),
        "SYNC_INTERVAL_MINUTES": get_setting(db, "SYNC_INTERVAL_MINUTES", "15"),
        "OLLAMA_URL": get_setting(db, "OLLAMA_URL", "http://ollama:11434"),
        "GH_REPO": get_setting(db, "GH_REPO", ""),
        "GH_TOKEN": get_setting(db, "GH_TOKEN", ""),
        "GH_BRANCH": get_setting(db, "GH_BRANCH", "main"),
        "DEFAULT_TAB": get_setting(db, "DEFAULT_TAB", "dashboard"),
        "UI_TABLE_DENSITY": get_setting(db, "UI_TABLE_DENSITY", "normal"),
        "UI_PAGE_SIZE": get_setting(db, "UI_PAGE_SIZE", "150"),
        "UI_TELEMETRY_REFRESH_SEC": get_setting(db, "UI_TELEMETRY_REFRESH_SEC", "10"),
        "RETENTION_DAYS_LOGS": get_setting(db, "RETENTION_DAYS_LOGS", "90"),
        "RETENTION_DAYS_TELEMETRY": get_setting(db, "RETENTION_DAYS_TELEMETRY", "60")
    }

@router.post("/save")
async def save_settings(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return JSONResponse(status_code=401, content={})
    try:
        data = await request.json()
        if "AD_SERVER" in data: update_setting(db, "AD_SERVER", data.get("AD_SERVER", "").strip())
        if "AD_USER" in data: update_setting(db, "AD_USER", data.get("AD_USER", "").strip())
        if "AD_PASSWORD" in data and data.get("AD_PASSWORD") is not None:
            val = data.get("AD_PASSWORD")
            if val != "***" and val != "":
                update_setting(db, "AD_PASSWORD", val)
        if "AD_SEARCH_BASE" in data: update_setting(db, "AD_SEARCH_BASE", data.get("AD_SEARCH_BASE", "").strip())
        if "OLLAMA_URL" in data: update_setting(db, "OLLAMA_URL", data.get("OLLAMA_URL", "").strip())
        if "GH_REPO" in data: update_setting(db, "GH_REPO", data.get("GH_REPO", "").strip())
        if "GH_TOKEN" in data and data.get("GH_TOKEN") is not None:
            val_t = data.get("GH_TOKEN")
            if val_t != "***" and val_t != "":
                update_setting(db, "GH_TOKEN", val_t.strip())
        if "GH_BRANCH" in data: update_setting(db, "GH_BRANCH", data.get("GH_BRANCH", "main").strip())
        
        if "SYNC_INTERVAL_MINUTES" in data:
            minutes = int(data.get("SYNC_INTERVAL_MINUTES", 15))
            update_setting(db, "SYNC_INTERVAL_MINUTES", str(minutes))
            try:
                from main import scheduler, JOB_ID, scheduled_sync_job
                if scheduler.get_job(JOB_ID): scheduler.remove_job(JOB_ID)
                if minutes > 0: scheduler.add_job(scheduled_sync_job, 'interval', minutes=minutes, id=JOB_ID)
            except Exception: pass

        if "DEFAULT_TAB" in data: update_setting(db, "DEFAULT_TAB", data.get("DEFAULT_TAB", "dashboard"))
        if "UI_TABLE_DENSITY" in data: update_setting(db, "UI_TABLE_DENSITY", data.get("UI_TABLE_DENSITY", "normal"))
        if "UI_PAGE_SIZE" in data: update_setting(db, "UI_PAGE_SIZE", str(data.get("UI_PAGE_SIZE", "150")))
        if "UI_TELEMETRY_REFRESH_SEC" in data: update_setting(db, "UI_TELEMETRY_REFRESH_SEC", str(data.get("UI_TELEMETRY_REFRESH_SEC", "10")))
        if "RETENTION_DAYS_LOGS" in data: update_setting(db, "RETENTION_DAYS_LOGS", str(data.get("RETENTION_DAYS_LOGS", "90")))
        if "RETENTION_DAYS_TELEMETRY" in data: update_setting(db, "RETENTION_DAYS_TELEMETRY", str(data.get("RETENTION_DAYS_TELEMETRY", "60")))

        log_web_activity(db, request, user, "BEÁLLÍTÁS_MENTÉS", "Módosított rendszerparaméterek elmentve", "SIKERES")
        return {"status": "SUCCESS"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "ERROR", "message": str(e)})

@router.post("/test/ad")
async def test_ad_endpoint(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    try:
        req_body = {}
        try: req_body = await request.json()
        except Exception: pass

        server_str = req_body.get("server") or get_setting(db, "AD_SERVER", "")
        user = req_body.get("user") or get_setting(db, "AD_USER", "")
        pwd = req_body.get("password")
        if not pwd or pwd == "***": pwd = get_setting(db, "AD_PASSWORD", "")
        base = req_body.get("base") or get_setting(db, "AD_SEARCH_BASE", "")

        if not server_str: return {"status": "ERROR", "message": "Nincs megadva AD szervercím!"}
        if not user: return {"status": "ERROR", "message": "Nincs megadva olvasó felhasználó!"}
        if not pwd: return {"status": "ERROR", "message": "Nincs megadva jelszó!"}

        host = server_str.split(":")[0]
        port = int(server_str.split(":")[1]) if ":" in server_str else 389

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3.0)
            sock.connect((host, port))
            sock.close()
        except Exception as se:
            return {"status": "ERROR", "message": f"Hálózati port elakadás a(z) {host}:{port} felé: {str(se)}"}

        from ldap3 import Server, Connection, ALL
        server = Server(server_str, get_info=ALL, connect_timeout=5)
        conn = Connection(server, user=user, password=pwd, auto_bind=True)
        if base:
            conn.search(search_base=base, search_filter='(objectClass=*)', search_scope='BASE')
        conn.unbind()
        return {"status": "SUCCESS", "message": f"Sikeres kapcsolat az Active Directory szerverrel ({server_str})! Hitelesítés rendben."}
    except Exception as e:
        return {"status": "ERROR", "message": f"AD LDAP hiba: {str(e)}"}

@router.post("/test/git")
async def test_git_endpoint(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    try:
        req_body = {}
        try: req_body = await request.json()
        except Exception: pass

        repo = req_body.get("repo") or get_setting(db, "GH_REPO", "")
        token = req_body.get("token")
        if not token or token == "***": token = get_setting(db, "GH_TOKEN", "")

        if not repo: return {"status": "ERROR", "message": "Nincs megadva GitHub repó (Owner/Repo)!"}
        if not token: return {"status": "ERROR", "message": "Nincs megadva GitHub token (PAT)!"}

        url = f"https://api.github.com/repos/{repo}"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "AD-Tracker"
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            repo_name = data.get("full_name", repo)
            return {"status": "SUCCESS", "message": f"Sikeres kapcsolat a GitHub repóval ({repo_name})! Jogosultságok rendben."}
    except urllib.error.HTTPError as e:
        if e.code == 401: return {"status": "ERROR", "message": "Érvénytelen vagy lejárt GitHub Personal Access Token (PAT)!"}
        elif e.code == 404: return {"status": "ERROR", "message": f"A repó nem található ({repo}), vagy a tokennek nincs hozzáférése privát repóhoz."}
        else: return {"status": "ERROR", "message": f"GitHub HTTP hiba ({e.code}): {e.reason}"}
    except Exception as e:
        return {"status": "ERROR", "message": f"Kapcsolódási hiba: {str(e)}"}

@router.post("/test/ollama")
def test_ollama_endpoint(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    url = get_setting(db, "OLLAMA_URL", "http://ollama:11434")
    try:
        req = urllib.request.Request(f"{url}/api/tags", headers={"User-Agent": "AD-Tracker"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            return {"status": "SUCCESS", "message": f"Sikeres kapcsolat az Ollama szerverrel ({url})!"}
    except Exception as e:
        return {"status": "ERROR", "message": f"Nem érhető el az Ollama szerver ({url}): {str(e)}"}

@router.get("/diagnostics/health")
def run_health_check(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    results = []

    t0 = time.time()
    try:
        db.execute(text("SELECT 1;"))
        db_lat = round((time.time() - t0) * 1000, 2)
        results.append({"name": "PostgreSQL Adatbázis", "status": "OK", "detail": f"Online (Válaszidő: {db_lat} ms)"})
    except Exception as e:
        results.append({"name": "PostgreSQL Adatbázis", "status": "ERROR", "detail": str(e)})

    try:
        total, used, free = shutil.disk_usage("/")
        free_gb = round(free / (1024**3), 2)
        pct = round((used / total) * 100, 1)
        st = "OK" if free_gb > 5 else "WARN"
        results.append({"name": "Tárhely Kapacitás (/)", "status": st, "detail": f"{free_gb} GB szabad ({pct}% használt)"})
    except Exception as e:
        results.append({"name": "Tárhely Kapacitás", "status": "WARN", "detail": str(e)})

    ad_srv = get_setting(db, "AD_SERVER", "")
    if ad_srv:
        try:
            host = ad_srv.split(":")[0]
            port = int(ad_srv.split(":")[1]) if ":" in ad_srv else 389
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.5)
            sock.connect((host, port))
            sock.close()
            results.append({"name": "Active Directory Hálózati Port", "status": "OK", "detail": f"Elérhető ({ad_srv})"})
        except Exception as e:
            results.append({"name": "Active Directory Hálózati Port", "status": "WARN", "detail": f"Port elakadás: {str(e)}"})
    else:
        results.append({"name": "Active Directory Hálózati Port", "status": "WARN", "detail": "Nincs beállítva szerver."})

    ollama_url = get_setting(db, "OLLAMA_URL", "http://ollama:11434")
    try:
        req = urllib.request.Request(f"{ollama_url}/api/tags", headers={"User-Agent": "AD-Tracker"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            results.append({"name": "Helyi Ollama LLM API", "status": "OK", "detail": f"Online és válaszol ({ollama_url})"})
    except Exception as e:
        results.append({"name": "Helyi Ollama LLM API", "status": "WARN", "detail": f"Nem válaszol ({ollama_url})"})

    return {"results": results, "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}

@router.post("/maintenance/cleanup-history")
def cleanup_old_history(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return JSONResponse(status_code=401, content={})
    try:
        ret_logs = int(get_setting(db, "RETENTION_DAYS_LOGS", "90"))
        ret_tel = int(get_setting(db, "RETENTION_DAYS_TELEMETRY", "60"))
        now = datetime.now(timezone.utc)
        cutoff_logs = now - timedelta(days=ret_logs)
        cutoff_tel = now - timedelta(days=ret_tel)

        del_tel = db.query(models.SystemTelemetry).filter(models.SystemTelemetry.timestamp < cutoff_tel).delete()
        del_logs = db.query(models.WebAccessLog).filter(models.WebAccessLog.timestamp < cutoff_logs).delete()
        db.commit()

        msg = f"Karbantartás kész: {del_tel} db elavult telemetria és {del_logs} db régi webnapló törölve."
        log_web_activity(db, request, user, "ELAVULT_ADATOK_TISZTÍTÁSA", msg, "SIKERES")
        return {"status": "SUCCESS", "deleted_telemetry": del_tel, "deleted_web_logs": del_logs, "message": msg}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "ERROR", "message": str(e)})

@router.post("/database/optimize")
def optimize_database(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return JSONResponse(status_code=401, content={})
    try:
        start_time = time.time()
        size_before_mb = 0.0
        try:
            size_before_mb = round(float(db.execute(text("SELECT pg_database_size(current_database()) / (1024.0 * 1024.0);")).scalar() or 0), 2)
        except Exception: pass

        index_stmts = [
            "CREATE INDEX IF NOT EXISTS idx_ad_users_sam ON ad_users(sam_account_name);",
            "CREATE INDEX IF NOT EXISTS idx_ad_users_display_name ON ad_users(display_name);",
            "CREATE INDEX IF NOT EXISTS idx_ad_users_mail ON ad_users(mail);",
            "CREATE INDEX IF NOT EXISTS idx_ad_audit_log_timestamp ON ad_audit_log(timestamp);",
            "CREATE INDEX IF NOT EXISTS idx_ad_audit_log_entity_name ON ad_audit_log(entity_name);",
            "CREATE INDEX IF NOT EXISTS idx_ad_audit_log_change_type ON ad_audit_log(change_type);",
            "CREATE INDEX IF NOT EXISTS idx_web_access_log_timestamp ON web_access_log(timestamp);",
            "CREATE INDEX IF NOT EXISTS idx_web_access_log_username ON web_access_log(username);",
            "CREATE INDEX IF NOT EXISTS idx_telemetry_timestamp ON system_telemetry(timestamp);"
        ]
        for stmt in index_stmts:
            try:
                db.execute(text(stmt))
                db.commit()
            except Exception:
                db.rollback()

        tables = [
            "ad_users", "ad_groups", "ad_group_members", "ad_audit_log",
            "sync_history", "web_access_log", "system_telemetry",
            "host_ip_history", "active_web_sessions", "app_settings"
        ]
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            for tbl in tables:
                try: conn.execute(text(f"REINDEX TABLE {tbl};"))
                except Exception: pass
                try: conn.execute(text(f"VACUUM ANALYZE {tbl};"))
                except Exception: pass

        size_after_mb = 0.0
        try:
            size_after_mb = round(float(db.execute(text("SELECT pg_database_size(current_database()) / (1024.0 * 1024.0);")).scalar() or 0), 2)
        except Exception: pass

        duration = round(time.time() - start_time, 2)
        log_web_activity(db, request, user, "ADATBÁZIS_OPTIMALIZÁLÁS", f"Sikeres ({duration} mp, Méret: {size_before_mb}MB -> {size_after_mb}MB)", "SIKERES")

        return {
            "status": "SUCCESS",
            "duration_sec": duration,
            "size_before_mb": size_before_mb,
            "size_after_mb": size_after_mb,
            "message": f"Optimalizálás sikeresen befejeződött {duration} mp alatt!\nAdatbázis méret: {size_before_mb} MB -> {size_after_mb} MB\nIndexek újraépítve, holt tárhely felszabadítva."
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "ERROR", "message": str(e)})

@router.post("/docs/rebuild")
def rebuild_docs_endpoint(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return JSONResponse(status_code=401, content={})
    try:
        from doc_generator import build_all_docs
        res = build_all_docs(db)
        log_web_activity(db, request, user, "DOKUMENTÁCIÓ_ÚJRAÉPÍTÉS", f"Generálva: {', '.join(res.get('generated_files', []))}", "SIKERES")
        return res
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "ERROR", "message": str(e)})
