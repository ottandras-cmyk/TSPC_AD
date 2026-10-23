from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from database import get_db
from auth import verify_session_token, COOKIE_NAME
from ad_analytics import get_ad_analytics_summary, ask_ad_changes_ai, get_day_detailed_events
from telemetry import log_web_activity

router = APIRouter(prefix="/api/ad-analytics", tags=["ad-analytics"])

def get_current_user(request: Request):
    user, _ = verify_session_token(request.cookies.get(COOKIE_NAME))
    return user

@router.get("/summary")
def api_ad_analytics_summary(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    return get_ad_analytics_summary(db)

@router.get("/day-events")
def api_ad_analytics_day_events(date: str, type: str = "ALL", request: Request = None, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    return get_day_detailed_events(db, date_str=date, event_type=type)

@router.post("/ask")
async def api_ad_analytics_ask(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return JSONResponse(status_code=401, content={})
    data = await request.json()
    res = ask_ad_changes_ai(db, data.get("model"), data.get("prompt"))
    log_web_activity(db, request, user, "AD_VÁLTOZÁS_AI_KÉRDÉS", f"Modell: {data.get('model')}", "SIKERES" if res.get("status") == "SUCCESS" else "HIBA")
    return res
