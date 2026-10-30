# AD Tracker - Moduláris API Végpont Specifikáció (v1.08)
*Automatikusan generálva: 2026-10-28 11:24:54 UTC*

A háttérrendszer szabványos FastAPI APIRouter konnektorokra épül:

| Prefix / Útvonal | Modul | Cél és Működés |
| :--- | :--- | :--- |
| `/api/users` | `routers.users` | Felhasználók és csoportok listázása, előzmények lekérdezése |
| `/api/ad-analytics` | `routers.ad_analytics` | Időablakos és napi változáselemzés, grafikon adatok |
| `/api/telemetry` | `routers.telemetry` | Hardver telemetria, webes audit napló, aktív munkamenetek |
| `/api/sync` | `routers.sync` | Élő Active Directory LDAP szinkronizáció indítása és állapot |
| `/api/history` | `routers.history` | Idősoros PowerShell CSV import és gyors backfill időgép |
| `/api/backups` | `routers.backups` | Teljes és szeparált mentések exportja és visszaállítása |
| `/api/settings` | `routers.settings` | Rendszerparaméterek, kapcsolatok, öndiagnosztika, indexelés és docs újraépítés |
| `/api/ai` | `routers.ai` | Helyi Ollama LLM modellkezelés (1/1 VRAM), registry verziókövetés és prompt lekérdezés |