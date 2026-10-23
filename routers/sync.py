import threading
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from database import get_db, SessionLocal
import models
from auth import verify_session_token, COOKIE_NAME
from telemetry import log_web_activity
from sync_engine import run_ad_sync

router = APIRouter(prefix="/api", tags=["sync"])

def get_current_user(request: Request):
    user, _ = verify_session_token(request.cookies.get(COOKIE_NAME))
    return user

sync_state = {"is_syncing": False, "last_run": None, "last_changes": 0}
sync_lock = threading.Lock()

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

@router.get("/sync-status")
def get_sync_status(request: Request):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    return sync_state

@router.get("/sync-history")
def get_sync_history(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    try:
        logs = db.query(models.SyncHistory).order_by(desc(models.SyncHistory.started_at)).limit(50).all()
        return [{"id": l.id, "started": l.started_at.strftime("%Y-%m-%d %H:%M:%S") if l.started_at else "-", "ended": l.ended_at.strftime("%Y-%m-%d %H:%M:%S") if l.ended_at else "-", "duration": f"{l.duration_seconds} mp" if l.duration_seconds is not None else "-", "trigger": l.trigger_type, "status": l.status, "changes": l.changes_detected, "error": l.error_message or ""} for l in logs]
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@router.post("/sync")
def trigger_sync_manual(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return JSONResponse(status_code=401, content={})
    log_web_activity(db, request, user, "AD_SZINKRON", "Manuális szinkronizálás indítva", "SIKERES")
    threading.Thread(target=execute_sync_with_log, args=("Manuális",)).start()
    return {"status": "STARTED"}
