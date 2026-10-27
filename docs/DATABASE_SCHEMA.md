# AD Tracker - Adatbázis Séma és Modell Dokumentáció (v1.08)
*Automatikusan generálva: 2026-10-26 12:32:06 UTC*

A rendszer PostgreSQL relációs adatbázist használ SQLAlchemy ORM modellekkel.

## Tábla: `ad_audit_log` (ORM Modell: `ADAuditLog`)
| Oszlop | Típus | Elsődleges kulcs | Nullable |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | Igen | Nem |
| `timestamp` | `DATETIME` | Nem | Igen |
| `entity_type` | `VARCHAR(50)` | Nem | Nem |
| `entity_dn` | `VARCHAR(500)` | Nem | Igen |
| `entity_name` | `VARCHAR(255)` | Nem | Igen |
| `change_type` | `VARCHAR(100)` | Nem | Nem |
| `attribute_name` | `VARCHAR(100)` | Nem | Igen |
| `old_value` | `TEXT` | Nem | Igen |
| `new_value` | `TEXT` | Nem | Igen |
| `details` | `TEXT` | Nem | Igen |

## Tábla: `ad_groups` (ORM Modell: `ADGroup`)
| Oszlop | Típus | Elsődleges kulcs | Nullable |
| :--- | :--- | :--- | :--- |
| `object_guid` | `UUID` | Igen | Nem |
| `sam_account_name` | `VARCHAR(100)` | Nem | Nem |
| `distinguished_name` | `VARCHAR(500)` | Nem | Igen |
| `description` | `VARCHAR(255)` | Nem | Igen |
| `group_scope` | `VARCHAR(50)` | Nem | Igen |
| `first_seen_at` | `DATETIME` | Nem | Igen |
| `last_seen_at` | `DATETIME` | Nem | Igen |

## Tábla: `ad_users` (ORM Modell: `ADUser`)
| Oszlop | Típus | Elsődleges kulcs | Nullable |
| :--- | :--- | :--- | :--- |
| `object_guid` | `UUID` | Igen | Nem |
| `sam_account_name` | `VARCHAR(100)` | Nem | Nem |
| `display_name` | `VARCHAR(255)` | Nem | Igen |
| `mail` | `VARCHAR(255)` | Nem | Igen |
| `title` | `VARCHAR(255)` | Nem | Igen |
| `department` | `VARCHAR(255)` | Nem | Igen |
| `telephone_number` | `VARCHAR(100)` | Nem | Igen |
| `distinguished_name` | `VARCHAR(500)` | Nem | Igen |
| `user_principal_name` | `VARCHAR(255)` | Nem | Igen |
| `user_account_control` | `INTEGER` | Nem | Igen |
| `is_enabled` | `BOOLEAN` | Nem | Igen |
| `pwd_last_set` | `DATETIME` | Nem | Igen |
| `last_logon_timestamp` | `DATETIME` | Nem | Igen |
| `when_created` | `DATETIME` | Nem | Igen |
| `when_changed` | `DATETIME` | Nem | Igen |
| `first_seen_at` | `DATETIME` | Nem | Igen |
| `last_seen_at` | `DATETIME` | Nem | Igen |

## Tábla: `active_web_sessions` (ORM Modell: `ActiveWebSession`)
| Oszlop | Típus | Elsődleges kulcs | Nullable |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | Igen | Nem |
| `session_token` | `VARCHAR(128)` | Nem | Nem |
| `username` | `VARCHAR(100)` | Nem | Nem |
| `client_ip` | `VARCHAR(50)` | Nem | Nem |
| `user_agent` | `VARCHAR(255)` | Nem | Igen |
| `device_type` | `VARCHAR(50)` | Nem | Igen |
| `created_at` | `DATETIME` | Nem | Igen |
| `last_activity_at` | `DATETIME` | Nem | Igen |

## Tábla: `app_settings` (ORM Modell: `SystemSetting`)
| Oszlop | Típus | Elsődleges kulcs | Nullable |
| :--- | :--- | :--- | :--- |
| `setting_key` | `VARCHAR(100)` | Igen | Nem |
| `setting_value` | `TEXT` | Nem | Igen |
| `description` | `VARCHAR(255)` | Nem | Igen |

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

## Tábla: `host_ip_history` (ORM Modell: `HostIpHistory`)
| Oszlop | Típus | Elsődleges kulcs | Nullable |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | Igen | Nem |
| `timestamp` | `DATETIME` | Nem | Igen |
| `interface_name` | `VARCHAR(50)` | Nem | Igen |
| `ip_address` | `VARCHAR(50)` | Nem | Igen |
| `ip_version` | `VARCHAR(10)` | Nem | Igen |

## Tábla: `sync_history` (ORM Modell: `SyncHistory`)
| Oszlop | Típus | Elsődleges kulcs | Nullable |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | Igen | Nem |
| `started_at` | `DATETIME` | Nem | Igen |
| `completed_at` | `DATETIME` | Nem | Igen |
| `duration_seconds` | `FLOAT` | Nem | Igen |
| `status` | `VARCHAR(50)` | Nem | Igen |
| `trigger_type` | `VARCHAR(50)` | Nem | Igen |
| `changes_detected` | `INTEGER` | Nem | Igen |
| `error_message` | `TEXT` | Nem | Igen |

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
| `cpu_freq_mhz` | `FLOAT` | Nem | Igen |
| `cpu_cores_logical` | `INTEGER` | Nem | Igen |
| `ram_total_gb` | `FLOAT` | Nem | Igen |
| `ram_used_gb` | `FLOAT` | Nem | Igen |
| `ram_percent` | `FLOAT` | Nem | Igen |
| `swap_total_gb` | `FLOAT` | Nem | Igen |
| `swap_used_gb` | `FLOAT` | Nem | Igen |
| `swap_percent` | `FLOAT` | Nem | Igen |
| `disk_total_gb` | `FLOAT` | Nem | Igen |
| `disk_used_gb` | `FLOAT` | Nem | Igen |
| `disk_free_gb` | `FLOAT` | Nem | Igen |
| `disk_percent` | `FLOAT` | Nem | Igen |
| `net_bytes_sent_mb` | `FLOAT` | Nem | Igen |
| `net_bytes_recv_mb` | `FLOAT` | Nem | Igen |
| `uptime_hours` | `FLOAT` | Nem | Igen |
| `process_count` | `INTEGER` | Nem | Igen |
| `system_load_1m` | `FLOAT` | Nem | Igen |

## Tábla: `web_access_log` (ORM Modell: `WebAccessLog`)
| Oszlop | Típus | Elsődleges kulcs | Nullable |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | Igen | Nem |
| `timestamp` | `DATETIME` | Nem | Igen |
| `username` | `VARCHAR(100)` | Nem | Nem |
| `client_ip` | `VARCHAR(50)` | Nem | Nem |
| `user_agent` | `VARCHAR(255)` | Nem | Igen |
| `device_type` | `VARCHAR(50)` | Nem | Igen |
| `browser` | `VARCHAR(50)` | Nem | Igen |
| `os_name` | `VARCHAR(50)` | Nem | Igen |
| `action` | `VARCHAR(100)` | Nem | Nem |
| `details` | `TEXT` | Nem | Igen |
| `status` | `VARCHAR(50)` | Nem | Igen |
