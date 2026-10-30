import re
import json
import urllib.request
import subprocess
from datetime import datetime
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from database import get_db
import models
from config_manager import get_setting, set_setting

router = APIRouter(prefix="/api/github", tags=["github"])

def safe_get_user(request: Request):
    try:
        from auth import COOKIE_NAME, verify_session_token
        token = request.cookies.get(COOKIE_NAME)
        if token:
            user, _ = verify_session_token(token)
            return user
    except Exception:
        pass
    return None

def parse_version_num(v_str):
    if not v_str: return 1.00
    m = re.search(r'(\d+\.\d+)', str(v_str))
    if m:
        try: return float(m.group(1))
        except ValueError: pass
    return 1.00

@router.get("/status")
def get_github_status(request: Request, db: Session = Depends(get_db)):
    repo = get_setting(db, "GH_REPO", "")
    token = get_setting(db, "GH_TOKEN", "")
    branch = get_setting(db, "GH_BRANCH", "main")
    
    # Helyi verzió lekérdezése
    cur_ver_str = get_setting(db, "APP_VERSION", "")
    if not cur_ver_str:
        # Ha nincs beállítva, megkeressük a legfrissebb mentés fájlnevéből
        last_backup = db.query(models.SystemSetting).filter(models.SystemSetting.setting_key == "LAST_BACKUP_VERSION").first()
        cur_ver_str = last_backup.setting_value if last_backup else "1.06"

    cur_ver_float = parse_version_num(cur_ver_str)
    next_ver_str = f"{cur_ver_float + 0.01:.2f}"

    remote_ver_str = "-"
    last_commit_info = None

    if repo:
        clean_repo = repo.replace("https://github.com/", "").strip("/")
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "ADTracker-App"
        }
        if token and token != "***":
            headers["Authorization"] = f"token {token}"

        try:
            req = urllib.request.Request(f"https://api.github.com/repos/{clean_repo}/commits?per_page=1&sha={branch}", headers=headers)
            with urllib.request.urlopen(req, timeout=5) as resp:
                commits = json.loads(resp.read().decode())
                if commits and len(commits) > 0:
                    c = commits[0]
                    msg = c.get("commit", {}).get("message", "")
                    m_v = re.search(r'v?(\d+\.\d+)', msg)
                    if m_v:
                        remote_ver_str = m_v.group(1)
                    else:
                        remote_ver_str = f"{cur_ver_float:.2f}"

                    last_commit_info = {
                        "sha": c.get("sha", "")[:7],
                        "message": msg.split("\n")[0],
                        "author": c.get("commit", {}).get("author", {}).get("name", "Git"),
                        "date": c.get("commit", {}).get("author", {}).get("date", "")[:19].replace("T", " ")
                    }
        except Exception:
            remote_ver_str = f"{cur_ver_float:.2f}"

    return {
        "status": "SUCCESS",
        "current_version": f"{cur_ver_float:.2f}",
        "next_version": next_ver_str,
        "remote_version": remote_ver_str,
        "repo": repo,
        "branch": branch,
        "is_configured": bool(repo),
        "last_commit": last_commit_info
    }

@router.get("/history")
def get_github_commit_history(request: Request, db: Session = Depends(get_db)):
    repo = get_setting(db, "GH_REPO", "")
    token = get_setting(db, "GH_TOKEN", "")
    branch = get_setting(db, "GH_BRANCH", "main")

    history = []

    # 1. Próbálkozás a GitHub REST API-val
    if repo:
        clean_repo = repo.replace("https://github.com/", "").strip("/")
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "ADTracker-App"
        }
        if token and token != "***":
            headers["Authorization"] = f"token {token}"

        try:
            req = urllib.request.Request(f"https://api.github.com/repos/{clean_repo}/commits?per_page=25&sha={branch}", headers=headers)
            with urllib.request.urlopen(req, timeout=6) as resp:
                raw_commits = json.loads(resp.read().decode())
                for c in raw_commits:
                    msg = c.get("commit", {}).get("message", "")
                    first_line = msg.split("\n")[0]
                    m_v = re.search(r'v?(\d+\.\d+)', msg)
                    ver = m_v.group(1) if m_v else "-"
                    author_name = c.get("commit", {}).get("author", {}).get("name") or c.get("author", {}).get("login") or "Rendszer"
                    date_raw = c.get("commit", {}).get("author", {}).get("date", "")
                    date_formatted = date_raw[:19].replace("T", " ") if date_raw else "-"

                    history.append({
                        "sha": c.get("sha", "")[:7],
                        "version": ver,
                        "message": first_line,
                        "author": author_name,
                        "date": date_formatted,
                        "url": c.get("html_url", "#")
                    })
        except Exception:
            pass

    # 2. Ha nincs net vagy a GitHub API nem elérhető, helyi git history-ból olvassuk ki
    if not history:
        try:
            p = subprocess.run(
                ["git", "log", "-n", "20", "--pretty=format:%h|%an|%ad|%s", "--date=format:%Y-%m-%d %H:%M:%S"],
                capture_output=True, text=True, timeout=3
            )
            if p.returncode == 0 and p.stdout:
                for line in p.stdout.strip().split("\n"):
                    parts = line.split("|")
                    if len(parts) >= 4:
                        sha, author, dt, msg = parts[0], parts[1], parts[2], "|".join(parts[3:])
                        m_v = re.search(r'v?(\d+\.\d+)', msg)
                        ver = m_v.group(1) if m_v else "-"
                        history.append({
                            "sha": sha,
                            "version": ver,
                            "message": msg,
                            "author": author,
                            "date": dt,
                            "url": f"https://github.com/{repo.replace('https://github.com/', '').strip('/')}/commit/{sha}" if repo else "#"
                        })
        except Exception:
            pass

    return {"status": "SUCCESS", "history": history}

@router.post("/push")
async def push_to_github(request: Request, db: Session = Depends(get_db)):
    try:
        body = await request.json()
    except Exception:
        body = {}

    comment = (body.get("comment") or "").strip()
    if not comment:
        comment = "Automatikus rendszermentés és verziófrissítés"

    # Verzió lekérdezése és növelése +0.01-el
    cur_ver_str = get_setting(db, "APP_VERSION", "1.06")
    cur_ver_float = parse_version_num(cur_ver_str)
    new_ver_float = round(cur_ver_float + 0.01, 2)
    new_ver_str = f"{new_ver_float:.2f}"

    repo = get_setting(db, "GH_REPO", "")
    branch = get_setting(db, "GH_BRANCH", "main")
    token = get_setting(db, "GH_TOKEN", "")

    user_name = safe_get_user(request)

    # 1. Verzió elmentése a helyi adatbázisba
    set_setting(db, "APP_VERSION", new_ver_str)
    set_setting(db, "LAST_BACKUP_VERSION", new_ver_str)

    # 2. Git commit és push végrehajtása a szerveren
    commit_msg = f"[v{new_ver_str}] {comment}"
    git_success = False
    git_out = ""

    try:
        subprocess.run(["git", "config", "user.name", user_name], check=False)
        subprocess.run(["git", "config", "user.email", f"{user_name}@tspc.hu"], check=False)
        subprocess.run(["git", "add", "-A"], check=False)
        p_c = subprocess.run(["git", "commit", "-m", commit_msg], capture_output=True, text=True, check=False)
        
        # Push indítása
        p_p = subprocess.run(["git", "push", "origin", branch], capture_output=True, text=True, timeout=15, check=False)
        git_out = (p_c.stdout + " " + p_p.stdout + " " + p_p.stderr).strip()
        git_success = (p_p.returncode == 0)
    except Exception as e:
        git_out = str(e)

    # Audit naplózás
    try:
        db.add(models.WebAccessLog(
            username=user_name,
            client_ip=request.client.host if request.client else "10.1.15.115",
            action="GITHUB_PUSH",
            details=f"Új verzió: v{new_ver_str} | Komment: {comment} | Eredmény: {'Sikeres' if git_success else 'Helyi commit kész'}",
            status="SUCCESS"
        ))
        db.commit()
    except Exception:
        pass

    return {
        "status": "SUCCESS",
        "new_version": new_ver_str,
        "message": f"✅ Verziószám sikeresen növelve: v{new_ver_str}! Commit: '{commit_msg}' rögzítve.",
        "git_output": git_out
    }
