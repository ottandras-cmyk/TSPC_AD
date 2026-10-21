# AD Tracker - Adatbázis Séma Dokumentáció
Generálva: 2026-10-21 18:17:33 UTC | Alkalmazás verzió: v1.04

## Feltárt Adatbázis Táblák és Mezők

### Tábla: `ad_audit_log`
- **Elsődleges kulcs(ok):** id
| Mező neve | Típus | Nullable |
| :--- | :--- | :--- |
| `id` | `BIGINT` | False |
| `timestamp` | `TIMESTAMP` | True |
| `entity_type` | `VARCHAR(50)` | False |
| `entity_name` | `VARCHAR(255)` | False |
| `change_type` | `VARCHAR(50)` | False |
| `details` | `TEXT` | True |
| `raw_diff` | `TEXT` | True |

### Tábla: `ad_group_members`
- **Elsődleges kulcs(ok):** user_guid, group_guid
- **Idegen kulcsok:** ['group_guid'] -> ad_groups.['object_guid'], ['user_guid'] -> ad_users.['object_guid']
| Mező neve | Típus | Nullable |
| :--- | :--- | :--- |
| `user_guid` | `UUID` | False |
| `group_guid` | `UUID` | False |
| `assigned_at` | `TIMESTAMP` | True |

### Tábla: `ad_users`
- **Elsődleges kulcs(ok):** object_guid
| Mező neve | Típus | Nullable |
| :--- | :--- | :--- |
| `object_guid` | `UUID` | False |
| `sam_account_name` | `VARCHAR(255)` | False |
| `display_name` | `VARCHAR(255)` | True |
| `mail` | `VARCHAR(255)` | True |
| `is_enabled` | `BOOLEAN` | True |
| `distinguished_name` | `TEXT` | True |
| `last_synced_at` | `TIMESTAMP` | True |
| `telephone_number` | `VARCHAR(255)` | True |
| `object_sid` | `VARCHAR(100)` | True |
| `when_created` | `TIMESTAMP` | True |
| `when_changed` | `TIMESTAMP` | True |
| `first_name` | `VARCHAR(255)` | True |
| `last_name` | `VARCHAR(255)` | True |
| `description` | `TEXT` | True |
| `office` | `VARCHAR(255)` | True |
| `title` | `VARCHAR(255)` | True |
| `department` | `VARCHAR(255)` | True |
| `company` | `VARCHAR(255)` | True |
| `mobile` | `VARCHAR(255)` | True |
| `last_logon_date` | `TIMESTAMP` | True |
| `user_status` | `VARCHAR(100)` | True |
| `ou_path` | `TEXT` | True |

### Tábla: `ad_groups`
- **Elsődleges kulcs(ok):** object_guid
| Mező neve | Típus | Nullable |
| :--- | :--- | :--- |
| `object_guid` | `UUID` | False |
| `sam_account_name` | `VARCHAR(255)` | False |
| `distinguished_name` | `TEXT` | False |
| `description` | `TEXT` | True |
| `last_synced_at` | `TIMESTAMP` | True |
| `group_type` | `VARCHAR(50)` | True |
| `object_sid` | `VARCHAR(100)` | True |
| `when_created` | `TIMESTAMP` | True |
| `when_changed` | `TIMESTAMP` | True |

### Tábla: `app_settings`
- **Elsődleges kulcs(ok):** setting_key
| Mező neve | Típus | Nullable |
| :--- | :--- | :--- |
| `setting_key` | `VARCHAR(50)` | False |
| `setting_value` | `TEXT` | True |
| `description` | `VARCHAR(255)` | True |

### Tábla: `sync_history`
- **Elsődleges kulcs(ok):** id
| Mező neve | Típus | Nullable |
| :--- | :--- | :--- |
| `id` | `BIGINT` | False |
| `started_at` | `TIMESTAMP` | True |
| `ended_at` | `TIMESTAMP` | True |
| `duration_seconds` | `BIGINT` | True |
| `trigger_type` | `VARCHAR(50)` | True |
| `status` | `VARCHAR(50)` | True |
| `changes_detected` | `BIGINT` | True |
| `error_message` | `TEXT` | True |
