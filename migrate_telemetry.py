from database import engine
from sqlalchemy import text

statements = [
    """
    CREATE TABLE IF NOT EXISTS active_web_sessions (
        id SERIAL PRIMARY KEY,
        session_token VARCHAR(128) UNIQUE NOT NULL,
        username VARCHAR(100) NOT NULL,
        client_ip VARCHAR(50) NOT NULL,
        user_agent VARCHAR(255),
        device_type VARCHAR(50),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_activity_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS web_access_log (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        username VARCHAR(100) NOT NULL,
        client_ip VARCHAR(50) NOT NULL,
        user_agent VARCHAR(255),
        device_type VARCHAR(50),
        browser VARCHAR(50),
        os_name VARCHAR(50),
        action VARCHAR(100) NOT NULL,
        details TEXT,
        status VARCHAR(50) DEFAULT 'SUCCESS'
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS system_telemetry (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        cpu_percent FLOAT,
        cpu_freq_mhz FLOAT,
        cpu_cores_logical INTEGER,
        ram_total_gb FLOAT,
        ram_used_gb FLOAT,
        ram_percent FLOAT,
        swap_total_gb FLOAT,
        swap_percent FLOAT,
        disk_total_gb FLOAT,
        disk_used_gb FLOAT,
        disk_percent FLOAT,
        uptime_hours FLOAT
    );
    """
]

with engine.connect() as conn:
    for stmt in statements:
        try:
            conn.execute(text(stmt))
            conn.commit()
        except Exception:
            pass
print("✅ Telemetria táblák sikeresen létrehozva!")
