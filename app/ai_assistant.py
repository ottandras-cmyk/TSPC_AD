import json
import urllib.request
import urllib.error
from config_manager import get_setting, update_setting
from telemetry import get_system_deep_dossier

def track_tokens(db, prompt_tokens: int, eval_tokens: int):
    try:
        p_curr = int(get_setting(db, "LLM_TOKENS_PROMPT", "0"))
        e_curr = int(get_setting(db, "LLM_TOKENS_EVAL", "0"))
        tot_curr = int(get_setting(db, "LLM_TOKENS_TOTAL", "0"))
        update_setting(db, "LLM_TOKENS_PROMPT", str(p_curr + prompt_tokens))
        update_setting(db, "LLM_TOKENS_EVAL", str(e_curr + eval_tokens))
        update_setting(db, "LLM_TOKENS_TOTAL", str(tot_curr + prompt_tokens + eval_tokens))
    except Exception:
        pass

def fetch_ollama_models(db) -> list:
    url = get_setting(db, "OLLAMA_URL", "http://ollama:11434")
    try:
        req = urllib.request.Request(f"{url}/api/tags", headers={"User-Agent": "AD-Tracker"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return [m.get("name") for m in data.get("models", [])]
    except Exception:
        return []

def ask_ollama(db, model: str, prompt: str) -> dict:
    url = get_setting(db, "OLLAMA_URL", "http://ollama:11434")
    
    try:
        system_dossier = get_system_deep_dossier(db)
    except Exception as e:
        system_dossier = f"Dosszié hiba: {str(e)}"
        
    full_prompt = f"""Te vagy az AD Tracker teljes architektúráját, kódját, adatbázis sémáját, hardver telemetriáját és felhasználói aktivitását ismerő Vezető Rendszer- és Biztonsági Asszisztens.

Rendelkezésedre áll a rendszer TELJES ÉLŐ DOSSZIÉJA:
- Kódstruktúra, DDL sémák és specifikációk a docs/ mappából
- Hardver telemetriai szélsőértékek (minimum és maximum CPU, RAM, GPU) a pontos időpontokkal
- Esemény-korreláció: mi futott a háttérben a telemetriai csúcsok idején, és ki volt bejelentkezve
- Webes belépések statisztikája (ki, hányszor, mikor, milyen IP-ről és milyen gépről lépett be)
- Jelenleg aktív felhasználók listája
- Legfrissebb audit események és csoportváltozások

---
[RENDSZERSZINTŰ ÉLŐ ADATTÁR ÉS TELEMETRIAI DOSSZIÉ]:
{system_dossier}
---

[FELHASZNÁLÓ KÉRDÉSE]:
{prompt}

Válaszolj részletesen, szakmailag pontosan a fenti valós adatok és korrelációk alapján magyar nyelven!"""

    payload = json.dumps({
        "model": model,
        "prompt": full_prompt,
        "stream": False,
        "options": {"temperature": 0.2}
    }).encode("utf-8")
    
    req = urllib.request.Request(f"{url}/api/generate", data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            p_tokens = data.get("prompt_eval_count", 0)
            e_tokens = data.get("eval_count", 0)
            if p_tokens or e_tokens:
                track_tokens(db, p_tokens, e_tokens)
            return {"status": "SUCCESS", "response": data.get("response", "")}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}
