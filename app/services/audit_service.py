from sqlalchemy.orm import Session
from datetime import datetime, timezone
import models
try:
    from repositories.audit_repository import AuditRepository
except ImportError:
    from app.repositories.audit_repository import AuditRepository

class AuditService:
    def __init__(self, db: Session = None):
        self.db = db

    def log_web_event(self, username: str, client_ip: str, action: str, details: str = "", status: str = "SIKERES", db: Session = None):
        target = db or self.db
        if not target: return
        try:
            entry = models.WebAccessLog(
                username=username, client_ip=client_ip, action=action,
                details=details, status=status, timestamp=datetime.now(timezone.utc)
            )
            target.add(entry)
            target.commit()
        except Exception:
            target.rollback()

    def get_recent_logs(self, limit: int = 50, db: Session = None):
        target = db or self.db
        if not target: return []
        repo = AuditRepository(target)
        return repo.get_latest_changes(limit=limit)

    def __call__(self, db: Session = None):
        return AuditService(db)

audit_service = AuditService()
