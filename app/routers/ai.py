import logging
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from database import get_db
from auth import COOKIE_NAME, verify_session_token
from services.ai_service import ai_service

logger = logging.getLogger("ai_router")
router = APIRouter(prefix="/api/ai", tags=["ai"])

def safe_get_user(request: Request):
    try:
        token = request.cookies.get(COOKIE_NAME)
        if not token:
            return None
        res = verify_session_token(token)
        if isinstance(res, tuple):
            return res[0]
        if isinstance(res, str):
            return res
        if res and hasattr(res, "username"):
            return res.username
        return None
    except Exception as e:
        logger.warning("Érvénytelen munkamenet token az AI végponton: %s", str(e))
        return None

@router.get("/models")
def get_ai_models(request: Request):
    if not safe_get_user(request):
        return JSONResponse(status_code=401, content={"status": "ERROR", "message": "Nincs bejelentkezve"})
    return ai_service.get_models()

@router.post("/models/pull")
async def pull_model_endpoint(request: Request):
    if not safe_get_user(request):
        return JSONResponse(status_code=401, content={"status": "ERROR", "message": "Nincs bejelentkezve"})
    try:
        data = await request.json()
        model_name = data.get("model_name", "").strip()
        return ai_service.pull_model(model_name)
    except Exception as e:
        return {"status": "ERROR", "message": f"Hiba a letöltés során: {str(e)}"}

@router.post("/ask")
@router.post("/chat")
async def chat_with_ai(request: Request, db: Session = Depends(get_db)):
    if not safe_get_user(request):
        return JSONResponse(status_code=401, content={"status": "ERROR", "message": "Nincs bejelentkezve"})
    try:
        data = await request.json()
        prompt = (data.get("prompt") or "").strip()
        model = data.get("model") or "llama3:8b"
        search_codebase = bool(data.get("search_codebase", True))

        if not prompt:
            return {"status": "ERROR", "message": "Kérjük, írjon be egy kérdést!"}

        return ai_service.execute_chat(db, prompt, model, search_codebase)
    except Exception as e:
        return {"status": "ERROR", "message": f"Hiba az AI válasz generálásakor: {str(e)}"}
