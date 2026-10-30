import os
import inspect
from datetime import datetime, timezone
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session
from config_manager import get_setting

CURR_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURR_DIR)

if os.path.exists(os.path.join(PARENT_DIR, "docker-compose.yml")) or os.path.exists(os.path.join(PARENT_DIR, ".git")):
    BASE_DIR = PARENT_DIR
else:
    BASE_DIR = CURR_DIR

DOCS_DIR = os.path.join(BASE_DIR, "docs")
os.makedirs(DOCS_DIR, exist_ok=True)

def build_all_docs(db: Session) -> dict:
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    version = get_setting(db, "APP_VERSION", "1.00")
    generated_files = []

    import models
    model_classes = [
        cls for name, cls in inspect.getmembers(models, inspect.isclass)
        if hasattr(cls, "__tablename__")
    ]

    schema_lines = [
        f"# AD Tracker - Adatbázis Séma és Modell Dokumentáció (v{version})",
        f"*Automatikusan generálva: {now_str}*",
        "",
        "A rendszer PostgreSQL relációs adatbázist használ SQLAlchemy ORM modellekkel.",
        ""
    ]

    for cls in model_classes:
        tname = cls.__tablename__
        schema_lines.append(f"## Tábla: `{tname}` (ORM Modell: `{cls.__name__}`)")
        schema_lines.append("| Oszlop | Típus | Elsődleges kulcs | Nullable |")
        schema_lines.append("| :--- | :--- | :--- | :--- |")
        try:
            mapper = sa_inspect(cls)
            for col in mapper.columns:
                pk_str = "Igen" if col.primary_key else "Nem"
                null_str = "Igen" if col.nullable else "Nem"
                schema_lines.append(f"| `{col.name}` | `{col.type}` | {pk_str} | {null_str} |")
        except Exception:
            pass
        schema_lines.append("")

    path_schema = os.path.join(DOCS_DIR, "DATABASE_SCHEMA.md")
    with open(path_schema, "w", encoding="utf-8") as f:
        f.write("\n".join(schema_lines))
    generated_files.append("DATABASE_SCHEMA.md")

    api_lines = [
        f"# AD Tracker - Moduláris API Végpont Specifikáció (v{version})",
        f"*Automatikusan generálva: {now_str}*",
        "",
        "A háttérrendszer szabványos FastAPI APIRouter konnektorokra épül:",
        "",
        "| Prefix / Útvonal | Modul | Cél és Működés |",
        "| :--- | :--- | :--- |",
        "| `/api/users` | `routers.users` | Felhasználók és csoportok listázása, előzmények lekérdezése |",
        "| `/api/ad-analytics` | `routers.ad_analytics` | Időablakos és napi változáselemzés, grafikon adatok |",
        "| `/api/telemetry` | `routers.telemetry` | Hardver telemetria, webes audit napló, aktív munkamenetek |",
        "| `/api/sync` | `routers.sync` | Élő Active Directory LDAP szinkronizáció indítása és állapot |",
        "| `/api/history` | `routers.history` | Idősoros PowerShell CSV import és gyors backfill időgép |",
        "| `/api/backups` | `routers.backups` | Teljes és szeparált mentések exportja és visszaállítása |",
        "| `/api/settings` | `routers.settings` | Rendszerparaméterek, kapcsolatok, öndiagnosztika, indexelés és docs újraépítés |",
        "| `/api/ai` | `routers.ai` | Helyi Ollama LLM modellkezelés (1/1 VRAM), registry verziókövetés és prompt lekérdezés |"
    ]
    path_api = os.path.join(DOCS_DIR, "API_DOCUMENTATION.md")
    with open(path_api, "w", encoding="utf-8") as f:
        f.write("\n".join(api_lines))
    generated_files.append("API_DOCUMENTATION.md")

    skill_lines = [
        f"# AD Tracker - Helyi LLM Tudásbázis és Szakértői Rendszerprompt",
        f"*Verzió: v{version} | Dátum: {now_str}*",
        "",
        "## Rendszer Áttekintés",
        "Az AD Tracker egy professzionális Active Directory változáskövető, telemetriai és biztonsági audit központ.",
        "",
        "## Kulcsfogalmak és Üzleti Logika",
        "1. **Felhasználói Státuszok (user_status):**",
        "   - `Aktív normál user`: Engedélyezett, normál vállalati munkatárs.",
        "   - `Külsős`: Alvállalkozó vagy külső partner.",
        "   - `Távozottak`: Volt kolléga, fiókja letiltva vagy az archívumba helyezve.",
        "   - `Hosszútávúszabadság`: GYES, fizetés nélküli vagy tartós távolléten lévő munkatárs.",
        "2. **Hatókör-illesztés (Scope Adoption):**",
        "   - A korábbi hiányos CSV mentések és az élő AD szinkron közötti hatókör-különbség nem jelent jogosultság-elvonást.",
        "   - Eseménytípus: `SCOPE_ADOPTED` és `SCOPE_RECONCILED`.",
        "3. **Jogosultsági Események:**",
        "   - `ADDED_TO_GROUP`: Új csoporttagság hozzáadva.",
        "   - `REMOVED_FROM_GROUP`: Csoporttagság megszüntetve / elvéve.",
        "   - `USER_DISABLED` / `USER_ENABLED`: Fiók letiltva vagy aktiválva.",
        "",
        "## Adatbázis Táblák és Lekérdezési Stratégia",
        "- `ad_users`: Felhasználók azonosítója (sam_account_name), teljes neve (display_name), emailje, beosztása (title), szervezeti egysége.",
        "- `ad_groups`: Biztonsági csoportok és terjesztési listák, leírások.",
        "- `ad_group_members`: M:N relációs kapcsolótábla a tagok és csoportok között.",
        "- `ad_audit_log`: Időbélyeggel ellátott pontos változástörténet."
    ]
    path_skill = os.path.join(DOCS_DIR, "LLM_SKILL_PROMPT.md")
    with open(path_skill, "w", encoding="utf-8") as f:
        f.write("\n".join(skill_lines))
    generated_files.append("LLM_SKILL_PROMPT.md")

    rebuild_lines = [
        f"# SYSTEM REBUILD PROMPT - AD TRACKER (v{version})",
        f"*Automatikusan generálva: {now_str}*",
        "",
        "Ez a fájl tartalmazza az alkalmazás moduláris szerkezetének, sémáinak és függőségeinek leírását.",
        "",
        "## Moduláris Felépítés",
        "- `app/main.py`: Natív sablonösszefűző motor (nincs külső jinja2 függőség), router regisztráció.",
        "- `app/routers/`: Független FastAPI modulok.",
        "- `app/templates/tabs/`: Izolált HTML mikrosablonok fülönként.",
        "- `app/static/css/theme.css`: Központi Design System és stílusok.",
        "- `app/static/js/ui-core.js`: Kliensoldali vezérlő és interaktivitás.",
        "",
        "## Adatbázis Modellek",
        "\n".join(schema_lines[4:])
    ]
    path_rebuild = os.path.join(DOCS_DIR, "SYSTEM_REBUILD_PROMPT.md")
    with open(path_rebuild, "w", encoding="utf-8") as f:
        f.write("\n".join(rebuild_lines))
    generated_files.append("SYSTEM_REBUILD_PROMPT.md")

    return {
        "status": "SUCCESS",
        "generated_files": generated_files,
        "docs_dir": DOCS_DIR,
        "timestamp": now_str,
        "message": f"Dokumentáció sikeresen újraépítve ({len(generated_files)} db fájl) a docs/ mappában!"
    }
