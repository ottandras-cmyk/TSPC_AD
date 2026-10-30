import os
import time
import shutil
import tarfile
from datetime import datetime

class BackupService:
    def __init__(self, db = None):
        self.db = db

    @staticmethod
    def get_backup_directory() -> str:
        for d in ["/app/backups", "app/backups", "backups"]:
            if os.path.exists(d): return d
        os.makedirs("backups", exist_ok=True)
        return "backups"

    def list_backups(self, db = None) -> dict:
        bdir = self.get_backup_directory()
        files = [f for f in os.listdir(bdir) if f.endswith((".tar.gz", ".sql.gz", ".zip"))]
        files.sort(key=lambda x: os.path.getmtime(os.path.join(bdir, x)), reverse=True)

        backups = []
        total_bytes = 0
        for f in files:
            fp = os.path.join(bdir, f)
            st = os.stat(fp)
            total_bytes += st.st_size
            sz_mb = round(st.st_size / (1024 * 1024), 2)
            sz_str = f"{sz_mb} MB" if sz_mb >= 0.05 else f"{round(st.st_size / 1024, 1)} KB"
            mtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime))

            desc = "Teljes Rendszermentés (DB Séma + Adatok + Doksi + Forráskód)"
            if "snapshot" in f: desc = "Restart előtti automatikus snapshot"

            backups.append({
                "filename": f,
                "name": f,
                "date": mtime,
                "created_at": mtime,
                "size": sz_str,
                "size_mb": sz_mb,
                "size_bytes": st.st_size,
                "comment": desc,
                "description": desc
            })

        total_mb = round(total_bytes / (1024 * 1024), 2)
        last_date = backups[0]["date"] if backups else "--"

        return {
            "status": "SUCCESS",
            "backups": backups,
            "data": backups,
            "count": len(backups),
            "total_size_mb": total_mb,
            "last_backup": last_date
        }

    def list_all_backups(self, db = None) -> dict:
        return self.list_backups(db)

    def create_backup(self, db = None, comment: str = "", user: str = "tadmin") -> dict:
        try:
            bdir = self.get_backup_directory()
            os.makedirs(bdir, exist_ok=True)

            ts = time.strftime("%Y%m%d_%H%M%S")
            display_time = time.strftime("%Y-%m-%d %H:%M:%S")
            version = "v1.26"

            # 1. AI kódállomány dossziék frissítése a mentés előtt
            try:
                from ai_bundle_generator import generate_both_ai_bundles
                for base in [os.getcwd(), "/app", os.path.dirname(os.path.abspath(__file__))]:
                    if os.path.exists(os.path.join(base, "docs")):
                        generate_both_ai_bundles(base)
                        break
            except Exception:
                pass

            stage = f"/tmp/backup_ad_tracker_full_{version}_{ts}"
            os.makedirs(f"{stage}/database", exist_ok=True)
            os.makedirs(f"{stage}/docs", exist_ok=True)
            os.makedirs(f"{stage}/config", exist_ok=True)
            os.makedirs(f"{stage}/source", exist_ok=True)

            # 2. Adatbázis dumpok bemásolása
            for s_path in ["app/db_dump/schema.sql", "/app/db_dump/schema.sql", "db_dump/schema.sql"]:
                if os.path.exists(s_path) and os.path.getsize(s_path) > 0:
                    shutil.copy2(s_path, f"{stage}/database/schema.sql")
                    break

            for f_path in ["app/db_dump/adaudit_full.sql", "/app/db_dump/adaudit_full.sql", "db_dump/adaudit_full.sql"]:
                if os.path.exists(f_path) and os.path.getsize(f_path) > 0:
                    shutil.copy2(f_path, f"{stage}/database/adaudit_full.sql")
                    break

            # 3. Dokumentációk bemásolása
            for d_dir in ["docs", "app/docs", "/app/docs", "source/docs"]:
                if os.path.exists(d_dir):
                    for doc_file in os.listdir(d_dir):
                        sp = os.path.join(d_dir, doc_file)
                        if os.path.isfile(sp):
                            shutil.copy2(sp, f"{stage}/docs/{doc_file}")

            # 4. Konfigurációs fájlok (.env, settings.json)
            for cf in ["app/config/settings.json", "config/settings.json", "app/settings.json", "settings.json", ".env", "app/.env"]:
                if os.path.exists(cf):
                    try: shutil.copy2(cf, f"{stage}/config/{os.path.basename(cf)}")
                    except Exception: pass

            # 5. Forráskódok
            allowed_exts = (".py", ".html", ".css", ".js", ".json", ".md", ".txt", ".sh", ".yml", ".yaml")
            root_dir = "/app" if os.path.exists("/app/main.py") else "."
            for root, dirs, files in os.walk(root_dir):
                dirs[:] = [d for d in dirs if d not in [".git", "venv", "__pycache__", "backups", "staging", ".cache", "tmp", "node_modules"]]
                for f in files:
                    if f.endswith(allowed_exts) or f in ["Dockerfile", "docker-compose.yml", "requirements.txt"]:
                        src = os.path.join(root, f)
                        rel = os.path.relpath(src, root_dir)
                        dst = os.path.join(f"{stage}/source", rel)
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        try: shutil.copy2(src, dst)
                        except Exception: pass

            # 6. Readme és leírás
            with open(f"{stage}/README.md", "w", encoding="utf-8") as rf:
                rf.write(f"# AD Tracker & Rendszerközpont - Teljes Rendszermentés\nVerzió: {version}\nIdőpont: {display_time}\n")

            # 7. Tömörítés (.tar.gz)
            arch_name = f"backup_ad_tracker_full_{version}_{ts}.tar.gz"
            arch_path = os.path.join(bdir, arch_name)

            with tarfile.open(arch_path, "w:gz") as tar:
                tar.add(stage, arcname=f"backup_ad_tracker_full_{version}_{ts}")

            shutil.rmtree(stage, ignore_errors=True)

            sz_bytes = os.path.getsize(arch_path)
            sz_str = f"{round(sz_bytes / (1024*1024), 2)} MB" if sz_bytes >= 1024*1024 else f"{round(sz_bytes / 1024, 1)} KB"

            return {
                "status": "SUCCESS",
                "message": f"Komplett rendszermentés elkészült: {arch_name} ({sz_str})",
                "filename": arch_name,
                "size": sz_str,
                "date": display_time,
                "version": version
            }
        except Exception as e:
            return {"status": "ERROR", "message": f"Hiba a mentés elkészítésekor: {str(e)}"}

    def create_full_backup(self, db = None, comment: str = "", user: str = "tadmin") -> dict:
        return self.create_backup(db, comment, user)

    def delete_backup(self, filename: str) -> dict:
        if not filename:
            return {"status": "ERROR", "message": "Hiányzó fájlnév."}
        safe_name = os.path.basename(filename)
        bdir = self.get_backup_directory()
        target = os.path.join(bdir, safe_name)
        if os.path.exists(target):
            try:
                os.remove(target)
                return {"status": "SUCCESS", "message": f"{safe_name} sikeresen törölve."}
            except Exception as e:
                return {"status": "ERROR", "message": str(e)}
        return {"status": "ERROR", "message": "A megadott mentési fájl nem található."}

    def __call__(self, db = None):
        return BackupService(db)

backup_service = BackupService()
