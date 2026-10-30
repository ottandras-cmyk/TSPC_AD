from apscheduler.schedulers.background import BackgroundScheduler
from database import SessionLocal
from config_manager import get_setting

scheduler = BackgroundScheduler()

def scheduled_sync_job():
    try:
        from routers import sync
        sync.execute_sync_with_log("Ütemezett")
    except Exception: pass

def scheduled_telemetry_job():
    db = SessionLocal()
    try:
        from telemetry import collect_and_save_telemetry
        collect_and_save_telemetry(db)
    except Exception: pass
    finally: db.close()

def scheduled_ep_sync_job():
    db = SessionLocal()
    try:
        if get_setting(db, "EP_SYNC_ENABLED", "0") == "1":
            from easy_project_sync import sync_easy_project_data
            sync_easy_project_data(db, trigger_type="SCHEDULED")
    finally: db.close()

def scheduled_hd_sync_job():
    db = SessionLocal()
    try:
        if get_setting(db, "HD_SYNC_ENABLED", "0") == "1":
            from easy_project_sync import sync_helpdesk_tickets
            sync_helpdesk_tickets(db, trigger_type="SCHEDULED", target_project_id=2403)
    finally: db.close()


def scheduled_sharepoint_sync_job():
    from routers.settings import get_all_settings
    from services.sharepoint_service import sync_sharepoint_lists_to_database

    result = sync_sharepoint_lists_to_database(
        get_all_settings()["sharepoint"],
        trigger_type="SCHEDULED",
    )
    if result["status"] != "SUCCESS":
        raise RuntimeError(result["message"])


def configure_sharepoint_sync_job(enabled, interval_minutes):
    job_id = "scheduled_sharepoint_sync_job"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    if enabled and interval_minutes > 0:
        scheduler.add_job(
            scheduled_sharepoint_sync_job,
            "interval",
            minutes=interval_minutes,
            id=job_id,
            replace_existing=True,
        )


def setup_and_start_scheduler():
    db = SessionLocal()
    try:
        sync_minutes = int(get_setting(db, "SYNC_INTERVAL_MINUTES", "15"))
        ep_mins = int(get_setting(db, "EP_SYNC_INTERVAL_MINUTES", "15"))
        hd_mins = int(get_setting(db, "HD_SYNC_INTERVAL_MINUTES", "15"))
        
        if sync_minutes > 0:
            scheduler.add_job(scheduled_sync_job, 'interval', minutes=sync_minutes, id="ad_sync_job", replace_existing=True)
        
        scheduler.add_job(scheduled_telemetry_job, 'interval', minutes=15, id="telemetry_job", replace_existing=True)
        
        if get_setting(db, "EP_SYNC_ENABLED", "0") == "1" and ep_mins > 0:
            scheduler.add_job(scheduled_ep_sync_job, 'interval', minutes=ep_mins, id="scheduled_ep_sync_job", replace_existing=True)
        
        if get_setting(db, "HD_SYNC_ENABLED", "0") == "1" and hd_mins > 0:
            scheduler.add_job(scheduled_hd_sync_job, 'interval', minutes=hd_mins, id="scheduled_hd_sync_job", replace_existing=True)

        from routers.settings import get_all_settings
        sharepoint = get_all_settings()["sharepoint"]
        configure_sharepoint_sync_job(
            sharepoint.get("sync_enabled", False),
            int(sharepoint.get("sync_interval_minutes", 60)),
        )
        
        scheduler.start()
    finally:
        db.close()

def shutdown_scheduler():
    scheduler.shutdown(wait=False)
