import html
import re
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from database import get_db
import models
from auth import verify_session_token, COOKIE_NAME
from config_manager import get_setting
from easy_project_sync import sync_helpdesk_tickets, sync_easy_project_data

router = APIRouter(prefix="/api/easyproject", tags=["easyproject"])

def get_current_user(request: Request):
    user, _ = verify_session_token(request.cookies.get(COOKIE_NAME))
    return user

def clean_html_snippet(text_c, max_len=140):
    if not text_c: return ""
    clean = html.unescape(text_c)
    clean = re.sub(r'<(br|p|/p)[^>]*>', ' ', clean, flags=re.IGNORECASE)
    clean = re.sub(r'<[^>]+>', '', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return (clean[:max_len] + "...") if len(clean) > max_len else clean

def is_ticket_closed(t) -> bool:
    """
    Hiteles Easy Project lezártság vizsgálat:
    1. raw_json-ban closed_on megléte (Easy Project natív lezárási időbélyeg)
    2. raw_json-ban status.is_closed == True
    3. Magyar és angol lezárt / befejezett / elutasított státuszok
    """
    # 1. Nyers Easy Project adatok vizsgálata
    if t.raw_json:
        try:
            raw = json.loads(t.raw_json)
            # Ha van closed_on kitöltve, az Easy Project szerint lezárt
            if raw.get("closed_on"):
                return True
            # Ha a státusz objektumban is_closed == True
            st_obj = raw.get("status", {})
            if isinstance(st_obj, dict) and st_obj.get("is_closed") is True:
                return True
        except Exception:
            pass

    # 2. Státusz szöveges vizsgálata
    s = (t.status_name or "").lower().strip()
    closed_keywords = [
        "lezárt", "lezárva", "megoldva", "elutasítva", "érvénytelen", 
        "törölve", "sztornó", "kész", "befejezve", "átadva", "archivált",
        "closed", "resolved", "rejected", "done", "cancelled", "invalid"
    ]
    if any(k in s for k in closed_keywords):
        return True

    return False

@router.get("/helpdesk/tickets")
def get_helpdesk_tickets_from_db(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request):
        return JSONResponse(status_code=401, content={"status": "ERROR", "message": "Nincs bejelentkezve"})

    tickets = db.query(models.EPHelpdeskTicket).order_by(desc(models.EPHelpdeskTicket.created_on)).all()

    last_sync_record = db.query(models.EPSyncHistory).filter(
        models.EPSyncHistory.sync_type == "HELPDESK",
        models.EPSyncHistory.status == "SIKERES"
    ).order_by(desc(models.EPSyncHistory.ended_at)).first()

    hd_interval = int(get_setting(db, "HD_SYNC_INTERVAL_MINUTES", "15"))
    hd_enabled = get_setting(db, "HD_SYNC_ENABLED", "0") == "1"

    last_sync_iso = None
    next_sync_iso = None
    last_sync_formatted = "-"

    if last_sync_record and last_sync_record.ended_at:
        dt = last_sync_record.ended_at
        last_sync_iso = dt.replace(tzinfo=timezone.utc).isoformat()
        last_sync_formatted = dt.strftime("%Y-%m-%d %H:%M:%S")
        if hd_enabled:
            next_sync_dt = dt.timestamp() + (hd_interval * 60)
            next_sync_iso = datetime.fromtimestamp(next_sync_dt, tz=timezone.utc).isoformat()

    statuses = set()
    categories = set()
    priorities = set()
    locations = set()

    tickets_payload = []
    open_count = 0
    closed_count = 0

    for t in tickets:
        st_name = t.status_name or "Nyitott"
        statuses.add(st_name)
        if t.category: categories.add(t.category)
        if t.priority_name: priorities.add(t.priority_name)
        if t.location: locations.add(t.location)

        # Hiteles lezártság számítás
        if is_ticket_closed(t):
            closed_count += 1
        else:
            open_count += 1

        tickets_payload.append({
            "id": t.ep_id,
            "hd_serial": t.hd_serial or f"#{t.ep_id}",
            "created_on": t.created_on.strftime("%Y-%m-%d %H:%M") if t.created_on else "-",
            "created_raw": t.created_on.isoformat() if t.created_on else "",
            "updated_on": t.updated_on.strftime("%Y-%m-%d %H:%M") if t.updated_on else "-",
            "subject": t.subject or "Névtelen hibajegy",
            "author_name": t.author_name or "Ismeretlen bejelentő",
            "assigned_to_name": t.assigned_to_name or "Nincs kiosztva",
            "assigned_to_mail": t.assigned_to_mail or "-",
            "phone": t.phone or "-",
            "location": t.location or "-",
            "inventory_number": t.inventory_number or "-",
            "category": t.category or "-",
            "status_name": st_name,
            "priority_name": t.priority_name or "Normál",
            "tracker_name": t.tracker_name or "Hibajegy",
            "contact_method": t.contact_method or "-",
            "desc_snippet": clean_html_snippet(t.ticket_desc_html),
            "solution_snippet": clean_html_snippet(t.solution_html),
            "desc_html": t.ticket_desc_html or "",
            "solution_html": t.solution_html or "",
            "raw_json": t.raw_json or "{}"
        })

    return {
        "status": "SUCCESS",
        "total_count": len(tickets_payload),
        "timing": {
            "last_sync_iso": last_sync_iso,
            "next_sync_iso": next_sync_iso,
            "hd_interval": hd_interval,
            "hd_enabled": hd_enabled
        },
        "summary": {
            "total_count": len(tickets_payload),
            "open_count": open_count,
            "closed_count": closed_count,
            "last_sync": last_sync_formatted,
            "statuses": sorted(list(statuses)),
            "categories": sorted(list(categories)),
            "priorities": sorted(list(priorities)),
            "locations": sorted(list(locations))
        },
        "tickets": tickets_payload
    }

@router.post("/helpdesk/sync")
def trigger_helpdesk_sync(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request):
        return JSONResponse(status_code=401, content={"status": "ERROR", "message": "Nincs bejelentkezve"})
    res = sync_helpdesk_tickets(db, trigger_type="MANUAL", target_project_id=2403)
    return res

@router.get("/summary")
def get_ep_summary(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    p_count = db.query(func.count(models.EPProject.id)).scalar() or 0
    t_count = db.query(func.count(models.EPTask.id)).scalar() or 0
    c_count = db.query(func.count(models.EPAuditLog.id)).scalar() or 0
    last_sync = db.query(models.EPSyncHistory).filter(models.EPSyncHistory.status == "SIKERES").order_by(desc(models.EPSyncHistory.ended_at)).first()
    return {
        "projects_count": p_count,
        "tasks_count": t_count,
        "changes_count": c_count,
        "last_sync": last_sync.ended_at.strftime("%Y-%m-%d %H:%M:%S") if last_sync and last_sync.ended_at else "-"
    }

@router.get("/tasks")
def get_ep_tasks(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    tasks = db.query(models.EPTask).order_by(desc(models.EPTask.created_on)).limit(2000).all()
    res = []
    projects, statuses, trackers, priorities = set(), set(), set(), set()
    for t in tasks:
        if t.project_name: projects.add(t.project_name)
        if t.status_name: statuses.add(t.status_name)
        if t.tracker_name: trackers.add(t.tracker_name)
        if t.priority_name: priorities.add(t.priority_name)
        res.append({
            "id": t.ep_id,
            "project_name": t.project_name or "-",
            "subject": t.subject or "Névtelen feladat",
            "tracker": t.tracker_name or "Feladat",
            "status": t.status_name or "Nyitott",
            "priority": t.priority_name or "Normál",
            "assigned_to": t.assigned_to_name or "Nincs kiosztva",
            "done_ratio": t.done_ratio or 0,
            "due_date": t.due_date.strftime("%Y-%m-%d") if t.due_date else "-",
            "created_on": t.created_on.strftime("%Y-%m-%d %H:%M") if t.created_on else "-",
            "description": t.description or "",
            "solution_html": t.solution_html or ""
        })
    return {
        "status": "SUCCESS",
        "tasks": res,
        "summary": {
            "projects": sorted(list(projects)),
            "statuses": sorted(list(statuses)),
            "trackers": sorted(list(trackers)),
            "priorities": sorted(list(priorities))
        }
    }

@router.get("/projects")
def get_ep_projects(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    projects = db.query(models.EPProject).all()
    res = []
    for p in projects:
        t_cnt = db.query(func.count(models.EPTask.id)).filter(models.EPTask.project_id == p.ep_id).scalar() or 0
        res.append({
            "id": p.ep_id,
            "name": p.name,
            "identifier": p.identifier or "-",
            "status": "Aktív" if p.status == 1 else "Lezárt",
            "tasks_count": t_cnt,
            "updated_on": p.updated_on.strftime("%Y-%m-%d") if p.updated_on else "-"
        })
    return {"projects": res}

@router.get("/sync-history")
def get_ep_sync_history(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    hist = db.query(models.EPSyncHistory).order_by(desc(models.EPSyncHistory.started_at)).limit(50).all()
    return [{"id": h.id, "started": h.started_at.strftime("%Y-%m-%d %H:%M") if h.started_at else "-", "ended": h.ended_at.strftime("%Y-%m-%d %H:%M") if h.ended_at else "-", "duration": f"{h.duration_seconds} mp", "status": h.status, "type": getattr(h, "sync_type", "GENERAL")} for h in hist]

@router.get("/changes")
def get_ep_changes(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    logs = db.query(models.EPAuditLog).order_by(desc(models.EPAuditLog.timestamp)).limit(100).all()
    return [{"id": l.id, "timestamp": l.timestamp.strftime("%Y-%m-%d %H:%M") if l.timestamp else "-", "entity_name": l.entity_name, "project_name": l.project_name, "change_type": l.change_type, "old_value": l.old_value, "new_value": l.new_value, "details": l.details} for l in logs]


# ========================================================
# ÁTEMELT FUNKCIÓK (easyproject.py integráció)
# ========================================================
@router.get("/helpdesk/ticket/{ticket_id}/debug")
def get_ticket_debug(ticket_id: str, db: Session = Depends(get_db)):
    """Minden nyers adat kiolvasása a PostgreSQL adatbázisból és konfigurációból."""
    try: tid = int(ticket_id)
    except Exception: tid = ticket_id

    result = {
        "queried_ticket_id": ticket_id,
        "database_status": "ONLINE",
        "ep_tasks_row": None,
        "ep_tasks_columns": [],
        "related_tables_data": {},
        "telegram_config": {}
    }

    try:
        tables = [r[0] for r in db.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public';")).fetchall()]
        result["database_tables"] = tables

        if "ep_tasks" in tables:
            cols = [r[0] for r in db.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'ep_tasks';")).fetchall()]
            result["ep_tasks_columns"] = cols
            row = db.execute(text("SELECT * FROM ep_tasks WHERE id = :tid;"), {"tid": tid}).mappings().first()
            if row:
                result["ep_tasks_row"] = dict(row)

        # Ha létezik custom_values tábla
        if "custom_values" in tables:
            cv_rows = db.execute(text("SELECT * FROM custom_values WHERE customized_id = :tid;"), {"tid": tid}).mappings().all()
            result["related_tables_data"]["custom_values"] = [dict(r) for r in cv_rows]

    except Exception as e:
        result["database_error"] = str(e)

    token, chat_id = get_telegram_creds()
    result["telegram_config"] = {
        "token_available": bool(token),
        "token_length": len(token) if token else 0,
        "token_prefix": (token[:8] + "...") if token and len(token) > 8 else "ÜRES",
        "chat_id": chat_id
    }
    return result

@router.post("/helpdesk/ticket/{ticket_id}/send-telegram")
async def send_ticket_telegram(ticket_id: str, request: Request, db: Session = Depends(get_db)):
    payload_data = {}
    try: payload_data = await request.json()
    except Exception: pass

    found = None
    try:
        row = db.execute(text("SELECT * FROM ep_tasks WHERE id = :tid;"), {"tid": int(ticket_id)}).mappings().first()
        if row: found = dict(row)
    except Exception: pass

    if not found and payload_data:
        found = payload_data

    if not found:
        return JSONResponse(status_code=404, content={"status": "ERROR", "message": f"A #{ticket_id} azonosítójú hibajegy nem található!"})

    token, chat_id = get_telegram_creds()
    if not token:
        return JSONResponse(status_code=400, content={"status": "ERROR", "message": "Hiányzó Telegram Bot Token a Beállítások menüben!"})

    # Tiszta szöveges összeállítás
    sorszam = found.get('custom_field_545') or found.get('hd_serial') or ''
    subject = str(found.get('subject') or 'Nincs tárgy').strip()
    author = str(found.get('author_name') or found.get('author') or 'Ismeretlen').strip()
    desc = str(found.get('custom_field_530') or found.get('description') or '').strip()

    lines = [
        f"🎫 Helpdesk Hibajegy #{ticket_id}" + (f" (#{sorszam})" if sorszam else ""),
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"📌 Tárgy: {subject}",
        f"👤 Bejelentő: {author}",
        f"🚦 Státusz: {found.get('status_name') or found.get('status') or '-'}",
        f"⚡ Prioritás: {found.get('priority_name') or found.get('priority') or '-'}",
    ]
    if desc and desc not in ("-", "None", ""):
        lines.extend(["━━━━━━━━━━━━━━━━━━━━━━", "📝 Jegy leírása:", desc[:2500]])

    msg_text = "\n".join(lines)
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = urllib.parse.urlencode({"chat_id": chat_id, "text": msg_text}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST")

    send_success, err_msg = False, ""
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            send_success = True
    except urllib.error.HTTPError as e:
        raw_e = e.read().decode("utf-8", errors="ignore")
        try: err_msg = json.loads(raw_e).get("description") or raw_e
        except Exception: err_msg = raw_e
    except Exception as e:
        err_msg = str(e)

    if send_success:
        return {"status": "SUCCESS", "message": f"A #{ticket_id} számú hibajegy sikeresen elküldve a Telegram csoportba!"}
    else:
        return JSONResponse(status_code=500, content={"status": "ERROR", "message": f"Telegram API hiba: {err_msg}"})
