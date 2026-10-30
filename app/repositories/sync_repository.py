from sqlalchemy.orm import Session
from sqlalchemy import desc
import models

class SyncRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_latest_ad_sync(self):
        return (
            self.db.query(models.SyncHistory)
            .order_by(desc(models.SyncHistory.started_at))
            .first()
        )

    def get_latest_ep_sync(self):
        return (
            self.db.query(models.EPSyncHistory)
            .order_by(desc(models.EPSyncHistory.started_at))
            .first()
        )

    def get_ad_history(self, limit: int = 40):
        return (
            self.db.query(models.SyncHistory)
            .order_by(desc(models.SyncHistory.started_at))
            .limit(limit)
            .all()
        )

    def get_ep_history(self, limit: int = 40):
        return (
            self.db.query(models.EPSyncHistory)
            .order_by(desc(models.EPSyncHistory.started_at))
            .limit(limit)
            .all()
        )
