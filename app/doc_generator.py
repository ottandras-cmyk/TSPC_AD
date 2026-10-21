import os
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from sqlalchemy.schema import CreateTable
from database import engine
import models
from config_manager import get_setting

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(APP_DIR, ".."))
DOCS_DIR = os.path.join(PROJECT_DIR, "docs")

def ensure_docs_dir():
    os.makedirs(DOCS_DIR, exist_ok=True)
    os.makedirs(os.path.join(APP_DIR, "docs"), exist_ok=True)

def generate_schema_sql() -> str:
    """Valós PostgreSQL DDL séma exportálása a modellekből"""
    ddl_statements = [
        "-- ============================================================================",
        "-- AD TRACKER - TELJES POSTGRESQL ADATBÁZIS SÉMA",
        f"-- Generálva: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "-- ============================================================================\n"
    ]
    for table in models.Base.metadata.sorted_tables:
        ddl = str(CreateTable(table).compile(engine)).strip()
        ddl_statements.append(f"{ddl};\n")
    return "\n".join(ddl_statements)

def generate_schema_markdown() -> str:
    """Részletes adatbázis leírás Markdown formátumban"""
    return f"""# AD Tracker - Adatbázis Séma és Adatstruktúra Dokumentáció
Generálva: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}

## 1. Táblák összefoglalása

| Tábla neve | Leírás | Kulcs / Indexek |
| :--- | :--- | :--- |
| `ad_users` | Active Directory felhasználói fiókok és kiterjesztett attribútumok | `object_guid` (PK, UUID), `sam_account_name` (UNIQUE) |
| `ad_groups` | Biztonsági csoportok és terjesztési listák | `object_guid` (PK, UUID), `sam_account_name` (UNIQUE) |
| `ad_group_members` | Felhasználó - Csoport N:M relációs kapcsolótábla | `(user_guid, group_guid)` (PK) |
| `ad_audit_log` | Minden észlelt változás (tagság, fiók-státusz, új objektum) | `id` (PK, Serial), `timestamp`, `entity_name` |
| `sync_history` | Szinkronizációs és importálási futások naplója | `id` (PK, Serial), `started_at` |
| `app_settings` | Kulcs-érték alapú rendszer- és LDAP/GitHub konfigurációk | `setting_key` (PK, VARCHAR) |

---

## 2. Részletes mezőleírások

### `ad_users` (Felhasználók)
* `object_guid` (UUID): AD belső egyedi azonosító.
* `sam_account_name` (VARCHAR): Bejelentkezési azonosító (pl. `kovacs.janos`).
* `display_name` (VARCHAR): Teljes megjelenített név.
* `mail` (VARCHAR): Elsődleges e-mail cím.
* `is_enabled` (BOOLEAN): Fiók állapota (`userAccountControl` bit 2 alapján).
* `user_status` (VARCHAR): Szervezeti besorolás (`Aktív normál user`, `Külsös`, `Távozottak`, `Hosszútávúszabadság`).
* `last_logon_date` (TIMESTAMP WITH TIME ZONE): A `lastLogonTimestamp` és `lastLogon` közül a legfrissebb bejelentkezési időpont.
* `ou_path` (TEXT): Tiszta szervezeti lánc (pl. `TSPC Users;TSPC`).
* `when_created` (TIMESTAMP WITH TIME ZONE): Eredeti létrehozási dátum az AD-ból.
* `when_changed` (TIMESTAMP WITH TIME ZONE): Utolsó módosítás ideje az AD-ban.
* `last_synced_at` (TIMESTAMP WITH TIME ZONE): Rendszerbeli utolsó szinkronizálás ideje.

### `ad_groups` (Csoportok)
* `object_guid` (UUID): Egyedi AD azonosító.
* `sam_account_name` (VARCHAR): Csoport neve (pl. `Domain Admins`, `Vezetőség`).
* `group_type` (VARCHAR): `Biztonsági Csoport` vagy `Terjesztési Lista`.
* `description` (TEXT): A csoport leírása / rendeltetése.
* `when_created` (TIMESTAMP WITH TIME ZONE): Létrehozás valós AD-beli dátuma.

### `ad_audit_log` (Eseménynapló)
* `entity_type`: `USER`, `GROUP`, `MEMBERSHIP`, `SYSTEM`.
* `change_type`:
  * `ADDED_TO_GROUP`: Csoporthoz adva.
  * `REMOVED_FROM_GROUP`: Csoportból eltávolítva.
  * `USER_CREATED`, `GROUP_CREATED`: Új objektum létrehozva.
  * `USER_DISABLED`, `USER_ENABLED`: Fiók letiltva / aktiválva.
  * `STATUS_CHANGED`: Besorolás változása (pl. Normál user -> Külsős).
"""

def generate_system_architecture() -> str:
    """A rendszer működési mechanizmusainak részletes leírása"""
    return f"""# AD Tracker - Rendszer Architektúra & Működési Mechanizmusok
Generálva: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}

## 1. Active Directory Élő Szinkronizáció (`sync_engine.py`)
1. **Dátumkonverzió (GeneralizedTime & FileTime):**
   * Az AD `whenCreated` és `whenChanged` mezői GeneralizedTime szövegként (`YYYYMMDDHHMMSS.0Z`) érkeznek; a regex parser ezt valós UTC `datetime` objektummá alakítja.
   * A bejelentkezési adatok (`lastLogonTimestamp`, `lastLogon`) Windows FileTime formátumúak (100-nanoszekundumos intervallum 1601 óta); a rendszer mindkettőt konvertálja, és a legfrissebb időpontot menti el.
2. **Szervezeti besorolás (`determine_user_status`):**
   * A felhasználó `memberOf` listájának szűrésével automatikusan meghatározza a speciális besorolást (`Hosszútávúszabadság`, `Külsös`, `Távozottak`), vagy engedélyezettség alapján `Aktív normál user` / `Letiltva`.
3. **OU Fa felépítés (`extract_ou_path`):**
   * A `distinguishedName`-ből kigyűjti a hierarchikus `OU=` elemeket pontosvesszővel elválasztva.
4. **Változáskövetés:**
   * Minden futás összeveti a memóriabeli AD állapotot a helyi PostgreSQL-lel; a tagsági és státuszbeli eltérések azonnal bekerülnek az `ad_audit_log` táblába.

## 2. Történeti Időgép & CSV Import (`history_importer.py`)
* **Kronológiai diff-képzés:** A múltbeli CSV mentéseket időrendbe rendezi (`YYYYMMDD_HHMMSS`), és lépésről lépésre visszajátssza.
* **10 vs 11 oszlopos CSV intelligens kezelés:** Kiszűri a státuszszavakat (`AlapAdat`, `Külsös`), megelőzve a téves csoporttagsági rekordok képződését.
* **Gyors Backfill funkció:** Az audit események újragenerálása nélkül képes a meglévő felhasználókhoz és csoportokhoz hozzárendelni a CSV-kben tárolt valós létrehozási időket és leírásokat.

## 3. GitHub Integráció (`github_sync.py`)
* **Nulla külső függőség:** Kizárólag a Python standard könyvtárát (`urllib.request`) használja.
* **Verziókezelés:** Közvetlenül a GitHub REST API-t kérdezi le (`/tags` és `/commits`), így a webfelületen látható verziószám mindig a távoli GitHub repó legfrissebb állapotát tükrözi.
"""

def generate_ai_skills_and_prompts() -> str:
    """Strukturált prompt- és skill-csomag bármely AI számára"""
    return """# AD Tracker - AI Rendszerpromtok és Speciális Skillek

Ezeket a promptokat bemásolhatja bármilyen új LLM (helyi Ollama, Gemini, Claude, ChatGPT) munkamenetbe, hogy a modell azonnal kontextusba kerüljön a forráskódok újraolvasása nélkül.

---

## 1. Rendszergazda & Audit Asszisztens Rendszerprompt

```text
Te vagy az AD Tracker intelligens audit és biztonsági asszisztense.
Közvetlen hozzáférésed van az Active Directory változáskövető adatbázisához.

Fő feladataid:
1. Jogosultsági változások elemzése: Figyeld a kiemelt csoportokat (Domain Admins, Rendszergazdák, Vezetőség).
2. Fluktuáció és kockázatkezelés: Azonosítsd a távozott vagy külsős kollégák bent maradt csoporttagságait.
3. Inaktív fiókok felderítése: Keresd a 90 vagy 180 napja be nem jelentkezett fiókokat (last_logon_date).
4. Idővonal vizsgálat: Elemezd, hogy egy adott fiók mikor, milyen csoportokba került be vagy került ki (ad_audit_log).

Válaszaid legyenek tömörek, tényszerűek és biztonság-fókuszúak.
