import os
import json
import zipfile
import uuid
from datetime import datetime, timezone
from sqlalchemy import text
import models
from config_manager import get_setting

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(APP_DIR, ".."))
BACKUP_DIR = os.path.join(APP_DIR, "backups")

def ensure_backup_dir():
    os.makedirs(BACKUP_DIR, exist_ok=True)

def serialize_val(v):
    if v is None: return None
    if isinstance(v, datetime): return v.isoformat()
    if isinstance(v, uuid.UUID): return str(v)
    return v

def parse_dt(s):
    if not s: return None
    try: return datetime.fromisoformat(s)
    except Exception: return None

def parse_uuid(s):
    if not s: return None
    try: return uuid.UUID(s)
    except Exception: return None

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

# A mentésbe automatikusan bekerülő Skill és Prompt fájlok tartalma
SKILL_CONTENT = """# AD Tracker Rendszer - Átfogó Agent Skill

## Rendszer Célja és Működése
Ez az alkalmazás egy Active Directory szinkronizáló és vizualizációs rendszer, amely naplózza a hozzáférési és jogosultságváltozásokat, és mesterséges intelligenciával (Ollama) elemzi azokat.

## Komponensek és Fájlok:
1. **app/main.py**: FastAPI webes háttérszolgáltatás, útválasztó végpontok (API) és a HTML/JS frontend kezelője.
2. **app/sync_engine.py**: Az élő Active Directory (LDAP) kapcsolat és az inkrementális diff-szinkronizáló (változásészlelő) logika.
3. **app/history_importer.py**: Történeti időgép. PowerShell CSV exportok alapján visszaépíti az audit naplót, és azonnali adatfrissítést (Backfill) is végez.
4. **app/models.py**: PostgreSQL adatbázis sémák SQLAlchemy ORM segítségével (ADUser, ADGroup, ADAuditLog, SyncHistory).
5. **app/backup_manager.py**: Automatikus ZIP alapú rendszermentés, amely csomagolja a forráskódot, a konfigurációkat és a relációs adatbázis tartalmát (JSON és SQL).
6. **app/ai_assistant.py**: Helyi LLM (Ollama) integráció a biztonsági összefoglalók generálásához.
7. **app/github_sync.py**: Rendszerverzió-követés, közvetlen kódpublikálás a távoli repóba.

## Mentés Visszaállítása és Működés:
A letöltött ZIP mentések a webes felületről vagy a szerveren közvetlenül is helyreállíthatók. A visszaállítás mind a PostgreSQL rekordokat, mind az alkalmazás fájljait az adott mentéskori állapotra írja felül.
"""

PROMPT_CONTENT = """Act as a Senior IT Systems and Python Engineer.
You have been provided with the complete local backup of the "AD Tracker" application.

Context:
The application is a Dockerized Python FastAPI backend with a PostgreSQL database, HTML/JS frontend, Active Directory LDAP integration, Ollama AI analysis, and an internal Zip-based backup manager.

Your Instructions:
1. Read the provided source files (`kod/*.py`), the database structure (`adatbazis/data.json` or `dump.sql`), and the configurations (`konfig/`).
2. Implement new features, fix bugs, or answer queries about the system architecture based on these files.
3. When providing code updates, ensure you use the existing SQLAlchemy ORM models, preserve the database schema logic, and follow the established FastAPI patterns.
4. All system text and frontend elements should be maintained in Hungarian.
"""

def create_backup(db, comment: str, user: str) -> dict:
    ensure_backup_dir()
    now_utc = datetime.now(timezone.utc)
    ts_str = now_utc.strftime("%Y%m%d_%H%M%S")
    app_ver = str(get_setting(db, "APP_VERSION", "1.00")).replace("v", "").strip()
    filename = f"backup_{ts_str}_v{app_ver}.zip"
    zip_path = os.path.join(BACKUP_DIR, filename)

    tables_data = {}

    settings_cols = ["setting_key", "setting_value", "description"]
    tables_data["app_settings"] = {
        "columns": settings_cols,
        "rows": [{c: getattr(row, c, None) for c in settings_cols} for row in db.query(models.SystemSetting).all()]
    }

    sync_cols = ["id", "started_at", "ended_at", "duration_seconds", "trigger_type", "status", "changes_detected", "error_message"]
    tables_data["sync_history"] = {
        "columns": sync_cols,
        "rows": [{c: serialize_val(getattr(row, c, None)) for c in sync_cols} for row in db.query(models.SyncHistory).all()]
    }

    group_cols = ["object_guid", "sam_account_name", "distinguished_name", "description", "group_type", "object_sid", "when_created", "when_changed", "last_synced_at"]
    tables_data["ad_groups"] = {
        "columns": group_cols,
        "rows": [{c: serialize_val(getattr(row, c, None)) for c in group_cols} for row in db.query(models.ADGroup).all()]
    }

    user_cols = [
        "object_guid", "sam_account_name", "display_name", "mail", "is_enabled",
        "distinguished_name", "first_name", "last_name", "description", "office",
        "title", "department", "company", "telephone_number", "mobile", "object_sid",
        "when_created", "when_changed", "last_synced_at",
        "last_logon_date", "user_status", "ou_path"
    ]
    user_rows = [{c: serialize_val(getattr(row, c, None)) for c in user_cols} for row in db.query(models.ADUser).all()]
    tables_data["ad_users"] = {"columns": user_cols, "rows": user_rows}

    membership_cols = ["user_guid", "group_guid", "assigned_at"]
    try:
        raw_memberships = db.execute(models.group_memberships.select()).fetchall()
        tables_data["ad_group_members"] = {
            "columns": membership_cols,
            "rows": [{"user_guid": serialize_val(r[0]), "group_guid": serialize_val(r[1]), "assigned_at": serialize_val(r[2])} for r in raw_memberships]
        }
    except Exception:
        tables_data["ad_group_members"] = {"columns": membership_cols, "rows": []}

    audit_cols = ["id", "timestamp", "entity_type", "entity_name", "change_type", "details", "raw_diff"]
    tables_data["ad_audit_log"] = {
        "columns": audit_cols,
        "rows": [{c: serialize_val(getattr(row, c, None)) for c in audit_cols} for row in db.query(models.ADAuditLog).all()]
    }

    sql_parts = ["-- AD TRACKER TELJES ADATBÁZIS MENTÉS\n\n"]
    for tname in ["app_settings", "sync_history", "ad_groups", "ad_users", "ad_group_members", "ad_audit_log"]:
        tinfo = tables_data[tname]
        sql_parts.append(generate_sql_insert(tname, tinfo["columns"], tinfo["rows"]))

    manifest = {
        "filename": filename,
        "version": app_ver,
        "comment": comment or "Automatikus/Kézi mentés (Nincs megjegyzés)",
        "created_by": user,
        "created_at": now_utc.isoformat(),
        "created_at_formatted": now_utc.strftime("%Y-%m-%d %H:%M:%S")
    }

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        # Alap metaadatok és adatbázis
        z.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
        z.writestr("adatbazis/data.json", json.dumps(tables_data, indent=2, ensure_ascii=False))
        z.writestr("adatbazis/dump.sql", "".join(sql_parts))
        
        # ÚJ: Rendszerleíró és Agent Prompt a gyökérkönyvtárba
        z.writestr("rendszer_skill.md", SKILL_CONTENT)
        z.writestr("fejlesztoi_prompt.txt", PROMPT_CONTENT)

        # Forráskód (kod/)
        for fname in os.listdir(APP_DIR):
            if fname.endswith(".py"):
                z.write(os.path.join(APP_DIR, fname), arcname=f"kod/{fname}")

        # Konfigurációk (konfig/)
        for cname in ["Dockerfile", "docker-compose.yml", "requirements.txt", ".env", ".gitignore"]:
            for search_dir in [PROJECT_DIR, APP_DIR]:
                cpath = os.path.join(search_dir, cname)
                if os.path.isfile(cpath) and cname not in [x.filename for x in z.filelist]:
                    z.write(cpath, arcname=f"konfig/{cname}")
                    break

    size_kb = round(os.path.getsize(zip_path) / 1024, 1)
    return {"status": "SUCCESS", "filename": filename, "size": f"{size_kb} KB", "manifest": manifest}

def list_backups() -> list:
    ensure_backup_dir()
    results = []
    for fname in os.listdir(BACKUP_DIR):
        if fname.endswith(".zip"):
            fpath = os.path.join(BACKUP_DIR, fname)
            size_kb = round(os.path.getsize(fpath) / 1024, 1)
            size_str = f"{size_kb} KB" if size_kb < 1024 else f"{round(size_kb/1024, 2)} MB"
            created_at = "-"
            version = "-"
            comment = "-"
            author = "-"

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
    ensure_backup_dir()
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
                db.add(models.SyncHistory(id=r["id"], started_at=parse_dt(r["started_at"]), ended_at=parse_dt(r["ended_at"]), duration_seconds=r.get("duration_seconds"), trigger_type=r.get("trigger_type"), status=r.get("status"), changes_detected=r.get("changes_detected", 0), error_message=r.get("error_message")))

            for r in db_data.get("ad_groups", {}).get("rows", []):
                db.add(models.ADGroup(object_guid=parse_uuid(r["object_guid"]), sam_account_name=r["sam_account_name"], distinguished_name=r.get("distinguished_name", ""), description=r.get("description"), group_type=r.get("group_type"), object_sid=r.get("object_sid"), when_created=parse_dt(r.get("when_created")), when_changed=parse_dt(r.get("when_changed")), last_synced_at=parse_dt(r.get("last_synced_at"))))

            for r in db_data.get("ad_users", {}).get("rows", []):
                db.add(models.ADUser(
                    object_guid=parse_uuid(r["object_guid"]),
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
                    last_logon_date=parse_dt(r.get("last_logon_date")),
                    user_status=r.get("user_status"),
                    ou_path=r.get("ou_path"),
                    when_created=parse_dt(r.get("when_created")),
                    when_changed=parse_dt(r.get("when_changed")),
                    last_synced_at=parse_dt(r.get("last_synced_at"))
                ))

            db.flush()
            for r in db_data.get("ad_group_members", {}).get("rows", []):
                db.execute(models.group_memberships.insert().values(user_guid=parse_uuid(r["user_guid"]), group_guid=parse_uuid(r["group_guid"]), assigned_at=parse_dt(r.get("assigned_at"))))

            for r in db_data.get("ad_audit_log", {}).get("rows", []):
                db.add(models.ADAuditLog(id=r["id"], timestamp=parse_dt(r["timestamp"]), entity_type=r["entity_type"], entity_name=r["entity_name"], change_type=r["change_type"], details=r.get("details"), raw_diff=r.get("raw_diff")))

            db.commit()

            try:
                db.execute(text("SELECT setval(pg_get_serial_sequence('ad_audit_log', 'id'), coalesce(max(id), 1), max(id) IS NOT NULL) FROM ad_audit_log;"))
                db.execute(text("SELECT setval(pg_get_serial_sequence('sync_history', 'id'), coalesce(max(id), 1), max(id) IS NOT NULL) FROM sync_history;"))
                db.commit()
            except Exception: pass

            for member in z.namelist():
                if member.startswith("kod/") and member.endswith(".py"):
                    with open(os.path.join(APP_DIR, os.path.basename(member)), "wb") as f_out:
                        f_out.write(z.read(member))
                elif member.startswith("konfig/"):
                    target = os.path.join(PROJECT_DIR, os.path.basename(member)) if os.path.isdir(PROJECT_DIR) else os.path.join(APP_DIR, os.path.basename(member))
                    with open(target, "wb") as f_out:
                        f_out.write(z.read(member))

        return {"status": "SUCCESS", "message": f"A(z) {safe_name} mentés sikeresen visszaállítva!"}
    except Exception as e:
        db.rollback()
        return {"status": "ERROR", "message": str(e)}

def delete_backup(filename: str) -> dict:
    ensure_backup_dir()
    safe_name = os.path.basename(filename)
    fpath = os.path.join(BACKUP_DIR, safe_name)
    if os.path.isfile(fpath):
        os.remove(fpath)
        return {"status": "SUCCESS", "message": "Törölve."}
    return {"status": "ERROR", "message": "Nem található."}
