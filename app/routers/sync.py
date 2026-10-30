import time
from datetime import timezone
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from sqlalchemy import desc
from database import get_db
import models

router = APIRouter(tags=["sync"])

def _timestamp_value(value):
    if value is None:
        return 0
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.timestamp()


@router.get("/api/sync/status")
@router.get("/api/sync-status")
def get_sync_status(db: Session = Depends(get_db)):
    last_ad = db.query(models.SyncHistory).order_by(desc(models.SyncHistory.started_at)).first()
    last_ep = db.query(models.EPSyncHistory).order_by(desc(models.EPSyncHistory.started_at)).first()
    last_sharepoint = db.query(models.SharePointSyncHistory).order_by(
        desc(models.SharePointSyncHistory.started_at)
    ).first()
    last_image_sync = db.query(models.SharePointImageSyncHistory).order_by(
        desc(models.SharePointImageSyncHistory.started_at)
    ).first()
    latest_sharepoint_record = max(
        (record for record in (last_sharepoint, last_image_sync) if record and record.started_at),
        default=None,
        key=lambda record: _timestamp_value(record.started_at),
    )
    sharepoint_started_at = latest_sharepoint_record.started_at if latest_sharepoint_record else None
    if latest_sharepoint_record is last_image_sync:
        sharepoint_status = last_image_sync.status
        sharepoint_changes = last_image_sync.new_versions_count
        sharepoint_duration = last_image_sync.duration_seconds
    else:
        sharepoint_status = last_sharepoint.status if last_sharepoint else "NINCS_ADAT"
        sharepoint_changes = (
            (last_sharepoint.added_count or 0) + (last_sharepoint.updated_count or 0)
            if last_sharepoint else 0
        )
        sharepoint_duration = last_sharepoint.duration_seconds if last_sharepoint else None

    return {
        "status": "SUCCESS",
        "ad_sync": {
            "last_run": last_ad.started_at.strftime("%Y-%m-%d %H:%M:%S") if last_ad and last_ad.started_at else "-",
            "status": last_ad.status if last_ad else "NINCS_ADAT",
            "changes": last_ad.changes_detected if last_ad else 0,
            "duration": f"{last_ad.duration_seconds} mp" if last_ad and last_ad.duration_seconds else "-"
        },
        "ep_sync": {
            "last_run": last_ep.started_at.strftime("%Y-%m-%d %H:%M:%S") if last_ep and last_ep.started_at else "-",
            "status": last_ep.status if last_ep else "NINCS_ADAT",
            "changes": getattr(last_ep, "changes_count", 0) if last_ep else 0,
            "duration": f"{round(last_ep.duration_seconds, 1)} mp" if last_ep and last_ep.duration_seconds else "-"
        },
        "sharepoint_sync": {
            "last_run": sharepoint_started_at.strftime("%Y-%m-%d %H:%M:%S") if sharepoint_started_at else "-",
            "status": sharepoint_status,
            "changes": sharepoint_changes or 0,
            "duration": f"{round(sharepoint_duration, 1)} mp" if sharepoint_duration is not None else "-"
        }
    }

@router.get("/api/sync/history")
@router.get("/api/sync-history")
@router.get("/api/sync/logs")
def get_sync_history_unified(db: Session = Depends(get_db)):
    ad_history = db.query(models.SyncHistory).order_by(desc(models.SyncHistory.started_at)).all()
    ep_history = db.query(models.EPSyncHistory).order_by(desc(models.EPSyncHistory.started_at)).all()
    sharepoint_history = db.query(models.SharePointSyncHistory).order_by(
        desc(models.SharePointSyncHistory.started_at)
    ).all()

    combined_logs = []

    for r in ad_history:
        is_succ = (r.status or "").upper() in ["SIKERES", "SUCCESS"]
        combined_logs.append({
            "id": f"AD-{r.id}",
            "source": "Active Directory (AD)",
            "start_time": r.started_at.strftime("%Y-%m-%d %H:%M:%S") if r.started_at else "-",
            "started_at": r.started_at.strftime("%Y-%m-%d %H:%M:%S") if r.started_at else "-",
            "end_time": r.ended_at.strftime("%Y-%m-%d %H:%M:%S") if r.ended_at else "-",
            "ended_at": r.ended_at.strftime("%Y-%m-%d %H:%M:%S") if r.ended_at else "-",
            "duration": f"{r.duration_seconds} mp" if r.duration_seconds is not None else "-",
            "duration_seconds": r.duration_seconds or 0,
            "trigger": r.trigger_type or "Kézi indítás",
            "trigger_type": r.trigger_type or "Kézi indítás",
            "status": "Sikeres" if is_succ else "Hiba",
            "details": r.error_message if r.error_message else f"{r.changes_detected or 0} változás rögzítve",
            "_sort_timestamp": _timestamp_value(r.started_at),
        })

    for r in ep_history:
        is_succ = (r.status or "").upper() in ["SIKERES", "SUCCESS"]
        dur = round(r.duration_seconds, 1) if r.duration_seconds is not None else 0
        combined_logs.append({
            "id": f"EP-{r.id}",
            "source": f"Easy Project ({getattr(r, 'sync_type', 'GENERAL')})",
            "start_time": r.started_at.strftime("%Y-%m-%d %H:%M:%S") if r.started_at else "-",
            "started_at": r.started_at.strftime("%Y-%m-%d %H:%M:%S") if r.started_at else "-",
            "end_time": r.ended_at.strftime("%Y-%m-%d %H:%M:%S") if r.ended_at else "-",
            "ended_at": r.ended_at.strftime("%Y-%m-%d %H:%M:%S") if r.ended_at else "-",
            "duration": f"{dur} mp",
            "duration_seconds": dur,
            "trigger": r.trigger_type or "Automatikus",
            "trigger_type": r.trigger_type or "Automatikus",
            "status": "Sikeres" if is_succ else "Hiba",
            "details": r.error_message if r.error_message else f"{getattr(r, 'changes_count', 0)} változás, {r.tasks_count or 0} feladat",
            "_sort_timestamp": _timestamp_value(r.started_at),
        })

    for r in sharepoint_history:
        is_succ = (r.status or "").upper() in ["SIKERES", "SUCCESS"]
        duration = round(r.duration_seconds, 1) if r.duration_seconds is not None else 0
        combined_logs.append({
            "id": f"SP-{r.id}",
            "source": f"SharePoint ({r.list_name})",
            "start_time": r.started_at.strftime("%Y-%m-%d %H:%M:%S") if r.started_at else "-",
            "started_at": r.started_at.strftime("%Y-%m-%d %H:%M:%S") if r.started_at else "-",
            "end_time": r.ended_at.strftime("%Y-%m-%d %H:%M:%S") if r.ended_at else "-",
            "ended_at": r.ended_at.strftime("%Y-%m-%d %H:%M:%S") if r.ended_at else "-",
            "duration": f"{duration} mp",
            "duration_seconds": duration,
            "trigger": r.trigger_type or "Kézi indítás",
            "trigger_type": r.trigger_type or "Kézi indítás",
            "status": "Sikeres" if is_succ else "Hiba",
            "details": r.error_message or (
                f"{r.items_count or 0} elem; új: {r.added_count or 0}, "
                f"módosult: {r.updated_count or 0}, törölt: {r.deleted_count or 0}"
            ),
            "_sort_timestamp": _timestamp_value(r.started_at),
        })

    image_history = db.query(models.SharePointImageSyncHistory).order_by(
        desc(models.SharePointImageSyncHistory.started_at)
    ).all()
    for r in image_history:
        is_success = (r.status or "").upper() == "SIKERES"
        combined_logs.append({
            "id": f"SPI-{r.id}",
            "source": "SharePoint (Eszközleltár képek)",
            "start_time": r.started_at.strftime("%Y-%m-%d %H:%M:%S") if r.started_at else "-",
            "started_at": r.started_at.strftime("%Y-%m-%d %H:%M:%S") if r.started_at else "-",
            "end_time": r.ended_at.strftime("%Y-%m-%d %H:%M:%S") if r.ended_at else "-",
            "ended_at": r.ended_at.strftime("%Y-%m-%d %H:%M:%S") if r.ended_at else "-",
            "duration": f"{round(r.duration_seconds, 1)} mp" if r.duration_seconds is not None else "-",
            "duration_seconds": r.duration_seconds or 0,
            "trigger": "Felhasználó által indított",
            "trigger_type": "MANUAL",
            "status": "Sikeres" if is_success else ("Részleges" if r.status == "RÉSZLEGES" else "Hiba"),
            "details": r.error_message or (
                f"{r.links_count} hivatkozás; új verzió: {r.new_versions_count}, "
                f"változatlan: {r.unchanged_count}, kihagyva: {r.skipped_count}, hibás: {r.failed_count}"
            ),
            "_sort_timestamp": _timestamp_value(r.started_at),
        })

    combined_logs.sort(key=lambda log: log["_sort_timestamp"], reverse=True)
    for log in combined_logs:
        log.pop("_sort_timestamp")
    return {
        "status": "SUCCESS",
        "logs": combined_logs,
        "history": combined_logs,
        "data": combined_logs
    }

@router.post("/api/sync")
@router.post("/api/sync/trigger")
async def trigger_sync(request: Request, db: Session = Depends(get_db)):
    t_start = time.time()
    try:
        from sync_engine import run_ad_sync
        res = run_ad_sync(db, trigger_type="MANUAL")
        dur = round(time.time() - t_start, 1)
        return {"status": "SUCCESS", "message": f"Szinkronizáció kész ({dur} mp).", "result": res}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}
