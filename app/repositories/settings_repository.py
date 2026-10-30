from sqlalchemy.orm import Session
from sqlalchemy import text
import models

class SettingsRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_setting(self, key: str, default: str = None) -> str:
        row = (
            self.db.query(models.SystemSetting)
            .filter(models.SystemSetting.setting_key == key)
            .first()
        )
        if row and row.setting_value is not None:
            return row.setting_value
        return default

    def set_setting(self, key: str, value: str, description: str = None) -> None:
        self.db.execute(text("""
            INSERT INTO app_settings (setting_key, setting_value, description)
            VALUES (:k, :v, :d)
            ON CONFLICT (setting_key) DO UPDATE 
            SET setting_value = :v, description = COALESCE(:d, app_settings.description);
        """), {"k": key, "v": str(value), "d": description})
        self.db.commit()

    def get_all_settings(self) -> dict:
        records = self.db.query(models.SystemSetting).all()
        return {r.setting_key: r.setting_value for r in records}
