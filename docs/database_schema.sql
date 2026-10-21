-- AD TRACKER - ÉLŐ POSTGRESQL DDL ADATBÁZIS SÉMA
-- Generálva: 2026-10-21 19:30:57 UTC | Verzió: v1.04

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
