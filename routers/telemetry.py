from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from database import get_db
from auth import verify_session_token, COOKIE_NAME
from telemetry import (
    collect_and_save_telemetry, get_live_telemetry, get_telemetry_history,
    log_web_activity, get_web_access_logs, get_host_ip_history,
    update_active_session, get_active_sessions_info
)

router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])

def get_current_session(request: Request):
    return verify_session_token(request.cookies.get(COOKIE_NAME))

@router.get("/live")
def api_telemetry_live(request: Request, db: Session = Depends(get_db)):
    user, session_id = get_current_session(request)
    if not user: return JSONResponse(status_code=401, content={})
    update_active_session(db, session_id)
    return get_live_telemetry(db)

@router.get("/sessions")
def api_telemetry_sessions(request: Request, db: Session = Depends(get_db)):
    user, session_id = get_current_session(request)
    if not user: return JSONResponse(status_code=401, content={})
    update_active_session(db, session_id)
    return get_active_sessions_info(db, session_id)

@router.get("/history")
def api_telemetry_history(request: Request, db: Session = Depends(get_db)):
    user, _ = get_current_session(request)
    if not user: return JSONResponse(status_code=401, content={})
    return {"history": get_telemetry_history(db, limit=96)}

@router.get("/web-logs")
def api_telemetry_web_logs(request: Request, db: Session = Depends(get_db)):
    user, _ = get_current_session(request)
    if not user: return JSONResponse(status_code=401, content={})
    return {"logs": get_web_access_logs(db, limit=100)}

@router.get("/host-ip-history")
def api_telemetry_host_ip_history(request: Request, db: Session = Depends(get_db)):
    user, _ = get_current_session(request)
    if not user: return JSONResponse(status_code=401, content={})
    return {"history": get_host_ip_history(db, limit=50)}

@router.post("/collect")
def api_telemetry_collect(request: Request, db: Session = Depends(get_db)):
    user, session_id = get_current_session(request)
    if not user: return JSONResponse(status_code=401, content={})
    update_active_session(db, session_id)
    rec = collect_and_save_telemetry(db)
    log_web_activity(db, request, user, "MÉRÉS_RÖGZÍTÉS", f"Azonnali telemetria mérés azonosító: #{rec.id}", "SIKERES")
    return {"status": "SUCCESS", "id": rec.id, "timestamp": rec.timestamp.strftime("%Y-%m-%d %H:%M:%S")}
