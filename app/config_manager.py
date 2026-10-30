import os
import json
import logging
import tempfile

logger = logging.getLogger("config_manager")
APP_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(APP_DIR, "config", "settings.local.json")
_MISSING = object()
LEGACY_SETTINGS_FILES = [
    os.path.join(APP_DIR, "app", "config", "settings.json"),
    os.path.join(APP_DIR, "config", "settings.json"),
    os.path.join(APP_DIR, "app", "settings.json"),
    os.path.join(APP_DIR, "settings.json"),
]
LEGACY_ENV_FILES = [
    os.path.join(APP_DIR, ".env"),
    os.path.join(APP_DIR, "app", ".env"),
]

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

SETTING_ALIASES = {
    "EP_URL": ("easyproject", "url"),
    "EP_API_KEY": ("easyproject", "api_key"),
    "EP_PROJECT_ID": ("easyproject", "project_id"),
    "EP_SYNC_INTERVAL_MINUTES": ("easyproject", "sync_interval_minutes"),
    "EP_SYNC_ENABLED": ("easyproject", "sync_enabled"),
    "AD_SERVER": ("ad", "server"),
    "AD_BIND_USER": ("ad", "bind_user"),
    "AD_USER": ("ad", "bind_user"),
    "AD_BIND_PASSWORD": ("ad", "bind_password"),
    "AD_PASSWORD": ("ad", "bind_password"),
    "AD_BASE_DN": ("ad", "base_dn"),
    "AD_SEARCH_BASE": ("ad", "base_dn"),
    "AD_SYNC_INTERVAL_MINUTES": ("ad", "sync_interval_minutes"),
    "TG_BOT_TOKEN": ("telegram", "bot_token"),
    "TELEGRAM_BOT_TOKEN": ("telegram", "bot_token"),
    "TG_CHAT_ID": ("telegram", "chat_id"),
    "GH_REPO": ("github", "repo_url"),
    "GH_TOKEN": ("github", "token"),
    "GITHUB_TOKEN": ("github", "token"),
    "GH_BRANCH": ("github", "branch"),
    "SP_CLIENT_SECRET": ("sharepoint", "client_secret"),
}

def read_json_file(fpath: str, default=_MISSING):
    if default is _MISSING:
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
        os.chmod(tmp_file, 0o600)
        os.replace(tmp_file, fpath)
        return True
    except Exception as e:
        logger.error("Hiba a(z) %s mentésekor: %s", fpath, str(e))
        if tmp_file and os.path.exists(tmp_file):
            try: os.remove(tmp_file)
            except OSError: pass
        return False


def _merge_missing(target: dict, source: dict) -> None:
    for key, value in source.items():
        if key not in target:
            target[key] = value
        elif isinstance(target[key], dict) and isinstance(value, dict):
            _merge_missing(target[key], value)


def _read_legacy_settings() -> dict:
    settings = {}
    found_legacy = False
    for path in LEGACY_SETTINGS_FILES:
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as source:
                data = json.load(source)
            if isinstance(data, dict):
                _merge_missing(settings, data)
                found_legacy = True
        except (OSError, json.JSONDecodeError) as error:
            logger.warning("Legacy beállításfájl nem olvasható (%s): %s", path, error)

    for path in LEGACY_ENV_FILES:
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as source:
                for line in source:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        settings[key.strip()] = value.strip().strip('"').strip("'")
                        found_legacy = True
        except OSError as error:
            logger.warning("Legacy környezeti fájl nem olvasható (%s): %s", path, error)
    return settings if found_legacy else {}


def load_local_settings() -> dict:
    if os.path.exists(SETTINGS_FILE):
        data = read_json_file(SETTINGS_FILE, default=None)
        if not isinstance(data, dict):
            raise ValueError(f"A helyi beállításfájl formátuma érvénytelen: {SETTINGS_FILE}")
        return data

    legacy = _read_legacy_settings()
    if legacy and not write_json_file(SETTINGS_FILE, legacy):
        logger.error("A legacy beállítások betöltődtek, de a helyi konfiguráció migrációja nem sikerült.")
    return legacy


def save_local_settings(data: dict) -> bool:
    if not isinstance(data, dict):
        raise TypeError("A helyi beállításoknak JSON objektumnak kell lenniük.")
    return write_json_file(SETTINGS_FILE, data)


def init_default_settings(*args, **kwargs):
    settings = load_local_settings()
    updated = False
    section_defaults = {
        "easyproject": {
            "url": DEFAULT_SETTINGS["EP_URL"],
            "api_key": DEFAULT_SETTINGS["EP_API_KEY"],
            "project_id": "2403",
            "sync_interval_minutes": 15,
        },
        "ad": {
            "server": DEFAULT_SETTINGS["AD_SERVER"],
            "base_dn": DEFAULT_SETTINGS["AD_SEARCH_BASE"],
            "bind_user": "",
            "bind_password": "",
            "sync_interval_minutes": 15,
        },
        "telegram": {
            "bot_token": DEFAULT_SETTINGS["TG_BOT_TOKEN"],
            "chat_id": DEFAULT_SETTINGS["TG_CHAT_ID"],
            "notify_helpdesk": True,
            "notify_audit": True,
        },
        "github": {
            "repo_url": "https://github.com/ottandras-cmyk/TSPC_AD.git",
            "token": DEFAULT_SETTINGS["GH_TOKEN"],
            "branch": "copilot/ad-tracker-v1.27-20261030",
        },
        "sharepoint": {
            "tenant_id": "",
            "client_id": "",
            "client_secret": "",
            "site_url": "",
            "sync_enabled": False,
            "sync_interval_minutes": 60,
        },
    }
    for section, defaults in section_defaults.items():
        if not isinstance(settings.get(section), dict):
            settings[section] = {}
            updated = True
        for key, value in defaults.items():
            if key not in settings[section]:
                settings[section][key] = value
                updated = True
    for k, v in DEFAULT_SETTINGS.items():
        if k not in SETTING_ALIASES and k not in settings:
            settings[k] = v
            updated = True
    if updated or not os.path.exists(SETTINGS_FILE):
        if not save_local_settings(settings):
            logger.error("Az alapértelmezett helyi beállítások mentése sikertelen.")
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

    settings = load_local_settings()
    alias = SETTING_ALIASES.get(key)
    if alias:
        section = settings.get(alias[0])
        if isinstance(section, dict) and alias[1] in section:
            return section[alias[1]]

    if key in settings:
        return settings[key]

    if db is not None:
        try:
            from sqlalchemy import text
            row = db.execute(text("SELECT setting_value FROM app_settings WHERE setting_key = :k LIMIT 1;"), {"k": key}).fetchone()
            if row and row[0] is not None:
                return row[0]
        except Exception:
            pass

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

    settings = load_local_settings()
    alias = SETTING_ALIASES.get(key)
    if alias:
        settings.setdefault(alias[0], {})[alias[1]] = value
    else:
        settings[key] = value
    return save_local_settings(settings)

def update_settings_bulk(data: dict) -> bool:
    settings = load_local_settings()
    settings.update(data)
    return save_local_settings(settings)

set_setting = update_setting
save_setting = update_setting
save_settings = update_settings_bulk

def get_all_settings():
    return load_local_settings()
