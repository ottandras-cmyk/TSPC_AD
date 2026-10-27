# TSPC AD Tracker & Rendszerközpont - Teljes Rendszerdokumentáció
Generálás ideje: 2026-10-27 05:13:56
Verzió: v1.08 / v1.09
Környezet: Éles üzemeltetés (Docker Compose konténeresítés)

## 1. Műszaki Áttekintés & Architektúra
- **Backend:** Python 3.11+, FastAPI (REST API architektúra), Uvicorn ASGI kiszolgáló.
- **Adatbázis Motor:** PostgreSQL 15 relációs adatbázis (Docker hálózatban izolálva).
- **Frontend:** Vanilla JavaScript ES6+, HTML5, CSS3 kártyadobozos elrendezés.
- **Alkalmazás Célja:** Active Directory jogosultságok, csoporttagságok, audit naplók, IT Helpdesk jegyek (#2403) és távoli GitHub verziók központi kezelése.

## 2. Élő Adatbázis Statisztika & Entitások
- **Összes Active Directory Felhasználó:** 3907 fő (2925 aktív, 982 letiltott).
- **Active Directory Csoportok:** 858 db (Biztonsági csoportok, Mappák, Terjesztési listák).
- **Helpdesk Hibajegyek (#2403 Projekt):** 1029 db szinkronizált hibajegy valós leltári számokkal.

## 3. Integrációs Végpontok és Hitelesítés
- **Telegram Bot:** @tspc_IT_bot (Chat ID: 229087988).
- **GitHub Integráció:** Repository: ottandras-cmyk/TSPC_AD (Release Tag pipeline).
- **LDAP Szinkronizáció:** dc1.tspc.hu:389 (Bázis: DC=tspc,DC=hu).
