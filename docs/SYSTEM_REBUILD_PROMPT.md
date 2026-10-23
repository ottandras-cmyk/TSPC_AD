# SYSTEM REBUILD PROMPT - AD TRACKER (v1.06)
*Automatikusan generálva: 2026-10-23 06:38:23 UTC*

Ez a fájl tartalmazza az alkalmazás moduláris szerkezetének, sémáinak és függőségeinek leírását.

## Moduláris Felépítés
- `app/main.py`: Natív sablonösszefűző motor (nincs külső jinja2 függőség), router regisztráció.
- `app/routers/`: Független FastAPI modulok.
- `app/templates/tabs/`: Izolált HTML mikrosablonok fülönként.
- `app/static/css/theme.css`: Központi Design System és stílusok.
- `app/static/js/ui-core.js`: Kliensoldali vezérlő és interaktivitás.

## Adatbázis Modellek

## Tábla: `ad_audit_log` (ORM Modell: `ADAuditLog`)
| Oszlop | Típus | Elsődleges kulcs | Nullable |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | Igen | Nem |
| `timestamp` | `DATETIME` | Nem | Igen |
| `entity_type` | `VARCHAR(50)` | Nem | Nem |
| `entity_name` | `VARCHAR(255)` | Nem | Nem |
| `change_type` | `VARCHAR(50)` | Nem | Nem |
| `details` | `TEXT` | Nem | Igen |
| `raw_diff` | `TEXT` | Nem | Igen |
| `source_type` | `VARCHAR(50)` | Nem | Igen |
| `source_ref` | `VARCHAR(255)` | Nem | Igen |

## Tábla: `ad_groups` (ORM Modell: `ADGroup`)
| Oszlop | Típus | Elsődleges kulcs | Nullable |
| :--- | :--- | :--- | :--- |
| `object_guid` | `UUID` | Igen | Nem |
| `sam_account_name` | `VARCHAR(255)` | Nem | Nem |
| `distinguished_name` | `TEXT` | Nem | Igen |
| `description` | `TEXT` | Nem | Igen |
| `group_type` | `VARCHAR(100)` | Nem | Igen |
| `object_sid` | `VARCHAR(255)` | Nem | Igen |
| `source_type` | `VARCHAR(50)` | Nem | Igen |
| `source_ref` | `VARCHAR(255)` | Nem | Igen |
| `when_created` | `DATETIME` | Nem | Igen |
| `when_changed` | `DATETIME` | Nem | Igen |
| `last_synced_at` | `DATETIME` | Nem | Igen |

## Tábla: `ad_users` (ORM Modell: `ADUser`)
| Oszlop | Típus | Elsődleges kulcs | Nullable |
| :--- | :--- | :--- | :--- |
| `object_guid` | `UUID` | Igen | Nem |
| `sam_account_name` | `VARCHAR(255)` | Nem | Nem |
| `display_name` | `VARCHAR(255)` | Nem | Igen |
| `mail` | `VARCHAR(255)` | Nem | Igen |
| `is_enabled` | `BOOLEAN` | Nem | Igen |
| `distinguished_name` | `TEXT` | Nem | Igen |
| `first_name` | `VARCHAR(255)` | Nem | Igen |
| `last_name` | `VARCHAR(255)` | Nem | Igen |
| `description` | `TEXT` | Nem | Igen |
| `office` | `VARCHAR(255)` | Nem | Igen |
| `title` | `VARCHAR(255)` | Nem | Igen |
| `department` | `VARCHAR(255)` | Nem | Igen |
| `company` | `VARCHAR(255)` | Nem | Igen |
| `telephone_number` | `VARCHAR(100)` | Nem | Igen |
| `mobile` | `VARCHAR(100)` | Nem | Igen |
| `object_sid` | `VARCHAR(255)` | Nem | Igen |
| `last_logon_date` | `DATETIME` | Nem | Igen |
| `user_status` | `VARCHAR(100)` | Nem | Igen |
| `ou_path` | `TEXT` | Nem | Igen |
| `source_type` | `VARCHAR(50)` | Nem | Igen |
| `source_ref` | `VARCHAR(255)` | Nem | Igen |
| `when_created` | `DATETIME` | Nem | Igen |
| `when_changed` | `DATETIME` | Nem | Igen |
| `last_synced_at` | `DATETIME` | Nem | Igen |

## Tábla: `active_web_sessions` (ORM Modell: `ActiveSession`)
| Oszlop | Típus | Elsődleges kulcs | Nullable |
| :--- | :--- | :--- | :--- |
| `session_id` | `VARCHAR(100)` | Igen | Nem |
| `username` | `VARCHAR(255)` | Nem | Nem |
| `login_time` | `DATETIME` | Nem | Igen |
| `last_activity` | `DATETIME` | Nem | Igen |
| `client_ip` | `VARCHAR(100)` | Nem | Igen |
| `browser` | `VARCHAR(100)` | Nem | Igen |
| `os_name` | `VARCHAR(100)` | Nem | Igen |
| `device_type` | `VARCHAR(50)` | Nem | Igen |
| `location` | `VARCHAR(255)` | Nem | Igen |
| `user_agent` | `TEXT` | Nem | Igen |

## Tábla: `host_ip_history` (ORM Modell: `HostIPLog`)
| Oszlop | Típus | Elsődleges kulcs | Nullable |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | Igen | Nem |
| `timestamp` | `DATETIME` | Nem | Igen |
| `ip_address` | `VARCHAR(100)` | Nem | Nem |
| `hostname` | `VARCHAR(255)` | Nem | Igen |
| `details` | `TEXT` | Nem | Igen |

## Tábla: `sync_history` (ORM Modell: `SyncHistory`)
| Oszlop | Típus | Elsődleges kulcs | Nullable |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | Igen | Nem |
| `started_at` | `DATETIME` | Nem | Igen |
| `ended_at` | `DATETIME` | Nem | Igen |
| `duration_seconds` | `INTEGER` | Nem | Igen |
| `trigger_type` | `VARCHAR(50)` | Nem | Igen |
| `status` | `VARCHAR(50)` | Nem | Igen |
| `changes_detected` | `INTEGER` | Nem | Igen |
| `error_message` | `TEXT` | Nem | Igen |

## Tábla: `app_settings` (ORM Modell: `SystemSetting`)
| Oszlop | Típus | Elsődleges kulcs | Nullable |
| :--- | :--- | :--- | :--- |
| `setting_key` | `VARCHAR(100)` | Igen | Nem |
| `setting_value` | `TEXT` | Nem | Nem |
| `description` | `VARCHAR(255)` | Nem | Igen |

## Tábla: `system_telemetry` (ORM Modell: `SystemTelemetry`)
| Oszlop | Típus | Elsődleges kulcs | Nullable |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | Igen | Nem |
| `timestamp` | `DATETIME` | Nem | Igen |
| `cpu_percent` | `FLOAT` | Nem | Igen |
| `cpu_temp_c` | `FLOAT` | Nem | Igen |
| `ram_total_mb` | `FLOAT` | Nem | Igen |
| `ram_used_mb` | `FLOAT` | Nem | Igen |
| `ram_percent` | `FLOAT` | Nem | Igen |
| `disk_total_gb` | `FLOAT` | Nem | Igen |
| `disk_used_gb` | `FLOAT` | Nem | Igen |
| `disk_free_gb` | `FLOAT` | Nem | Igen |
| `db_size_mb` | `FLOAT` | Nem | Igen |
| `gpu_name` | `VARCHAR(100)` | Nem | Igen |
| `gpu_util_percent` | `FLOAT` | Nem | Igen |
| `gpu_mem_used_mb` | `FLOAT` | Nem | Igen |
| `gpu_mem_total_mb` | `FLOAT` | Nem | Igen |
| `gpu_temp_c` | `FLOAT` | Nem | Igen |
| `gpu_power_w` | `FLOAT` | Nem | Igen |
| `llm_tokens_prompt` | `INTEGER` | Nem | Igen |
| `llm_tokens_eval` | `INTEGER` | Nem | Igen |
| `llm_tokens_total` | `INTEGER` | Nem | Igen |

## Tábla: `web_access_log` (ORM Modell: `WebAccessLog`)
| Oszlop | Típus | Elsődleges kulcs | Nullable |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | Igen | Nem |
| `timestamp` | `DATETIME` | Nem | Igen |
| `username` | `VARCHAR(255)` | Nem | Nem |
| `client_ip` | `VARCHAR(100)` | Nem | Nem |
| `browser` | `VARCHAR(100)` | Nem | Igen |
| `os_name` | `VARCHAR(100)` | Nem | Igen |
| `device_type` | `VARCHAR(50)` | Nem | Igen |
| `location` | `VARCHAR(255)` | Nem | Igen |
| `user_agent` | `TEXT` | Nem | Igen |
| `action` | `VARCHAR(100)` | Nem | Nem |
| `details` | `TEXT` | Nem | Igen |
| `status` | `VARCHAR(50)` | Nem | Igen |
