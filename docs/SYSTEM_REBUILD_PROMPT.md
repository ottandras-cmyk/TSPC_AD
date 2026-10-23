# MASTER SYSTEM REBUILDER BLUEPRINT & PROMPT
# Generálva az élő rendszerből: 2026-10-23 04:54:55 UTC | Verzió: v1.05

---
[DIRECTIVE FOR AI SYSTEM ARCHITECT]
Reconstruct the complete, production-grade AD Tracker application using the live technical specifications below.
Generate every component (endpoints, database models, background scheduler, LDAP sync logic, and environment configurations) matching these exact contracts.
---

## 1. REQUIREMENTS ÉS CSOMAGVERZIÓK
```text
ad_analytics
apscheduler>=3.10.4
fastapi>=0.110.0
hashlib
hmac
ipaddress
ldap3>=2.9.1
main
psycopg2-binary>=2.9.9
python-multipart>=0.0.9
socket
sqlalchemy>=2.0.28
ssl
subprocess
telemetry
uvicorn>=0.28.0
```

## 2. FASTAPI VÉGPONTOK (ROUTES) ÉS DECORATOROK
```json
[
  {
    "path": "/openapi.json",
    "name": "openapi",
    "methods": [
      "HEAD",
      "GET"
    ]
  },
  {
    "path": "/docs",
    "name": "swagger_ui_html",
    "methods": [
      "HEAD",
      "GET"
    ]
  },
  {
    "path": "/docs/oauth2-redirect",
    "name": "swagger_ui_redirect",
    "methods": [
      "HEAD",
      "GET"
    ]
  },
  {
    "path": "/redoc",
    "name": "redoc_html",
    "methods": [
      "HEAD",
      "GET"
    ]
  },
  {
    "path": "/login",
    "name": "login_page",
    "methods": [
      "GET"
    ]
  },
  {
    "path": "/login",
    "name": "process_login",
    "methods": [
      "POST"
    ]
  },
  {
    "path": "/logout",
    "name": "process_logout",
    "methods": [
      "GET"
    ]
  },
  {
    "path": "/api/sync-status",
    "name": "get_sync_status",
    "methods": [
      "GET"
    ]
  },
  {
    "path": "/api/sync-history",
    "name": "get_sync_history",
    "methods": [
      "GET"
    ]
  },
  {
    "path": "/api/users",
    "name": "get_all_users",
    "methods": [
      "GET"
    ]
  },
  {
    "path": "/api/users/{sam}/history",
    "name": "get_user_history",
    "methods": [
      "GET"
    ]
  },
  {
    "path": "/api/groups",
    "name": "get_all_groups",
    "methods": [
      "GET"
    ]
  },
  {
    "path": "/api/sync",
    "name": "trigger_sync_manual",
    "methods": [
      "POST"
    ]
  },
  {
    "path": "/api/ad-analytics/day-events",
    "name": "api_ad_analytics_day_events",
    "methods": [
      "GET"
    ]
  },
  {
    "path": "/api/ad-analytics/summary",
    "name": "api_ad_analytics_summary",
    "methods": [
      "GET"
    ]
  },
  {
    "path": "/api/ad-analytics/ask",
    "name": "api_ad_analytics_ask",
    "methods": [
      "POST"
    ]
  },
  {
    "path": "/api/telemetry/live",
    "name": "api_telemetry_live",
    "methods": [
      "GET"
    ]
  },
  {
    "path": "/api/telemetry/sessions",
    "name": "api_telemetry_sessions",
    "methods": [
      "GET"
    ]
  },
  {
    "path": "/api/telemetry/history",
    "name": "api_telemetry_history",
    "methods": [
      "GET"
    ]
  },
  {
    "path": "/api/telemetry/web-logs",
    "name": "api_telemetry_web_logs",
    "methods": [
      "GET"
    ]
  },
  {
    "path": "/api/telemetry/host-ip-history",
    "name": "api_telemetry_host_ip_history",
    "methods": [
      "GET"
    ]
  },
  {
    "path": "/api/telemetry/collect",
    "name": "api_telemetry_collect",
    "methods": [
      "POST"
    ]
  },
  {
    "path": "/api/history/upload-files",
    "name": "api_history_upload_files",
    "methods": [
      "POST"
    ]
  },
  {
    "path": "/api/history/scan",
    "name": "api_history_scan",
    "methods": [
      "POST"
    ]
  },
  {
    "path": "/api/history/backfill",
    "name": "api_history_backfill",
    "methods": [
      "POST"
    ]
  },
  {
    "path": "/api/history/import",
    "name": "api_history_import",
    "methods": [
      "POST"
    ]
  },
  {
    "path": "/api/history/progress",
    "name": "api_history_progress",
    "methods": [
      "GET"
    ]
  },
  {
    "path": "/api/backups",
    "name": "get_backups_list",
    "methods": [
      "GET"
    ]
  },
  {
    "path": "/api/backups/create",
    "name": "create_backup_endpoint",
    "methods": [
      "POST"
    ]
  },
  {
    "path": "/api/backups/restore",
    "name": "restore_backup_endpoint",
    "methods": [
      "POST"
    ]
  },
  {
    "path": "/api/backups/download/{filename}",
    "name": "download_backup_endpoint",
    "methods": [
      "GET"
    ]
  },
  {
    "path": "/api/backups/{filename}",
    "name": "delete_backup_endpoint",
    "methods": [
      "DELETE"
    ]
  },
  {
    "path": "/api/github/version",
    "name": "api_gh_get_version",
    "methods": [
      "GET"
    ]
  },
  {
    "path": "/api/github/test",
    "name": "api_gh_test",
    "methods": [
      "POST"
    ]
  },
  {
    "path": "/api/github/history",
    "name": "api_gh_history",
    "methods": [
      "GET"
    ]
  },
  {
    "path": "/api/github/push",
    "name": "api_gh_push",
    "methods": [
      "POST"
    ]
  },
  {
    "path": "/api/ai/models",
    "name": "get_ai_models",
    "methods": [
      "GET"
    ]
  },
  {
    "path": "/api/ai/ask",
    "name": "ask_ai_endpoint",
    "methods": [
      "POST"
    ]
  },
  {
    "path": "/api/settings",
    "name": "save_settings",
    "methods": [
      "POST"
    ]
  },
  {
    "path": "/",
    "name": "index_page",
    "methods": [
      "GET"
    ]
  }
]
```

## 3. FORRÁSKÓD FÜGGVÉNYEK ÉS DEKORÁTOROK (AST INTROSPEKCIÓ)
```json
{
  "app/doc_generator.py": {
    "classes": [],
    "functions": [
      {
        "name": "ensure_docs_dir",
        "decorators": []
      },
      {
        "name": "inspect_database_schema",
        "decorators": []
      },
      {
        "name": "inspect_sqlalchemy_relationships",
        "decorators": []
      },
      {
        "name": "inspect_codebase",
        "decorators": []
      },
      {
        "name": "inspect_ldap_attributes",
        "decorators": []
      },
      {
        "name": "inspect_fastapi_and_scheduler",
        "decorators": []
      },
      {
        "name": "inspect_environment_and_settings",
        "decorators": []
      },
      {
        "name": "generate_live_requirements",
        "decorators": []
      },
      {
        "name": "build_all_docs",
        "decorators": []
      }
    ]
  },
  "app/ldap_client.py": {
    "classes": [],
    "functions": [
      {
        "name": "parse_ad_server",
        "decorators": []
      },
      {
        "name": "test_ad_connection",
        "decorators": []
      }
    ]
  },
  "app/config_manager.py": {
    "classes": [],
    "functions": [
      {
        "name": "get_setting",
        "decorators": []
      },
      {
        "name": "update_setting",
        "decorators": []
      },
      {
        "name": "init_default_settings",
        "decorators": []
      }
    ]
  },
  "app/github_sync.py": {
    "classes": [],
    "functions": [
      {
        "name": "_request",
        "decorators": []
      },
      {
        "name": "test_github_connection",
        "decorators": []
      },
      {
        "name": "get_latest_github_version",
        "decorators": []
      },
      {
        "name": "get_github_commit_history",
        "decorators": []
      },
      {
        "name": "push_code_to_github",
        "decorators": []
      }
    ]
  },
  "app/backup_manager.py": {
    "classes": [],
    "functions": [
      {
        "name": "serialize_val",
        "decorators": []
      },
      {
        "name": "generate_sql_insert",
        "decorators": []
      },
      {
        "name": "create_backup",
        "decorators": []
      },
      {
        "name": "list_backups",
        "decorators": []
      },
      {
        "name": "restore_backup",
        "decorators": []
      },
      {
        "name": "delete_backup",
        "decorators": []
      }
    ]
  },
  "app/ad_analytics.py": {
    "classes": [],
    "functions": [
      {
        "name": "is_valid_group_name",
        "decorators": []
      },
      {
        "name": "extract_group_name",
        "decorators": []
      },
      {
        "name": "get_clean_ad_changes",
        "decorators": []
      },
      {
        "name": "get_ad_analytics_summary",
        "decorators": []
      },
      {
        "name": "get_day_detailed_events",
        "decorators": []
      },
      {
        "name": "ask_ad_changes_ai",
        "decorators": []
      }
    ]
  },
  "app/main.py": {
    "classes": [],
    "functions": [
      {
        "name": "execute_sync_with_log",
        "decorators": []
      },
      {
        "name": "scheduled_sync_job",
        "decorators": []
      },
      {
        "name": "scheduled_telemetry_job",
        "decorators": []
      },
      {
        "name": "lifespan",
        "decorators": [
          "@asynccontextmanager"
        ]
      },
      {
        "name": "get_current_session",
        "decorators": []
      },
      {
        "name": "get_current_user",
        "decorators": []
      },
      {
        "name": "login_page",
        "decorators": [
          "@app.get"
        ]
      },
      {
        "name": "process_login",
        "decorators": [
          "@app.post"
        ]
      },
      {
        "name": "process_logout",
        "decorators": [
          "@app.get"
        ]
      },
      {
        "name": "get_sync_status",
        "decorators": [
          "@app.get"
        ]
      },
      {
        "name": "get_sync_history",
        "decorators": [
          "@app.get"
        ]
      },
      {
        "name": "get_all_users",
        "decorators": [
          "@app.get"
        ]
      },
      {
        "name": "get_user_history",
        "decorators": [
          "@app.get"
        ]
      },
      {
        "name": "get_all_groups",
        "decorators": [
          "@app.get"
        ]
      },
      {
        "name": "trigger_sync_manual",
        "decorators": [
          "@app.post"
        ]
      },
      {
        "name": "api_ad_analytics_day_events",
        "decorators": [
          "@app.get"
        ]
      },
      {
        "name": "api_ad_analytics_summary",
        "decorators": [
          "@app.get"
        ]
      },
      {
        "name": "api_ad_analytics_ask",
        "decorators": [
          "@app.post"
        ]
      },
      {
        "name": "api_telemetry_live",
        "decorators": [
          "@app.get"
        ]
      },
      {
        "name": "api_telemetry_sessions",
        "decorators": [
          "@app.get"
        ]
      },
      {
        "name": "api_telemetry_history",
        "decorators": [
          "@app.get"
        ]
      },
      {
        "name": "api_telemetry_web_logs",
        "decorators": [
          "@app.get"
        ]
      },
      {
        "name": "api_telemetry_host_ip_history",
        "decorators": [
          "@app.get"
        ]
      },
      {
        "name": "api_telemetry_collect",
        "decorators": [
          "@app.post"
        ]
      },
      {
        "name": "api_history_upload_files",
        "decorators": [
          "@app.post"
        ]
      },
      {
        "name": "api_history_scan",
        "decorators": [
          "@app.post"
        ]
      },
      {
        "name": "api_history_backfill",
        "decorators": [
          "@app.post"
        ]
      },
      {
        "name": "async_import_worker",
        "decorators": []
      },
      {
        "name": "api_history_import",
        "decorators": [
          "@app.post"
        ]
      },
      {
        "name": "api_history_progress",
        "decorators": [
          "@app.get"
        ]
      },
      {
        "name": "get_backups_list",
        "decorators": [
          "@app.get"
        ]
      },
      {
        "name": "create_backup_endpoint",
        "decorators": [
          "@app.post"
        ]
      },
      {
        "name": "restore_backup_endpoint",
        "decorators": [
          "@app.post"
        ]
      },
      {
        "name": "download_backup_endpoint",
        "decorators": [
          "@app.get"
        ]
      },
      {
        "name": "delete_backup_endpoint",
        "decorators": [
          "@app.delete"
        ]
      },
      {
        "name": "api_gh_get_version",
        "decorators": [
          "@app.get"
        ]
      },
      {
        "name": "api_gh_test",
        "decorators": [
          "@app.post"
        ]
      },
      {
        "name": "api_gh_history",
        "decorators": [
          "@app.get"
        ]
      },
      {
        "name": "api_gh_push",
        "decorators": [
          "@app.post"
        ]
      },
      {
        "name": "get_ai_models",
        "decorators": [
          "@app.get"
        ]
      },
      {
        "name": "ask_ai_endpoint",
        "decorators": [
          "@app.post"
        ]
      },
      {
        "name": "save_settings",
        "decorators": [
          "@app.post"
        ]
      },
      {
        "name": "index_page",
        "decorators": [
          "@app.get"
        ]
      },
      {
        "name": "startup_worker",
        "decorators": []
      },
      {
        "name": "on_progress",
        "decorators": []
      }
    ]
  },
  "app/database.py": {
    "classes": [],
    "functions": [
      {
        "name": "get_db",
        "decorators": []
      }
    ]
  },
  "app/ai_assistant.py": {
    "classes": [],
    "functions": [
      {
        "name": "track_tokens",
        "decorators": []
      },
      {
        "name": "fetch_ollama_models",
        "decorators": []
      },
      {
        "name": "ask_ollama",
        "decorators": []
      }
    ]
  },
  "app/telemetry.py": {
    "classes": [],
    "functions": [
      {
        "name": "parse_user_agent",
        "decorators": []
      },
      {
        "name": "resolve_ip_network",
        "decorators": []
      },
      {
        "name": "get_client_ip",
        "decorators": []
      },
      {
        "name": "register_active_session",
        "decorators": []
      },
      {
        "name": "update_active_session",
        "decorators": []
      },
      {
        "name": "close_active_session",
        "decorators": []
      },
      {
        "name": "get_active_sessions_info",
        "decorators": []
      },
      {
        "name": "log_web_activity",
        "decorators": []
      },
      {
        "name": "detect_host_machine_info",
        "decorators": []
      },
      {
        "name": "parse_cpu_metrics",
        "decorators": []
      },
      {
        "name": "parse_ram_metrics",
        "decorators": []
      },
      {
        "name": "parse_disk_metrics",
        "decorators": []
      },
      {
        "name": "parse_gpu_metrics",
        "decorators": []
      },
      {
        "name": "get_db_size_mb",
        "decorators": []
      },
      {
        "name": "get_llm_token_counts",
        "decorators": []
      },
      {
        "name": "collect_and_save_telemetry",
        "decorators": []
      },
      {
        "name": "get_live_telemetry",
        "decorators": []
      },
      {
        "name": "get_telemetry_history",
        "decorators": []
      },
      {
        "name": "get_web_access_logs",
        "decorators": []
      },
      {
        "name": "get_host_ip_history",
        "decorators": []
      },
      {
        "name": "get_system_deep_dossier",
        "decorators": []
      },
      {
        "name": "find_tasks_around",
        "decorators": []
      },
      {
        "name": "find_logins_around",
        "decorators": []
      }
    ]
  },
  "app/sync_engine.py": {
    "classes": [],
    "functions": [
      {
        "name": "parse_ad_datetime",
        "decorators": []
      },
      {
        "name": "parse_ad_filetime",
        "decorators": []
      },
      {
        "name": "extract_ou_path",
        "decorators": []
      },
      {
        "name": "determine_user_status",
        "decorators": []
      },
      {
        "name": "get_attr",
        "decorators": []
      },
      {
        "name": "get_guid",
        "decorators": []
      },
      {
        "name": "run_ad_sync",
        "decorators": []
      }
    ]
  },
  "app/models.py": {
    "classes": [
      "ADUser",
      "ADGroup",
      "ADAuditLog",
      "SyncHistory",
      "SystemSetting",
      "SystemTelemetry",
      "WebAccessLog",
      "HostIPLog",
      "ActiveSession"
    ],
    "functions": []
  },
  "app/history_importer.py": {
    "classes": [],
    "functions": [
      {
        "name": "parse_ad_datetime",
        "decorators": []
      },
      {
        "name": "extract_ou_path",
        "decorators": []
      },
      {
        "name": "read_csv_lines_safe",
        "decorators": []
      },
      {
        "name": "scan_csv_directory",
        "decorators": []
      },
      {
        "name": "parse_snapshot_state",
        "decorators": []
      },
      {
        "name": "fast_backfill_extra_data",
        "decorators": []
      },
      {
        "name": "run_historical_replay",
        "decorators": []
      }
    ]
  },
  "app/auth.py": {
    "classes": [],
    "functions": [
      {
        "name": "create_session_token",
        "decorators": []
      },
      {
        "name": "verify_session_token",
        "decorators": []
      },
      {
        "name": "authenticate_ad_user",
        "decorators": []
      }
    ]
  }
}
```

## 4. SQLALCHEMY RELATIONSHIP-EK ÉS MODELL RELÁCIÓK
```json
{
  "ADUser": {
    "groups": {
      "target_entity": "ad_groups",
      "direction": "MANYTOMANY",
      "secondary_table": "ad_group_members",
      "cascade": "CascadeOptions('merge,save-update')"
    }
  },
  "ADGroup": {
    "members": {
      "target_entity": "ad_users",
      "direction": "MANYTOMANY",
      "secondary_table": "ad_group_members",
      "cascade": "CascadeOptions('merge,save-update')"
    }
  }
}
```

## 5. ACTIVE DIRECTORY / LDAP LEKÉRT ATTRIBUTELISTÁK
```json
{
  "user_attributes": [
    "objectGUID",
    "sAMAccountName",
    "displayName",
    "mail",
    "telephoneNumber",
    "mobile",
    "physicalDeliveryOfficeName",
    "title",
    "department",
    "company",
    "description",
    "objectSid",
    "distinguishedName",
    "userAccountControl",
    "whenCreated",
    "whenChanged",
    "memberOf",
    "lastLogonTimestamp",
    "lastLogon"
  ],
  "group_attributes": [
    "objectGUID",
    "sAMAccountName",
    "distinguishedName",
    "description",
    "groupType",
    "objectSid",
    "whenCreated",
    "whenChanged"
  ]
}
```

## 6. APSCHEDULER ÜTEMEZETT HÁTTÉRFOLYAMATOK
```json
[
  {
    "id": "telemetry_job",
    "name": "scheduled_telemetry_job",
    "trigger": "interval[0:15:00]",
    "next_run_time": "2026-10-23 05:06:56.041609+00:00"
  },
  {
    "id": "ad_sync_job",
    "name": "scheduled_sync_job",
    "trigger": "interval[1 day, 0:00:00]",
    "next_run_time": "2026-10-23 18:06:56.041550+00:00"
  }
]
```

## 7. RENDSZER- ÉS KÖRNYEZETI BEÁLLÍTÁSOK (ENV & CONFIG)
```json
{
  "database_app_settings": {
    "AD_SERVER": {
      "value": "dc1.tspc.hu:389",
      "desc": "Példa: dc1.ceg.hu:389"
    },
    "AD_USER": {
      "value": "tadmin@tspc.hu",
      "desc": "Példa: admin@ceg.hu"
    },
    "AD_PASSWORD": {
      "value": "***",
      "desc": "Az AD olvasó fiók jelszava"
    },
    "AD_SEARCH_BASE": {
      "value": "DC=tspc,DC=hu",
      "desc": "Példa: DC=ceg,DC=hu"
    },
    "OLLAMA_URL": {
      "value": "http://ollama:11434",
      "desc": "A helyi Ollama API címe"
    },
    "SYNC_INTERVAL_MINUTES": {
      "value": "1440",
      "desc": "Automatikus szinkronizáció gyakorisága percben (0 = kikapcsolva)"
    },
    "GH_REPO": {
      "value": "ottandras-cmyk/TSPC_AD",
      "desc": ""
    },
    "GH_TOKEN": {
      "value": "***",
      "desc": ""
    },
    "GH_BRANCH": {
      "value": "main",
      "desc": ""
    },
    "APP_VERSION": {
      "value": "1.05",
      "desc": ""
    },
    "LLM_TOKENS_PROMPT": {
      "value": "***",
      "desc": ""
    },
    "LLM_TOKENS_EVAL": {
      "value": "***",
      "desc": ""
    },
    "LLM_TOKENS_TOTAL": {
      "value": "***",
      "desc": ""
    }
  },
  "active_env_variables": [
    "AD_PASSWORD",
    "AD_SEARCH_BASE",
    "AD_SERVER",
    "AD_USER",
    "GPG_KEY",
    "HOME",
    "HOSTNAME",
    "LANG",
    "PATH",
    "POSTGRES_URL",
    "PYTHON_SHA256",
    "PYTHON_VERSION"
  ]
}
```

## 8. POSTGRESQL DDL ADATBÁZIS SÉMA
```sql
-- AD TRACKER - ÉLŐ POSTGRESQL DDL ADATBÁZIS SÉMA
-- Generálva: 2026-10-23 04:54:55 UTC | Verzió: v1.05

CREATE TABLE active_web_sessions (
	session_id VARCHAR(100) NOT NULL, 
	username VARCHAR(255) NOT NULL, 
	login_time TIMESTAMP WITH TIME ZONE, 
	last_activity TIMESTAMP WITH TIME ZONE, 
	client_ip VARCHAR(100), 
	browser VARCHAR(100), 
	os_name VARCHAR(100), 
	device_type VARCHAR(50), 
	location VARCHAR(255), 
	user_agent TEXT, 
	PRIMARY KEY (session_id)
);

CREATE TABLE ad_audit_log (
	id SERIAL NOT NULL, 
	timestamp TIMESTAMP WITH TIME ZONE, 
	entity_type VARCHAR(50) NOT NULL, 
	entity_name VARCHAR(255) NOT NULL, 
	change_type VARCHAR(50) NOT NULL, 
	details TEXT, 
	raw_diff TEXT, 
	source_type VARCHAR(50), 
	source_ref VARCHAR(255), 
	PRIMARY KEY (id)
);

CREATE TABLE ad_groups (
	object_guid UUID NOT NULL, 
	sam_account_name VARCHAR(255) NOT NULL, 
	distinguished_name TEXT, 
	description TEXT, 
	group_type VARCHAR(100), 
	object_sid VARCHAR(255), 
	source_type VARCHAR(50), 
	source_ref VARCHAR(255), 
	when_created TIMESTAMP WITH TIME ZONE, 
	when_changed TIMESTAMP WITH TIME ZONE, 
	last_synced_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (object_guid)
);

CREATE TABLE ad_users (
	object_guid UUID NOT NULL, 
	sam_account_name VARCHAR(255) NOT NULL, 
	display_name VARCHAR(255), 
	mail VARCHAR(255), 
	is_enabled BOOLEAN, 
	distinguished_name TEXT, 
	first_name VARCHAR(255), 
	last_name VARCHAR(255), 
	description TEXT, 
	office VARCHAR(255), 
	title VARCHAR(255), 
	department VARCHAR(255), 
	company VARCHAR(255), 
	telephone_number VARCHAR(100), 
	mobile VARCHAR(100), 
	object_sid VARCHAR(255), 
	last_logon_date TIMESTAMP WITH TIME ZONE, 
	user_status VARCHAR(100), 
	ou_path TEXT, 
	source_type VARCHAR(50), 
	source_ref VARCHAR(255), 
	when_created TIMESTAMP WITH TIME ZONE, 
	when_changed TIMESTAMP WITH TIME ZONE, 
	last_synced_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (object_guid)
);

CREATE TABLE app_settings (
	setting_key VARCHAR(100) NOT NULL, 
	setting_value TEXT NOT NULL, 
	description VARCHAR(255), 
	PRIMARY KEY (setting_key)
);

CREATE TABLE host_ip_history (
	id SERIAL NOT NULL, 
	timestamp TIMESTAMP WITH TIME ZONE, 
	ip_address VARCHAR(100) NOT NULL, 
	hostname VARCHAR(255), 
	details TEXT, 
	PRIMARY KEY (id)
);

CREATE TABLE sync_history (
	id SERIAL NOT NULL, 
	started_at TIMESTAMP WITH TIME ZONE, 
	ended_at TIMESTAMP WITH TIME ZONE, 
	duration_seconds INTEGER, 
	trigger_type VARCHAR(50), 
	status VARCHAR(50), 
	changes_detected INTEGER, 
	error_message TEXT, 
	PRIMARY KEY (id)
);

CREATE TABLE system_telemetry (
	id SERIAL NOT NULL, 
	timestamp TIMESTAMP WITH TIME ZONE, 
	cpu_percent FLOAT, 
	cpu_temp_c FLOAT, 
	ram_total_mb FLOAT, 
	ram_used_mb FLOAT, 
	ram_percent FLOAT, 
	disk_total_gb FLOAT, 
	disk_used_gb FLOAT, 
	disk_free_gb FLOAT, 
	db_size_mb FLOAT, 
	gpu_name VARCHAR(100), 
	gpu_util_percent FLOAT, 
	gpu_mem_used_mb FLOAT, 
	gpu_mem_total_mb FLOAT, 
	gpu_temp_c FLOAT, 
	gpu_power_w FLOAT, 
	llm_tokens_prompt INTEGER, 
	llm_tokens_eval INTEGER, 
	llm_tokens_total INTEGER, 
	PRIMARY KEY (id)
);

CREATE TABLE web_access_log (
	id SERIAL NOT NULL, 
	timestamp TIMESTAMP WITH TIME ZONE, 
	username VARCHAR(255) NOT NULL, 
	client_ip VARCHAR(100) NOT NULL, 
	browser VARCHAR(100), 
	os_name VARCHAR(100), 
	device_type VARCHAR(50), 
	location VARCHAR(255), 
	user_agent TEXT, 
	action VARCHAR(100) NOT NULL, 
	details TEXT, 
	status VARCHAR(50), 
	PRIMARY KEY (id)
);

CREATE TABLE ad_group_members (
	user_guid UUID NOT NULL, 
	group_guid UUID NOT NULL, 
	assigned_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (user_guid, group_guid), 
	FOREIGN KEY(user_guid) REFERENCES ad_users (object_guid), 
	FOREIGN KEY(group_guid) REFERENCES ad_groups (object_guid)
);
```