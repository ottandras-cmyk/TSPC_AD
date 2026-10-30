from sqlalchemy.orm import Session
from config_manager import get_setting, update_setting

class SettingsService:
    def __init__(self, db: Session = None):
        self.db = db

    def get_value(self, key: str, default: str = None, db: Session = None) -> str:
        return get_setting(db or self.db, key, default)

    def set_value(self, key: str, value: str, db: Session = None) -> bool:
        return update_setting(db or self.db, key, value)

    def __call__(self, db: Session = None):
        return SettingsService(db)

settings_service = SettingsService()
