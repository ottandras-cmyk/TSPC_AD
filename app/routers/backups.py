import os
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from services.backup_service import backup_service

router = APIRouter(prefix="/api/backups", tags=["backups"])

@router.get("")
@router.get("/")
@router.get("/list")
def list_backups():
    res = backup_service.list_backups()
    return JSONResponse(status_code=200, content=res)

@router.post("/create")
@router.post("/create-full")
def create_backup():
    res = backup_service.create_backup()
    return JSONResponse(status_code=200, content=res)

@router.get("/download/{filename}")
def download_backup(filename: str):
    filename = os.path.basename(filename)
    bdir = backup_service.get_backup_directory()
    target = os.path.join(bdir, filename)
    if os.path.exists(target):
        return FileResponse(target, filename=filename, media_type="application/gzip")
    raise HTTPException(status_code=404, detail="Mentés nem található.")

@router.delete("/{filename}")
@router.post("/delete")
def delete_backup_endpoint(filename: str = None):
    if not filename:
        raise HTTPException(status_code=400, detail="Hiányzó fájlnév.")
    res = backup_service.delete_backup(filename)
    return JSONResponse(status_code=200, content=res)

@router.get("/git-log")
def get_backup_git_log():
    import subprocess
    try:
        out = subprocess.check_output(
            ["git", "log", "-n", "10", "--pretty=format:%h|%cd|%s", "--date=format:%Y-%m-%d %H:%M"],
            stderr=subprocess.STDOUT
        ).decode("utf-8")
        commits = []
        for line in out.splitlines():
            if line:
                parts = line.split("|", 2)
                commits.append({
                    "sha": parts[0] if len(parts) > 0 else "-",
                    "date": parts[1] if len(parts) > 1 else "-",
                    "message": parts[2] if len(parts) > 2 else "-"
                })
        return {"status": "SUCCESS", "commits": commits, "history": commits}
    except Exception as e:
        return {"status": "SUCCESS", "commits": [], "history": [], "message": str(e)}
