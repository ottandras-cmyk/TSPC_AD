import os
import json
import zipfile
from datetime import datetime, timezone
from sqlalchemy import text
from config_manager import get_setting, update_setting

CURR_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURR_DIR)

if os.path.exists(os.path.join(PARENT_DIR, "docker-compose.yml")) or os.path.exists(os.path.join(PARENT_DIR, ".git")):
    BASE_DIR = PARENT_DIR
    APP_DIR = os.path.join(BASE_DIR, "app")
    DOCS_DIR = os.path.join(BASE_DIR, "docs")
    BACKUP_DIR = os.path.join(BASE_DIR, "backups")
else:
    BASE_DIR = CURR_DIR
    APP_DIR = CURR_DIR
    DOCS_DIR = os.path.join(CURR_DIR, "docs")
    BACKUP_DIR = os.path.join(CURR_DIR, "backups")

EXPORTS_DIR = os.path.join(BACKUP_DIR, "exports")
os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(DOCS_DIR, exist_ok=True)
os.makedirs(EXPORTS_DIR, exist_ok=True)

TABLES_TO_DUMP = [
    "app_settings", "ad_users", "ad_groups", "ad_group_members",
    "ad_audit_log", "sync_history", "web_access_log",
    "system_telemetry", "host_ip_history", "active_web_sessions"
]

EXCLUDED_DIRS = {"__pycache__", ".git", "venv", ".pytest_cache", "backups", "exports", ".idea", ".vscode"}

def get_all_settings_dict(db) -> dict:
    try:
        import models
        for attr in ["AppSetting", "AppSettings", "Setting", "Config"]:
            if hasattr(models, attr):
                cls = getattr(models, attr)
                records = db.query(cls).all()
                if records:
                    res = {}
                    for rec in records:
                        k = getattr(rec, "setting_key", None) or getattr(rec, "key", None) or getattr(rec, "name", None)
                        v = getattr(rec, "setting_value", None) or getattr(rec, "value", None) or getattr(rec, "val", None)
                        if k is not None:
                            res[str(k)] = str(v) if v is not None else ""
                    if res: return res
    except Exception: pass

    try:
        res = db.execute(text("SELECT * FROM app_settings;"))
        cols = [c.lower() for c in res.keys()]
        rows = res.fetchall()
        key_idx = next((i for i, c in enumerate(cols) if "key" in c or "name" in c), 0)
        val_idx = next((i for i, c in enumerate(cols) if "val" in c), 1 if len(cols) > 1 else 0)
        return {str(r[key_idx]): str(r[val_idx]) if r[val_idx] is not None else "" for r in rows}
    except Exception: return {}

def generate_database_sql_dump(db) -> tuple:
    stats = {}
    lines = [
        "-- ========================================================",
        "-- AD Tracker PostgreSQL Adatbázis Dump",
        f"-- Generálva: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "-- ========================================================",
        "BEGIN;",
        ""
    ]
    for tbl in TABLES_TO_DUMP:
        try:
            res = db.execute(text(f"SELECT * FROM {tbl};"))
            col_names = list(res.keys())
            rows = res.fetchall()
            stats[tbl] = len(rows)
            lines.append(f"-- Tábla: {tbl} ({len(rows)} rekord)")
            for r in rows:
                val_strs = []
                for v in r:
                    if v is None:
                        val_strs.append("NULL")
                    elif isinstance(v, bool):
                        val_strs.append("TRUE" if v else "FALSE")
                    elif isinstance(v, (int, float)):
                        val_strs.append(str(v))
                    elif isinstance(v, bytes):
                        try:
                            clean_str = v.decode('utf-8', errors='ignore').replace("'", "''")
                            val_strs.append("'" + clean_str + "'")
                        except Exception:
                            val_strs.append("NULL")
                    else:
                        esc = str(v).replace("'", "''")
                        val_strs.append("'" + esc + "'")
                col_part = ", ".join(f'"{c}"' for c in col_names)
                val_part = ", ".join(val_strs)
                lines.append(f"INSERT INTO {tbl} ({col_part}) VALUES ({val_part}) ON CONFLICT DO NOTHING;")
            lines.append("")
        except Exception as e:
            lines.append(f"-- Hiba a(z) {tbl} táblánál: {str(e)}\n")
    lines.append("COMMIT;")
    return "\n".join(lines), stats

def export_codebase_zip() -> tuple:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    fname = f"ad_tracker_codebase_{ts}.zip"
    fpath = os.path.join(EXPORTS_DIR, fname)
    with zipfile.ZipFile(fpath, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(APP_DIR):
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
            for file in files:
                if file.endswith((".pyc", ".pyo", ".DS_Store")): continue
                full_p = os.path.join(root, file)
                rel_p = os.path.relpath(full_p, BASE_DIR)
                zf.write(full_p, rel_p)
    return fpath, fname

def export_docs_zip() -> tuple:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    fname = f"ad_tracker_documentation_{ts}.zip"
    fpath = os.path.join(EXPORTS_DIR, fname)
    with zipfile.ZipFile(fpath, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(DOCS_DIR):
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
            for file in files:
                full_p = os.path.join(root, file)
                rel_p = os.path.relpath(full_p, BASE_DIR)
                zf.write(full_p, rel_p)
    return fpath, fname

def export_config_json_file(db) -> tuple:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    fname = f"ad_tracker_config_{ts}.json"
    fpath = os.path.join(EXPORTS_DIR, fname)
    cfg = get_all_settings_dict(db)
    data = {
        "exported_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "version": get_setting(db, "APP_VERSION", "1.00"),
        "settings": cfg
    }
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return fpath, fname

def export_database_sql_file(db) -> tuple:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    fname = f"ad_tracker_database_{ts}.sql"
    fpath = os.path.join(EXPORTS_DIR, fname)
    sql_dump, _ = generate_database_sql_dump(db)
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(sql_dump)
    return fpath, fname

def create_backup(db, comment: str = "", user: str = "Rendszer") -> dict:
    try:
        from doc_generator import build_all_docs
        build_all_docs(db)
    except Exception: pass

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    version = get_setting(db, "APP_VERSION", "1.00")
    fname = f"ad_tracker_full_backup_v{version}_{ts}.zip"
    fpath = os.path.join(BACKUP_DIR, fname)

    meta = {
        "version": version,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "author": user,
        "comment": comment
    }

    try:
        with zipfile.ZipFile(fpath, "w", zipfile.ZIP_DEFLATED) as zf:
            # 1. Adatbázis dump és tételes statisztika
            sql_dump, stats = generate_database_sql_dump(db)
            meta["record_counts"] = stats
            zf.writestr("metadata.json", json.dumps(meta, ensure_ascii=False, indent=2))
            zf.writestr("database_dump.sql", sql_dump)

            # 2. Beállítások
            cfg = get_all_settings_dict(db)
            zf.writestr("config.json", json.dumps(cfg, ensure_ascii=False, indent=2))

            # 3. Kódbázis
            for root, dirs, files in os.walk(APP_DIR):
                dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
                for file in files:
                    if file.endswith((".pyc", ".pyo", ".DS_Store")): continue
                    full_p = os.path.join(root, file)
                    rel_p = os.path.relpath(full_p, BASE_DIR)
                    zf.write(full_p, rel_p)

            # 4. Dokumentáció
            if os.path.isdir(DOCS_DIR):
                for root, dirs, files in os.walk(DOCS_DIR):
                    dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
                    for file in files:
                        full_p = os.path.join(root, file)
                        rel_p = os.path.relpath(full_p, BASE_DIR)
                        zf.write(full_p, rel_p)

            # 5. Történeti nyers CSV mentések beemelése
            csv_dir = os.path.join(BASE_DIR, "csv_imports")
            if not os.path.isdir(csv_dir):
                csv_dir = os.path.join(APP_DIR, "csv_imports")
            if os.path.isdir(csv_dir):
                for root, dirs, files in os.walk(csv_dir):
                    dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
                    for file in files:
                        if file.lower().endswith(".csv"):
                            full_p = os.path.join(root, file)
                            rel_p = os.path.relpath(full_p, BASE_DIR)
                            zf.write(full_p, rel_p)

        file_size_mb = os.path.getsize(fpath) / (1024 * 1024)
        return {
            "status": "SUCCESS",
            "filename": fname,
            "size": f"{file_size_mb:.2f} MB",
            "stats": stats
        }
    except Exception as e:
        if os.path.exists(fpath):
            try: os.remove(fpath)
            except Exception: pass
        return {"status": "ERROR", "message": f"Hiba a mentés elkészítésekor: {str(e)}"}

def list_backups() -> list:
    results = []
    if not os.path.isdir(BACKUP_DIR): return results
    for fn in sorted(os.listdir(BACKUP_DIR), reverse=True):
        if fn.endswith(".zip") and not fn.startswith("."):
            fp = os.path.join(BACKUP_DIR, fn)
            sz = f"{os.path.getsize(fp) / (1024*1024):.2f} MB"
            meta = {"version": "1.00", "created_at": "-", "author": "Rendszer", "comment": ""}
            try:
                with zipfile.ZipFile(fp, "r") as z:
                    if "metadata.json" in z.namelist():
                        meta = json.loads(z.read("metadata.json").decode("utf-8"))
            except Exception: pass
            results.append({
                "filename": fn,
                "size": sz,
                "version": meta.get("version", "1.00"),
                "created_at": meta.get("created_at", "-"),
                "author": meta.get("author", "Rendszer"),
                "comment": meta.get("comment", "")
            })
    return results

def restore_backup(db, filename: str) -> dict:
    safe_name = os.path.basename(filename)
    fpath = os.path.join(BACKUP_DIR, safe_name)
    if not os.path.isfile(fpath):
        return {"status": "ERROR", "message": "Mentési fájl nem található!"}
    try:
        with zipfile.ZipFile(fpath, "r") as zf:
            if "database_dump.sql" in zf.namelist():
                sql_content = zf.read("database_dump.sql").decode("utf-8")
                db.execute(text(sql_content))
                db.commit()
            if "config.json" in zf.namelist():
                cfg_data = json.loads(zf.read("config.json").decode("utf-8"))
                for k, v in cfg_data.items():
                    if v is not None:
                        update_setting(db, k, str(v))
        return {"status": "SUCCESS", "message": f"{safe_name} visszaállítása sikeres!"}
    except Exception as e:
        db.rollback()
        return {"status": "ERROR", "message": str(e)}

def delete_backup(filename: str) -> dict:
    safe_name = os.path.basename(filename)
    fpath = os.path.join(BACKUP_DIR, safe_name)
    if os.path.isfile(fpath):
        os.remove(fpath)
        return {"status": "SUCCESS", "message": f"{safe_name} törölve."}
    return {"status": "ERROR", "message": "Fájl nem található."}
