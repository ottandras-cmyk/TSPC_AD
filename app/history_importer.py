import os
import re
import csv
import uuid
from datetime import datetime, timezone
import models

def parse_ad_datetime(val):
    if not val:
        return None
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    s = str(val).strip()
    if not s or s in ["Nincs adat", "None", "NULL"]:
        return None
    m = re.match(r'^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})', s)
    if m:
        try:
            p = [int(x) for x in m.groups()]
            return datetime(p[0], p[1], p[2], p[3], p[4], p[5], tzinfo=timezone.utc)
        except Exception:
            pass
    for fmt in ("%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y%m%d_%H%M%S", "%Y%m%d-%H%M%S"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except Exception:
            continue
    return None

def extract_ou_path(dn: str) -> str:
    if not dn: return ""
    ou_matches = re.findall(r'OU=([^,]+)', dn, re.IGNORECASE)
    return ";".join(ou_matches)

def read_csv_lines_safe(file_path):
    encodings = ["utf-8-sig", "utf-8", "cp1250", "iso-8859-2"]
    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc) as f:
                reader = csv.reader(f, delimiter=";")
                rows = list(reader)
                if rows: return rows
        except Exception:
            continue
    return []

def scan_csv_directory(folder_path: str) -> dict:
    if not os.path.isabs(folder_path):
        folder_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), folder_path)
    
    if not os.path.isdir(folder_path):
        return {"status": "ERROR", "message": f"A megadott mappa nem létezik: {folder_path}"}

    snapshots = {}
    time_regex = re.compile(r"(\d{8}[-_]\d{6})")

    for fname in os.listdir(folder_path):
        if not fname.lower().endswith(".csv"): continue
        match = time_regex.search(fname)
        if not match: continue

        ts_str = match.group(1).replace("-", "_")
        if ts_str not in snapshots:
            dt = parse_ad_datetime(ts_str)
            snapshots[ts_str] = {
                "timestamp_str": ts_str,
                "datetime": dt.strftime("%Y-%m-%d %H:%M:%S") if dt else ts_str,
                "dt_obj": dt or datetime.min.replace(tzinfo=timezone.utc),
                "user_files": [],
                "group_files": [],
                "alluser_files": []
            }

        full_p = os.path.join(folder_path, fname)
        lower_name = fname.lower()
        if "group_" in lower_name or lower_name.startswith("groups"):
            snapshots[ts_str]["group_files"].append(full_p)
        elif lower_name.startswith("alluser"):
            snapshots[ts_str]["alluser_files"].append(full_p)
        else:
            snapshots[ts_str]["user_files"].append(full_p)

    sorted_snapshots = sorted(snapshots.values(), key=lambda s: s["dt_obj"])
    clean_list = []
    for s in sorted_snapshots:
        clean_list.append({
            "timestamp": s["timestamp_str"],
            "datetime": s["datetime"],
            "user_files_count": len(s["user_files"]),
            "has_groups": len(s["group_files"]) > 0,
            "has_alluser": len(s["alluser_files"]) > 0,
            "total_files": len(s["user_files"]) + len(s["group_files"]) + len(s["alluser_files"])
        })

    return {
        "status": "SUCCESS",
        "folder": folder_path,
        "total_snapshots": len(clean_list),
        "snapshots": clean_list,
        "_raw_data": sorted_snapshots
    }

KNOWN_STATUS_WORDS = {
    "alapadat", "aktív normál user", "aktiv normal user",
    "hosszútávúszabadság", "hosszutavuszabadsag",
    "külsös", "kulsos", "távozottak", "tavozottak",
    "engedélyezve", "letiltva", "enabled", "disabled"
}

def parse_snapshot_state(snapshot_item: dict) -> dict:
    users = {}
    groups = {}

    # Groups_*.csv -> Név, Típus, Létrehozás ideje, Leírás
    for gf in snapshot_item["group_files"]:
        rows = read_csv_lines_safe(gf)
        if len(rows) <= 1: continue
        for row in rows[1:]:
            if not row or len(row) < 2: continue
            g_name = row[0].strip()
            if not g_name or g_name.lower() in KNOWN_STATUS_WORDS: continue
            groups[g_name.lower()] = {
                "name": g_name,
                "type": row[1].strip() if len(row) > 1 else "Security Group",
                "created": parse_ad_datetime(row[2]) if len(row) > 2 else None,
                "description": row[3].strip() if len(row) > 3 else ""
            }

    # alluser*.csv
    alluser_map = {}
    for af in snapshot_item["alluser_files"]:
        rows = read_csv_lines_safe(af)
        if len(rows) <= 1: continue
        for row in rows[1:]:
            if not row or len(row) < 2: continue
            sam = row[0].strip()
            if not sam: continue
            alluser_map[sam.lower()] = {
                "title": row[2].strip() if len(row) > 2 else "",
                "department": row[3].strip() if len(row) > 3 else "",
                "ou": row[6].strip() if len(row) > 6 else ""
            }

    # *Users_*.csv
    for uf in snapshot_item["user_files"]:
        rows = read_csv_lines_safe(uf)
        if len(rows) <= 1: continue
        for row in rows[1:]:
            if not row or len(row) < 2: continue
            name = row[0].strip()
            sam = row[1].strip()
            if not sam: continue
            sam_key = sam.lower()

            email = row[2].strip() if len(row) > 2 else ""
            phone = row[3].strip() if len(row) > 3 else ""
            sid = row[4].strip() if len(row) > 4 else ""
            c_date = parse_ad_datetime(row[5]) if len(row) > 5 else None
            last_logon = parse_ad_datetime(row[6]) if len(row) > 6 else None
            enabled_str = row[7].strip() if len(row) > 7 else "Engedélyezve"
            is_enabled = (enabled_str.lower() != "letiltva")

            if len(row) >= 11:
                grp_type = row[8].strip()
                grp_name = row[9].strip()
                user_status = row[10].strip()
            elif len(row) == 10:
                grp_type = ""
                grp_name = row[8].strip()
                user_status = row[9].strip()
            else:
                grp_type = ""
                grp_name = ""
                user_status = "Aktív normál user"

            if grp_name.lower() in KNOWN_STATUS_WORDS:
                if user_status == "Aktív normál user" or not user_status:
                    user_status = grp_name
                grp_name = ""

            extra = alluser_map.get(sam_key, {})
            ou_val = extra.get("ou", "")

            if sam_key not in users:
                users[sam_key] = {
                    "name": name,
                    "sam": sam,
                    "mail": email,
                    "phone": phone,
                    "sid": sid,
                    "created": c_date,
                    "last_logon": last_logon,
                    "enabled": is_enabled,
                    "status": user_status,
                    "title": extra.get("title", ""),
                    "department": extra.get("department", ""),
                    "ou_path": ou_val,
                    "groups": set()
                }
            else:
                if c_date and not users[sam_key]["created"]:
                    users[sam_key]["created"] = c_date
                if last_logon and not users[sam_key]["last_logon"]:
                    users[sam_key]["last_logon"] = last_logon
                if user_status != "AlapAdat":
                    users[sam_key]["status"] = user_status
                if ou_val and not users[sam_key]["ou_path"]:
                    users[sam_key]["ou_path"] = ou_val

            if grp_name and grp_name.lower() not in KNOWN_STATUS_WORDS:
                users[sam_key]["groups"].add(grp_name)
                if grp_name.lower() not in groups:
                    groups[grp_name.lower()] = {
                        "name": grp_name,
                        "type": grp_type or "Security Group",
                        "created": None,
                        "description": ""
                    }

    return {"users": users, "groups": groups, "timestamp": snapshot_item["dt_obj"]}

def fast_backfill_extra_data(db, folder_path: str) -> dict:
    """Gyorsan beolvassa a CSV-kből a CreationDate, Description, LastLogon, Status, OU mezőket és frissíti a meglévő rekordokat"""
    scan_res = scan_csv_directory(folder_path)
    if scan_res.get("status") == "ERROR": return scan_res

    snapshots = scan_res.get("_raw_data", [])
    if not snapshots: return {"status": "ERROR", "message": "Nincs CSV fájl a mappában."}

    user_extras = {}
    group_extras = {}

    for snap in snapshots:
        state = parse_snapshot_state(snap)
        for sam_key, u in state["users"].items():
            if sam_key not in user_extras:
                user_extras[sam_key] = {
                    "created": u.get("created"),
                    "last_logon": u.get("last_logon"),
                    "status": u.get("status"),
                    "ou_path": u.get("ou_path")
                }
            else:
                if not user_extras[sam_key]["created"] and u.get("created"):
                    user_extras[sam_key]["created"] = u.get("created")
                if u.get("last_logon"):
                    user_extras[sam_key]["last_logon"] = u.get("last_logon")
                if u.get("status") != "AlapAdat":
                    user_extras[sam_key]["status"] = u.get("status")
                if u.get("ou_path"):
                    user_extras[sam_key]["ou_path"] = u.get("ou_path")

        for g_key, g in state["groups"].items():
            if g_key not in group_extras:
                group_extras[g_key] = {
                    "created": g.get("created"),
                    "description": g.get("description"),
                    "type": g.get("type")
                }
            else:
                if not group_extras[g_key]["created"] and g.get("created"):
                    group_extras[g_key]["created"] = g.get("created")
                if g.get("description"):
                    group_extras[g_key]["description"] = g.get("description")
                if g.get("type"):
                    group_extras[g_key]["type"] = g.get("type")

    # 1. Felhasználók frissítése
    db_users = db.query(models.ADUser).all()
    updated_users = 0
    for db_u in db_users:
        sam_k = db_u.sam_account_name.lower()
        extra = user_extras.get(sam_k)
        if extra:
            if extra.get("created"): db_u.when_created = extra["created"]
            if extra.get("last_logon"): db_u.last_logon_date = extra["last_logon"]
            if extra.get("status") and extra["status"] != "AlapAdat": db_u.user_status = extra["status"]
            if extra.get("ou_path"): db_u.ou_path = extra["ou_path"]
            updated_users += 1

    # 2. Csoportok frissítése
    db_groups = db.query(models.ADGroup).all()
    updated_groups = 0
    for db_g in db_groups:
        g_k = db_g.sam_account_name.lower()
        g_extra = group_extras.get(g_k)
        if g_extra:
            if g_extra.get("created"): db_g.when_created = g_extra["created"]
            if g_extra.get("description"): db_g.description = g_extra["description"]
            if g_extra.get("type"): db_g.group_type = g_extra["type"]
            updated_groups += 1

    db.commit()
    return {
        "status": "SUCCESS",
        "message": f"Sikeres frissítés! {updated_users} db felhasználó (Valós létrehozási idő, utolsó belépés, OU) és {updated_groups} db csoport (Létrehozási idő, leírás) frissítve az adatbázisban!"
    }

def run_historical_replay(db, folder_path: str, progress_callback=None) -> dict:
    scan_res = scan_csv_directory(folder_path)
    if scan_res.get("status") == "ERROR": return scan_res

    snapshots = scan_res.get("_raw_data", [])
    if not snapshots: return {"status": "ERROR", "message": "Nem található feldolgozható CSV fájl!"}

    total_snaps = len(snapshots)
    total_events_logged = 0

    prev_users = {}
    prev_groups = {}
    db_groups_cache = {g.sam_account_name.lower(): g for g in db.query(models.ADGroup).all()}
    db_users_cache = {u.sam_account_name.lower(): u for u in db.query(models.ADUser).all()}

    for idx, snap in enumerate(snapshots):
        ts = snap["dt_obj"]
        ts_str = snap["datetime"]
        if progress_callback: progress_callback(idx + 1, total_snaps, ts_str)

        current_state = parse_snapshot_state(snap)
        curr_users = current_state["users"]
        curr_groups = current_state["groups"]
        snap_events = 0

        # Csoportok
        for g_key, g_info in curr_groups.items():
            if g_key not in db_groups_cache:
                new_grp = models.ADGroup(
                    object_guid=uuid.uuid4(),
                    sam_account_name=g_info["name"],
                    distinguished_name=f"CN={g_info['name']}",
                    description=g_info["description"],
                    group_type=g_info["type"],
                    when_created=g_info["created"] or ts,
                    when_changed=ts,
                    last_synced_at=ts
                )
                db.add(new_grp)
                db.flush()
                db_groups_cache[g_key] = new_grp
                if idx > 0:
                    db.add(models.ADAuditLog(
                        timestamp=ts, entity_type="GROUP", entity_name=g_info["name"],
                        change_type="GROUP_CREATED", details=f"Új AD csoport detektálva ({g_info['type']})",
                        raw_diff=None
                    ))
                    snap_events += 1
            else:
                grp_obj = db_groups_cache[g_key]
                if g_info.get("created"): grp_obj.when_created = g_info["created"]
                if g_info.get("description"): grp_obj.description = g_info["description"]
                if g_info.get("type"): grp_obj.group_type = g_info["type"]

        # Felhasználók
        for u_key, u_info in curr_users.items():
            db_user = db_users_cache.get(u_key)
            final_status = u_info["status"] if u_info["status"] != "AlapAdat" else ("Aktív normál user" if u_info["enabled"] else "Letiltva")
            ou_val = u_info["ou_path"] or extract_ou_path(u_info.get("name", ""))

            if not db_user:
                db_user = models.ADUser(
                    object_guid=uuid.uuid4(),
                    sam_account_name=u_info["sam"],
                    display_name=u_info["name"],
                    mail=u_info["mail"],
                    telephone_number=u_info["phone"],
                    object_sid=u_info["sid"],
                    is_enabled=u_info["enabled"],
                    description=u_info["status"] if u_info["status"] != "AlapAdat" else "",
                    title=u_info["title"],
                    department=u_info["department"],
                    last_logon_date=u_info.get("last_logon"),
                    user_status=final_status,
                    ou_path=ou_val,
                    when_created=u_info["created"] or ts,
                    when_changed=ts,
                    last_synced_at=ts
                )
                db.add(db_user)
                db.flush()
                db_users_cache[u_key] = db_user

                if idx > 0:
                    db.add(models.ADAuditLog(
                        timestamp=ts, entity_type="USER", entity_name=u_info["sam"],
                        change_type="USER_CREATED", details=f"Új fiók azonosítva ({u_info['name']})",
                        raw_diff=None
                    ))
                    snap_events += 1
            else:
                if u_info.get("created"): db_user.when_created = u_info["created"]
                db_user.display_name = u_info["name"] or db_user.display_name
                if u_info["mail"]: db_user.mail = u_info["mail"]
                if u_info["phone"]: db_user.telephone_number = u_info["phone"]
                if u_info["sid"]: db_user.object_sid = u_info["sid"]
                if u_info["title"]: db_user.title = u_info["title"]
                if u_info["department"]: db_user.department = u_info["department"]
                if u_info.get("last_logon"): db_user.last_logon_date = u_info["last_logon"]
                if final_status: db_user.user_status = final_status
                if ou_val: db_user.ou_path = ou_val
                db_user.when_changed = ts
                db_user.last_synced_at = ts

            if idx > 0 and u_key in prev_users:
                p_user = prev_users[u_key]
                if p_user["enabled"] and not u_info["enabled"]:
                    db_user.is_enabled = False
                    db.add(models.ADAuditLog(
                        timestamp=ts, entity_type="USER", entity_name=u_info["sam"],
                        change_type="USER_DISABLED", details="Fiók inaktiválva / letiltva",
                        raw_diff=None
                    ))
                    snap_events += 1
                elif not p_user["enabled"] and u_info["enabled"]:
                    db_user.is_enabled = True
                    db.add(models.ADAuditLog(
                        timestamp=ts, entity_type="USER", entity_name=u_info["sam"],
                        change_type="USER_ENABLED", details="Fiók újraaktiválva",
                        raw_diff=None
                    ))
                    snap_events += 1

                if p_user["status"] != u_info["status"] and u_info["status"] != "AlapAdat":
                    db.add(models.ADAuditLog(
                        timestamp=ts, entity_type="USER", entity_name=u_info["sam"],
                        change_type="STATUS_CHANGED",
                        details=f"Besorolás változott: '{p_user['status']}' -> '{u_info['status']}'",
                        raw_diff=None
                    ))
                    snap_events += 1

                added_grps = u_info["groups"] - p_user["groups"]
                for ag in added_grps:
                    grp_obj = db_groups_cache.get(ag.lower())
                    if grp_obj and grp_obj not in db_user.groups:
                        db_user.groups.append(grp_obj)
                    db.add(models.ADAuditLog(
                        timestamp=ts, entity_type="MEMBERSHIP", entity_name=u_info["sam"],
                        change_type="ADDED_TO_GROUP", details=f"Hozzáadva: '{ag}'",
                        raw_diff=None
                    ))
                    snap_events += 1

                removed_grps = p_user["groups"] - u_info["groups"]
                for rg in removed_grps:
                    grp_obj = db_groups_cache.get(rg.lower())
                    if grp_obj and grp_obj in db_user.groups:
                        db_user.groups.remove(grp_obj)
                    db.add(models.ADAuditLog(
                        timestamp=ts, entity_type="MEMBERSHIP", entity_name=u_info["sam"],
                        change_type="REMOVED_FROM_GROUP", details=f"Eltávolítva: '{rg}'",
                        raw_diff=None
                    ))
                    snap_events += 1
            else:
                for g_name in u_info["groups"]:
                    grp_obj = db_groups_cache.get(g_name.lower())
                    if grp_obj and grp_obj not in db_user.groups:
                        db_user.groups.append(grp_obj)

        if idx == 0:
            db.add(models.ADAuditLog(
                timestamp=ts, entity_type="SYSTEM", entity_name="IMPORT",
                change_type="BASELINE_ESTABLISHED",
                details=f"Alapállapot: {len(curr_users)} fiók és {len(curr_groups)} csoport",
                raw_diff=None
            ))
            snap_events += 1

        db.add(models.SyncHistory(
            started_at=ts, ended_at=ts, duration_seconds=1,
            trigger_type="Történeti CSV import", status="SIKERES",
            changes_detected=snap_events, error_message=""
        ))
        db.commit()
        total_events_logged += snap_events
        prev_users = curr_users
        prev_groups = curr_groups

    return {
        "status": "SUCCESS",
        "processed_snapshots": total_snaps,
        "total_events_logged": total_events_logged,
        "first_snapshot": snapshots[0]["datetime"],
        "last_snapshot": snapshots[-1]["datetime"]
    }
