# Skill: AD Tracker Rendszerelemző és Teljes Újraépítési Playbook
Ez a skill leírja a teljes rendszer nulláról történő újraépítésének lépéseit:

## 1. Lépés: Docker és Környezet Felállítása
- `docker-compose.yml`: Web és PostgreSQL 15 alpine szolgáltatás.
- `Dockerfile`: Python 3.11-slim + git és PostgreSQL kliens.

## 2. Lépés: Adatbázis Séma Felépítése
- Alkalmazni kell a `docs/DATABASE_SCHEMA.sql` DDL utasításait a táblák létrehozásához.

## 3. Lépés: Keresztbe-hivatkozásos Tagságfeloldó Algoritmus
- Egy felhasználó csoportjainak feltárásakor a `member_of` mezőt, az `ad_groups.members` oszlopot és az `ad_audit_log` előzményeket össze kell uniózni.
