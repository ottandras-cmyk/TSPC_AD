import urllib.request
import urllib.error
import json
import re
import os

def _request(url: str, method: str = "GET", token: str = "", data: dict = None, timeout: int = 15):
    headers = {
        "User-Agent": "AD-Tracker",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = None
    if data is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read().decode("utf-8")
            if "application/json" in content_type or raw.startswith(("{", "[")):
                return resp.status, json.loads(raw)
            return resp.status, raw
    except urllib.error.HTTPError as e:
        raw_err = e.read().decode("utf-8", errors="ignore")
        try:
            return e.code, json.loads(raw_err)
        except Exception:
            return e.code, raw_err
    except Exception as e:
        return 0, str(e)

def test_github_connection(repo: str, token: str) -> tuple[bool, str]:
    status, res = _request(f"https://api.github.com/repos/{repo}", "GET", token)
    if status == 200 and isinstance(res, dict):
        return True, f"Sikeres kapcsolat! Repó: {res.get('full_name')} (Privát: {res.get('private')})"
    elif status == 401:
        return False, "Érvénytelen GitHub Token (Bad credentials)!"
    elif status == 404:
        return False, "A megadott repó nem található, vagy a tokennek nincs hozzáférése!"
    else:
        msg = res.get("message") if isinstance(res, dict) else str(res)
        return False, f"GitHub hiba (HTTP {status}): {msg}"

def get_latest_github_version(repo: str, token: str, branch: str = "main") -> str:
    if not repo or not token:
        return "1.00"
    status, res = _request(f"https://api.github.com/repos/{repo}/tags?per_page=5", "GET", token)
    if status == 200 and isinstance(res, list) and res:
        first_tag = res[0].get("name", "")
        m = re.search(r"v?([0-9]+\.[0-9]+)", first_tag)
        if m:
            return m.group(1)
    status, res = _request(f"https://api.github.com/repos/{repo}/commits?sha={branch}&per_page=5", "GET", token)
    if status == 200 and isinstance(res, list) and res:
        for c in res:
            msg = c.get("commit", {}).get("message", "")
            m = re.search(r"v?([0-9]+\.[0-9]+)", msg)
            if m:
                return m.group(1)
    return "1.00"

def get_github_commit_history(repo: str, token: str, branch: str = "main") -> tuple[bool, list]:
    status, res = _request(f"https://api.github.com/repos/{repo}/commits?sha={branch}&per_page=10", "GET", token)
    if status == 200 and isinstance(res, list):
        commits = []
        for item in res:
            c = item.get("commit", {})
            commits.append({
                "sha": item.get("sha", "")[:7],
                "message": c.get("message", ""),
                "author": c.get("author", {}).get("name", ""),
                "date": c.get("author", {}).get("date", "")
            })
        return True, commits
    err = res.get("message") if isinstance(res, dict) else str(res)
    return False, [f"HTTP {status}: {err}"]

def push_code_to_github(repo: str, branch: str, token: str, new_version: str, custom_message: str = "") -> tuple[bool, str]:
    app_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.abspath(os.path.join(app_dir, ".."))

    # Javított endpoint: /git/refs/heads/... (többes számban)
    ref_url = f"https://api.github.com/repos/{repo}/git/refs/heads/{branch}"
    status, r_ref = _request(ref_url, "GET", token)
    if status != 200 or not isinstance(r_ref, dict):
        return False, f"A(z) '{branch}' ág nem található a repóban! (HTTP {status})"

    latest_commit_sha = r_ref["object"]["sha"]
    commit_url = f"https://api.github.com/repos/{repo}/git/commits/{latest_commit_sha}"
    status, r_commit = _request(commit_url, "GET", token)
    if status != 200 or not isinstance(r_commit, dict):
        return False, f"Nem sikerült lekérni a legutóbbi commitot! (HTTP {status})"
    base_tree_sha = r_commit["tree"]["sha"]

    tree_items = []
    # 1. Python kódok
    for fname in os.listdir(app_dir):
        if fname.endswith(".py"):
            fpath = os.path.join(app_dir, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            tree_items.append({"path": f"app/{fname}", "mode": "100644", "type": "blob", "content": content})

    # 2. HTML Sablonok
    templates_dir = os.path.join(app_dir, "templates")
    if os.path.isdir(templates_dir):
        for tname in os.listdir(templates_dir):
            tpath = os.path.join(templates_dir, tname)
            if os.path.isfile(tpath):
                with open(tpath, "r", encoding="utf-8") as f:
                    content = f.read()
                tree_items.append({"path": f"app/templates/{tname}", "mode": "100644", "type": "blob", "content": content})

    # 3. Konfigurációs fájlok
    for cname in ["Dockerfile", "docker-compose.yml", "requirements.txt", ".gitignore"]:
        cpath = os.path.join(project_dir, cname)
        if os.path.isfile(cpath):
            with open(cpath, "r", encoding="utf-8") as f:
                content = f.read()
            tree_items.append({"path": cname, "mode": "100644", "type": "blob", "content": content})

    # 4. Generált dokumentáció, sémák és AI promptok
    for search_docs in [os.path.join(project_dir, "docs"), os.path.join(app_dir, "docs")]:
        if os.path.isdir(search_docs):
            for dname in os.listdir(search_docs):
                dpath = os.path.join(search_docs, dname)
                if os.path.isfile(dpath):
                    with open(dpath, "r", encoding="utf-8") as f:
                        content = f.read()
                    if f"docs/{dname}" not in [x["path"] for x in tree_items]:
                        tree_items.append({"path": f"docs/{dname}", "mode": "100644", "type": "blob", "content": content})

    tree_post_url = f"https://api.github.com/repos/{repo}/git/trees"
    status, r_tree = _request(tree_post_url, "POST", token, data={"base_tree": base_tree_sha, "tree": tree_items})
    if status != 201 or not isinstance(r_tree, dict):
        return False, f"Git tree hiba: {r_tree}"
    new_tree_sha = r_tree["sha"]

    commit_msg = f"v{new_version}"
    if custom_message.strip():
        commit_msg += f" - {custom_message.strip()}"
    else:
        commit_msg += " - Teljes rendszer mentés és dokumentáció frissítés"

    commit_post_url = f"https://api.github.com/repos/{repo}/git/commits"
    commit_payload = {"message": commit_msg, "tree": new_tree_sha, "parents": [latest_commit_sha]}
    status, r_new_commit = _request(commit_post_url, "POST", token, data=commit_payload)
    if status != 201 or not isinstance(r_new_commit, dict):
        return False, f"Git commit hiba: {r_new_commit}"
    new_commit_sha = r_new_commit["sha"]

    # Ág frissítése a helyes endpointtal (/git/refs/heads/...) és force: True opcióval
    status, r_update_ref = _request(ref_url, "PATCH", token, data={"sha": new_commit_sha, "force": True})
    if status != 200:
        return False, f"Branch frissítési hiba: {r_update_ref}"

    try:
        tag_ref_url = f"https://api.github.com/repos/{repo}/git/refs"
        _request(tag_ref_url, "POST", token, data={"ref": f"refs/tags/v{new_version}", "sha": new_commit_sha})
    except Exception:
        pass

    return True, f"Sikeres publikáció a GitHubra! Verzió: v{new_version} (Commit: {new_commit_sha[:7]})"
