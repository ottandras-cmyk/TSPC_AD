import urllib.request
import urllib.error
import json
import time
import ssl
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import engine
from config_manager import get_setting
import models

def get_ssl_context():
    """Belső vállalati HTTPS tanúsítványok elfogadása SSL hiba nélkül"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

def parse_iso_date(dt_str):
    if not dt_str: return None
    try:
        clean = dt_str.replace("Z", "+00:00")
        if "T" in clean:
            return datetime.fromisoformat(clean.split("+")[0])
        return datetime.strptime(clean, "%Y-%m-%d")
    except Exception:
        return None

def test_easy_project_connection(url: str, api_key: str) -> tuple:
    if not url: return False, "Nincs megadva Easy Project szerver cím!"
    if not api_key: return False, "Nincs megadva API kulcs!"
    
    clean_url = url.rstrip("/")
    test_endpoints = [
        f"{clean_url}/users/current.json",
        f"{clean_url}/projects.json?limit=1"
    ]
    
    headers = {
        "X-Redmine-API-Key": api_key,
        "Accept": "application/json",
        "User-Agent": "ADTracker-EasyProject-Connector"
    }
    
    ssl_ctx = get_ssl_context()
    last_err = ""
    for ep in test_endpoints:
        try:
            req = urllib.request.Request(ep, headers=headers)
            with urllib.request.urlopen(req, timeout=10, context=ssl_ctx) as resp:
                if resp.status in (200, 201):
                    return True, f"Sikeres kapcsolat az Easy Project szerverrel ({clean_url})! Hitelesítés érvényes."
        except urllib.error.HTTPError as e:
            if e.code == 401: return False, "Érvénytelen Easy Project API kulcs (401 Nem jogosult)!"
            if e.code == 403: return False, "Nincs megfelelő jogosultság az Easy Project API eléréséhez (403 Tiltva)!"
            last_err = f"HTTP hiba ({e.code}): {e.reason}"
        except Exception as e:
            last_err = str(e)
            
    return False, f"Nem sikerült csatlakozni az Easy Project szerverhez: {last_err}"

def fetch_json(url: str, api_key: str) -> dict:
    headers = {
        "X-Redmine-API-Key": api_key,
        "Accept": "application/json",
        "User-Agent": "ADTracker-EasyProject-Connector"
    }
    ssl_ctx = get_ssl_context()
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30, context=ssl_ctx) as resp:
        return json.loads(resp.read().decode("utf-8"))

def sync_easy_project_data(db: Session, trigger_type: str = "MANUAL") -> dict:
    url = get_setting(db, "EP_URL", "").rstrip("/")
    api_key = get_setting(db, "EP_API_KEY", "")
    
    if not url or not api_key:
        return {"status": "ERROR", "message": "Hiányzó Easy Project URL vagy API kulcs a beállításokban!"}

    models.Base.metadata.create_all(bind=engine)

    sync_log = models.EPSyncHistory(
        started_at=datetime.utcnow(),
        trigger_type=trigger_type,
        status="FOLYAMATBAN"
    )
    db.add(sync_log)
    db.commit()
    db.refresh(sync_log)

    start_time = time.time()
    projects_count = 0
    tasks_count = 0
    users_count = 0

    try:
        # 1. Projektek kinyerése
        try:
            p_data = fetch_json(f"{url}/projects.json?limit=100", api_key)
            for p in p_data.get("projects", []):
                ep_p = db.query(models.EPProject).filter(models.EPProject.ep_id == p.get("id")).first()
                if not ep_p:
                    ep_p = models.EPProject(ep_id=p.get("id"))
                    db.add(ep_p)
                ep_p.name = p.get("name", "Névtelen projekt")
                ep_p.identifier = p.get("identifier")
                ep_p.description = p.get("description")
                ep_p.status = p.get("status", 1)
                ep_p.created_on = parse_iso_date(p.get("created_on"))
                ep_p.updated_on = parse_iso_date(p.get("updated_on"))
                ep_p.synced_at = datetime.utcnow()
                projects_count += 1
            db.commit()
        except Exception:
            pass

        # 2. Felhasználók kinyerése
        try:
            u_data = fetch_json(f"{url}/users.json?limit=100", api_key)
            for u in u_data.get("users", []):
                ep_u = db.query(models.EPUser).filter(models.EPUser.ep_id == u.get("id")).first()
                if not ep_u:
                    ep_u = models.EPUser(ep_id=u.get("id"))
                    db.add(ep_u)
                ep_u.login = u.get("login")
                ep_u.firstname = u.get("firstname")
                ep_u.lastname = u.get("lastname")
                ep_u.mail = u.get("mail")
                ep_u.status = u.get("status", 1)
                ep_u.synced_at = datetime.utcnow()
                users_count += 1
            db.commit()
        except Exception:
            pass

        # 3. Feladatok (Issues) kinyerése
        try:
            t_data = fetch_json(f"{url}/issues.json?limit=150&sort=updated_on:desc", api_key)
            for t in t_data.get("issues", []):
                ep_t = db.query(models.EPTask).filter(models.EPTask.ep_id == t.get("id")).first()
                if not ep_t:
                    ep_t = models.EPTask(ep_id=t.get("id"))
                    db.add(ep_t)
                
                ep_t.subject = t.get("subject", "Névtelen feladat")
                ep_t.description = t.get("description")
                ep_t.done_ratio = t.get("done_ratio", 0)
                ep_t.estimated_hours = t.get("estimated_hours")
                ep_t.spent_hours = t.get("spent_hours")
                ep_t.created_on = parse_iso_date(t.get("created_on"))
                ep_t.updated_on = parse_iso_date(t.get("updated_on"))
                ep_t.due_date = parse_iso_date(t.get("due_date"))
                
                if t.get("project"):
                    ep_t.project_id = t["project"].get("id")
                    ep_t.project_name = t["project"].get("name")
                if t.get("tracker"):
                    ep_t.tracker_name = t["tracker"].get("name")
                if t.get("status"):
                    ep_t.status_name = t["status"].get("name")
                if t.get("priority"):
                    ep_t.priority_name = t["priority"].get("name")
                if t.get("assigned_to"):
                    ep_t.assigned_to_id = t["assigned_to"].get("id")
                    ep_t.assigned_to_name = t["assigned_to"].get("name")
                    matched_u = db.query(models.EPUser).filter(models.EPUser.ep_id == ep_t.assigned_to_id).first()
                    if matched_u:
                        ep_t.assigned_to_mail = matched_u.mail

                ep_t.synced_at = datetime.utcnow()
                tasks_count += 1
            db.commit()
        except Exception:
            pass

        duration = round(time.time() - start_time, 2)
        sync_log.ended_at = datetime.utcnow()
        sync_log.duration_seconds = duration
        sync_log.status = "SIKERES"
        sync_log.projects_count = projects_count
        sync_log.tasks_count = tasks_count
        sync_log.users_count = users_count
        db.commit()

        return {
            "status": "SUCCESS",
            "duration": duration,
            "projects": projects_count,
            "tasks": tasks_count,
            "users": users_count,
            "message": f"Kinyerés sikeres ({duration} mp)! Projektek: {projects_count} db, Feladatok: {tasks_count} db, Munkatársak: {users_count} fő."
        }
    except Exception as e:
        duration = round(time.time() - start_time, 2)
        sync_log.ended_at = datetime.utcnow()
        sync_log.duration_seconds = duration
        sync_log.status = "HIBA"
        sync_log.error_message = str(e)
        db.commit()
        return {"status": "ERROR", "message": f"Hiba a kinyeréskor: {str(e)}"}
