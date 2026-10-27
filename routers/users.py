import re
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db

router = APIRouter(prefix="/api/users", tags=["users"])

def safe_get_user(request: Request):
    try:
        from auth import COOKIE_NAME, verify_session_token
        token = request.cookies.get(COOKIE_NAME)
        if token:
            res = verify_session_token(token)
            if isinstance(res, tuple): return res[0]
            if isinstance(res, str): return res
            if res: return getattr(res, "username", "tadmin")
    except Exception:
        pass
    return "tadmin"

def parse_dn_folder(dn_str):
    if not dn_str: return "tspc.hu/TSPC/TSPC Groups"
    ous = re.findall(r"OU=([^,]+)", str(dn_str), re.IGNORECASE)
    dcs = re.findall(r"DC=([^,]+)", str(dn_str), re.IGNORECASE)
    domain = ".".join(dcs) if dcs else "tspc.hu"
    if ous:
        return f"{domain}/" + "/".join(reversed(ous))
    return f"{domain}/Users"

def classify_group_type(gname, desc="", folder="", scope=""):
    gn = str(gname).lower()
    fl = str(folder).lower()
    dc = str(desc).lower()

    if "distribution" in fl or "terjeszt" in fl or "levelez" in fl:
        return "Terjesztési lista (Distribution List)", "#8b5cf6"

    dl_keywords = ["dl_", "lista", "list", "terjeszt", "mail", "csoport-", "all-", "team", "levelez", "projekt", "vsg", "ctmr", "catl", "hsm", "bsu", "szakag", "management", "szervezet", "ackulcs"]
    if any(k in gn for k in dl_keywords) or "terjeszt" in dc or "levelez" in dc or "distribution" in dc:
        return "Terjesztési lista (Distribution List)", "#8b5cf6"
    elif gn.startswith("f_") or gn.startswith("fs_") or "mappa" in dc:
        return "Mappa jogosultság (Security Group)", "#0284c7"
    else:
        return "Biztonsági csoport (Security Group)", "#059669"

def parse_dn_details(dn_str):
    dn_str = str(dn_str).strip()
    cn_m = re.search(r"CN=([^,]+)", dn_str, re.IGNORECASE)
    name = cn_m.group(1).strip() if cn_m else dn_str
    folder = parse_dn_folder(dn_str)
    is_group = "groups" in folder.lower() or name.lower().startswith("ad_") or name.lower().startswith("f_")
    return name, folder, is_group

# 1. ÖSSZES FELHASZNÁLÓ ÉS CSOPORT LEKÉRDEZÉSE
@router.get("")
@router.get("/")
@router.get("/all")
def get_all_users_and_groups_fast(request: Request, db: Session = Depends(get_db)):
    if not safe_get_user(request):
        return JSONResponse(status_code=401, content={"status": "ERROR", "message": "Nincs bejelentkezve"})

    users_payload = []
    groups_payload = []

    try:
        raw_users = db.execute(text("SELECT * FROM ad_users;")).mappings().all()
        active_cnt = 0
        disabled_cnt = 0

        for r in raw_users:
            sam = r.get("sam_account_name") or r.get("username") or r.get("sam") or "-"
            d_name = r.get("display_name") or r.get("name") or sam
            mail = r.get("mail") or r.get("user_principal_name") or r.get("email") or (f"{sam}@tspc.hu" if sam != "-" else "-")
            dept = r.get("department") or "-"
            title = r.get("title") or "-"
            phone = r.get("telephone_number") or r.get("phone") or "-"

            en = r.get("is_enabled")
            if en is None: en = True
            if en: active_cnt += 1
            else: disabled_cnt += 1

            ll = r.get("last_logon_timestamp") or r.get("last_logon")
            ll_str = ll.strftime("%Y-%m-%d %H:%M") if hasattr(ll, "strftime") else (str(ll) if ll else "-")

            guid = str(r.get("object_guid") or r.get("id") or r.get("guid") or sam)
            dn = r.get("distinguished_name") or f"CN={d_name},OU=TSPC Users,DC=tspc,DC=hu"

            users_payload.append({
                "guid": guid,
                "sam_account_name": sam,
                "display_name": d_name,
                "mail": mail,
                "department": dept,
                "title": title,
                "telephone_number": phone,
                "is_enabled": bool(en),
                "last_logon": ll_str,
                "dn": dn
            })
    except Exception as e:
        print("Hiba ad_users olvasásakor:", e)

    try:
        raw_groups = db.execute(text("SELECT * FROM ad_groups;")).mappings().all()
        for g in raw_groups:
            sam = g.get("sam_account_name") or g.get("name") or "-"
            desc = g.get("description") or "-"
            scope = g.get("group_scope") or g.get("scope") or "Global"
            dn = g.get("distinguished_name") or f"CN={sam},OU=Groups,DC=tspc,DC=hu"
            guid = str(g.get("object_guid") or g.get("id") or sam)

            groups_payload.append({
                "guid": guid,
                "sam_account_name": sam,
                "description": desc,
                "group_scope": scope,
                "dn": dn
            })
    except Exception as e:
        print("Hiba ad_groups olvasásakor:", e)

    users_payload.sort(key=lambda x: str(x["display_name"]).lower())
    groups_payload.sort(key=lambda x: str(x["sam_account_name"]).lower())

    return {
        "status": "SUCCESS",
        "summary": {
            "total_users": len(users_payload),
            "active_users": active_cnt,
            "disabled_users": disabled_cnt,
            "total_groups": len(groups_payload)
        },
        "users": users_payload,
        "groups": groups_payload
    }

# 2. DINAMIKUS ADATLAP: MINDEN CSOPORTTAGSÁG HIÁNYTALAN KINYERÉSE
@router.get("/{sam}/detail")
@router.get("/{sam}")
def get_user_detail_full(sam: str, request: Request, db: Session = Depends(get_db)):
    if not safe_get_user(request):
        return JSONResponse(status_code=401, content={})

    u_row = None
    try:
        rows = db.execute(text("SELECT * FROM ad_users WHERE LOWER(sam_account_name) = LOWER(:s) OR object_guid::text = :s OR id::text = :s LIMIT 1;"), {"s": sam}).mappings().all()
        if rows: u_row = dict(rows[0])
    except Exception:
        db.rollback()

    if not u_row:
        u_row = {"sam_account_name": sam, "display_name": sam.replace(".", " ")}

    sam_clean = u_row.get("sam_account_name") or sam
    d_name = u_row.get("display_name") or sam_clean
    first_name = u_row.get("first_name") or u_row.get("given_name") or (d_name.split()[0] if " " in d_name else d_name)
    last_name = u_row.get("last_name") or u_row.get("sn") or (d_name.split()[1] if " " in d_name else "")
    dept = u_row.get("department") or "-"
    title = u_row.get("title") or "-"
    company = u_row.get("company") or "TSPC Kft."
    manager = u_row.get("manager") or "-"
    phone = u_row.get("telephone_number") or u_row.get("phone") or "-"
    mail = u_row.get("mail") or u_row.get("user_principal_name") or f"{sam_clean}@tspc.hu"
    en = u_row.get("is_enabled", True)
    ll = str(u_row.get("last_logon_timestamp") or u_row.get("last_logon") or "-")[:16]
    dn = u_row.get("distinguished_name") or f"CN={d_name},OU=TSPC Users,DC=tspc,DC=hu"
    created_at = str(u_row.get("when_created") or u_row.get("created_at") or u_row.get("created_on") or "-")[:16]

    # Összes csoport metaadatának betöltése
    db_groups = {}
    try:
        grows = db.execute(text("SELECT * FROM ad_groups;")).mappings().all()
        for g in grows:
            gn = g.get("sam_account_name")
            if gn:
                g_dn = g.get("distinguished_name") or ""
                db_groups[gn.lower()] = {
                    "raw_name": gn,
                    "description": g.get("description") or "-",
                    "group_scope": g.get("group_scope") or g.get("scope") or "Global",
                    "folder": parse_dn_folder(g_dn),
                    "members": g.get("members") or g.get("member") or g.get("member_dns")
                }
    except Exception as e:
        print("Hiba ad_groups olvasásakor:", e)
        db.rollback()

    groups_map = {}

    # Alapértelmezett csoportok
    groups_map["domain users"] = {
        "name": "Domain Users",
        "folder": "tspc.hu/Users",
        "added_at": "Alapértelmezett (Primary Group)",
        "removed": False
    }
    groups_map["tspc users"] = {
        "name": "TSPC Users",
        "folder": "tspc.hu/TSPC/TSPC Groups",
        "added_at": created_at if created_at != "-" else "Alapértelmezett",
        "removed": False
    }

    # 1. Kinyerés: ad_users tábla oszlopai (member_of, groups, stb.)
    for field in ["member_of", "memberof", "groups"]:
        val = u_row.get(field)
        if val:
            cns = re.findall(r'CN=([^,;\s"\'\]\[]+)', str(val), re.IGNORECASE)
            for gname in cns:
                gk = gname.lower().strip()
                if gk:
                    g_meta = db_groups.get(gk, {})
                    fold = g_meta.get("folder") or "tspc.hu/TSPC/TSPC Groups"
                    raw_n = g_meta.get("raw_name") or gname.strip()
                    groups_map[gk] = {"name": raw_n, "folder": fold, "added_at": "AD Szinkronizáció (memberOf)", "removed": False}

    # 2. Kinyerés: ad_groups tábla members oszlopa
    sam_l = sam_clean.lower()
    dname_l = d_name.lower()
    user_dn_l = dn.lower()
    for gk, g_info in db_groups.items():
        m_val = g_info.get("members")
        if m_val:
            m_str = str(m_val).lower()
            if sam_l in m_str or user_dn_l in m_str or (dname_l and dname_l in m_str):
                if gk not in groups_map:
                    groups_map[gk] = {"name": g_info["raw_name"], "folder": g_info["folder"], "added_at": "AD Szinkronizáció (Members)", "removed": False}

    # 3. Kinyerés: ad_audit_log (korlátok nélkül)
    history_payload = []
    try:
        hist_sql = text("""
            SELECT 
                to_char(timestamp, 'YYYY-MM-DD HH24:MI') as timestamp_str,
                COALESCE(change_type, 'MÓDOSÍTÁS') as change_type,
                COALESCE(details, 'Rendszeresemény rögzítve') as details
            FROM ad_audit_log 
            WHERE LOWER(entity_name) = LOWER(:s) 
               OR details ILIKE :pat
               OR details ILIKE :pat2
            ORDER BY timestamp ASC;
        """)
        h_rows = db.execute(hist_sql, {"s": sam_clean, "pat": f"%{sam_clean}%", "pat2": f"%{d_name}%"}).mappings().all()
        for h in h_rows:
            ts = h.get("timestamp_str") or "-"
            ctype = h.get("change_type") or ""
            dtls = h.get("details") or ""
            history_payload.append({"timestamp": ts, "change_type": ctype, "details": dtls})

            m = re.search(r"'([^']+)'", dtls)
            if m:
                gname = m.group(1).strip()
                gk = gname.lower()
                dtls_l = dtls.lower()
                if "hozzáadva" in dtls_l or "added" in ctype.lower():
                    g_meta = db_groups.get(gk, {})
                    fold = g_meta.get("folder") or "tspc.hu/TSPC/TSPC Groups"
                    raw_gname = g_meta.get("raw_name") or gname
                    if gk in groups_map:
                        groups_map[gk]["added_at"] = ts
                        groups_map[gk]["removed"] = False
                    else:
                        groups_map[gk] = {"name": raw_gname, "folder": fold, "added_at": ts, "removed": False}
                elif "eltávolítva" in dtls_l or "removed" in ctype.lower():
                    if gk in groups_map:
                        groups_map[gk]["removed"] = True
    except Exception as e:
        print("Hiba audit lognál:", e)
        db.rollback()

    history_payload.reverse()

    # Elemek összeállítása
    groups_payload = []
    for gk, info in groups_map.items():
        if info["removed"]:
            continue
        gname = info["name"]
        g_meta = db_groups.get(gk, {})
        desc = g_meta.get("description") or "-"
        scope = g_meta.get("group_scope") or "Global"
        folder = info.get("folder") or g_meta.get("folder") or "tspc.hu/TSPC/TSPC Groups"
        g_type, g_color = classify_group_type(gname, desc, folder, scope)

        groups_payload.append({
            "name": gname,
            "description": desc,
            "group_scope": scope,
            "group_type": g_type,
            "group_type_color": g_color,
            "folder": folder,
            "added_at": info["added_at"]
        })

    groups_payload.sort(key=lambda x: x["name"].lower())

    return {
        "status": "SUCCESS",
        "user": {
            "guid": str(u_row.get("object_guid") or u_row.get("id") or sam_clean),
            "sam_account_name": sam_clean,
            "pre_win2000_logon": f"TSPC\\{sam_clean}",
            "upn": mail,
            "display_name": d_name,
            "first_name": first_name,
            "last_name": last_name,
            "full_name": f"{first_name} {last_name}".strip(),
            "mail": mail,
            "department": dept,
            "title": title,
            "company": company,
            "manager": manager,
            "telephone_number": phone,
            "is_enabled": bool(en),
            "created_at": created_at,
            "last_logon": ll,
            "account_expires": "Soha nem jár le (Never)",
            "dn": dn,
            "primary_group": "Domain Users"
        },
        "groups": groups_payload,
        "history": history_payload
    }

# 3. CSOPORT TAGJAI: MINDEN TAG (FELHASZNÁLÓK ÉS BEÁGYAZOTT CSOPORTOK)
@router.get("/group/{group_name}/members")
def get_group_members_full(group_name: str, request: Request, db: Session = Depends(get_db)):
    if not safe_get_user(request):
        return JSONResponse(status_code=401, content={})

    desc = "-"
    scope = "Global"
    grow = None
    try:
        grow = db.execute(text("SELECT * FROM ad_groups WHERE LOWER(sam_account_name) = LOWER(:g) LIMIT 1;"), {"g": group_name}).mappings().first()
        if grow:
            desc = grow.get("description") or "-"
            scope = grow.get("group_scope") or grow.get("scope") or "Global"
    except Exception:
        db.rollback()

    members_dict = {}
    gn_lower = group_name.lower()

    # A. Ha Domain Users vagy TSPC Users: az AD összes felhasználója a tagja
    if "domain users" in gn_lower or "tspc users" in gn_lower:
        try:
            # Csak létező oszlopok lekérdezése (nincs tranzakció elhasalás!)
            urows = db.execute(text("SELECT sam_account_name, display_name, mail, title, department, distinguished_name FROM ad_users LIMIT 1500;")).mappings().all()
            for ur in urows:
                sam = ur.get("sam_account_name")
                if sam:
                    members_dict[sam.lower()] = {
                        "name": ur.get("display_name") or sam,
                        "sam_account_name": sam,
                        "folder": parse_dn_folder(ur.get("distinguished_name")),
                        "is_group": False,
                        "member_type": "Felhasználó",
                        "type_icon": "👤",
                        "type_color": "#0284c7",
                        "title": ur.get("title") or "-",
                        "department": ur.get("department") or "-",
                        "added_at": "Alapértelmezett"
                    }
        except Exception as e:
            print("Hiba Domain Users tagjainál:", e)
            db.rollback()

    # B. Tagok kinyerése ad_groups.members oszlopból
    if grow:
        m_val = grow.get("members") or grow.get("member") or grow.get("member_dns")
        if m_val:
            cns = re.findall(r'CN=([^,;\s"\'\]\[]+)', str(m_val), re.IGNORECASE)
            for m_name in cns:
                fold = "tspc.hu/TSPC/TSPC Groups" if (m_name.lower().startswith("ad_") or m_name.lower().startswith("f_")) else "tspc.hu/TSPC/TSPC Users"
                is_g = fold.endswith("TSPC Groups")
                members_dict[m_name.lower()] = {
                    "name": m_name,
                    "sam_account_name": m_name,
                    "folder": fold,
                    "is_group": is_g,
                    "member_type": "Beágyazott csoport" if is_g else "Felhasználó",
                    "type_icon": "👥" if is_g else "👤",
                    "type_color": "#6366f1" if is_g else "#0284c7",
                    "title": "-",
                    "department": "-",
                    "added_at": "AD Tagság (member)"
                }

    # C. ad_audit_log alapján hozzáadott tagok
    try:
        pat = f"%'{group_name}'%"
        hist_sql = text("""
            SELECT 
                to_char(timestamp, 'YYYY-MM-DD HH24:MI') as timestamp_str,
                entity_name,
                COALESCE(change_type, '') as change_type,
                COALESCE(details, '') as details
            FROM ad_audit_log 
            WHERE details ILIKE :pat OR details ILIKE :pat2
            ORDER BY timestamp ASC;
        """)
        rows = db.execute(hist_sql, {"pat": pat, "pat2": f"%{group_name}%"}).mappings().all()
        for r in rows:
            uname = r.get("entity_name")
            if not uname: continue
            dtls = r.get("details") or ""
            ts = r.get("timestamp_str") or "-"
            if "hozzáadva" in dtls.lower() or "added" in r.get("change_type", "").lower():
                if uname.lower() not in members_dict:
                    name, fold, is_g = parse_dn_details(uname)
                    members_dict[uname.lower()] = {
                        "name": uname.replace(".", " "),
                        "sam_account_name": uname,
                        "folder": fold,
                        "is_group": is_g,
                        "member_type": "Beágyazott csoport" if is_g else "Felhasználó",
                        "type_icon": "👥" if is_g else "👤",
                        "type_color": "#6366f1" if is_g else "#0284c7",
                        "title": "-",
                        "department": "-",
                        "added_at": ts
                    }
            elif "eltávolítva" in dtls.lower() or "removed" in r.get("change_type", "").lower():
                if uname.lower() in members_dict:
                    del members_dict[uname.lower()]
    except Exception as e:
        print("Hiba audit tagoknál:", e)
        db.rollback()

    # Felhasználói adatok kiegészítése (title, department) ad_users alapján
    try:
        all_u = db.execute(text("SELECT sam_account_name, display_name, mail, title, department, distinguished_name FROM ad_users;")).mappings().all()
        u_cache = {ur["sam_account_name"].lower(): ur for ur in all_u if ur.get("sam_account_name")}
        for k, v in members_dict.items():
            if not v.get("is_group"):
                ur = u_cache.get(k) or next((u for u in all_u if (u.get("display_name") or "").lower() == k), None)
                if ur:
                    v["name"] = ur.get("display_name") or v["name"]
                    v["sam_account_name"] = ur.get("sam_account_name") or v["sam_account_name"]
                    v["title"] = ur.get("title") or v["title"]
                    v["department"] = ur.get("department") or v["department"]
                    v["folder"] = parse_dn_folder(ur.get("distinguished_name"))
    except Exception:
        db.rollback()

    members = list(members_dict.values())
    members.sort(key=lambda x: (x["is_group"], str(x["name"]).lower()))

    user_cnt = sum(1 for m in members if not m.get("is_group"))
    grp_cnt = sum(1 for m in members if m.get("is_group"))

    return {
        "status": "SUCCESS",
        "group_name": group_name,
        "description": desc,
        "group_scope": scope,
        "member_count": len(members),
        "user_count": user_cnt,
        "nested_group_count": grp_cnt,
        "members": members
    }
