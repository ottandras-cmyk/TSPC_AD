import os, re, json, html, time, logging, urllib.request, urllib.parse, urllib.error
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db

logger = logging.getLogger("easyproject")
router = APIRouter(prefix="/api/easyproject", tags=["easyproject"])

def get_status_rank(status_name):
    if not status_name: return 99
    s = str(status_name).lower().strip()
    if any(k in s for k in ['új', 'uj', 'kioszt', 'new', '1.0']): return 0
    if any(k in s for k in ['elhalaszt', 'folyamat', 'vizsgá', 'vizsga', 'kívül', 'kivul', 'nyitott', 'open', '3.1', '3.2', '4.1']): return 1
    return 2

def get_telegram_creds():
    token, chat_id = "", "229087988"
    for p in ["settings.json", "config/settings.json"]:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    tg = d.get("telegram_bot_notifications") or {}
                    token = d.get("TG_BOT_TOKEN") or tg.get("bot_token") or tg.get("token") or token
                    chat_id = d.get("TG_CHAT_ID") or tg.get("chat_id") or chat_id
            except Exception: pass
    if not token: token = os.environ.get("TG_BOT_TOKEN", "")
    if not chat_id: chat_id = os.environ.get("TG_CHAT_ID", "229087988")
    return str(token).strip(), str(chat_id).strip()

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

@router.get("/helpdesk/tickets")
def get_helpdesk_tickets(request: Request, db: Session = Depends(get_db)):
    tickets = []
    try:
        rows = db.execute(text("SELECT * FROM ep_tasks WHERE project_id = 2403 OR project_name LIKE '%Helpdesk%' ORDER BY id DESC;")).mappings().all()
        for r in rows:
            t_dict = dict(r)
            tickets.append(t_dict)
    except Exception as e:
        logger.warning("Adatbázis hiba jegyek lekérdezésekor: %s", str(e))

    tickets.sort(key=lambda t: (get_status_rank(t.get("status_name")), -int(t.get("id") or 0)))
    open_cnt = sum(1 for t in tickets if get_status_rank(t.get("status_name")) < 2)
    closed_cnt = len(tickets) - open_cnt

    return {
        "status": "SUCCESS",
        "summary": {
            "total_count": len(tickets),
            "open_count": open_cnt,
            "closed_count": closed_cnt,
            "last_sync": time.strftime("%Y-%m-%d %H:%M:%S")
        },
        "tickets": tickets
    }

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
