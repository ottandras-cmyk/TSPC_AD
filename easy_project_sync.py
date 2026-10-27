import urllib.request
import urllib.error
import json
import time
import ssl
import html
import re
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import engine
from config_manager import get_setting
import models

def get_ssl_context():
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

def clean_html_to_text(html_content):
    if not html_content: return ""
    text_c = html.unescape(html_content)
    text_c = re.sub(r'<(br|p|/p)[^>]*>', ' ', text_c, flags=re.IGNORECASE)
    text_c = re.sub(r'<[^>]+>', '', text_c)
    return re.sub(r'\s+', ' ', text_c).strip()

def extract_cf_value(cf):
    val = cf.get("value")
    if val is None: return ""
    if isinstance(val, list): return ", ".join(str(v) for v in val if v is not None)
    if isinstance(val, dict): return val.get("name") or str(val)
    return str(val)

def test_easy_project_connection(url: str, api_key: str) -> tuple:
    if not url: return False, "Nincs megadva Easy Project szerver cím!"
    if not api_key: return False, "Nincs megadva API kulcs!"
    clean_url = url.rstrip("/")
    headers = {
        "X-Redmine-API-Key": api_key,
        "Accept": "application/json",
        "User-Agent": "ADTracker-EasyProject-Connector"
    }
    ssl_ctx = get_ssl_context()
    for ep in [f"{clean_url}/users/current.json", f"{clean_url}/projects.json?limit=1"]:
        try:
            req = urllib.request.Request(ep, headers=headers)
            with urllib.request.urlopen(req, timeout=10, context=ssl_ctx) as resp:
                if resp.status in (200, 201):
                    return True, f"Sikeres kapcsolat az Easy Project szerverrel ({clean_url})!"
        except Exception:
            pass
    return False, "Nem sikerült csatlakozni az Easy Project szerverhez."

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

def sync_helpdesk_tickets(db: Session, trigger_type: str = "MANUAL", target_project_id: int = 2403) -> dict:
    url = get_setting(db, "EP_URL", "").rstrip("/")
    api_key = get_setting(db, "EP_API_KEY", "")
    if not url or not api_key:
        return {"status": "ERROR", "message": "Hiányzó Easy Project URL vagy API kulcs!"}

    models.Base.metadata.create_all(bind=engine)
    sync_log = models.EPSyncHistory(started_at=datetime.utcnow(), trigger_type=trigger_type, status="FOLYAMATBAN")
    setattr(sync_log, "sync_type", "HELPDESK")
    db.add(sync_log)
    db.commit()
    db.refresh(sync_log)

    start_time = time.time()
    new_tickets_count = 0
    updated_tickets_count = 0
    changes_detected = 0

    issues = []
    limit = 100
    offset = 0
    max_total = 10000

    try:
        while True:
            issues_url = f"{url}/issues.json?project_id={target_project_id}&status_id=*&limit={limit}&offset={offset}&sort=id:desc"
            data = fetch_json(issues_url, api_key)
            batch = data.get("issues", [])
            if not batch: break
            issues.extend(batch)
            total_count = data.get("total_count", 0)
            offset += len(batch)
            if (total_count and offset >= total_count) or len(batch) < limit or offset >= max_total:
                break
    except Exception as e:
        sync_log.ended_at = datetime.utcnow()
        sync_log.status = "HIBA"
        sync_log.error_message = str(e)
        db.commit()
        return {"status": "ERROR", "message": f"Nem sikerült lekérni a hibajegyeket: {str(e)}"}

    existing_tickets = {t.ep_id: t for t in db.query(models.EPHelpdeskTicket).all()}
    user_mail_map = {u.ep_id: u.mail for u in db.query(models.EPUser).all() if u.ep_id}

    for t in issues:
        issue_id = t.get("id")
        subject = t.get("subject", "Névtelen hibajegy")
        project_name = t.get("project", {}).get("name", "Helpdesk Kezelő")
        tracker_name = t.get("tracker", {}).get("name", "Hibajegy")
        status_id = t.get("status", {}).get("id")
        status_name = t.get("status", {}).get("name", "Nyitott")
        priority_name = t.get("priority", {}).get("name", "Normál")
        author_id = t.get("author", {}).get("id")
        author_name = t.get("author", {}).get("name", "Ismeretlen bejelentő")

        assigned_id = t.get("assigned_to", {}).get("id") if t.get("assigned_to") else None
        assigned_name = t.get("assigned_to", {}).get("name") if t.get("assigned_to") else None
        assigned_mail = user_mail_map.get(assigned_id) if assigned_id else None

        done_ratio = t.get("done_ratio", 0)
        created_on = parse_iso_date(t.get("created_on"))
        updated_on = parse_iso_date(t.get("updated_on"))
        due_date = parse_iso_date(t.get("due_date"))

        # EGYEDI MEZŐK ÉS FORMÁZOTT HTML TARTALMAK
        cfs = {cf.get("id"): extract_cf_value(cf) for cf in t.get("custom_fields", [])}
        category = cfs.get(498, "")
        inventory_number = cfs.get(499, "")
        ticket_desc_html = cfs.get(530, "") or t.get("description", "")
        contact_method = cfs.get(501, "")
        solution_html = cfs.get(531, "")
        location = cfs.get(503, "")
        hd_serial = cfs.get(545, "")
        phone = cfs.get(500, "")

        raw_json_str = json.dumps(t, ensure_ascii=False)
        ticket = existing_tickets.get(issue_id)

        if not ticket:
            ticket = models.EPHelpdeskTicket(ep_id=issue_id)
            db.add(ticket)
            existing_tickets[issue_id] = ticket
            new_tickets_count += 1
            changes_detected += 1
            db.add(models.EPAuditLog(
                entity_type="TICKET",
                entity_id=issue_id,
                entity_name=f"#{hd_serial or issue_id}: {subject}",
                project_name=project_name,
                change_type="TICKET_CREATED",
                old_value="-",
                new_value=status_name,
                details=f"Új hibajegy: #{hd_serial or issue_id} '{subject}' | Bejelentő: {author_name} | Tel: {phone or '-'}",
                assigned_mail=assigned_mail
            ))
        else:
            if ticket.status_name and ticket.status_name != status_name:
                db.add(models.EPAuditLog(
                    entity_type="TICKET",
                    entity_id=issue_id,
                    entity_name=f"#{hd_serial or issue_id}: {subject}",
                    project_name=project_name,
                    change_type="TICKET_STATUS_CHANGED",
                    old_value=ticket.status_name,
                    new_value=status_name,
                    details=f"Hibajegy státusz: '{ticket.status_name}' ➔ '{status_name}'",
                    assigned_mail=assigned_mail or ticket.assigned_to_mail
                ))
                changes_detected += 1

            old_assignee = ticket.assigned_to_name or "Nincs kiosztva"
            curr_assignee = assigned_name or "Nincs kiosztva"
            if old_assignee != curr_assignee:
                db.add(models.EPAuditLog(
                    entity_type="TICKET",
                    entity_id=issue_id,
                    entity_name=f"#{hd_serial or issue_id}: {subject}",
                    project_name=project_name,
                    change_type="TICKET_ASSIGNED_CHANGED",
                    old_value=old_assignee,
                    new_value=curr_assignee,
                    details=f"Hibajegy felelős: '{old_assignee}' ➔ '{curr_assignee}'",
                    assigned_mail=assigned_mail or ticket.assigned_to_mail
                ))
                changes_detected += 1

            if not ticket.solution_html and solution_html:
                db.add(models.EPAuditLog(
                    entity_type="TICKET",
                    entity_id=issue_id,
                    entity_name=f"#{hd_serial or issue_id}: {subject}",
                    project_name=project_name,
                    change_type="TICKET_RESOLVED",
                    old_value="Nincs megoldás",
                    new_value="Megoldva",
                    details=f"Megoldás rögzítve: {clean_html_to_text(solution_html)[:120]}",
                    assigned_mail=assigned_mail or ticket.assigned_to_mail
                ))
                changes_detected += 1

            updated_tickets_count += 1

        # Rekord mentése a helyi PostgreSQL-be
        ticket.project_id = target_project_id
        ticket.project_name = project_name
        ticket.subject = subject
        ticket.status_id = status_id
        ticket.status_name = status_name
        ticket.priority_name = priority_name
        ticket.tracker_name = tracker_name
        ticket.author_id = author_id
        ticket.author_name = author_name
        ticket.assigned_to_id = assigned_id
        ticket.assigned_to_name = assigned_name
        ticket.assigned_to_mail = assigned_mail
        ticket.done_ratio = done_ratio
        ticket.created_on = created_on
        ticket.updated_on = updated_on
        ticket.due_date = due_date
        ticket.hd_serial = hd_serial
        ticket.inventory_number = inventory_number
        ticket.phone = phone
        ticket.location = location
        ticket.category = category
        ticket.contact_method = contact_method
        ticket.ticket_desc_html = ticket_desc_html
        ticket.solution_html = solution_html
        ticket.raw_json = raw_json_str
        ticket.synced_at = datetime.utcnow()

    db.commit()
    duration = round(time.time() - start_time, 2)
    sync_log.ended_at = datetime.utcnow()
    sync_log.duration_seconds = duration
    sync_log.status = "SIKERES"
    sync_log.tasks_count = len(issues)
    sync_log.changes_count = changes_detected
    setattr(sync_log, "sync_type", "HELPDESK")
    db.commit()

    return {
        "status": "SUCCESS",
        "duration": duration,
        "total_fetched": len(issues),
        "new_tickets": new_tickets_count,
        "updated_tickets": updated_tickets_count,
        "changes_detected": changes_detected,
        "message": f"Helpdesk kinyerés sikeres ({duration} mp)! Jegyek: {len(issues)} db (+{changes_detected} változás)."
    }

def sync_easy_project_data(db: Session, trigger_type: str = "MANUAL") -> dict:
    url = get_setting(db, "EP_URL", "").rstrip("/")
    api_key = get_setting(db, "EP_API_KEY", "")
    if not url or not api_key:
        return {"status": "ERROR", "message": "Hiányzó Easy Project URL vagy API kulcs!"}

    models.Base.metadata.create_all(bind=engine)
    sync_log = models.EPSyncHistory(started_at=datetime.utcnow(), trigger_type=trigger_type, status="FOLYAMATBAN")
    setattr(sync_log, "sync_type", "PROJECTS")
    db.add(sync_log)
    db.commit()
    db.refresh(sync_log)

    start_time = time.time()
    projects_count = 0
    tasks_count = 0
    users_count = 0
    changes_detected = 0

    try:
        user_mail_map = {u.ep_id: u.mail for u in db.query(models.EPUser).all() if u.ep_id}

        # 1. Projektek kinyerése
        p_offset = 0
        while True:
            p_data = fetch_json(f"{url}/projects.json?limit=100&offset={p_offset}", api_key)
            p_batch = p_data.get("projects", [])
            if not p_batch: break
            for p in p_batch:
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
            p_offset += len(p_batch)
            if len(p_batch) < 100 or p_offset >= p_data.get("total_count", 0): break

        # 2. Összes feladat kinyerése és a HTML/megoldás mezők rögzítése
        existing_tasks = {t.ep_id: t for t in db.query(models.EPTask).all()}
        t_offset = 0
        while True:
            t_url = f"{url}/issues.json?status_id=*&limit=100&offset={t_offset}&sort=id:desc"
            t_data = fetch_json(t_url, api_key)
            t_batch = t_data.get("issues", [])
            if not t_batch: break

            for t in t_batch:
                issue_id = t.get("id")
                subject = t.get("subject", "Névtelen feladat")
                project_name = t.get("project", {}).get("name", "Projekt")
                project_id = t.get("project", {}).get("id")
                tracker_name = t.get("tracker", {}).get("name", "Feladat")
                new_status = t.get("status", {}).get("name", "Nyitott")
                new_priority = t.get("priority", {}).get("name", "Normál")
                new_done = t.get("done_ratio", 0)
                new_assignee = t.get("assigned_to", {}).get("name") if t.get("assigned_to") else "Nincs kiosztva"
                new_assignee_id = t.get("assigned_to", {}).get("id") if t.get("assigned_to") else None
                assigned_mail = user_mail_map.get(new_assignee_id)

                created_on = parse_iso_date(t.get("created_on"))
                updated_on = parse_iso_date(t.get("updated_on"))
                due_date = parse_iso_date(t.get("due_date"))

                cfs = {cf.get("id"): extract_cf_value(cf) for cf in t.get("custom_fields", [])}
                ticket_desc_html = cfs.get(530, "") or t.get("description", "")
                solution_html = cfs.get(531, "")
                inventory_number = cfs.get(499, "")
                phone = cfs.get(500, "")
                location = cfs.get(503, "")
                category = cfs.get(498, "")
                contact_method = cfs.get(501, "")
                hd_serial = cfs.get(545, "")

                ep_t = existing_tasks.get(issue_id)
                if not ep_t:
                    ep_t = models.EPTask(ep_id=issue_id)
                    db.add(ep_t)
                    existing_tasks[issue_id] = ep_t
                    changes_detected += 1
                else:
                    if ep_t.status_name and ep_t.status_name != new_status:
                        changes_detected += 1

                ep_t.project_id = project_id
                ep_t.project_name = project_name
                ep_t.tracker_name = tracker_name
                ep_t.status_name = new_status
                ep_t.priority_name = new_priority
                ep_t.subject = subject
                ep_t.description = t.get("description")
                ep_t.assigned_to_id = new_assignee_id
                ep_t.assigned_to_name = new_assignee
                ep_t.assigned_to_mail = assigned_mail
                ep_t.done_ratio = new_done
                ep_t.estimated_hours = t.get("estimated_hours")
                ep_t.spent_hours = t.get("spent_hours")
                ep_t.created_on = created_on
                ep_t.updated_on = updated_on
                ep_t.due_date = due_date

                # HTML és egyedi mezők rögzítése
                ep_t.ticket_desc_html = ticket_desc_html
                ep_t.solution_html = solution_html
                ep_t.hd_serial = hd_serial
                ep_t.inventory_number = inventory_number
                ep_t.phone = phone
                ep_t.location = location
                ep_t.category = category
                ep_t.contact_method = contact_method
                ep_t.raw_json = json.dumps(t, ensure_ascii=False)
                ep_t.synced_at = datetime.utcnow()
                tasks_count += 1

            db.commit()
            t_offset += len(t_batch)
            if len(t_batch) < 100 or t_offset >= t_data.get("total_count", 0): break

        duration = round(time.time() - start_time, 2)
        sync_log.ended_at = datetime.utcnow()
        sync_log.duration_seconds = duration
        sync_log.status = "SIKERES"
        sync_log.projects_count = projects_count
        sync_log.tasks_count = tasks_count
        sync_log.changes_count = changes_detected
        db.commit()

        return {
            "status": "SUCCESS",
            "duration": duration,
            "projects": projects_count,
            "tasks": tasks_count,
            "changes": changes_detected,
            "message": f"EP Teljes kinyerés sikeres ({duration} mp)! Projektek: {projects_count} db, Feladatok: {tasks_count} db."
        }
    except Exception as e:
        sync_log.ended_at = datetime.utcnow()
        sync_log.status = "HIBA"
        sync_log.error_message = str(e)
        db.commit()
        return {"status": "ERROR", "message": str(e)}
