from database import engine
from sqlalchemy import text

statements = [
    # 1. ad_audit_log hiányzó mezői
    "ALTER TABLE ad_audit_log ADD COLUMN IF NOT EXISTS entity_dn VARCHAR(500) DEFAULT '';",
    "ALTER TABLE ad_audit_log ADD COLUMN IF NOT EXISTS entity_type VARCHAR(50) DEFAULT 'USER';",
    "ALTER TABLE ad_audit_log ADD COLUMN IF NOT EXISTS entity_name VARCHAR(255) DEFAULT '';",
    "ALTER TABLE ad_audit_log ADD COLUMN IF NOT EXISTS change_type VARCHAR(100) DEFAULT '';",
    "ALTER TABLE ad_audit_log ADD COLUMN IF NOT EXISTS attribute_name VARCHAR(100) DEFAULT '';",
    "ALTER TABLE ad_audit_log ADD COLUMN IF NOT EXISTS old_value TEXT;",
    "ALTER TABLE ad_audit_log ADD COLUMN IF NOT EXISTS new_value TEXT;",
    "ALTER TABLE ad_audit_log ADD COLUMN IF NOT EXISTS details TEXT;",

    # 2. ep_tickets HTML leírás és megoldás oszlopok
    "ALTER TABLE ep_tickets ADD COLUMN IF NOT EXISTS ticket_desc_html TEXT;",
    "ALTER TABLE ep_tickets ADD COLUMN IF NOT EXISTS solution_html TEXT;",
    "ALTER TABLE ep_tickets ADD COLUMN IF NOT EXISTS hd_serial VARCHAR(100);",
    "ALTER TABLE ep_tickets ADD COLUMN IF NOT EXISTS inventory_number VARCHAR(100);",
    "ALTER TABLE ep_tickets ADD COLUMN IF NOT EXISTS phone VARCHAR(100);",
    "ALTER TABLE ep_tickets ADD COLUMN IF NOT EXISTS location VARCHAR(255);",
    "ALTER TABLE ep_tickets ADD COLUMN IF NOT EXISTS category VARCHAR(255);",
    "ALTER TABLE ep_tickets ADD COLUMN IF NOT EXISTS contact_method VARCHAR(100);",
    "ALTER TABLE ep_tickets ADD COLUMN IF NOT EXISTS raw_json TEXT;",

    # 3. ep_tasks HTML leírás és megoldás oszlopok
    "ALTER TABLE ep_tasks ADD COLUMN IF NOT EXISTS ticket_desc_html TEXT;",
    "ALTER TABLE ep_tasks ADD COLUMN IF NOT EXISTS solution_html TEXT;",
    "ALTER TABLE ep_tasks ADD COLUMN IF NOT EXISTS hd_serial VARCHAR(100);",
    "ALTER TABLE ep_tasks ADD COLUMN IF NOT EXISTS inventory_number VARCHAR(100);",
    "ALTER TABLE ep_tasks ADD COLUMN IF NOT EXISTS phone VARCHAR(100);",
    "ALTER TABLE ep_tasks ADD COLUMN IF NOT EXISTS location VARCHAR(255);",
    "ALTER TABLE ep_tasks ADD COLUMN IF NOT EXISTS category VARCHAR(255);",
    "ALTER TABLE ep_tasks ADD COLUMN IF NOT EXISTS contact_method VARCHAR(100);",
    "ALTER TABLE ep_tasks ADD COLUMN IF NOT EXISTS raw_json TEXT;",

    # 4. ep_sync_history mezők
    "ALTER TABLE ep_sync_history ADD COLUMN IF NOT EXISTS sync_type VARCHAR(50) DEFAULT 'GENERAL';",
    "ALTER TABLE ep_sync_history ADD COLUMN IF NOT EXISTS changes_count INTEGER DEFAULT 0;"
]

with engine.connect() as conn:
    for stmt in statements:
        try:
            conn.execute(text(stmt))
            conn.commit()
        except Exception:
            pass
print("✅ Adatbázis sémák sikeresen frissítve!")
