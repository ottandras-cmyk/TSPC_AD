import threading
from database import SessionLocal
from config_manager import init_default_settings
from scheduler.registry import setup_and_start_scheduler

def startup_worker():
    db = SessionLocal()
    try:
        from telemetry import collect_and_save_telemetry, log_web_activity
        collect_and_save_telemetry(db)
        log_web_activity(db, None, "SYSTEM", "RENDSZER_INDULÁS", "AD Tracker szerver sikeresen elindult", "SIKERES")
    except Exception:
        pass
    finally:
        db.close()

def on_startup():
    db_init = SessionLocal()
    try:
        init_default_settings(db_init)
    finally:
        db_init.close()
    
    setup_and_start_scheduler()
    threading.Thread(target=startup_worker, daemon=True).start()
