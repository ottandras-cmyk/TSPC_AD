from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from database import get_db
import models
from auth import verify_session_token, COOKIE_NAME
from config_manager import get_setting, update_setting
from easy_project_sync import sync_easy_project_data
from telemetry import log_web_activity

router = APIRouter(prefix="/api/easyproject", tags=["easyproject"])

def get_current_user(request: Request):
    user, _ = verify_session_token(request.cookies.get(COOKIE_NAME))
    return user

@router.get("/summary")
def get_ep_summary(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    p_cnt = db.query(models.EPProject).count()
    t_cnt = db.query(models.EPTask).count()
    u_cnt = db.query(models.EPUser).count()
    last_sync = db.query(models.EPSyncHistory).order_by(desc(models.EPSyncHistory.started_at)).first()
    
    last_sync_info = "-"
    if last_sync and last_sync.started_at:
        last_sync_info = f"{last_sync.started_at.strftime('%Y-%m-%d %H:%M')} ({last_sync.status})"
        
    return {
        "projects_count": p_cnt,
        "tasks_count": t_cnt,
        "users_count": u_cnt,
        "last_sync": last_sync_info
    }

@router.get("/tasks")
def get_ep_tasks(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    tasks = db.query(models.EPTask).order_by(desc(models.EPTask.updated_on)).limit(200).all()
    results = []
    for t in tasks:
        results.append({
            "id": t.ep_id,
            "subject": t.subject,
            "project_name": t.project_name or "-",
            "tracker": t.tracker_name or "-",
            "status": t.status_name or "Nyitott",
            "priority": t.priority_name or "Normál",
            "assigned_to": t.assigned_to_name or "Nincs kiosztva",
            "assigned_mail": t.assigned_to_mail or "-",
            "done_ratio": t.done_ratio,
            "due_date": t.due_date.strftime("%Y-%m-%d") if t.due_date else "-",
            "updated_on": t.updated_on.strftime("%Y-%m-%d %H:%M") if t.updated_on else "-"
        })
    return {"tasks": results}

@router.get("/projects")
def get_ep_projects(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    projects = db.query(models.EPProject).order_by(desc(models.EPProject.updated_on)).limit(100).all()
    results = []
    for p in projects:
        task_count = db.query(models.EPTask).filter(models.EPTask.project_id == p.ep_id).count()
        results.append({
            "id": p.ep_id,
            "name": p.name,
            "identifier": p.identifier or "-",
            "description": p.description or "-",
            "status": "Aktív" if p.status == 1 else "Lezárt",
            "task_count": task_count,
            "updated_on": p.updated_on.strftime("%Y-%m-%d %H:%M") if p.updated_on else "-"
        })
    return {"projects": results}

@router.get("/sync-history")
def get_ep_sync_history(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    logs = db.query(models.EPSyncHistory).order_by(desc(models.EPSyncHistory.started_at)).limit(50).all()
    return [{
        "started": l.started_at.strftime("%Y-%m-%d %H:%M:%S") if l.started_at else "-",
        "ended": l.ended_at.strftime("%Y-%m-%d %H:%M:%S") if l.ended_at else "-",
        "duration": f"{l.duration_seconds:.1f} mp",
        "status": l.status,
        "trigger": "Manuális" if l.trigger_type == "MANUAL" else "Automatikus",
        "counts": f"P: {l.projects_count} | F: {l.tasks_count} | M: {l.users_count}",
        "error": l.error_message or ""
    } for l in logs]

@router.post("/sync")
async def trigger_ep_sync(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return JSONResponse(status_code=401, content={})
    try:
        body = await request.json()
    except Exception:
        body = {}

    # Ha a kérésben érkezett URL és API kulcs, közvetlenül beállítjuk
    if body.get("url"):
        update_setting(db, "EP_URL", body.get("url").strip())
    if body.get("key") and body.get("key") != "***":
        update_setting(db, "EP_API_KEY", body.get("key").strip())

    res = sync_easy_project_data(db, trigger_type="MANUAL")
    st = "SIKERES" if res.get("status") == "SUCCESS" else "HIBA"
    log_web_activity(db, request, user, "EASY_PROJECT_KINYERÉS", res.get("message", ""), st)
    return res
