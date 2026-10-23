import os
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy.orm import Session
from database import get_db
from auth import verify_session_token, COOKIE_NAME
from backup_manager import (
    create_backup, list_backups, restore_backup, delete_backup, BACKUP_DIR,
    export_codebase_zip, export_docs_zip, export_config_json_file, export_database_sql_file
)
from telemetry import log_web_activity

router = APIRouter(prefix="/api/backups", tags=["backups"])

def get_current_user(request: Request):
    user, _ = verify_session_token(request.cookies.get(COOKIE_NAME))
    return user

@router.get("")
def get_backups_list(request: Request):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    try:
        return {"backups": list_backups()}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "ERROR", "message": str(e)})

@router.post("/create")
async def create_backup_endpoint(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return JSONResponse(status_code=401, content={})
    try:
        data = await request.json()
        comment = data.get("comment", "")
        res = create_backup(db, comment=comment, user=user)
        if res.get("status") == "SUCCESS":
            log_web_activity(db, request, user, "MENTÉS_LÉTREHOZÁS", f"Fájl: {res.get('filename')}, Megjegyzés: {comment}", "SIKERES")
        return res
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "ERROR", "message": f"Kiszolgálói hiba: {str(e)}"})

@router.get("/export/code")
def export_code_endpoint(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return JSONResponse(status_code=401, content={})
    try:
        fpath, fname = export_codebase_zip()
        log_web_activity(db, request, user, "KÓDBÁZIS_EXPORT", f"Letöltve: {fname}", "SIKERES")
        return FileResponse(fpath, filename=fname, media_type="application/zip")
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "ERROR", "message": str(e)})

@router.get("/export/docs")
def export_docs_endpoint(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return JSONResponse(status_code=401, content={})
    try:
        fpath, fname = export_docs_zip()
        log_web_activity(db, request, user, "DOKUMENTÁCIÓ_EXPORT", f"Letöltve: {fname}", "SIKERES")
        return FileResponse(fpath, filename=fname, media_type="application/zip")
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "ERROR", "message": str(e)})

@router.get("/export/config")
def export_config_endpoint(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return JSONResponse(status_code=401, content={})
    try:
        fpath, fname = export_config_json_file(db)
        log_web_activity(db, request, user, "KONFIG_EXPORT", f"Letöltve: {fname}", "SIKERES")
        return FileResponse(fpath, filename=fname, media_type="application/json")
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "ERROR", "message": str(e)})

@router.get("/export/database")
def export_database_endpoint(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return JSONResponse(status_code=401, content={})
    try:
        fpath, fname = export_database_sql_file(db)
        log_web_activity(db, request, user, "ADATBÁZIS_SQL_EXPORT", f"Letöltve: {fname}", "SIKERES")
        return FileResponse(fpath, filename=fname, media_type="application/sql")
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "ERROR", "message": str(e)})

@router.post("/restore")
async def restore_backup_endpoint(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return JSONResponse(status_code=401, content={})
    try:
        data = await request.json()
        filename = data.get("filename", "")
        res = restore_backup(db, filename=filename)
        st = "SIKERES" if res.get("status") == "SUCCESS" else "HIBA"
        log_web_activity(db, request, user, "MENTÉS_VISSZAÁLLÍTÁS", f"Fájl: {filename}", st)
        return res
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "ERROR", "message": str(e)})

@router.get("/download/{filename}")
def download_backup_endpoint(filename: str, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return JSONResponse(status_code=401, content={})
    safe_name = os.path.basename(filename)
    fpath = os.path.join(BACKUP_DIR, safe_name)
    if not os.path.isfile(fpath): return JSONResponse(status_code=404, content={"error": "Fájl nem található"})
    log_web_activity(db, request, user, "MENTÉS_LETÖLTÉS", f"Fájl: {safe_name}", "SIKERES")
    return FileResponse(fpath, filename=safe_name, media_type="application/zip")

@router.delete("/{filename}")
def delete_backup_endpoint(filename: str, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return JSONResponse(status_code=401, content={})
    try:
        res = delete_backup(filename)
        log_web_activity(db, request, user, "MENTÉS_TÖRLÉS", f"Fájl: {filename}", "SIKERES")
        return res
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "ERROR", "message": str(e)})
