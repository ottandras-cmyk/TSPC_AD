import ssl
from urllib.parse import urlparse
from ldap3 import Server, Connection, Tls, ALL, NTLM, SIMPLE, SUBTREE
from config_manager import get_setting

def parse_ad_server(raw_server: str):
    raw = raw_server.strip()
    use_ssl = False
    port = None
    if "://" in raw:
        parsed = urlparse(raw)
        host = parsed.hostname
        port = parsed.port
        if parsed.scheme.lower() == "ldaps":
            use_ssl = True
    else:
        if ":" in raw:
            parts = raw.split(":")
            host = parts[0]
            port = int(parts[1])
        else:
            host = raw
    if not port:
        port = 636 if use_ssl else 389
    return host, port, use_ssl

def test_ad_connection(db):
    raw_server = get_setting(db, "AD_SERVER")
    user = get_setting(db, "AD_USER")
    password = get_setting(db, "AD_PASSWORD")
    search_base = get_setting(db, "AD_SEARCH_BASE")

    if not all([raw_server, user, password, search_base]):
        return {"ad_kapcsolat": "HIBA", "reszletek": "Hiányzó AD beállítások! Kérjük, töltse ki a Beállítások menüben."}

    try:
        host, port, use_ssl = parse_ad_server(raw_server)
        tls_config = Tls(validate=ssl.CERT_NONE) if use_ssl else None
        server = Server(host=host, port=port, use_ssl=use_ssl, tls=tls_config, get_info=ALL, connect_timeout=8)
        auth_type = SIMPLE if "@" in user else NTLM
        conn = Connection(server, user=user, password=password, authentication=auth_type, auto_bind=True)

        conn.search(search_base=search_base, search_filter="(&(objectClass=user)(objectCategory=person))", search_scope=SUBTREE, attributes=['sAMAccountName'], size_limit=1)
        found = len(conn.entries)
        conn.unbind()
        return {"ad_kapcsolat": "SIKERES", "celpont": f"{host}:{port}", "talalt_objektum": found}
    except Exception as e:
        return {"ad_kapcsolat": "HIBA", "reszletek": str(e)}
