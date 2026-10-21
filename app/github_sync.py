import urllib.request
import urllib.error
import json
import base64
import os

def gh_req(url, token, method="GET", data=None):
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
            return True, json.loads(resp_body) if resp_body else {}
    except urllib.error.HTTPError as e:
        raw_body = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw_body)
            err_msg = parsed.get("message", raw_body)
        except Exception:
            err_msg = raw_body

        if e.code == 401:
            return False, f"401: Hibás vagy lejárt GitHub PAT token! ({err_msg})"
        elif e.code == 403:
            return False, f"403: Nincs írási (Push) joga a tokennek! (Contents: Read and write szükséges) ({err_msg})"
        elif e.code == 404:
            return False, f"404: A repó vagy az ág nem található, vagy nincs írási hozzáférés! ({err_msg})"
        elif e.code == 422:
            return False, f"422: Feldolgozási hiba: {err_msg}"
        return False, f"HTTP {e.code}: {err_msg}"
    except Exception as e:
        return False, f"Hálózati hiba: {str(e)}"

def test_github_connection(repo, token):
    ok, res = gh_req(f"https://api.github.com/repos/{repo}", token)
    if ok:
        perms = res.get("permissions", {})
        push_ok = perms.get("push", False)
        msg = f"Sikeres kapcsolat: {res.get('full_name')}"
        if not push_ok:
            msg += "\n⚠️ FIGYELEM: A tokennek CSAK OLVASÁSI joga van! Íráshoz adjon 'repo' vagy 'Contents: Read and write' jogosultságot a GitHubon!"
        else:
            msg += "\n✅ Írási jogosultság rendben!"
        return True, msg
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
    print(f"[GitHub Push] Indítás -> Repó: {repo}, Ág: {branch}")
    
    # 1. Ág lekérése
    ok, branch_info = gh_req(f"{base_url}/branches/{branch}", token)
    if not ok:
        print(f"[GitHub Push] Hiba az ág lekérésekor: {branch_info}")
        return False, f"Ág hiba: {branch_info}"
        
    latest_sha = branch_info['commit']['sha']
    base_tree_sha = branch_info['commit']['commit']['tree']['sha']
    print(f"[GitHub Push] Bázis commit: {latest_sha[:7]}, Bázis fa: {base_tree_sha[:7]}")

    # 2. Fájlok összeszedése
    current_dir = os.path.dirname(os.path.abspath(__file__))
    files_to_push = []
    for fname in os.listdir(current_dir):
        if fname.endswith(".py"):
            files_to_push.append((f"app/{fname}", os.path.join(current_dir, fname)))

    parent_dir = os.path.dirname(current_dir)
    for rname in ["Dockerfile", "docker-compose.yml", "requirements.txt", ".gitignore", ".env.example"]:
        p_path = os.path.join(parent_dir, rname)
        c_path = os.path.join(current_dir, rname)
        if os.path.isfile(p_path): files_to_push.append((rname, p_path))
        elif os.path.isfile(c_path): files_to_push.append((rname, c_path))

    print(f"[GitHub Push] Összegyűjtve: {len(files_to_push)} db fájl feltöltésre")

    # 3. Fájlok küldése blobként
    tree_items = []
    for repo_path, local_path in files_to_push:
        try:
            with open(local_path, "rb") as f:
                content = f.read()
            blob_data = {"content": base64.b64encode(content).decode("utf-8"), "encoding": "base64"}
            ok, b_res = gh_req(f"{base_url}/git/blobs", token, method="POST", data=blob_data)
            if not ok:
                print(f"[GitHub Push] Hiba a blob feltöltésnél ({repo_path}): {b_res}")
                return False, f"Blob hiba ({repo_path}): {b_res}"
            tree_items.append({"path": repo_path, "mode": "100644", "type": "blob", "sha": b_res["sha"]})
        except Exception as e:
            return False, f"Fájl olvasási hiba ({repo_path}): {str(e)}"

    # 4. Fa létrehozása
    ok, new_tree = gh_req(f"{base_url}/git/trees", token, method="POST", data={"base_tree": base_tree_sha, "tree": tree_items})
    if not ok:
        print(f"[GitHub Push] Hiba a fa létrehozásakor: {new_tree}")
        return False, f"Tree hiba: {new_tree}"

    # 5. Commit létrehozása
    msg = f"v{version_str} - {custom_msg}" if custom_msg else f"v{version_str} - Automatikus mentés"
    commit_payload = {"message": msg, "tree": new_tree["sha"], "parents": [latest_sha]}
    ok, new_commit = gh_req(f"{base_url}/git/commits", token, method="POST", data=commit_payload)
    if not ok:
        print(f"[GitHub Push] Hiba a commit létrehozásakor: {new_commit}")
        return False, f"Commit hiba: {new_commit}"

    # 6. Branch mutató frissítése (PATCH)
    ref_payload = {"sha": new_commit["sha"], "force": True}
    ok, ref_update = gh_req(f"{base_url}/git/refs/heads/{branch}", token, method="PATCH", data=ref_payload)
    if not ok:
        print(f"[GitHub Push] Hiba az ág frissítésekor: {ref_update}")
        return False, f"Ág frissítés hiba: {ref_update}"

    print(f"[GitHub Push] SIKER! Új commit: {new_commit['sha'][:7]}")
    return True, f"Sikeres feltöltés! Új commit: {new_commit['sha'][:7]} (v{version_str})"
