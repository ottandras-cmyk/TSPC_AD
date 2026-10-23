from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_
from database import get_db
import models
from auth import verify_session_token, COOKIE_NAME

router = APIRouter(prefix="/api", tags=["users"])

def get_current_user(request: Request):
    user, _ = verify_session_token(request.cookies.get(COOKIE_NAME))
    return user

@router.get("/users")
def get_all_users(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    try:
        users = db.query(models.ADUser).all()
        result = []
        for u in users:
            u_status = getattr(u, "user_status", None) or ("Aktív normál user" if getattr(u, "is_enabled", True) else "Letiltva")
            last_logon_dt = getattr(u, "last_logon_date", None)
            last_logon_str = last_logon_dt.strftime("%Y-%m-%d %H:%M") if last_logon_dt and hasattr(last_logon_dt, "strftime") else "-"
            w_created = getattr(u, "when_created", None)
            w_changed = getattr(u, "when_changed", None)

            result.append({
                "guid": str(getattr(u, "object_guid", "")),
                "sam": getattr(u, "sam_account_name", "-"),
                "name": getattr(u, "display_name", None) or "-",
                "first_name": getattr(u, "first_name", None) or "-",
                "last_name": getattr(u, "last_name", None) or "-",
                "mail": getattr(u, "mail", None) or "-",
                "enabled": getattr(u, "is_enabled", True),
                "status": u_status,
                "last_logon": last_logon_str,
                "ou": getattr(u, "ou_path", None) or "-",
                "phone": getattr(u, "telephone_number", None) or "-",
                "mobile": getattr(u, "mobile", None) or "-",
                "title": getattr(u, "title", None) or "-",
                "department": getattr(u, "department", None) or "-",
                "company": getattr(u, "company", None) or "-",
                "office": getattr(u, "office", None) or "-",
                "desc": getattr(u, "description", None) or "-",
                "sid": getattr(u, "object_sid", None) or "-",
                "source_type": getattr(u, "source_type", "AD_SYNC") or "AD_SYNC",
                "source_ref": getattr(u, "source_ref", "LIVE_AD") or "LIVE_AD",
                "created": w_created.strftime("%Y-%m-%d %H:%M") if w_created else "-",
                "changed": w_changed.strftime("%Y-%m-%d %H:%M") if w_changed else "-",
                "groups": [{"name": getattr(g, "sam_account_name", "-"), "type": getattr(g, "group_type", None) or "Ismeretlen"} for g in getattr(u, "groups", [])]
            })
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@router.get("/users/{identifier}/history")
def get_user_history(identifier: str, request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    try:
        clean_id = identifier.strip()
        prefix = clean_id.split("@")[0] if "@" in clean_id else clean_id
        
        filters = [
            models.ADAuditLog.entity_name.ilike(clean_id),
            models.ADAuditLog.entity_name.ilike(prefix),
            models.ADAuditLog.details.ilike(f"%{prefix}%")
        ]
        
        logs = db.query(models.ADAuditLog)\
            .filter(or_(*filters))\
            .order_by(desc(models.ADAuditLog.timestamp))\
            .limit(100)\
            .all()
            
        return [{
            "timestamp": l.timestamp.strftime("%Y-%m-%d %H:%M:%S") if l.timestamp else "-",
            "change_type": l.change_type,
            "details": l.details or "",
            "source_type": getattr(l, "source_type", "AD_SYNC") or "AD_SYNC",
            "source_ref": getattr(l, "source_ref", "LIVE_AD") or "LIVE_AD"
        } for l in logs]
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@router.get("/groups")
def get_all_groups(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    try:
        groups = db.query(models.ADGroup).all()
        return [{
            "sam": g.sam_account_name,
            "desc": g.description or "-",
            "type": g.group_type or "Ismeretlen",
            "sid": g.object_sid or "-",
            "source_type": getattr(g, "source_type", "AD_SYNC") or "AD_SYNC",
            "source_ref": getattr(g, "source_ref", "LIVE_AD") or "LIVE_AD",
            "created": g.when_created.strftime("%Y-%m-%d %H:%M") if g.when_created else "-",
            "changed": g.when_changed.strftime("%Y-%m-%d %H:%M") if g.when_changed else "-",
            "members": [u.sam_account_name for u in g.members]
        } for g in groups]
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
