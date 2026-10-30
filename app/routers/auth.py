from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from database import get_db
from auth import authenticate_ad_user, create_session_token, verify_session_token, COOKIE_NAME
from telemetry import register_active_session, close_active_session, log_web_activity

router = APIRouter(tags=["auth"])

def get_current_session(request: Request):
    return verify_session_token(request.cookies.get(COOKIE_NAME))

def get_current_user(request: Request):
    user, _ = get_current_session(request)
    return user

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: str = None):
    if get_current_user(request): return RedirectResponse(url="/", status_code=303)
    err_html = f'<div style="background:#fee2e2; color:#dc2626; padding:12px; border-radius:6px; margin-bottom:15px; font-size:14px;">{error}</div>' if error else ''
    return f"""<!DOCTYPE html><html lang="hu"><head><meta charset="UTF-8"><title>Belépés</title><style>
    body{{font-family:sans-serif; background:#0f172a; display:flex; align-items:center; justify-content:center; height:100vh; margin:0;}}
    .card{{background:white; padding:35px; border-radius:12px; max-width:400px; width:100%; box-sizing:border-box;}}
    input{{width:100%; padding:10px; border:1px solid #cbd5e1; border-radius:6px; box-sizing:border-box; margin-bottom:15px;}}
    .btn{{width:100%; background:#0284c7; color:white; border:none; padding:12px; border-radius:6px; cursor:pointer; font-weight:bold;}}
</style></head><body><div class="card"><h2>AD Tracker Belépés</h2>{err_html}
<form method="POST" action="/login">
    Felhasználó (@tspc.hu)<input type="text" name="username" required autofocus>
    Jelszó<input type="password" name="password" required>
    <button type="submit" class="btn">Bejelentkezés</button>
</form></div></body></html>"""

@router.post("/login")
def process_login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    success, result = authenticate_ad_user(db, username, password)
    if not success:
        log_web_activity(db, request, username, "BEJELENTKEZÉS", "Hibás felhasználónév vagy jelszó", "SIKERTELEN")
        return RedirectResponse(url="/login?error=Hibas+adatok", status_code=303)
    token, session_id = create_session_token(result)
    register_active_session(db, request, session_id, result)
    log_web_activity(db, request, result, "BEJELENTKEZÉS", f"Sikeres belépés (Munkamenet: {session_id[:8]})", "SIKERES")
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(key=COOKIE_NAME, value=token, httponly=True, max_age=86400 * 7, samesite="lax")
    return response

@router.get("/logout")
def process_logout(request: Request, db: Session = Depends(get_db)):
    user, session_id = get_current_session(request)
    if user:
        close_active_session(db, session_id)
        log_web_activity(db, request, user, "KIJELENTKEZÉS", f"Kijelentkezés (Munkamenet: {session_id[:8] if session_id else '-'})", "SIKERES")
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response
