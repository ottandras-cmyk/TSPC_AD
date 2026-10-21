import os
import json
import zipfile
import uuid
from datetime import datetime, timezone
from sqlalchemy import text
import models
from config_manager import get_setting
from doc_generator import build_all_docs, DOCS_DIR

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(APP_DIR, ".."))
BACKUP_DIR = os.path.join(APP_DIR, "backups")

def serialize_val(v):
    if v is None: return None
    if isinstance(v, datetime): return v.isoformat()
    if isinstance(v, uuid.UUID): return str(v)
    return v

def generate_sql_insert(table_name, columns, rows):
    if not rows: return f"-- {table_name}: 0 sor\n\n"
    sql = [f"-- {table_name} ({len(rows)} sor)"]
    col_list = ", ".join(f'"{c}"' for c in columns)
    for r in rows:
        vals = []
        for c in columns:
            v = r.get(c)
            if v is None: vals.append("NULL")
            elif isinstance(v, bool): vals.append("TRUE" if v else "FALSE")
            elif isinstance(v, (int, float)): vals.append(str(v))
            else:
                escaped = str(v).replace("'", "''")
                vals.append(f"'{escaped}'")
        sql.append(f"INSERT INTO {table_name} ({col_list}) VALUES ({', '.join(vals)});")
    return "\n".join(sql) + "\n\n"

def create_backup(db, comment: str, user: str) -> dict:
    os.makedirs(BACKUP_DIR, exist_ok=True)
    now_utc = datetime.now(timezone.utc)
    ts_str = now_utc.strftime("%Y%m%d_%H%M%S")
    app_ver = str(get_setting(db, "APP_VERSION", "1.00")).replace("v", "").strip()
    filename = f"backup_{ts_str}_v{app_ver}.zip"
    zip_path = os.path.join(BACKUP_DIR, filename)

    generated_docs = []
    try:
        generated_docs = build_all_docs(db)
    except Exception:
        pass

    tables_data = {}
    sql_parts = ["-- AD TRACKER TELJES ADATBÁZIS MENTÉS\n\n"]
    
    for model_cls, tname in [
        (models.SystemSetting, "app_settings"),
        (models.SyncHistory, "sync_history"),
        (models.ADGroup, "ad_groups"),
        (models.ADUser, "ad_users"),
        (models.ADAuditLog, "ad_audit_log")
    ]:
        cols = [c.name for c in model_cls.__table__.columns]
        rows = [{c: serialize_val(getattr(row, c)) for c in cols} for row in db.query(model_cls).all()]
        tables_data[tname] = {"columns": cols, "rows": rows}
        sql_parts.append(generate_sql_insert(tname, cols, rows))

    raw_m = db.execute(models.group_memberships.select()).fetchall()
    m_rows = [{"user_guid": serialize_val(r[0]), "group_guid": serialize_val(r[1]), "assigned_at": serialize_val(r[2])} for r in raw_m]
    tables_data["ad_group_members"] = {"columns": ["user_guid", "group_guid", "assigned_at"], "rows": m_rows}
    sql_parts.append(generate_sql_insert("ad_group_members", ["user_guid", "group_guid", "assigned_at"], m_rows))

    manifest = {
        "filename": filename,
        "version": app_ver,
        "comment": comment or "Kézi mentés",
        "created_by": user,
        "created_at": now_utc.isoformat(),
        "created_at_formatted": now_utc.strftime("%Y-%m-%d %H:%M:%S"),
        "docs_included": generated_docs
    }

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
        z.writestr("adatbazis/data.json", json.dumps(tables_data, indent=2, ensure_ascii=False))
        z.writestr("adatbazis/dump.sql", "".join(sql_parts))

        for fname in os.listdir(APP_DIR):
            if fname.endswith(".py"):
                z.write(os.path.join(APP_DIR, fname), arcname=f"kod/{fname}")

        req_path = os.path.join(PROJECT_DIR, "requirements.txt")
        if not os.path.isfile(req_path):
            req_path = os.path.join(APP_DIR, "requirements.txt")
        if os.path.isfile(req_path):
            z.write(req_path, arcname="requirements.txt")
            z.write(req_path, arcname="konfig/requirements.txt")

        for cname in ["Dockerfile", "docker-compose.yml", ".gitignore"]:
            for sdir in [PROJECT_DIR, APP_DIR]:
                cp = os.path.join(sdir, cname)
                if os.path.isfile(cp) and f"konfig/{cname}" not in z.namelist():
                    z.write(cp, arcname=f"konfig/{cname}")

        if os.path.isdir(DOCS_DIR):
            for dfile in os.listdir(DOCS_DIR):
                dfpath = os.path.join(DOCS_DIR, dfile)
                if os.path.isfile(dfpath):
                    z.write(dfpath, arcname=f"docs/{dfile}")

    size_kb = round(os.path.getsize(zip_path) / 1024, 1)
    return {"status": "SUCCESS", "filename": filename, "size": f"{size_kb} KB"}

def list_backups() -> list:
    os.makedirs(BACKUP_DIR, exist_ok=True)
    results = []
    for fname in os.listdir(BACKUP_DIR):
        if fname.endswith(".zip"):
            fpath = os.path.join(BACKUP_DIR, fname)
            size_kb = round(os.path.getsize(fpath) / 1024, 1)
            size_str = f"{size_kb} KB" if size_kb < 1024 else f"{round(size_kb/1024, 2)} MB"
            created_at, version, comment, author = "-", "-", "-", "-"
            try:
                with zipfile.ZipFile(fpath, "r") as z:
                    if "manifest.json" in z.namelist():
                        meta = json.loads(z.read("manifest.json").decode("utf-8"))
                        created_at = meta.get("created_at_formatted") or meta.get("created_at", "-")[:19].replace("T", " ")
                        version = f"v{meta.get('version', '-')}"
                        comment = meta.get("comment", "-")
                        author = meta.get("created_by", "-")
            except Exception: pass
            results.append({"filename": fname, "size": size_str, "created_at": created_at, "version": version, "comment": comment, "author": author})
    results.sort(key=lambda x: x["filename"], reverse=True)
    return results

def restore_backup(db, filename: str) -> dict:
    os.makedirs(BACKUP_DIR, exist_ok=True)
    safe_name = os.path.basename(filename)
    fpath = os.path.join(BACKUP_DIR, safe_name)
    if not os.path.isfile(fpath): return {"status": "ERROR", "message": "A mentés nem létezik!"}
    try:
        with zipfile.ZipFile(fpath, "r") as z:
            db_data = json.loads(z.read("adatbazis/data.json").decode("utf-8"))
            db.execute(models.group_memberships.delete())
            db.query(models.ADAuditLog).delete()
            db.query(models.ADUser).delete()
            db.query(models.ADGroup).delete()
            db.query(models.SyncHistory).delete()
            db.query(models.SystemSetting).delete()
            db.flush()

            for r in db_data.get("app_settings", {}).get("rows", []):
                db.add(models.SystemSetting(setting_key=r["setting_key"], setting_value=r["setting_value"], description=r.get("description")))

            for r in db_data.get("sync_history", {}).get("rows", []):
                db.add(models.SyncHistory(id=r["id"], started_at=datetime.fromisoformat(r["started_at"]) if r.get("started_at") else None, ended_at=datetime.fromisoformat(r["ended_at"]) if r.get("ended_at") else None, duration_seconds=r.get("duration_seconds"), trigger_type=r.get("trigger_type"), status=r.get("status"), changes_detected=r.get("changes_detected", 0), error_message=r.get("error_message")))

            for r in db_data.get("ad_groups", {}).get("rows", []):
                db.add(models.ADGroup(
                    object_guid=uuid.UUID(r["object_guid"]),
                    sam_account_name=r["sam_account_name"],
                    distinguished_name=r.get("distinguished_name", ""),
                    description=r.get("description"),
                    group_type=r.get("group_type"),
                    object_sid=r.get("object_sid"),
                    source_type=r.get("source_type", "AD_SYNC"),
                    source_ref=r.get("source_ref", "LIVE_AD"),
                    when_created=datetime.fromisoformat(r["when_created"]) if r.get("when_created") else None,
                    when_changed=datetime.fromisoformat(r["when_changed"]) if r.get("when_changed") else None,
                    last_synced_at=datetime.fromisoformat(r["last_synced_at"]) if r.get("last_synced_at") else None
                ))

            for r in db_data.get("ad_users", {}).get("rows", []):
                db.add(models.ADUser(
                    object_guid=uuid.UUID(r["object_guid"]),
                    sam_account_name=r["sam_account_name"],
                    display_name=r.get("display_name"),
                    mail=r.get("mail"),
                    is_enabled=r.get("is_enabled", True),
                    distinguished_name=r.get("distinguished_name"),
                    first_name=r.get("first_name"),
                    last_name=r.get("last_name"),
                    description=r.get("description"),
                    office=r.get("office"),
                    title=r.get("title"),
                    department=r.get("department"),
                    company=r.get("company"),
                    telephone_number=r.get("telephone_number"),
                    mobile=r.get("mobile"),
                    object_sid=r.get("object_sid"),
                    last_logon_date=datetime.fromisoformat(r["last_logon_date"]) if r.get("last_logon_date") else None,
                    user_status=r.get("user_status"),
                    ou_path=r.get("ou_path"),
                    source_type=r.get("source_type", "AD_SYNC"),
                    source_ref=r.get("source_ref", "LIVE_AD"),
                    when_created=datetime.fromisoformat(r["when_created"]) if r.get("when_created") else None,
                    when_changed=datetime.fromisoformat(r["when_changed"]) if r.get("when_changed") else None,
                    last_synced_at=datetime.fromisoformat(r["last_synced_at"]) if r.get("last_synced_at") else None
                ))
            db.flush()

            for r in db_data.get("ad_group_members", {}).get("rows", []):
                db.execute(models.group_memberships.insert().values(user_guid=uuid.UUID(r["user_guid"]), group_guid=uuid.UUID(r["group_guid"]), assigned_at=datetime.fromisoformat(r["assigned_at"]) if r.get("assigned_at") else None))

            for r in db_data.get("ad_audit_log", {}).get("rows", []):
                db.add(models.ADAuditLog(
                    id=r["id"],
                    timestamp=datetime.fromisoformat(r["timestamp"]) if r.get("timestamp") else None,
                    entity_type=r["entity_type"],
                    entity_name=r["entity_name"],
                    change_type=r["change_type"],
                    details=r.get("details"),
                    raw_diff=r.get("raw_diff"),
                    source_type=r.get("source_type", "AD_SYNC"),
                    source_ref=r.get("source_ref", "LIVE_AD")
                ))

            db.commit()

            try:
                db.execute(text("SELECT setval(pg_get_serial_sequence('ad_audit_log', 'id'), coalesce(max(id), 1), max(id) IS NOT NULL) FROM ad_audit_log;"))
                db.execute(text("SELECT setval(pg_get_serial_sequence('sync_history', 'id'), coalesce(max(id), 1), max(id) IS NOT NULL) FROM sync_history;"))
                db.commit()
            except Exception: pass

        return {"status": "SUCCESS", "message": f"A(z) {safe_name} mentés sikeresen visszaállítva!"}
    except Exception as e:
        db.rollback()
        return {"status": "ERROR", "message": str(e)}

def delete_backup(filename: str) -> dict:
    os.makedirs(BACKUP_DIR, exist_ok=True)
    safe_name = os.path.basename(filename)
    fpath = os.path.join(BACKUP_DIR, safe_name)
    if os.path.isfile(fpath):
        os.remove(fpath)
        return {"status": "SUCCESS", "message": "Törölve."}
    return {"status": "ERROR", "message": "Nem található."}
