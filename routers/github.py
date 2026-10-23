from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from database import get_db
from auth import verify_session_token, COOKIE_NAME
from config_manager import get_setting
from github_sync import get_github_history, push_to_github_api, test_github_connection
from telemetry import log_web_activity

router = APIRouter(prefix="/api/github", tags=["github"])

def get_current_user(request: Request):
    user, _ = verify_session_token(request.cookies.get(COOKIE_NAME))
    return user

@router.get("/version")
def get_version(request: Request, db: Session = Depends(get_db)):
    ver = get_setting(db, "APP_VERSION", "1.00")
    return {"version": ver}

@router.get("/history")
def get_history(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    history = get_github_history(db)
    return {"status": "SUCCESS", "data": history}

@router.post("/test")
async def test_endpoint(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    try: body = await request.json()
    except Exception: body = {}
    repo = body.get("repo") or get_setting(db, "GH_REPO", "")
    token = body.get("token") or get_setting(db, "GH_TOKEN", "")
    ok, msg = test_github_connection(repo, token)
    return {"status": "SUCCESS" if ok else "ERROR", "message": msg}

@router.post("/push")
async def push_endpoint(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return JSONResponse(status_code=401, content={})
    try:
        body = await request.json()
        msg = body.get("message", "")
        res = push_to_github_api(db, message=msg, user=user)
        if res.get("status") == "SUCCESS":
            log_web_activity(db, request, user, "GITHUB_PUSH", f"Verzió: v{res.get('new_version')}, Üzenet: {msg}", "SIKERES")
        return res
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "ERROR", "message": str(e)})
