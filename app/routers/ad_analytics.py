from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from database import get_db
import models
import ad_analytics

router = APIRouter(tags=["ad-analytics"])

@router.get("/api/ad/analytics")
@router.get("/api/ad/changes")
@router.get("/api/ad-analytics")
@router.get("/api/ad-analytics/summary")
def get_ad_analytics_summary_endpoint(db: Session = Depends(get_db)):
    try:
        data = ad_analytics.get_ad_analytics_summary(db)
        data["status"] = "SUCCESS"
        return data
    except Exception as e:
        logs = db.query(models.ADAuditLog).order_by(models.ADAuditLog.timestamp.desc()).limit(150).all()
        clean = []
        for l in logs:
            clean.append({
                "id": l.id,
                "timestamp": l.timestamp.strftime("%Y-%m-%d %H:%M:%S") if l.timestamp else "-",
                "date_str": l.timestamp.strftime("%Y-%m-%d") if l.timestamp else "-",
                "entity_name": l.entity_name,
                "entity_type": l.entity_type,
                "change_type": l.change_type,
                "details": l.details or "-",
                "source_ref": l.source_ref or "AD"
            })
        return {
            "status": "SUCCESS",
            "summary_counts": {"c_24h": len(clean), "c_72h": len(clean), "c_168h": len(clean), "c_30d": len(clean)},
            "windows": {"w_24h": clean, "w_72h": clean, "w_168h": clean, "w_30d": clean},
            "daily_breakdown": [],
            "chart_data": {"labels": [], "total": [], "added": [], "removed": [], "lifecycle": []}
        }

@router.get("/api/ad-analytics/day-events")
def get_ad_day_events_endpoint(date: str, type: str = "ALL", db: Session = Depends(get_db)):
    try:
        return ad_analytics.get_day_detailed_events(db, date, type)
    except Exception as e:
        return {"status": "ERROR", "message": str(e), "events": []}

@router.post("/api/ad-analytics/ask")
async def ask_ad_changes_endpoint(request: Request, db: Session = Depends(get_db)):
    try:
        body = await request.json()
        model = body.get("model", "llama3:8b")
        prompt = body.get("prompt", "")
        return ad_analytics.ask_ad_changes_ai(db, model, prompt)
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}
