# AD Tracker - Rendszer Architektúra és Modultérkép
Generálva: 2026-10-21 18:17:33 UTC | Verzió: v1.04

## Feltárt Forráskód Modulok

### Modul: `app/doc_generator.py`
- **Függvények / Metódusok:** ensure_docs_dir, inspect_database_schema, inspect_codebase, generate_live_requirements, query_local_ollama, build_all_docs

### Modul: `app/ldap_client.py`
- **Függvények / Metódusok:** parse_ad_server, test_ad_connection

### Modul: `app/config_manager.py`
- **Függvények / Metódusok:** get_setting, update_setting, init_default_settings

### Modul: `app/github_sync.py`
- **Függvények / Metódusok:** _request, test_github_connection, get_latest_github_version, get_github_commit_history, push_code_to_github

### Modul: `app/backup_manager.py`
- **Függvények / Metódusok:** serialize_val, generate_sql_insert, create_backup, list_backups, restore_backup, delete_backup

### Modul: `app/main.py`
- **Függvények / Metódusok:** execute_sync_with_log, scheduled_sync_job, get_current_user, login_page, process_login, process_logout, get_sync_status, get_sync_history, get_all_users, get_user_history, get_all_groups, trigger_sync_manual, async_import_worker, api_history_progress, get_backups_list, download_backup_endpoint, delete_backup_endpoint, api_gh_get_version, api_gh_history, get_ai_models, index_page, on_progress

### Modul: `app/database.py`
- **Függvények / Metódusok:** get_db

### Modul: `app/ai_assistant.py`
- **Függvények / Metódusok:** fetch_ollama_models, extract_search_terms, build_database_context, ask_ollama

### Modul: `app/sync_engine.py`
- **Függvények / Metódusok:** parse_ad_datetime, parse_ad_filetime, extract_ou_path, determine_user_status, get_attr, get_guid, run_ad_sync

### Modul: `app/models.py`
- **Osztályok:** ADUser, ADGroup, ADAuditLog, SyncHistory, SystemSetting

### Modul: `app/history_importer.py`
- **Függvények / Metódusok:** parse_ad_datetime, extract_ou_path, read_csv_lines_safe, scan_csv_directory, parse_snapshot_state, fast_backfill_extra_data, run_historical_replay

### Modul: `app/auth.py`
- **Függvények / Metódusok:** authenticate_ad_user, create_session_token, verify_session_token
