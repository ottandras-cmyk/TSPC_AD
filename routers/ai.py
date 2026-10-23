import threading
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from database import get_db
from auth import verify_session_token, COOKIE_NAME
from ai_assistant import (
    fetch_ollama_models, ask_ollama, switch_active_model,
    start_model_update, check_all_models_updates, update_tasks
)
from telemetry import log_web_activity

router = APIRouter(prefix="/api/ai", tags=["ai"])

def get_current_user(request: Request):
    user, _ = verify_session_token(request.cookies.get(COOKIE_NAME))
    return user

@router.get("/models")
def get_ai_models(request: Request, db: Session = Depends(get_db)):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    return fetch_ollama_models(db)

@router.get("/check-updates")
def check_updates_endpoint(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return JSONResponse(status_code=401, content={})
    res = check_all_models_updates(db)
    log_web_activity(db, request, user, "AI_MODELL_FRISSÍTÉS_ELLENŐRZÉS", f"{len(res)} modell ellenőrizve a registry-ben", "SIKERES")
    return {"updates": res}

@router.post("/update-model")
async def update_model_endpoint(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return JSONResponse(status_code=401, content={})
    data = await request.json()
    model = data.get("model")
    if not model: return JSONResponse(status_code=400, content={"error": "Nincs modellnév!"})
    res = start_model_update(db, model)
    log_web_activity(db, request, user, "AI_MODELL_FRISSÍTÉS_INDÍTVA", f"Modell: {model}", "SIKERES")
    return res

@router.get("/update-tasks")
def get_update_tasks_endpoint(request: Request):
    if not get_current_user(request): return JSONResponse(status_code=401, content={})
    return {"tasks": update_tasks}

@router.post("/switch-model")
async def switch_ai_model(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return JSONResponse(status_code=401, content={})
    data = await request.json()
    model = data.get("model")
    if not model: return JSONResponse(status_code=400, content={"error": "Nincs modell megadva!"})
    res = switch_active_model(db, model)
    log_web_activity(db, request, user, "AI_MODELL_VÁLTÁS", f"Aktív modell memóriába töltve: {model}", "SIKERES")
    return res

@router.post("/ask")
async def ask_ai_endpoint(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return JSONResponse(status_code=401, content={})
    data = await request.json()
    res = ask_ollama(db, data.get("model"), data.get("prompt"))
    log_web_activity(db, request, user, "AI_LEKÉRDEZÉS", f"Modell: {data.get('model')}", "SIKERES" if res.get("status") == "SUCCESS" else "HIBA")
    return res
