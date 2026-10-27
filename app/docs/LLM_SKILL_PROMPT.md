# AD Tracker - Helyi LLM Tudásbázis és Szakértői Rendszerprompt
*Verzió: v1.08 | Dátum: 2026-10-26 12:32:06 UTC*

## Rendszer Áttekintés
Az AD Tracker egy professzionális Active Directory változáskövető, telemetriai és biztonsági audit központ.

## Kulcsfogalmak és Üzleti Logika
1. **Felhasználói Státuszok (user_status):**
   - `Aktív normál user`: Engedélyezett, normál vállalati munkatárs.
   - `Külsős`: Alvállalkozó vagy külső partner.
   - `Távozottak`: Volt kolléga, fiókja letiltva vagy az archívumba helyezve.
   - `Hosszútávúszabadság`: GYES, fizetés nélküli vagy tartós távolléten lévő munkatárs.
2. **Hatókör-illesztés (Scope Adoption):**
   - A korábbi hiányos CSV mentések és az élő AD szinkron közötti hatókör-különbség nem jelent jogosultság-elvonást.
   - Eseménytípus: `SCOPE_ADOPTED` és `SCOPE_RECONCILED`.
3. **Jogosultsági Események:**
   - `ADDED_TO_GROUP`: Új csoporttagság hozzáadva.
   - `REMOVED_FROM_GROUP`: Csoporttagság megszüntetve / elvéve.
   - `USER_DISABLED` / `USER_ENABLED`: Fiók letiltva vagy aktiválva.

## Adatbázis Táblák és Lekérdezési Stratégia
- `ad_users`: Felhasználók azonosítója (sam_account_name), teljes neve (display_name), emailje, beosztása (title), szervezeti egysége.
- `ad_groups`: Biztonsági csoportok és terjesztési listák, leírások.
- `ad_group_members`: M:N relációs kapcsolótábla a tagok és csoportok között.
- `ad_audit_log`: Időbélyeggel ellátott pontos változástörténet.