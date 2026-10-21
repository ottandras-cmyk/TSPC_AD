import urllib.request
import urllib.error
import json
import base64
import os

def gh_req(url, token, method="GET", data=None):
    """Általános GitHub API hívó függvény részletes hibavisszajelzéssel"""
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "AD-Tracker-Sync")
    if data:
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(data).encode("utf-8")
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            resp_body = response.read().decode("utf-8")
            if not resp_body:
                return True, {}
            return True, json.loads(resp_body)
    except urllib.error.HTTPError as e:
        raw_body = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw_body)
            err_msg = parsed.get("message", raw_body)
        except Exception:
            err_msg = raw_body

        if e.code == 401:
            return False, f"Hitelesítési hiba (401): Hibás vagy lejárt GitHub PAT token! ({err_msg})"
        elif e.code == 403:
            return False, f"Jogosultság megtagadva (403): A tokennek nincs írási (Write) joga! Ellenőrizd a 'repo' vagy 'Contents: Read and write' beállítást! ({err_msg})"
        elif e.code == 404:
            return False, f"Nem található (404): Nem létezik a repó/ág, vagy a tokennek nincs írási hozzáférése! ({err_msg})"
        elif e.code == 422:
            return False, f"Feldolgozási hiba (422): {err_msg}"
        else:
            return False, f"HTTP {e.code} hiba: {err_msg}"
    except Exception as e:
        return False, f"Hálózati hiba: {str(e)}"

def test_github_connection(repo, token):
    ok, res = gh_req(f"https://api.github.com/repos/{repo}", token)
    if ok:
        perms = res.get("permissions", {})
        push_allowed = perms.get("push", False)
        status_msg = f"Sikeres kapcsolat a(z) {res.get('full_name')} repóhoz."
        if not push_allowed and perms:
            status_msg += "\n\n⚠️ FIGYELEM: A tokennek CSAK OLVASÁSI joga van! A kód feltöltéséhez generálj tokent 'repo' (vagy Contents: Read and write) jogosultsággal!"
        else:
            status_msg += "\n\n✅ Írási jogosultság ellenőrizve, a publikálás engedélyezett!"
        return True, status_msg
    return False, res

def get_github_commit_history(repo, token, branch):
    url = f"https://api.github.com/repos/{repo}/commits?sha={branch}&per_page=10"
    ok, res = gh_req(url, token)
    if not ok:
        return False, res
    history = []
    for c in res:
        history.append({
            "sha": c.get('sha', '')[:7],
            "message": c.get('commit', {}).get('message', ''),
            "date": c.get('commit', {}).get('author', {}).get('date', ''),
            "author": c.get('commit', {}).get('author', {}).get('name', '')
        })
    return True, history

def push_code_to_github(repo, branch, token, version_str, custom_msg=""):
    base_url = f"https://api.github.com/repos/{repo}"
    
    # 1. Ág állapotának és legfrissebb commitjának lekérése
    ok, branch_info = gh_req(f"{base_url}/branches/{branch}", token)
    if not ok:
        ok, commits_list = gh_req(f"{base_url}/commits?sha={branch}&per_page=1", token)
        if not ok or not commits_list:
            return False, f"Nem sikerült lekérni a(z) '{branch}' ág adatait: {branch_info}"
        latest_sha = commits_list[0]['sha']
        base_tree_sha = commits_list[0]['commit']['tree']['sha']
    else:
        latest_sha = branch_info['commit']['sha']
        base_tree_sha = branch_info['commit']['commit']['tree']['sha']

    # 2. Fájlok dinamikus összegyűjtése (konténer könyvtárszerkezetétől függetlenül)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    files_to_push = []
    
    # Python modulok az app mappából
    for fname in os.listdir(current_dir):
        if fname.endswith(".py"):
            files_to_push.append((f"app/{fname}", os.path.join(current_dir, fname)))
            
    # Alapvető konfigurációk és leírók a gyökérből
    parent_dir = os.path.dirname(current_dir)
    extra_files = ["Dockerfile", "docker-compose.yml", "requirements.txt", ".gitignore", ".env.example", "README.md"]
    for rname in extra_files:
        p_path = os.path.join(parent_dir, rname)
        c_path = os.path.join(current_dir, rname)
        if os.path.isfile(p_path):
            files_to_push.append((rname, p_path))
        elif os.path.isfile(c_path):
            files_to_push.append((rname, c_path))
            
    if not files_to_push:
        return False, "Nem található feltölthető forrásfájl a szerveren!"

    # 3. Fájlok feltöltése Git Blobként
    tree_items = []
    for repo_path, local_path in files_to_push:
        try:
            with open(local_path, "rb") as f:
                content = f.read()
            blob_data = {
                "content": base64.b64encode(content).decode("utf-8"),
                "encoding": "base64"
            }
            ok, blob_resp = gh_req(f"{base_url}/git/blobs", token, method="POST", data=blob_data)
            if not ok:
                return False, f"Hiba a fájl feltöltésekor ({repo_path}): {blob_resp}"
            tree_items.append({
                "path": repo_path,
                "mode": "100644",
                "type": "blob",
                "sha": blob_resp["sha"]
            })
        except Exception as e:
            return False, f"Hiba a(z) {repo_path} beolvasásakor: {str(e)}"

    # 4. Git Fa (Tree) létrehozása
    tree_payload = {
        "base_tree": base_tree_sha,
        "tree": tree_items
    }
    ok, new_tree = gh_req(f"{base_url}/git/trees", token, method="POST", data=tree_payload)
    if not ok:
        return False, f"Git Fa létrehozási hiba: {new_tree}"

    # 5. Git Commit létrehozása
    msg = f"v{version_str} - {custom_msg}" if custom_msg else f"v{version_str} - Automatikus kódmentés"
    commit_payload = {
        "message": msg,
        "tree": new_tree["sha"],
        "parents": [latest_sha]
    }
    ok, new_commit = gh_req(f"{base_url}/git/commits", token, method="POST", data=commit_payload)
    if not ok:
        return False, f"Git Commit létrehozási hiba: {new_commit}"

    # 6. Branch mutató frissítése a legújabb commitra
    ref_payload = {
        "sha": new_commit["sha"],
        "force": True
    }
    ok, ref_update = gh_req(f"{base_url}/git/refs/heads/{branch}", token, method="PATCH", data=ref_payload)
    if not ok:
        return False, f"Ág frissítési hiba: {ref_update}"

    return True, f"Sikeresen publikálva a GitHub-ra!\nCommit: {new_commit['sha'][:7]}\nVerzió: v{version_str}"
