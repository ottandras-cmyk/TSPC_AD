from sqlalchemy.orm import Session
try:
    from repositories.user_repository import UserRepository
except ImportError:
    from app.repositories.user_repository import UserRepository

class UserService:
    def __init__(self, db: Session = None):
        self.db = db

    def _repo(self, db: Session = None):
        target = db or self.db
        if target:
            return UserRepository(target)
        return None

    def get_users_list(self, db: Session = None):
        r = self._repo(db)
        return r.get_all_clean_users() if r else []

    def get_all_users(self, db: Session = None):
        return self.get_users_list(db)

    def get_users(self, db: Session = None):
        return self.get_users_list(db)

    def get_user_by_sam(self, sam: str, db: Session = None):
        r = self._repo(db)
        return r.get_by_sam(sam) if r else None

    def get_by_sam(self, sam: str, db: Session = None):
        return self.get_user_by_sam(sam, db)

    def get_groups_list(self, db: Session = None):
        r = self._repo(db)
        return r.get_all_groups() if r else []

    def get_all_groups(self, db: Session = None):
        return self.get_groups_list(db)

    def get_user_kpis(self, db: Session = None):
        users = self.get_users_list(db)
        total = len(users)
        active = sum(1 for u in users if getattr(u, 'is_enabled', True))
        return {
            "total_users": total,
            "active_users": active,
            "disabled_users": total - active
        }

    def __call__(self, db: Session = None):
        return UserService(db)

user_service = UserService()
