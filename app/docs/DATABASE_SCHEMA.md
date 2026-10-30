# AD Tracker - Adatbázis Séma és Modell Dokumentáció (v1.08)
*Automatikusan generálva: 2026-10-28 11:24:54 UTC*

A rendszer PostgreSQL relációs adatbázist használ SQLAlchemy ORM modellekkel.

## Tábla: `ad_audit_log` (ORM Modell: `ADAuditLog`)
| Oszlop | Típus | Elsődleges kulcs | Nullable |
| :--- | :--- | :--- | :--- |
| `id` | `BIGINT` | Igen | Nem |
| `timestamp` | `DATETIME` | Nem | Igen |
| `entity_type` | `VARCHAR(50)` | Nem | Nem |
| `entity_name` | `VARCHAR(255)` | Nem | Nem |
| `change_type` | `VARCHAR(50)` | Nem | Nem |
| `details` | `TEXT` | Nem | Igen |
| `raw_diff` | `TEXT` | Nem | Igen |
| `source_type` | `VARCHAR(50)` | Nem | Igen |
| `source_ref` | `VARCHAR(255)` | Nem | Igen |
| `entity_dn` | `VARCHAR(500)` | Nem | Igen |
| `attribute_name` | `VARCHAR(100)` | Nem | Igen |
| `old_value` | `TEXT` | Nem | Igen |
| `new_value` | `TEXT` | Nem | Igen |

## Tábla: `ad_groups` (ORM Modell: `ADGroup`)
| Oszlop | Típus | Elsődleges kulcs | Nullable |
| :--- | :--- | :--- | :--- |
| `object_guid` | `UUID` | Igen | Nem |
| `sam_account_name` | `VARCHAR(255)` | Nem | Nem |
| `distinguished_name` | `TEXT` | Nem | Nem |
| `description` | `TEXT` | Nem | Igen |
| `group_type` | `VARCHAR(50)` | Nem | Igen |
| `object_sid` | `VARCHAR(100)` | Nem | Igen |
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
| `telephone_number` | `VARCHAR(255)` | Nem | Igen |
| `mobile` | `VARCHAR(255)` | Nem | Igen |
| `object_sid` | `VARCHAR(100)` | Nem | Igen |
| `last_logon_date` | `DATETIME` | Nem | Igen |
| `user_status` | `VARCHAR(100)` | Nem | Igen |
| `ou_path` | `TEXT` | Nem | Igen |
| `source_type` | `VARCHAR(50)` | Nem | Igen |
| `source_ref` | `VARCHAR(255)` | Nem | Igen |
| `user_principal_name` | `VARCHAR(255)` | Nem | Igen |
| `user_account_control` | `INTEGER` | Nem | Igen |
| `pwd_last_set` | `DATETIME` | Nem | Igen |
| `last_logon_timestamp` | `DATETIME` | Nem | Igen |
| `first_seen_at` | `DATETIME` | Nem | Igen |
| `last_seen_at` | `DATETIME` | Nem | Igen |
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

## Tábla: `ep_audit_log` (ORM Modell: `EPAuditLog`)
| Oszlop | Típus | Elsődleges kulcs | Nullable |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | Igen | Nem |
| `timestamp` | `DATETIME` | Nem | Igen |
| `entity_type` | `VARCHAR(50)` | Nem | Igen |
| `entity_id` | `INTEGER` | Nem | Igen |
| `entity_name` | `VARCHAR(500)` | Nem | Igen |
| `project_name` | `VARCHAR(255)` | Nem | Igen |
| `change_type` | `VARCHAR(100)` | Nem | Igen |
| `old_value` | `VARCHAR(255)` | Nem | Igen |
| `new_value` | `VARCHAR(255)` | Nem | Igen |
| `details` | `TEXT` | Nem | Igen |
| `assigned_mail` | `VARCHAR(255)` | Nem | Igen |

## Tábla: `ep_tickets` (ORM Modell: `EPHelpdeskTicket`)
| Oszlop | Típus | Elsődleges kulcs | Nullable |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | Igen | Nem |
| `ep_id` | `INTEGER` | Nem | Igen |
| `project_id` | `INTEGER` | Nem | Igen |
| `project_name` | `VARCHAR(255)` | Nem | Igen |
| `subject` | `VARCHAR(500)` | Nem | Nem |
| `status_id` | `INTEGER` | Nem | Igen |
| `status_name` | `VARCHAR(100)` | Nem | Igen |
| `priority_name` | `VARCHAR(100)` | Nem | Igen |
| `tracker_name` | `VARCHAR(100)` | Nem | Igen |
| `author_id` | `INTEGER` | Nem | Igen |
| `author_name` | `VARCHAR(255)` | Nem | Igen |
| `assigned_to_id` | `INTEGER` | Nem | Igen |
| `assigned_to_name` | `VARCHAR(255)` | Nem | Igen |
| `assigned_to_mail` | `VARCHAR(255)` | Nem | Igen |
| `done_ratio` | `INTEGER` | Nem | Igen |
| `created_on` | `DATETIME` | Nem | Igen |
| `updated_on` | `DATETIME` | Nem | Igen |
| `due_date` | `DATETIME` | Nem | Igen |
| `hd_serial` | `VARCHAR(100)` | Nem | Igen |
| `inventory_number` | `VARCHAR(100)` | Nem | Igen |
| `phone` | `VARCHAR(100)` | Nem | Igen |
| `location` | `VARCHAR(255)` | Nem | Igen |
| `category` | `VARCHAR(255)` | Nem | Igen |
| `contact_method` | `VARCHAR(100)` | Nem | Igen |
| `ticket_desc_html` | `TEXT` | Nem | Igen |
| `solution_html` | `TEXT` | Nem | Igen |
| `raw_json` | `TEXT` | Nem | Igen |
| `synced_at` | `DATETIME` | Nem | Igen |

## Tábla: `ep_projects` (ORM Modell: `EPProject`)
| Oszlop | Típus | Elsődleges kulcs | Nullable |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | Igen | Nem |
| `ep_id` | `INTEGER` | Nem | Igen |
| `name` | `VARCHAR(255)` | Nem | Nem |
| `identifier` | `VARCHAR(255)` | Nem | Igen |
| `description` | `TEXT` | Nem | Igen |
| `status` | `INTEGER` | Nem | Igen |
| `is_public` | `BOOLEAN` | Nem | Igen |
| `created_on` | `DATETIME` | Nem | Igen |
| `updated_on` | `DATETIME` | Nem | Igen |
| `synced_at` | `DATETIME` | Nem | Igen |

## Tábla: `ep_sync_history` (ORM Modell: `EPSyncHistory`)
| Oszlop | Típus | Elsődleges kulcs | Nullable |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | Igen | Nem |
| `started_at` | `DATETIME` | Nem | Igen |
| `ended_at` | `DATETIME` | Nem | Igen |
| `duration_seconds` | `FLOAT` | Nem | Igen |
| `status` | `VARCHAR(50)` | Nem | Igen |
| `trigger_type` | `VARCHAR(50)` | Nem | Igen |
| `projects_count` | `INTEGER` | Nem | Igen |
| `tasks_count` | `INTEGER` | Nem | Igen |
| `users_count` | `INTEGER` | Nem | Igen |
| `changes_count` | `INTEGER` | Nem | Igen |
| `sync_type` | `VARCHAR(50)` | Nem | Igen |
| `error_message` | `TEXT` | Nem | Igen |

## Tábla: `ep_tasks` (ORM Modell: `EPTask`)
| Oszlop | Típus | Elsődleges kulcs | Nullable |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | Igen | Nem |
| `ep_id` | `INTEGER` | Nem | Igen |
| `project_id` | `INTEGER` | Nem | Igen |
| `project_name` | `VARCHAR(255)` | Nem | Igen |
| `tracker_name` | `VARCHAR(100)` | Nem | Igen |
| `status_name` | `VARCHAR(100)` | Nem | Igen |
| `priority_name` | `VARCHAR(100)` | Nem | Igen |
| `subject` | `VARCHAR(500)` | Nem | Nem |
| `description` | `TEXT` | Nem | Igen |
| `assigned_to_id` | `INTEGER` | Nem | Igen |
| `assigned_to_name` | `VARCHAR(255)` | Nem | Igen |
| `assigned_to_mail` | `VARCHAR(255)` | Nem | Igen |
| `done_ratio` | `INTEGER` | Nem | Igen |
| `estimated_hours` | `FLOAT` | Nem | Igen |
| `spent_hours` | `FLOAT` | Nem | Igen |
| `created_on` | `DATETIME` | Nem | Igen |
| `updated_on` | `DATETIME` | Nem | Igen |
| `due_date` | `DATETIME` | Nem | Igen |
| `hd_serial` | `VARCHAR(100)` | Nem | Igen |
| `inventory_number` | `VARCHAR(100)` | Nem | Igen |
| `phone` | `VARCHAR(100)` | Nem | Igen |
| `location` | `VARCHAR(255)` | Nem | Igen |
| `category` | `VARCHAR(255)` | Nem | Igen |
| `contact_method` | `VARCHAR(100)` | Nem | Igen |
| `ticket_desc_html` | `TEXT` | Nem | Igen |
| `solution_html` | `TEXT` | Nem | Igen |
| `raw_json` | `TEXT` | Nem | Igen |
| `custom_field_498` | `TEXT` | Nem | Igen |
| `custom_field_499` | `TEXT` | Nem | Igen |
| `custom_field_500` | `TEXT` | Nem | Igen |
| `custom_field_503` | `TEXT` | Nem | Igen |
| `custom_field_530` | `TEXT` | Nem | Igen |
| `custom_field_545` | `TEXT` | Nem | Igen |
| `synced_at` | `DATETIME` | Nem | Igen |

## Tábla: `ep_users` (ORM Modell: `EPUser`)
| Oszlop | Típus | Elsődleges kulcs | Nullable |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | Igen | Nem |
| `ep_id` | `INTEGER` | Nem | Igen |
| `login` | `VARCHAR(100)` | Nem | Igen |
| `firstname` | `VARCHAR(100)` | Nem | Igen |
| `lastname` | `VARCHAR(100)` | Nem | Igen |
| `mail` | `VARCHAR(255)` | Nem | Igen |
| `status` | `INTEGER` | Nem | Igen |
| `synced_at` | `DATETIME` | Nem | Igen |

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
| `id` | `BIGINT` | Igen | Nem |
| `started_at` | `DATETIME` | Nem | Igen |
| `ended_at` | `DATETIME` | Nem | Igen |
| `duration_seconds` | `BIGINT` | Nem | Igen |
| `trigger_type` | `VARCHAR(50)` | Nem | Igen |
| `status` | `VARCHAR(50)` | Nem | Igen |
| `changes_detected` | `BIGINT` | Nem | Igen |
| `error_message` | `TEXT` | Nem | Igen |
| `completed_at` | `DATETIME` | Nem | Igen |

## SharePoint helyi másolatok

Az `eszkozleltar_nonIT`, `O365LicenceInfo`, `Atadas_atvetel` és `IT_Inventory` listák
az alábbi külön PostgreSQL-táblákba szinkronizálódnak:
`SP_eszkozleltar_nonIT`, `SP_O365LicenceInfo`, `SP_Atadas_atvetel` és `SP_IT_Inventory`.
Mindegyik tábla az egyedi `sharepoint_item_id`, a teljes SharePoint-mezőket tároló
`fields` JSONB, a `source_modified_at`, `synced_at` és `is_deleted` oszlopokat tartalmazza.
Az egyes frissítések minden listát együtt dolgoznak fel. Az új, módosult, visszaállított
és a SharePointból eltávolított elemek verzióit a `sharepoint_item_changes` tárolja.

## Tábla: `sharepoint_sync_history` (ORM Modell: `SharePointSyncHistory`)
| Oszlop | Típus | Elsődleges kulcs | Nullable |
| :--- | :--- | :--- | :--- |
| `id` | `BIGINT` | Igen | Nem |
| `list_name` | `VARCHAR(255)` | Nem | Nem |
| `started_at` | `DATETIME` | Nem | Nem |
| `ended_at` | `DATETIME` | Nem | Igen |
| `duration_seconds` | `FLOAT` | Nem | Igen |
| `trigger_type` | `VARCHAR(50)` | Nem | Nem |
| `status` | `VARCHAR(50)` | Nem | Nem |
| `items_count` | `INTEGER` | Nem | Nem |
| `added_count` | `INTEGER` | Nem | Nem |
| `updated_count` | `INTEGER` | Nem | Nem |
| `deleted_count` | `INTEGER` | Nem | Nem |
| `error_message` | `TEXT` | Nem | Igen |

## Tábla: `sharepoint_item_changes` (ORM Modell: `SharePointItemChange`)
| Oszlop | Típus | Elsődleges kulcs | Nullable |
| :--- | :--- | :--- | :--- |
| `id` | `BIGINT` | Igen | Nem |
| `list_name` | `VARCHAR(255)` | Nem | Nem |
| `sharepoint_item_id` | `VARCHAR(100)` | Nem | Nem |
| `change_type` | `VARCHAR(20)` | Nem | Nem |
| `changed_fields` | `JSONB` | Nem | Nem |
| `previous_fields` | `JSONB` | Nem | Igen |
| `current_fields` | `JSONB` | Nem | Igen |
| `changed_at` | `DATETIME` | Nem | Nem |
| `trigger_type` | `VARCHAR(50)` | Nem | Nem |

## Tábla: `app_settings` (ORM Modell: `SystemSetting`)
| Oszlop | Típus | Elsődleges kulcs | Nullable |
| :--- | :--- | :--- | :--- |
| `setting_key` | `VARCHAR(100)` | Igen | Nem |
| `setting_value` | `TEXT` | Nem | Igen |
| `description` | `VARCHAR(255)` | Nem | Igen |

## Tábla: `system_telemetry` (ORM Modell: `SystemTelemetry`)
| Oszlop | Típus | Elsődleges kulcs | Nullable |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | Igen | Nem |
| `timestamp` | `DATETIME` | Nem | Igen |
| `cpu_percent` | `FLOAT` | Nem | Igen |
| `cpu_temp_c` | `FLOAT` | Nem | Igen |
| `cpu_power_w` | `FLOAT` | Nem | Igen |
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
