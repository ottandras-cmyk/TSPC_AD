import os
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from database import get_db
import models
from config_manager import get_setting
from routers.auth import get_current_user
from services.template_engine import render_modular_template

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
router = APIRouter(tags=["web"])

@router.get("/static/{file_path:path}")
def serve_static(file_path: str):
    full_path = os.path.join(APP_DIR, "static", file_path)
    if os.path.isfile(full_path):
        media_type = "text/css" if file_path.endswith(".css") else ("application/javascript" if file_path.endswith(".js") else None)
        return FileResponse(full_path, media_type=media_type)
    return HTMLResponse("File not found", status_code=404)

@router.get("/", response_class=HTMLResponse)
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

    interval_min = int(get_setting(db, "SYNC_INTERVAL_MINUTES", "15"))
    opts = [(0, "Kikapcsolva"), (5, "5 percenként"), (15, "15 percenként"), (60, "1 óra"), (240, "4 óra"), (360, "6 óra"), (720, "12 óra"), (1440, "24 óra"), (2880, "48 óra")]
    interval_options = "\n".join([f'<option value="{m}" {"selected" if interval_min==m else ""}>{lbl}</option>' for m, lbl in opts])

    content = render_modular_template("index.html", {
        "current_user": current_user,
        "rows": rows,
        "ad_server": get_setting(db, "AD_SERVER", ""),
        "ad_user": get_setting(db, "AD_USER", ""),
        "ad_base": get_setting(db, "AD_SEARCH_BASE", ""),
        "ollama_url": get_setting(db, "OLLAMA_URL", "http://ollama:11434"),
        "gh_repo": get_setting(db, "GH_REPO", ""),
        "gh_token": get_setting(db, "GH_TOKEN", ""),
        "gh_branch": get_setting(db, "GH_BRANCH", "main"),
        "interval_options": interval_options
    })
    return HTMLResponse(content=content)
