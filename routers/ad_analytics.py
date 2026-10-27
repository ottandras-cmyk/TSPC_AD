from datetime import datetime
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from database import get_db
import models
from auth import verify_session_token, COOKIE_NAME

router = APIRouter(prefix="/api/ad", tags=["ad-analytics"])

def get_current_user(request: Request):
    user, _ = verify_session_token(request.cookies.get(COOKIE_NAME))
    return user

@router.get("/analytics")
def get_ad_analytics_data(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    
    logs = db.query(models.ADAuditLog).order_by(desc(models.ADAuditLog.timestamp)).limit(300).all()
    
    total_changes = len(logs)
    user_changes = 0
    group_changes = 0
    
    results = []
    for l in logs:
        e_type = (l.entity_type or "USER").upper()
        if "USER" in e_type: user_changes += 1
        elif "GROUP" in e_type: group_changes += 1

        results.append({
            "id": l.id,
            "timestamp": l.timestamp.strftime("%Y-%m-%d %H:%M:%S") if l.timestamp else "-",
            "entity_name": l.entity_name or "-",
            "entity_type": l.entity_type or "AD",
            "change_type": l.change_type or "MÓDOSÍTÁS",
            "old_value": l.old_value or "-",
            "new_value": l.new_value or "-",
            "details": l.details or "-"
        })

    return {
        "status": "SUCCESS",
        "total_changes": total_changes,
        "user_changes": user_changes,
        "group_changes": group_changes,
        "timeline": results
    }
