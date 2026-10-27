import os, json, glob, subprocess, time, tarfile, shutil
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse

router = APIRouter(prefix="/api/backups", tags=["backups"])

def get_bdir():
    for d in ["/app/backups", "app/backups", "backups"]:
        if os.path.exists(d): return d
    os.makedirs("/app/backups", exist_ok=True)
    return "/app/backups"

@router.get("")
@router.get("/")
@router.get("/list")
def list_backups():
    bdir = get_bdir()
    os.makedirs(bdir, exist_ok=True)
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

    return JSONResponse(status_code=200, content={
        "status": "SUCCESS",
        "backups": backups,
        "data": backups,
        "count": len(backups),
        "total_size_mb": total_mb,
        "last_backup": last_date
    })

@router.post("/create")
@router.post("/create-full")
def create_backup():
    bdir = get_bdir()
    os.makedirs(bdir, exist_ok=True)

    ts = time.strftime("%Y%m%d_%H%M%S")
    display_time = time.strftime("%Y-%m-%d %H:%M:%S")
    version = "v1.26"

    stage = f"/tmp/backup_ad_tracker_full_{version}_{ts}"
    os.makedirs(f"{stage}/database", exist_ok=True)
    os.makedirs(f"{stage}/docs", exist_ok=True)
    os.makedirs(f"{stage}/config", exist_ok=True)
    os.makedirs(f"{stage}/source", exist_ok=True)

    # 1. VALÓS POSTGRESQL DUMP BEMÁSOLÁSA
    for s_path in ["app/db_dump/schema.sql", "/app/db_dump/schema.sql", "db_dump/schema.sql"]:
        if os.path.exists(s_path) and os.path.getsize(s_path) > 0:
            shutil.copy2(s_path, f"{stage}/database/schema.sql")
            break

    for f_path in ["app/db_dump/adaudit_full.sql", "/app/db_dump/adaudit_full.sql", "db_dump/adaudit_full.sql"]:
        if os.path.exists(f_path) and os.path.getsize(f_path) > 0:
            shutil.copy2(f_path, f"{stage}/database/adaudit_full.sql")
            break

    # 2. VALÓS DOKUMENTÁCIÓK BEMÁSOLÁSA A FŐ DOCS/ MAPPÁBA
    for d_dir in ["docs", "app/docs", "/app/docs", "source/docs"]:
        if os.path.exists(d_dir):
            for doc_file in os.listdir(d_dir):
                sp = os.path.join(d_dir, doc_file)
                if os.path.isfile(sp):
                    shutil.copy2(sp, f"{stage}/docs/{doc_file}")

    # Katasztrófa-helyreállítási útmutató hozzáadása a docs/ mappába
    restore_guide = f"""# AD Tracker - Katasztrófa-helyreállítási Útmutató (Disaster Recovery)
Mentés dátuma: {display_time} ({version})

## 1. Adatbázis Visszaállítása
- Teljes adatbázis visszatöltése (séma + minden adat):
  cat database/adaudit_full.sql | docker exec -i ad-postgres psql -U adaudit -d adaudit

- Csak a séma létrehozása (üres adatbázis esetén):
  cat database/schema.sql | docker exec -i ad-postgres psql -U adaudit -d adaudit

## 2. Konfiguráció Visszaállítása
cp config/settings.json ~/ad-tracker/app/config/settings.json
cp config/.env ~/ad-tracker/.env

## 3. Alkalmazás Újraindítása
docker compose restart
"""
    with open(f"{stage}/docs/RESTORE_GUIDE.md", "w", encoding="utf-8") as rf:
        rf.write(restore_guide)

    # 3. README.md A CSOMAG GYÖKERÉBE
    readme_content = f"""# AD Tracker & Rendszerközpont - Teljes Rendszermentés
Verzió: {version}
Készítés ideje: {display_time}

Tartalom:
- `database/schema.sql` - Tiszta PostgreSQL adatbázis séma (DDL: táblák, oszlopok, indexek)
- `database/adaudit_full.sql` - Teljes adatbázis mentés (séma + minden rekord)
- `docs/` - Teljes műszaki dokumentáció (DATABASE_SCHEMA.md, SYSTEM_ARCHITECTURE.md, API_DOCUMENTATION.md, openapi.json, RESTORE_GUIDE.md)
- `config/` - Rendszer konfigurációk (.env, settings.json)
- `source/` - A teljes alkalmazás forráskódja
"""
    with open(f"{stage}/README.md", "w", encoding="utf-8") as rf:
        rf.write(readme_content)

    # 4. KONFIGURÁCIÓK BEMÁSOLÁSA
    for cf in ["app/config/settings.json", "config/settings.json", "app/settings.json", "settings.json", ".env", "app/.env"]:
        if os.path.exists(cf):
            try: shutil.copy2(cf, f"{stage}/config/{os.path.basename(cf)}")
            except Exception: pass

    # 5. FORRÁSKÓDOK BEMÁSOLÁSA
    allowed_exts = (".py", ".html", ".css", ".js", ".json", ".md", ".txt", ".sh", ".yml", ".yaml")
    for root, dirs, files in os.walk("."):
        if any(bad in root for bad in [".git", "venv", "__pycache__", "backups", "staging", ".cache", "tmp"]):
            continue
        for f in files:
            if f.endswith(allowed_exts) or f in ["Dockerfile", "docker-compose.yml", "requirements.txt"]:
                src = os.path.join(root, f)
                rel = os.path.relpath(src, ".")
                dst = os.path.join(f"{stage}/source", rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                try: shutil.copy2(src, dst)
                except Exception: pass

    # 6. ARCHÍVUM TÖMÖRÍTÉSE (.TAR.GZ)
    arch_name = f"backup_ad_tracker_full_{version}_{ts}.tar.gz"
    arch_path = os.path.join(bdir, arch_name)

    with tarfile.open(arch_path, "w:gz") as tar:
        tar.add(stage, arcname=f"backup_ad_tracker_full_{version}_{ts}")

    shutil.rmtree(stage, ignore_errors=True)

    for alt in ["app/backups", "backups", "/app/backups"]:
        if os.path.exists(alt) and alt != bdir:
            try: shutil.copy2(arch_path, os.path.join(alt, arch_name))
            except Exception: pass

    sz_bytes = os.path.getsize(arch_path)
    sz_str = f"{round(sz_bytes / (1024*1024), 2)} MB" if sz_bytes >= 1024*1024 else f"{round(sz_bytes / 1024, 1)} KB"

    return JSONResponse(status_code=200, content={
        "status": "SUCCESS",
        "message": f"Komplett rendszermentés elkészült: {arch_name} ({sz_str})",
        "filename": arch_name,
        "size": sz_str,
        "date": display_time,
        "version": version
    })

@router.get("/download/{filename}")
def download_backup(filename: str):
    filename = os.path.basename(filename)
    for d in [get_bdir(), "/app/backups", "app/backups", "backups"]:
        target = os.path.join(d, filename)
        if os.path.exists(target):
            return FileResponse(target, filename=filename, media_type="application/gzip")
    raise HTTPException(status_code=404, detail="Mentés nem található.")

@router.delete("/{filename}")
@router.post("/delete")
def delete_backup(filename: str = None):
    if not filename: raise HTTPException(status_code=400, detail="Hiányzó fájlnév.")
    filename = os.path.basename(filename)
    deleted = False
    for d in [get_bdir(), "/app/backups", "app/backups", "backups"]:
        target = os.path.join(d, filename)
        if os.path.exists(target):
            try:
                os.remove(target)
                deleted = True
            except Exception: pass
    if deleted:
        return {"status": "SUCCESS", "message": f"{filename} törölve."}
    return {"status": "ERROR", "message": "Fájl nem található."}
