# AD Tracker & Rendszerközpont - Grafikai Megjelenési Könyvtár & UI Design System
Verzió: v1.08 / v1.09
Téma: Modern Enterprise Dashboard (Világos felület, sötét tónusú konzolokkal)

## 1. Színpaletta & Design Tokenek
- **Márkaszín (Primary Blue):** `#0284c7` (Sky-600) | Fejlécek, kiemelések, aktív fülek.
- **Siker (Success Green):** `#16a34a` (Green-600) | Aktív állapotok, mentés gombok, jóváhagyások.
- **Figyelmeztetés (Warning Amber):** `#f59e0b` (Amber-500) | Folyamatban lévő jegyek, szinkron állapot.
- **Hiba / Letiltva (Danger Red):** `#dc2626` (Red-600) | Törlés gombok, letiltott AD fiókok.
- **Lila akcentus (Indigo/Purple):** `#6366f1` / `#8b5cf6` | Terjesztési listák, beágyazott csoportok, Git funkciók.
- **Konzol fekete (Dark Slate):** `#0f172a` (Slate-900) | Telegram élő napló és terminál doboz.
- **Alap felületek:** Oldalháttér `#f8fafc`, kártyák `#ffffff`, szegélyek `#e2e8f0`.

## 2. UI Komponensek Felépítése
### A. Felső Navigációs Sáv (.app-navbar)
- Z-index: `99999 !important` (biztosítja, hogy semmilyen modál vagy réteg ne fedje le).
- Gombok: `.app-nav-btn` (border-radius: 6px, aktív állapotban kék háttér `#0284c7` fehér betűvel).

### B. KPI Statisztikai Kártyák (.card-box)
- Bal szegély kiemelés: `border-left: 4px solid [szín]`.
- Kisbetűs szürke felirat (`#64748b`), alatta nagyméretű numerikus érték.

### C. Adattáblázatok
- Váltakozó vagy hover hatás (`#f8fafc`), interaktív oszloprendezés (`▲ / ▼ / ⇅`).
- Kétirányú átjárhatóság: névre vagy csoportra kattintva azonnal felugrik az adott entitás profilja.

### D. Státusz Jelvények (Pills & Badges)
- **AD Aktív:** `background: #dcfce7; color: #15803d;`
- **AD Letiltva:** `background: #fee2e2; color: #dc2626;`
- **Biztonsági csoport:** `background: #05966918; color: #059669; border: 1px solid #05966940;`
- **Terjesztési lista:** `background: #8b5cf618; color: #8b5cf6; border: 1px solid #8b5cf640;`
- **Mappa jogosultság:** `background: #0284c718; color: #0284c7; border: 1px solid #0284c740;`

### E. Modális Dialógusablakok (.modal-overlay)
- Fekete áttetsző réteg backdrop-filterrel, középre igazított fehér kártya görgethető tartalommal.
