import os, shutil, threading
from typing import List
from fastapi import APIRouter, Depends, Request, File, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from database import get_db, SessionLocal
from auth import verify_session_token, COOKIE_NAME
from history_importer import scan_csv_directory, run_historical_replay, fast_backfill_extra_data
from telemetry import log_web_activity

router = APIRouter(prefix="/api/history", tags=["history"])

def get_current_user(request: Request):
    user, _ = verify_session_token(request.cookies.get(COOKIE_NAME))
    return user

import_progress = {
    "is_running": False,
    "current_step": 0,
    "total_steps": 0,
    "current_time": "",
    "result": None
}

def async_import_worker(folder: str):
    global import_progress
    import_progress["is_running"] = True
    import_progress["result"] = None
    def on_progress(cur, total, ts_str):
        import_progress["current_step"] = cur
        import_progress["total_steps"] = total
        import_progress["current_time"] = ts_str
    db = SessionLocal()
    try:
        res = run_historical_replay(db, folder, progress_callback=on_progress)
        import_progress["result"] = res
    except Exception as e:
        import_progress["result"] = {"status": "ERROR", "message": str(e)}
    finally:
        db.close()
        import_progress["is_running"] = False

@router.post("/upload-files")
async def api_history_upload_files(request: Request, files: List[UploadFile] = File(...)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    upload_dir = os.path.join(app_dir, "csv_imports")
    os.makedirs(upload_dir, exist_ok=True)

    saved_count = 0
    for file in files:
        fname = os.path.basename(file.filename)
        if fname.lower().endswith(".csv"):
            dest_path = os.path.join(upload_dir, fname)
            with open(dest_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            saved_count += 1
    return {"status": "SUCCESS", "saved_files": saved_count}

@router.post("/scan")
async def api_history_scan(request: Request):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    data = await request.json()
    folder = data.get("folder", "csv_imports")
    return scan_csv_directory(folder)

@router.post("/backfill")
async def api_history_backfill(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return JSONResponse(status_code=401, content={})
    data = await request.json()
    folder = data.get("folder", "csv_imports")
    log_web_activity(db, request, user, "CSV_BACKFILL", f"Mappa: {folder}", "SIKERES")
    return fast_backfill_extra_data(db, folder)

@router.post("/import")
async def api_history_import(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return JSONResponse(status_code=401, content={})
    if import_progress["is_running"]: return {"status": "ERROR", "message": "Importálás folyamatban!"}
    data = await request.json()
    folder = data.get("folder", "csv_imports")
    log_web_activity(db, request, user, "CSV_IMPORT_INDÍTÁS", f"Mappa: {folder}", "SIKERES")
    threading.Thread(target=async_import_worker, args=(folder,)).start()
    return {"status": "STARTED"}

@router.get("/progress")
def api_history_progress(request: Request):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    return import_progress
