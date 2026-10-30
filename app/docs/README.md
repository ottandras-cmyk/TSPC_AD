# TSPC AD Tracker & Rendszerközpont
Verzió: v1.08 / v1.09
Frissítve: 2026-10-27 05:13:56
Adatbázis: PostgreSQL (3907 felhasználó, 858 csoport)
Helpdesk: #2403 projekt (1029 hibajegy)

## Helyi csatlakozási beállítások

Az AD, Easy Project, Telegram, SharePoint és GitHub csatlakozási adatait, valamint a szinkronizálási gyakoriságokat az alkalmazás helyben az `app/config/settings.local.json` fájlban tárolja. A fájl jogosultsága korlátozott, és a Git, a Docker build, illetve a GitHub-feltöltő kizárja. A repositoryban található `settings.local.json.example` csak üres, anonimizált mintát tartalmaz.

Az alkalmazás első induláskor a korábbi beállításfájlokból és környezeti változókból migrálja az adatokat. A régi konfigurációs fájlokat a migráció nem törli automatikusan.
