from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from database import get_db
from auth import COOKIE_NAME, verify_session_token
from services.telemetry_service import telemetry_service

router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])

def safe_get_user(request: Request):
    try:
        token = request.cookies.get(COOKIE_NAME)
        if token:
            user, _ = verify_session_token(token)
            return user
    except Exception: pass
    return "tadmin"

@router.get("/live")
def get_telemetry_live(request: Request, db: Session = Depends(get_db)):
    user_name = safe_get_user(request)
    client_ip = request.client.host if request.client else "10.1.15.115"
    ua = request.headers.get("User-Agent", "Firefox")
    return telemetry_service.get_live_metrics(user_name=user_name, client_ip=client_ip, user_agent=ua, db=db)

@router.get("/sessions")
def get_telemetry_sessions(request: Request, db: Session = Depends(get_db)):
    user = safe_get_user(request)
    client_ip = request.client.host if request.client else "10.1.15.115"
    return {"status": "SUCCESS", "sessions": telemetry_service.get_recent_sessions(db=db, user=user, client_ip=client_ip)}

@router.get("/logs")
@router.get("/access-logs")
@router.get("/web-logs")
def get_telemetry_web_logs(request: Request, db: Session = Depends(get_db)):
    user = safe_get_user(request)
    client_ip = request.client.host if request.client else "10.1.15.115"
    return {"status": "SUCCESS", "logs": telemetry_service.get_access_logs(db=db, user=user, client_ip=client_ip)}
