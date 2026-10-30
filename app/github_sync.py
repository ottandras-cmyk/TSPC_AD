import os
import json
import base64
import urllib.request
import urllib.error
from datetime import datetime, timezone
from config_manager import get_setting, update_setting

CURR_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURR_DIR)

if os.path.exists(os.path.join(PARENT_DIR, "docker-compose.yml")) or os.path.exists(os.path.join(PARENT_DIR, ".git")):
    BASE_DIR = PARENT_DIR
    APP_DIR = os.path.join(BASE_DIR, "app")
    DOCS_DIR = os.path.join(BASE_DIR, "docs")
else:
    BASE_DIR = CURR_DIR
    APP_DIR = CURR_DIR
    DOCS_DIR = os.path.join(CURR_DIR, "docs")

EXCLUDED_DIRS = {"__pycache__", ".git", "venv", ".pytest_cache", "backups", "csv_imports", "exports", ".idea", ".vscode"}

def bump_version_str(current_ver: str) -> str:
    try:
        clean = current_ver.strip().lstrip("v")
        parts = clean.split(".")
        if len(parts) == 2:
            major = int(parts[0])
            minor = int(parts[1]) + 1
            return f"{major}.{minor:02d}"
        elif len(parts) == 3:
            major = int(parts[0])
            minor = int(parts[1])
            patch = int(parts[2]) + 1
            return f"{major}.{minor}.{patch}"
        else:
            val = float(clean) + 0.01
            return f"{val:.2f}"
    except Exception:
        return "1.01"

def api_request(url, token, data=None, method="GET"):
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "AD-Tracker"
    }
    encoded_data = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=encoded_data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        res_body = resp.read().decode("utf-8")
        return json.loads(res_body) if res_body else {}

def test_github_connection(repo, token):
    if not repo: return False, "Nincs megadva GitHub repó!"
    if not token: return False, "Nincs megadva GitHub token (PAT)!"
    try:
        data = api_request(f"https://api.github.com/repos/{repo}", token)
        return True, f"Sikeres kapcsolat: {data.get('full_name', repo)}"
    except urllib.error.HTTPError as e:
        if e.code == 401: return False, "Érvénytelen vagy lejárt GitHub token (PAT)!"
        if e.code == 404: return False, f"A repó nem található ({repo}) vagy nincs hozzáférés."
        return False, f"GitHub hiba ({e.code}): {e.reason}"
    except Exception as e:
        return False, f"Hiba: {str(e)}"

def get_github_history(db):
    repo = get_setting(db, "GH_REPO", "")
    token = get_setting(db, "GH_TOKEN", "")
    branch = get_setting(db, "GH_BRANCH", "main")
    if not repo or not token:
        return []
    try:
        url = f"https://api.github.com/repos/{repo}/commits?sha={branch}&per_page=10"
        commits = api_request(url, token)
        results = []
        for c in commits:
            commit_obj = c.get("commit", {})
            results.append({
                "message": commit_obj.get("message", "-"),
                "date": commit_obj.get("author", {}).get("date", "-")[:19].replace("T", " "),
                "author": commit_obj.get("author", {}).get("name", "-"),
                "sha": c.get("sha", "")[:7]
            })
        return results
    except Exception:
        return []

def push_to_github_api(db, message: str, user: str = "tadmin") -> dict:
    repo = get_setting(db, "GH_REPO", "")
    token = get_setting(db, "GH_TOKEN", "")
    branch = get_setting(db, "GH_BRANCH", "main")
    curr_ver = get_setting(db, "APP_VERSION", "1.00")
    
    if not repo:
        return {"status": "ERROR", "message": "Nincs beállítva a GitHub repó (Owner/Repo)!"}
    if not token:
        return {"status": "ERROR", "message": "Nincs beállítva a GitHub Personal Access Token (PAT)!"}

    # 1. Verziószám automatikus növelése
    new_ver = bump_version_str(curr_ver)
    commit_msg = f"v{new_ver}: {message}" if message else f"v{new_ver}: Automatikus kódfrissítés ({user})"

    try:
        # A. Branch referencia lekérése
        ref_data = api_request(f"https://api.github.com/repos/{repo}/git/ref/heads/{branch}", token)
        commit_sha = ref_data.get("object", {}).get("sha")
        if not commit_sha:
            return {"status": "ERROR", "message": f"Nem található a(z) '{branch}' ág a repóban!"}

        # B. Alap fa (base tree) azonosító lekérése
        commit_data = api_request(f"https://api.github.com/repos/{repo}/git/commits/{commit_sha}", token)
        base_tree_sha = commit_data.get("tree", {}).get("sha")

        # C. Fájlok összegyűjtése (app/ és docs/)
        tree_elements = []
        
        for root, dirs, files in os.walk(APP_DIR):
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
            for file in files:
                if file.endswith((".pyc", ".pyo", ".DS_Store")): continue
                full_p = os.path.join(root, file)
                rel_p = os.path.relpath(full_p, BASE_DIR).replace("\\", "/")
                try:
                    with open(full_p, "rb") as fp:
                        raw_bytes = fp.read()
                    try:
                        text_content = raw_bytes.decode("utf-8")
                        tree_elements.append({
                            "path": rel_p,
                            "mode": "100644",
                            "type": "blob",
                            "content": text_content
                        })
                    except UnicodeDecodeError:
                        b64_content = base64.b64encode(raw_bytes).decode("ascii")
                        blob_res = api_request(f"https://api.github.com/repos/{repo}/git/blobs", token, {
                            "content": b64_content,
                            "encoding": "base64"
                        }, method="POST")
                        tree_elements.append({
                            "path": rel_p,
                            "mode": "100644",
                            "type": "blob",
                            "sha": blob_res.get("sha")
                        })
                except Exception:
                    pass

        if os.path.isdir(DOCS_DIR):
            for root, dirs, files in os.walk(DOCS_DIR):
                dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
                for file in files:
                    full_p = os.path.join(root, file)
                    rel_p = os.path.relpath(full_p, BASE_DIR).replace("\\", "/")
                    try:
                        with open(full_p, "r", encoding="utf-8") as fp:
                            tree_elements.append({
                                "path": rel_p,
                                "mode": "100644",
                                "type": "blob",
                                "content": fp.read()
                            })
                    except Exception:
                        pass

        # D. Új git fa feltöltése
        tree_res = api_request(f"https://api.github.com/repos/{repo}/git/trees", token, {
            "base_tree": base_tree_sha,
            "tree": tree_elements
        }, method="POST")
        new_tree_sha = tree_res.get("sha")

        # E. Új commit létrehozása
        new_commit_res = api_request(f"https://api.github.com/repos/{repo}/git/commits", token, {
            "message": commit_msg,
            "tree": new_tree_sha,
            "parents": [commit_sha]
        }, method="POST")
        new_commit_sha = new_commit_res.get("sha")

        # F. Ág mutató (branch ref) frissítése
        api_request(f"https://api.github.com/repos/{repo}/git/refs/heads/{branch}", token, {
            "sha": new_commit_sha,
            "force": False
        }, method="PATCH")

        # G. Új verzió elmentése a helyi adatbázisba
        update_setting(db, "APP_VERSION", new_ver)

        return {
            "status": "SUCCESS",
            "new_version": new_ver,
            "commit_sha": new_commit_sha[:7],
            "message": f"Kód sikeresen publikálva a GitHubra! Új verzió: v{new_ver} (Commit: {new_commit_sha[:7]})"
        }
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8") if hasattr(e, "read") else str(e)
        return {"status": "ERROR", "message": f"GitHub API hiba ({e.code}): {err_msg}"}
    except Exception as e:
        return {"status": "ERROR", "message": f"Hiba a kód publikálásakor: {str(e)}"}
