import os
from sqlalchemy.orm import Session
from models import SystemSetting

def get_setting(db: Session, key: str, default_val: str = ""):
    setting = db.query(SystemSetting).filter(SystemSetting.setting_key == key).first()
    return setting.setting_value if setting else default_val

def update_setting(db: Session, key: str, value: str, description: str = ""):
    setting = db.query(SystemSetting).filter(SystemSetting.setting_key == key).first()
    if setting:
        setting.setting_value = str(value)
    else:
        new_setting = SystemSetting(setting_key=key, setting_value=str(value), description=description)
        db.add(new_setting)
    db.commit()

def init_default_settings(db: Session):
    defaults = {
        "AD_SERVER": (os.getenv("AD_SERVER", ""), "Példa: dc1.tspc.hu:389"),
        "AD_USER": (os.getenv("AD_USER", ""), "Példa: tadmin@tspc.hu"),
        "AD_PASSWORD": (os.getenv("AD_PASSWORD", ""), "Az AD olvasó fiók jelszava"),
        "AD_SEARCH_BASE": (os.getenv("AD_SEARCH_BASE", ""), "Példa: DC=tspc,DC=hu"),
        "SYNC_INTERVAL_MINUTES": ("15", "Automatikus szinkronizáció gyakorisága percben (0 = kikapcsolva)"),
        "OLLAMA_URL": ("http://ollama:11434", "A helyi Ollama API címe")
    }
    for key, (def_val, desc) in defaults.items():
        if not db.query(SystemSetting).filter(SystemSetting.setting_key == key).first():
            db.add(SystemSetting(setting_key=key, setting_value=def_val, description=desc))
    db.commit()
