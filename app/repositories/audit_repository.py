from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc
import models

class AuditRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_clean_logs(self, start_time: datetime = None, limit: int = 1000):
        query = (
            self.db.query(models.ADAuditLog)
            .filter(models.ADAuditLog.change_type != 'BASELINE_ESTABLISHED')
        )
        if start_time:
            query = query.filter(models.ADAuditLog.timestamp >= start_time)
        return query.order_by(desc(models.ADAuditLog.timestamp)).limit(limit).all()

    def get_latest_changes(self, limit: int = 50):
        return (
            self.db.query(models.ADAuditLog)
            .order_by(desc(models.ADAuditLog.timestamp))
            .limit(limit)
            .all()
        )

    def get_user_history(self, sam: str, limit: int = 200):
        return (
            self.db.query(models.ADAuditLog)
            .filter(models.ADAuditLog.entity_name == sam)
            .order_by(desc(models.ADAuditLog.timestamp))
            .limit(limit)
            .all()
        )
