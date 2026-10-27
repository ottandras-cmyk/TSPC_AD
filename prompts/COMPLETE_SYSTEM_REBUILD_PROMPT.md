# SYSTEM PROMPT - TSPC AD TRACKER & RENDSZERKÖZPONT TELJES SPECIFIKÁCIÓ
Generálva: 2026-10-27 05:13:56 | Kiadás: v1.08 / v1.09 | TSPC Csoport

Te vagy az AD Tracker & Rendszerközpont mesterszintű szoftverarchitektje és műszaki szakértője.
Ez a prompt a teljes rendszer reprodukálásához szükséges összes adatot, architektúrát és logikát tartalmazza.
Ebből a specifikációból a teljes alkalmazás, backend, frontend és adatbázis a nulláról újraépíthető:

## 1. RENDSZER PROFIL & INFRASTRUKTÚRA
- **Alkalmazás:** TSPC AD Tracker & Rendszerközpont
- **Környezet:** Docker Compose konténeresítés (FastAPI backend + PostgreSQL 15 DB).
- **Portkiosztás:** Web felület: 8080 (konténer belső: 8000), Adatbázis: 5432.
- **Adatbázis forrás:** 3907 Active Directory fiók (2925 aktív, 982 letiltott munkatárs), 858 AD csoport.
- **Helpdesk integráció:** Easy Project REST API (#2403 Helpdesk projekt, 1029 hibajegy).
- **Értesítési motor:** Telegram Bot API (@tspc_IT_bot, Chat ID: 229087988).
- **Verziókezelés:** GitHub REST API (Repo: ottandras-cmyk/TSPC_AD, Release Tag pipeline).

## 2. BACKEND ROUTER STRUKTÚRA & API SZERZŐDÉSEK
1. `/api/users`:
   - `GET /`: Teljes felhasználói lista (3907 fő), KPI számlálók, keresés, lapozás.
   - `GET /{sam}/detail`: ADUC kompatibilis adatlap. Keresztbe hivatkozások feloldása: `ad_users.member_of` mező, `ad_groups.members` mező és `ad_audit_log` előzmények összefésülése valós időben. Besorolás: Biztonsági csoport (zöld), Terjesztési lista (lila), Mappajogosultság (kék).
   - `GET /group/{group_name}/members`: Csoporttagok feloldása. Megkülönbözteti a felhasználókat (👤) és a beágyazott csoportokat (👥). Domain Users esetén kiadja az összes AD fiókot.
2. `/api/easyproject`:
   - `GET /helpdesk/tickets`: 1029 hibajegy listázása sorszámmal (HD-xxx), leltári számmal, bejelentővel, státusszal és leírással.
   - `POST /helpdesk/ticket/{id}/send-telegram`: Részletes hibajegy kiküldése Telegramra HTML formázással és fallbackkel.
3. `/api/settings`:
   - `GET /all`, `POST /save`: settings.json perzisztens kezelése (6 db eseménykapcsolóval).
   - `POST /test/telegram`: Tesztüzenet HTML &amp; védelemmel és fallbackkel.
   - `POST /telegram/detect-chat-id`: Automatikus Chat ID felderítés getUpdates alapján.
   - `GET /telegram/history`: Élő kétirányú eseménynapló (telefonról bejövő és kimenő üzenetek 5 mp-enként).
   - `POST /github/test`: Kapcsolatteszt, utolsó Release (v1.06), tagek és commitok lekérdezése GitHub REST API-n keresztül.
4. `/api/backups`:
   - `GET /data`: Helyi PostgreSQL mentések (valós méret, dátum, komment) és Git commit előzmények.
   - `POST /create`: Teljes rendszermentés (.tar.gz vagy .sql.gz) generálása a forráskódokkal, képernyőképekkel és adatbázis dumppal.
   - `POST /regenerate-docs`: Rendszerleírások, élő DDL sémák és AI tudásbázis frissítése gombnyomásra.
   - `POST /git-commit-push`: Új verzió (+0.01) commit és Release Tag készítése a GitHub API-n keresztül.
   - `POST /save-screenshot`, `GET /screenshots`: Automatikus képernyőképek mentése és kiszolgálása (.jpg).
