# Skill: AD Tracker Rendszerelemző és Teljes Újraépítési Playbook
Ez a skill leírja a teljes rendszer nulláról történő újraépítésének lépéseit:

## 1. Lépés: Docker és Környezet Felállítása
- `docker-compose.yml`: Web (8080:8000) és PostgreSQL 15 alpine (5432) szolgáltatás.
- `Dockerfile`: Python 3.11-slim + git és PostgreSQL kliens.

## 2. Lépés: Adatbázis Séma Felépítése
- Alkalmazni kell a `docs/DATABASE_SCHEMA.sql` DDL utasításait a táblák létrehozásához (`ad_users`, `ad_groups`, `ad_audit_log`, `ep_tasks`, `ep_projects`, `ep_tickets`).

## 3. Lépés: Keresztbe-hivatkozásos Tagságfeloldó Algoritmus (Reverse Resolution)
- Egy felhasználó csoportjainak feltárásakor a `member_of` mezőt, az `ad_groups.members` oszlopot és az `ad_audit_log` előzményeket össze kell uniózni.
- Csoport megnyitásakor szét kell választani a `Felhasználókat (👤)` és a `Beágyazott csoportokat (👥)`.

## 4. Lépés: Telegram és GitHub Integrációk
- Telegram küldéskor kötelező a HTML karaktervédelem (`&` helyett `&amp;`), parse hiba esetén automatikus sima szöveges fallback.
- GitHub Release esetén a GitHub REST API-t (`POST /repos/owner/repo/releases`) kell meghívni `tag_name="vX.XX"` paraméterrel.
