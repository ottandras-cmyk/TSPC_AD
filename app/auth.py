import os
import hmac
import hashlib
import time
import ssl
from ldap3 import Server, Connection, Tls, ALL, SIMPLE, NTLM
from ldap_client import parse_ad_server
from config_manager import get_setting

SECRET_KEY = os.getenv("AUTH_SECRET_KEY", "tspc-ad-tracker-session-secret-2026")
COOKIE_NAME = "ad_tracker_session"
SESSION_DURATION_SECONDS = 86400  # 24 órás munkamenet

def authenticate_ad_user(db, username: str, password: str):
    """Felhasználó ellenőrzése az Active Directory-ban"""
    raw_server = get_setting(db, "AD_SERVER")
    if not raw_server:
        return False, "Nincs konfigurálva AD szerver az adatbázisban!"

    # Ha a felhasználó nem írt tartományt, automatikusan hozzáfűzzük a @tspc.hu-t
    user_clean = username.strip()
    if "@" not in user_clean and "\\" not in user_clean:
        ad_principal = f"{user_clean}@tspc.hu"
    else:
        ad_principal = user_clean

    try:
        host, port, use_ssl = parse_ad_server(raw_server)
        tls_config = Tls(validate=ssl.CERT_NONE) if use_ssl else None
        server = Server(host=host, port=port, use_ssl=use_ssl, tls=tls_config, get_info=ALL, connect_timeout=5)
        
        auth_type = SIMPLE if "@" in ad_principal else NTLM
        
        # Próba csatlakozás a megadott adatokkal
        conn = Connection(
            server,
            user=ad_principal,
            password=password,
            authentication=auth_type,
            auto_bind=True
        )
        conn.unbind()
        return True, ad_principal
    except Exception as e:
        return False, f"Sikertelen hitelesítés: hibás felhasználónév vagy jelszó! ({e})"

def create_session_token(username: str) -> str:
    """Biztonságos HMAC-aláírt token generálása"""
    ts = str(int(time.time()))
    payload = f"{username}:{ts}"
    sig = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{username}:{ts}:{sig}"

def verify_session_token(token: str) -> str | None:
    """Munkamenet érvényességének vizsgálata"""
    if not token:
        return None
    parts = token.split(":")
    if len(parts) != 3:
        return None
    user, ts_str, sig = parts
    try:
        ts = int(ts_str)
    except ValueError:
        return None

    # Időkorlát ellenőrzése
    if time.time() - ts > SESSION_DURATION_SECONDS:
        return None

    expected_sig = hmac.new(SECRET_KEY.encode(), f"{user}:{ts_str}".encode(), hashlib.sha256).hexdigest()
    if hmac.compare_digest(sig, expected_sig):
        return user
    return None
