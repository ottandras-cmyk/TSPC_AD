import json
import urllib.request
import urllib.error
import os
import re
import threading
from datetime import datetime, timezone
from sqlalchemy import or_, desc
import models
from config_manager import get_setting, update_setting
from telemetry import get_system_deep_dossier

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

DEVELOPER_KEYWORDS = [
    "coder", "code", "deepseek-coder", "qwen2.5-coder", "qwen-coder", "dev", "starcoder", "qwen3.5", "qwen2.5"
]

update_tasks = {}

def is_developer_model(model_name: str) -> bool:
    if not model_name: return False
    m_lower = model_name.lower()
    return any(k in m_lower for k in DEVELOPER_KEYWORDS)

def stem_hungarian_word(word: str) -> list:
    w = word.lower().strip("?,.!:;\"'()[]{}")
    variants = {w}
    suffixes = [
        "ról", "ről", "nak", "nek", "val", "vel", "ban", "ben",
        "hoz", "hez", "höz", "ba", "be", "ra", "re", "nál", "nél",
        "tól", "től", "ul", "ül", "t", "ot", "et", "öt", "at"
    ]
    for s in suffixes:
        if w.endswith(s) and len(w) - len(s) >= 3:
            stem = w[:-len(s)]
            if stem.endswith("é"): stem = stem[:-1] + "e"
            elif stem.endswith("á"): stem = stem[:-1] + "a"
            elif stem.endswith("ó"): stem = stem[:-1] + "o"
            elif stem.endswith("ő"): stem = stem[:-1] + "ö"
            variants.add(stem)
            break
    return list(variants)

def search_ad_entities_for_prompt(db, prompt: str) -> str:
    if not prompt: return ""
    clean_prompt = prompt.replace("?", " ").replace("!", " ").replace(".", " ").replace(",", " ").replace(":", " ")
    tokens = [w.strip() for w in clean_prompt.split() if len(w.strip()) >= 3]

    stopwords = {
        "mit", "tudsz", "mondani", "mondj", "róla", "rola", "kik", "kicsoda", "hogy", "vagy",
        "volt", "neve", "nevű", "nevu", "felhasználó", "felhasznalo", "csoport", "fiók", "fiok",
        "rendszer", "rendszerben", "keresem", "érdekel", "erdekel", "listázd", "listazd", "mutasd"
    }
    
    search_terms = set()
    for t in tokens:
        if t.lower() not in stopwords:
            for variant in stem_hungarian_word(t):
                if len(variant) >= 3 and variant not in stopwords:
                    search_terms.add(variant)

    user_filters = []
    group_filters = []
    for term in search_terms:
        pat = f"%{term}%"
        user_filters.append(models.ADUser.sam_account_name.ilike(pat))
        user_filters.append(models.ADUser.display_name.ilike(pat))
        user_filters.append(models.ADUser.mail.ilike(pat))
        user_filters.append(models.ADUser.title.ilike(pat))
        group_filters.append(models.ADGroup.sam_account_name.ilike(pat))
        group_filters.append(models.ADGroup.description.ilike(pat))

    p_lower = prompt.lower()
    if "távoz" in p_lower or "tavoz" in p_lower:
        user_filters.append(models.ADUser.user_status.ilike("%Távozottak%"))
    if "küls" in p_lower or "kuls" in p_lower:
        user_filters.append(models.ADUser.user_status.ilike("%Külsős%"))
    if "hosszú" in p_lower or "hosszu" in p_lower:
        user_filters.append(models.ADUser.user_status.ilike("%Hosszútávú%"))
    if "letilt" in p_lower or "inaktív" in p_lower or "inaktiv" in p_lower:
        user_filters.append(models.ADUser.is_enabled == False)

    matched_users = []
    matched_groups = []
    if user_filters:
        matched_users = db.query(models.ADUser).filter(or_(*user_filters)).limit(8).all()
    if group_filters:
        matched_groups = db.query(models.ADGroup).filter(or_(*group_filters)).limit(6).all()

    sections = []
    if matched_users:
        sections.append("### [ADATBÁZISBÓL KIKERESETT RELEVÁNS AD FELHASZNÁLÓK]:")
        for u in matched_users:
            grps = [g.sam_account_name for g in u.groups]
            last_logon = u.last_logon_date.strftime("%Y-%m-%d %H:%M") if u.last_logon_date else "Nincs adat / Nem lépett be"
            created = u.when_created.strftime("%Y-%m-%d %H:%M") if u.when_created else "-"
            changed = u.when_changed.strftime("%Y-%m-%d %H:%M") if u.when_changed else "-"
            
            u_logs = db.query(models.ADAuditLog)\
                .filter(models.ADAuditLog.entity_name.ilike(u.sam_account_name))\
                .order_by(desc(models.ADAuditLog.timestamp))\
                .limit(10).all()

            u_lines = [
                f"👤 Név: {u.display_name} (Azonosító/SAM: {u.sam_account_name})",
                f"  - Email cím: {u.mail or 'Nincs megadva'}",
                f"  - Státusz / Besorolás: {u.user_status} ({'Aktív, engedélyezve' if u.is_enabled else 'Letiltva'})",
                f"  - Beosztás / Titulus: {u.title or 'Nincs megadva'}",
                f"  - Szervezeti egység: Részleg: {u.department or '-'} | Cég: {u.company or '-'} | Iroda: {u.office or '-'}",
                f"  - Telefonszámok: {u.telephone_number or '-'} | Mobil: {u.mobile or '-'}",
                f"  - Adatforrás: {u.source_ref} ({u.source_type})",
                f"  - Utolsó belépés dátuma: {last_logon}",
                f"  - Létrehozva: {created} | Utolsó módosítás: {changed}",
                f"  - OU útvonal: {u.ou_path or '-'}",
                f"  - Aktuális csoporttagságok ({len(grps)} db): {', '.join(grps) if grps else 'Nincs csoporttagsága'}"
            ]
            if u_logs:
                u_lines.append("  - Rögzített változástörténet (Audit napló):")
                for al in u_logs:
                    ts = al.timestamp.strftime("%Y-%m-%d %H:%M") if al.timestamp else "-"
                    u_lines.append(f"    * {ts}: [{al.change_type}] {al.details} (Forrás: {al.source_ref})")
            sections.append("\n".join(u_lines))

    if matched_groups:
        sections.append("### [ADATBÁZISBÓL KIKERESETT RELEVÁNS AD CSOPORTOK]:")
        for g in matched_groups:
            members = [u.sam_account_name for u in g.members]
            g_lines = [
                f"👥 Csoport neve: {g.sam_account_name}",
                f"  - Típus: {g.group_type or 'Ismeretlen'}",
                f"  - Leírás: {g.description or 'Nincs leírás'}",
                f"  - Forrás: {g.source_ref} ({g.source_type})",
                f"  - Tagok száma: {len(members)} fő",
                f"  - Tagok listája: {', '.join(members[:40]) if members else 'A csoport jelenleg üres'}" + (f" (+még {len(members)-40} fő...)" if len(members) > 40 else "")
            ]
            sections.append("\n".join(g_lines))

    return "\n\n".join(sections)

def get_running_ollama_models(db) -> list:
    url = get_setting(db, "OLLAMA_URL", "http://ollama:11434")
    try:
        req = urllib.request.Request(f"{url}/api/ps", headers={"User-Agent": "AD-Tracker"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("models", [])
    except Exception:
        return []

def unload_model(db, model_name: str) -> bool:
    url = get_setting(db, "OLLAMA_URL", "http://ollama:11434")
    try:
        payload = json.dumps({"model": model_name, "keep_alive": 0}).encode("utf-8")
        req = urllib.request.Request(f"{url}/api/generate", data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return True
    except Exception:
        return False

def switch_active_model(db, target_model: str) -> dict:
    running = get_running_ollama_models(db)
    unloaded = []
    for m in running:
        name = m.get("name") or m.get("model")
        if name and name != target_model:
            if unload_model(db, name):
                unloaded.append(name)
    url = get_setting(db, "OLLAMA_URL", "http://ollama:11434")
    try:
        payload = json.dumps({"model": target_model, "keep_alive": "60m"}).encode("utf-8")
        req = urllib.request.Request(f"{url}/api/generate", data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=20) as resp:
            pass
        return {"status": "SUCCESS", "active_model": target_model, "unloaded": unloaded}
    except Exception as e:
        return {"status": "PARTIAL", "active_model": target_model, "unloaded": unloaded, "error": str(e)}

def get_remote_registry_digest(model_name: str) -> str:
    if ":" in model_name:
        name_part, tag = model_name.split(":", 1)
    else:
        name_part, tag = model_name, "latest"
    repo = name_part if "/" in name_part else f"library/{name_part}"
    manifest_url = f"https://registry.ollama.ai/v2/{repo}/manifests/{tag}"
    headers = {
        "Accept": "application/vnd.docker.distribution.manifest.v2+json, application/vnd.oci.image.manifest.v1+json",
        "User-Agent": "ollama/0.1.0"
    }
    try:
        req = urllib.request.Request(manifest_url, headers=headers)
        with urllib.request.urlopen(req, timeout=6) as resp:
            digest = resp.headers.get("Docker-Content-Digest")
            if digest: return digest
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("config", {}).get("digest")
    except urllib.error.HTTPError as e:
        if e.code == 401:
            auth_header = e.headers.get("Www-Authenticate", "")
            realm_m = re.search(r'realm="([^"]+)"', auth_header)
            service_m = re.search(r'service="([^"]+)"', auth_header)
            scope_m = re.search(r'scope="([^"]+)"', auth_header)
            if realm_m and service_m:
                tok_url = f"{realm_m.group(1)}?service={service_m.group(1)}"
                if scope_m: tok_url += f"&scope={scope_m.group(1)}"
                try:
                    req_tok = urllib.request.Request(tok_url, headers={"User-Agent": "ollama/0.1.0"})
                    with urllib.request.urlopen(req_tok, timeout=6) as r_tok:
                        token = json.loads(r_tok.read().decode("utf-8")).get("token")
                    headers["Authorization"] = f"Bearer {token}"
                    req2 = urllib.request.Request(manifest_url, headers=headers)
                    with urllib.request.urlopen(req2, timeout=6) as resp2:
                        digest = resp2.headers.get("Docker-Content-Digest")
                        if digest: return digest
                        data2 = json.loads(resp2.read().decode("utf-8"))
                        return data2.get("config", {}).get("digest")
                except Exception: pass
    except Exception: pass
    return None

def check_all_models_updates(db) -> list:
    url = get_setting(db, "OLLAMA_URL", "http://ollama:11434")
    results = []
    try:
        req = urllib.request.Request(f"{url}/api/tags", headers={"User-Agent": "AD-Tracker"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            models_data = json.loads(resp.read().decode("utf-8")).get("models", [])
            
        for m in models_data:
            name = m.get("name")
            local_digest = m.get("digest", "")
            remote_digest = get_remote_registry_digest(name)
            
            if not remote_digest:
                status = "UNKNOWN"
                status_text = "Nem ellenőrizhető (Egyéni vagy nincs kapcsolat)"
            elif remote_digest == local_digest:
                status = "UP_TO_DATE"
                status_text = "Naprakész (Legfrissebb)"
            else:
                status = "UPDATE_AVAILABLE"
                status_text = "Újabb verzió érhető el a registryben!"
                
            results.append({
                "name": name,
                "size_gb": round(m.get("size", 0) / (1024**3), 2),
                "modified_at": m.get("modified_at", "-")[:19].replace("T", " "),
                "local_digest": local_digest[:16] + "..." if local_digest else "-",
                "remote_digest": remote_digest[:16] + "..." if remote_digest else "-",
                "status": status,
                "status_text": status_text
            })
    except Exception: pass
    return results

def pull_ollama_model_worker(db, model_name: str):
    url = get_setting(db, "OLLAMA_URL", "http://ollama:11434")
    update_tasks[model_name] = {"status": "RUNNING", "message": "Letöltés folyamatban..."}
    try:
        payload = json.dumps({"name": model_name, "stream": False}).encode("utf-8")
        req = urllib.request.Request(f"{url}/api/pull", data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=1800) as resp:
            update_tasks[model_name] = {"status": "SUCCESS", "message": f"{model_name} frissítve!"}
    except Exception as e:
        update_tasks[model_name] = {"status": "ERROR", "message": f"Hiba: {str(e)}"}

def start_model_update(db, model_name: str) -> dict:
    if model_name in update_tasks and update_tasks[model_name]["status"] == "RUNNING":
        return {"status": "ALREADY_RUNNING", "message": "A modell frissítése folyamatban van."}
    threading.Thread(target=pull_ollama_model_worker, args=(db, model_name)).start()
    return {"status": "STARTED", "message": f"{model_name} frissítése elindult a háttérben."}

def fetch_ollama_models(db) -> dict:
    url = get_setting(db, "OLLAMA_URL", "http://ollama:11434")
    models_list = []
    running = get_running_ollama_models(db)
    running_names = [m.get("name") or m.get("model") for m in running]
    try:
        req = urllib.request.Request(f"{url}/api/tags", headers={"User-Agent": "AD-Tracker"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for m in data.get("models", []):
                name = m.get("name")
                is_dev = is_developer_model(name)
                is_active = name in running_names
                models_list.append({
                    "name": name,
                    "size_gb": round(m.get("size", 0) / (1024**3), 2),
                    "is_developer": is_dev,
                    "tag": "Fejlesztői funkció (Teljes Kódbázis & Séma)" if is_dev else "Általános Asszisztens",
                    "is_active": is_active,
                    "update_task": update_tasks.get(name)
                })
    except Exception: pass
    return {
        "models": models_list,
        "running_models": running_names,
        "active_loaded_model": running_names[0] if running_names else None
    }

def get_codebase_deep_dossier() -> str:
    sections = []
    sections.append("=== AD TRACKER TELJES FORRÁSKÓD, SÉMA ÉS DOKUMENTÁCIÓS ELEMZŐ KÖRNYEZET ===")

    if os.path.isdir(DOCS_DIR):
        for doc_file in ["DATABASE_SCHEMA.md", "LLM_SKILL_PROMPT.md", "API_DOCUMENTATION.md", "SYSTEM_REBUILD_PROMPT.md"]:
            doc_path = os.path.join(DOCS_DIR, doc_file)
            if os.path.isfile(doc_path):
                try:
                    with open(doc_path, "r", encoding="utf-8") as f:
                        sections.append(f"### [DOKUMENTÁCIÓS FORRÁS: docs/{doc_file}]\n" + f.read())
                except Exception: pass

    models_path = os.path.join(APP_DIR, "models.py")
    if os.path.isfile(models_path):
        try:
            with open(models_path, "r", encoding="utf-8") as f:
                sections.append("### [FORRÁS: app/models.py - SQLAlchemy Adatbázis Sémák]\n```python\n" + f.read() + "\n```")
        except Exception: pass

    routers_dir = os.path.join(APP_DIR, "routers")
    if os.path.isdir(routers_dir):
        for r_file in sorted(os.listdir(routers_dir)):
            if r_file.endswith(".py"):
                r_path = os.path.join(routers_dir, r_file)
                try:
                    with open(r_path, "r", encoding="utf-8") as f:
                        sections.append(f"### [FORRÁS: app/routers/{r_file} - API Router]\n```python\n" + f.read() + "\n```")
                except Exception: pass

    core_files = [
        "main.py", "sync_engine.py", "ad_analytics.py", "telemetry.py",
        "auth.py", "history_importer.py", "backup_manager.py", "config_manager.py", "doc_generator.py"
    ]
    for c_file in core_files:
        c_path = os.path.join(APP_DIR, c_file)
        if os.path.isfile(c_path):
            try:
                with open(c_path, "r", encoding="utf-8") as f:
                    sections.append(f"### [FORRÁS: app/{c_file} - Üzleti Logika]\n```python\n" + f.read() + "\n```")
            except Exception: pass

    tabs_dir = os.path.join(APP_DIR, "templates", "tabs")
    if os.path.isdir(tabs_dir):
        for t_file in sorted(os.listdir(tabs_dir)):
            if t_file.endswith(".html"):
                t_path = os.path.join(tabs_dir, t_file)
                try:
                    with open(t_path, "r", encoding="utf-8") as f:
                        sections.append(f"### [FORRÁS: app/templates/tabs/{t_file} - HTML Mikrosablon]\n```html\n" + f.read() + "\n```")
                except Exception: pass

    ui_js = os.path.join(APP_DIR, "static", "js", "ui-core.js")
    if os.path.isfile(ui_js):
        try:
            with open(ui_js, "r", encoding="utf-8") as f:
                sections.append(f"### [FORRÁS: app/static/js/ui-core.js - Kliensoldali Logika]\n```javascript\n" + f.read() + "\n```")
        except Exception: pass

    return "\n\n".join(sections)

def track_tokens(db, prompt_tokens: int, eval_tokens: int):
    try:
        p_curr = int(get_setting(db, "LLM_TOKENS_PROMPT", "0"))
        e_curr = int(get_setting(db, "LLM_TOKENS_EVAL", "0"))
        tot_curr = int(get_setting(db, "LLM_TOKENS_TOTAL", "0"))
        update_setting(db, "LLM_TOKENS_PROMPT", str(p_curr + prompt_tokens))
        update_setting(db, "LLM_TOKENS_EVAL", str(e_curr + eval_tokens))
        update_setting(db, "LLM_TOKENS_TOTAL", str(tot_curr + prompt_tokens + eval_tokens))
    except Exception: pass

def ask_ollama(db, model: str, prompt: str) -> dict:
    url = get_setting(db, "OLLAMA_URL", "http://ollama:11434")
    switch_active_model(db, model)
    is_dev = is_developer_model(model)
    
    ad_entity_data = search_ad_entities_for_prompt(db, prompt)
    system_dossier = get_system_deep_dossier(db)
    
    if is_dev:
        codebase_dossier = get_codebase_deep_dossier()
        full_prompt = f"""Te vagy az AD Tracker vezető szoftverfejlesztője és kódvizsgáló AI szakértője.
Rendelkezel az alkalmazás TELJES ÉLŐ FORRÁSKÓDJÁVAL, GENERÁLT DOKUMENTÁCIÓIVAL (docs/DATABASE_SCHEMA.md, docs/LLM_SKILL_PROMPT.md, docs/API_DOCUMENTATION.md), valamint az élő telemetriai és jogosultsági adatokkal.

---
[KIKERESETT AD SZEMÉLYEK / CSOPORTOK]:
{ad_entity_data if ad_entity_data else "A kérdés nem tartalmazott közvetlenül beazonosítható személynevet vagy csoportot."}
---

---
[AD TRACKER TELJES FORRÁSKÓD, SÉMÁK ÉS DOKUMENTÁCIÓ]:
{codebase_dossier}
---

[ÉLŐ RENDSZERÁLLAPOT ÉS AUDIT DOSSZIÉ]:
{system_dossier}
---

[FEJLESZTŐI KÉRDÉS / UTASÍTÁS]:
{prompt}

Válaszolj mint vezető mérnök magyar nyelven!"""
        num_ctx = 16384
        request_timeout = 600
    else:
        full_prompt = f"""Te vagy az AD Tracker Rendszer- és Biztonsági Asszisztense.
Rendelkezel az élő rendszerállapottal, a keresett Active Directory fiókok és csoportok teljes adatlapjával, a jogosultság-változásokkal és a belépési naplókkal.

---
[ADATBÁZISBÓL KÖZVETLENÜL KIKERESETT AD ADATOK A KÉRDÉSHEZ]:
{ad_entity_data if ad_entity_data else "A kérdés nem egy konkrét személyre vagy csoportra vonatkozott, hanem általános rendszerszintű kérdés."}
---

---
[RENDSZER DOSSZIÉ ÉS STATISZTIKÁK]:
{system_dossier}
---

[KÉRDÉS]:
{prompt}

Válaszolj részletesen és pontosan a fenti adatbázis-találatok alapján magyar nyelven! Ha konkrét személyről kérdeztek, ismertesd a nevét, beosztását, email címét, státuszát, csoporttagságait és a történetét!"""
        num_ctx = 8192
        request_timeout = 180

    payload = json.dumps({
        "model": model,
        "prompt": full_prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_ctx": num_ctx
        }
    }).encode("utf-8")
    
    req = urllib.request.Request(f"{url}/api/generate", data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=request_timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            p_tokens = data.get("prompt_eval_count", 0)
            e_tokens = data.get("eval_count", 0)
            if p_tokens or e_tokens:
                track_tokens(db, p_tokens, e_tokens)
            return {"status": "SUCCESS", "response": data.get("response", "")}
    except Exception as e:
        return {"status": "ERROR", "message": f"Időtúllépés vagy hiba ({str(e)})"}
