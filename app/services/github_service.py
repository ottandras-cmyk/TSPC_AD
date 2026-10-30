import re
from sqlalchemy.orm import Session
try:
    from repositories.settings_repository import SettingsRepository
except ImportError:
    from app.repositories.settings_repository import SettingsRepository

class GithubService:
    def __init__(self, db: Session = None):
        self.db = db

    @staticmethod
    def parse_version_num(v_str) -> float:
        if not v_str: return 1.00
        m = re.search(r'(\d+\.\d+)', str(v_str))
        if m:
            try: return float(m.group(1))
            except ValueError: pass
        return 1.00

    def get_next_version(self, db: Session = None) -> str:
        target = db or self.db
        if not target: return "1.07"
        repo = SettingsRepository(target)
        cur_v = repo.get_setting("APP_VERSION", "1.06")
        val = self.parse_version_num(cur_v)
        return f"{round(val + 0.01, 2):.2f}"

    def __call__(self, db: Session = None):
        return GithubService(db)

github_service = GithubService()
