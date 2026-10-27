# AD Tracker - Audit Lekérdezések és Promptok
Generálva: 2026-10-21 18:17:33 UTC

```sql
-- Kiemelt felhasználók ellenőrzése
SELECT sam_account_name, display_name, user_status, last_logon_date 
FROM ad_users WHERE is_enabled = TRUE 
ORDER BY last_logon_date DESC NULLS LAST;

-- Legfrissebb jogosultság-változások
SELECT timestamp, entity_name, change_type, details 
FROM ad_audit_log WHERE entity_type = 'MEMBERSHIP' 
ORDER BY timestamp DESC LIMIT 50;
```
