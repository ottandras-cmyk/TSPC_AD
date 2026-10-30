import os
import json
import urllib.request
import urllib.error
from ai_assistant import stem_hungarian_word, get_system_deep_dossier
from config_manager import get_setting
from sqlalchemy.orm import Session

class AiService:
    def __init__(self, db: Session = None):
        self.db = db

    def get_ollama_url(self, db: Session = None) -> str:
        url = get_setting(db or self.db, "OLLAMA_URL") or get_setting(db or self.db, "OLLAMA_HOST") or "http://ollama:11434"
        return str(url).rstrip("/")

    def get_system_dossier(self, db: Session = None) -> dict:
        return get_system_deep_dossier(db or self.db)

    @staticmethod
    def stem_query(word: str) -> str:
        return stem_hungarian_word(word)

    def get_models(self) -> dict:
        url = self.get_ollama_url()
        try:
            req = urllib.request.Request(f"{url}/api/tags", headers={"User-Agent": "ADTracker-AI"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode())
                models = [{"name": m.get("name"), "size": f"{round(m.get('size', 0)/(1024**3), 1)} GB"} for m in data.get("models", [])]
                if models:
                    return {"status": "SUCCESS", "models": models}
        except Exception:
            pass

        return {
            "status": "SUCCESS",
            "models": [
                {"name": "llama3:8b", "size": "4.7 GB"},
                {"name": "mistral:latest", "size": "4.1 GB"},
                {"name": "qwen2.5:7b", "size": "4.5 GB"}
            ],
            "note": "Alapertelmezett modellek"
        }

    def pull_model(self, model_name: str) -> dict:
        if not model_name:
            return {"status": "ERROR", "message": "Hianyzo modellnev"}
        url = self.get_ollama_url()
        try:
            payload = json.dumps({"name": model_name, "stream": False}).encode("utf-8")
            req = urllib.request.Request(f"{url}/api/pull", data=payload, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=120) as resp:
                return {"status": "SUCCESS", "message": f"{model_name} letoltese kesz"}
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}

    def execute_chat(self, db: Session, prompt: str, model: str = "llama3:8b", search_codebase: bool = True) -> dict:
        url = self.get_ollama_url(db)
        context_str = ""
        if search_codebase:
            try:
                dossier = self.get_system_dossier(db)
                context_str = dossier.get("summary_prompt_context", "")
            except Exception:
                pass

        full_prompt = (
            "Te vagy a TSPC AD Tracker & Rendszerkozpont AI asszisztense.\n"
            f"[DOSSZIE]:\n{context_str}\n\n"
            f"[KERDES]:\n{prompt}\n\n"
            "Valaszolj tomoren magyarul."
        )

        payload = json.dumps({
            "model": model or "llama3:8b",
            "prompt": full_prompt,
            "stream": False,
            "options": {"temperature": 0.3}
        }).encode("utf-8")

        req = urllib.request.Request(f"{url}/api/generate", data=payload, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {"status": "SUCCESS", "response": data.get("response", "")}
        except Exception as e:
            return {"status": "SUCCESS", "response": f"Ollama nem erheto el ({e}). Kontextus: {context_str}"}

    def __call__(self, db: Session = None):
        return AiService(db)

ai_service = AiService()
