import os, json, logging, tempfile

logger = logging.getLogger("config_manager")
SETTINGS_FILE = "settings.json"

DEFAULT_SETTINGS = {
    "EP_URL": "https://ep.tspc.hu/",
    "EP_API_KEY": "",
    "AD_SERVER": "dc1.tspc.hu:389",
    "AD_SEARCH_BASE": "DC=tspc,DC=hu",
    "TG_BOT_TOKEN": "",
    "TG_CHAT_ID": "229087988",
    "TG_NOTIFY_NEW_TICKET": True,
    "TG_EV_GROUPS": True,
    "TG_EV_USER_CREATE": True,
    "TG_EV_USER_DISABLE": True,
    "TG_EV_SYNC_ERROR": True,
    "TG_EV_HELPDESK": True,
    "TG_EV_DAILY_REPORT": True,
    "GH_REPO": "ottandras-cmyk/TSPC_AD",
    "GH_TOKEN": "",
    "OLLAMA_HOST": "http://host.docker.internal:11434",
    "SYNC_INTERVAL_MINUTES": "15"
}

def read_json_file(fpath: str, default=None):
    if default is None:
        default = {}
    if not os.path.exists(fpath):
        return default
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Hiba a(z) %s olvasásakor: %s", fpath, str(e))
        return default

def write_json_file(fpath: str, data: dict) -> bool:
    dir_name = os.path.dirname(fpath) or "."
    os.makedirs(dir_name, exist_ok=True)
    tmp_file = None
    try:
        with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tf:
            tmp_file = tf.name
            json.dump(data, tf, indent=2, ensure_ascii=False)
        os.replace(tmp_file, fpath)
        return True
    except Exception as e:
        logger.error("Hiba a(z) %s mentésekor: %s", fpath, str(e))
        if tmp_file and os.path.exists(tmp_file):
            try: os.remove(tmp_file)
            except OSError: pass
        return False

def init_default_settings(*args, **kwargs):
    settings = read_json_file(SETTINGS_FILE, default={})
    updated = False
    for k, v in DEFAULT_SETTINGS.items():
        if k not in settings:
            settings[k] = v
            updated = True
    if updated or not os.path.exists(SETTINGS_FILE):
        write_json_file(SETTINGS_FILE, settings)
    return settings

def get_setting(*args, **kwargs):
    """
    Támogatja a get_setting(key, default) ÉS get_setting(db, key, default) formákat is!
    """
    db = None
    key = None
    default = kwargs.get("default", None)

    if len(args) == 1:
        key = args[0]
    elif len(args) == 2:
        if isinstance(args[0], str):
            key, default = args[0], args[1]
        else:
            db, key = args[0], args[1]
    elif len(args) >= 3:
        db, key, default = args[0], args[1], args[2]
    elif "key" in kwargs:
        key = kwargs["key"]

    if not key:
        return default

    if db is not None:
        try:
            from sqlalchemy import text
            row = db.execute(text("SELECT setting_value FROM app_settings WHERE setting_key = :k LIMIT 1;"), {"k": key}).fetchone()
            if row and row[0] is not None:
                return row[0]
        except Exception:
            pass

    settings = read_json_file(SETTINGS_FILE)
    if key in settings:
        return settings[key]

    for sec in ["system_information", "postgresql_database_connection", "active_directory_ldap_connection", "easy_project_helpdesk_connection", "telegram_bot_notifications", "github_version_control"]:
        if isinstance(settings.get(sec), dict) and key in settings[sec]:
            return settings[sec][key]

    if key in os.environ:
        return os.environ[key]

    if default is not None:
        return default

    return DEFAULT_SETTINGS.get(key, default)

def update_setting(*args, **kwargs) -> bool:
    db = None
    key = None
    value = None

    if len(args) == 2:
        key, value = args[0], args[1]
    elif len(args) >= 3:
        db, key, value = args[0], args[1], args[2]
    else:
        key = kwargs.get("key")
        value = kwargs.get("value")

    if not key:
        return False

    if db is not None:
        try:
            from sqlalchemy import text
            db.execute(text("""
                INSERT INTO app_settings (setting_key, setting_value)
                VALUES (:k, :v)
                ON CONFLICT (setting_key) DO UPDATE SET setting_value = :v;
            """), {"k": key, "v": str(value)})
            db.commit()
        except Exception:
            pass

    settings = read_json_file(SETTINGS_FILE)
    settings[key] = value
    return write_json_file(SETTINGS_FILE, settings)

def update_settings_bulk(data: dict) -> bool:
    settings = read_json_file(SETTINGS_FILE)
    settings.update(data)
    return write_json_file(SETTINGS_FILE, settings)

set_setting = update_setting
save_setting = update_setting
save_settings = update_settings_bulk

def get_all_settings():
    return read_json_file(SETTINGS_FILE)
