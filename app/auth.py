import hmac
import hashlib
import time
import uuid
from ldap3 import Server, Connection, ALL
from config_manager import get_setting
from fastapi import Request, HTTPException, status

SECRET_KEY = "ad-tracker-secret-key-change-in-production"
COOKIE_NAME = "ad_session"

def create_session_token(username: str, session_id: str = None) -> tuple[str, str]:
    if not session_id:
        session_id = str(uuid.uuid4())
    ts = str(int(time.time()))
    data = f"{username}:{session_id}:{ts}"
    signature = hmac.new(SECRET_KEY.encode(), data.encode(), hashlib.sha256).hexdigest()
    return f"{data}:{signature}", session_id

def verify_session_token(token: str):
    if not token:
        return None, None
    try:
        parts = token.split(":")
        if len(parts) == 4:
            username, session_id, ts, sig = parts
            data = f"{username}:{session_id}:{ts}"
            expected_sig = hmac.new(SECRET_KEY.encode(), data.encode(), hashlib.sha256).hexdigest()
            if hmac.compare_digest(sig, expected_sig):
                if time.time() - int(ts) < 86400 * 7:
                    return username, session_id
        elif len(parts) == 3:
            username, ts, sig = parts
            data = f"{username}:{ts}"
            expected_sig = hmac.new(SECRET_KEY.encode(), data.encode(), hashlib.sha256).hexdigest()
            if hmac.compare_digest(sig, expected_sig):
                return username, f"legacy_{username}"
    except Exception:
        pass
    return None, None

def authenticate_ad_user(db, username: str, password: str) -> tuple[bool, str]:
    server_addr = get_setting(db, "AD_SERVER")
    search_base = get_setting(db, "AD_SEARCH_BASE")
    if not server_addr or not search_base:
        return False, "Nincs konfigurálva AD szerver!"
    if not password:
        return False, "Üres jelszó nem engedélyezett!"
    
    clean_user = username.strip()
    if "@" not in clean_user and "\\" not in clean_user:
        user_dn_try = f"{clean_user}@tspc.hu"
    else:
        user_dn_try = clean_user
        
    try:
        server = Server(server_addr, get_info=ALL)
        conn = Connection(server, user=user_dn_try, password=password, auto_bind=True)
        conn.unbind()
        return True, clean_user
    except Exception as e:
        return False, str(e)

def get_current_session(request: Request) -> tuple[str, str]:
    token = request.cookies.get(COOKIE_NAME) or request.cookies.get("ad_session") or request.cookies.get("adaudit_session")
    if not token:
        return None, None
    return verify_session_token(token)

def get_current_user(request: Request) -> str:
    user, _ = get_current_session(request)
    return user

def require_current_user(request: Request) -> str:
    user = get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Érvénytelen vagy lejárt munkamenet"
        )
    return user
