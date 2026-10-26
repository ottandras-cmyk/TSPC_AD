import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, Text, Table, ForeignKey, Integer, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from database import Base

group_memberships = Table(
    'ad_group_members',
    Base.metadata,
    Column('user_guid', UUID(as_uuid=True), ForeignKey('ad_users.object_guid'), primary_key=True),
    Column('group_guid', UUID(as_uuid=True), ForeignKey('ad_groups.object_guid'), primary_key=True),
    Column('assigned_at', DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
)

class ADUser(Base):
    __tablename__ = 'ad_users'
    object_guid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sam_account_name = Column(String(255), unique=True, index=True, nullable=False)
    display_name = Column(String(255))
    mail = Column(String(255))
    is_enabled = Column(Boolean, default=True)
    distinguished_name = Column(Text)
    first_name = Column(String(255))
    last_name = Column(String(255))
    description = Column(Text)
    office = Column(String(255))
    title = Column(String(255))
    department = Column(String(255))
    company = Column(String(255))
    telephone_number = Column(String(100))
    mobile = Column(String(100))
    object_sid = Column(String(255))
    last_logon_date = Column(DateTime(timezone=True))
    user_status = Column(String(100))
    ou_path = Column(Text)
    source_type = Column(String(50), default="AD_SYNC")
    source_ref = Column(String(255), default="LIVE_AD")
    when_created = Column(DateTime(timezone=True))
    when_changed = Column(DateTime(timezone=True))
    last_synced_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    groups = relationship('ADGroup', secondary=group_memberships, back_populates='members')

class ADGroup(Base):
    __tablename__ = 'ad_groups'
    object_guid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sam_account_name = Column(String(255), unique=True, index=True, nullable=False)
    distinguished_name = Column(Text)
    description = Column(Text)
    group_type = Column(String(100))
    object_sid = Column(String(255))
    source_type = Column(String(50), default="AD_SYNC")
    source_ref = Column(String(255), default="LIVE_AD")
    when_created = Column(DateTime(timezone=True))
    when_changed = Column(DateTime(timezone=True))
    last_synced_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    members = relationship('ADUser', secondary=group_memberships, back_populates='groups')

class ADAuditLog(Base):
    __tablename__ = 'ad_audit_log'
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    entity_type = Column(String(50), nullable=False)
    entity_name = Column(String(255), nullable=False, index=True)
    change_type = Column(String(50), nullable=False)
    details = Column(Text)
    raw_diff = Column(Text)
    source_type = Column(String(50), default="AD_SYNC")
    source_ref = Column(String(255), default="LIVE_AD")

class SyncHistory(Base):
    __tablename__ = 'sync_history'
    id = Column(Integer, primary_key=True, index=True)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    ended_at = Column(DateTime(timezone=True))
    duration_seconds = Column(Integer)
    trigger_type = Column(String(50))
    status = Column(String(50))
    changes_detected = Column(Integer, default=0)
    error_message = Column(Text)

class SystemSetting(Base):
    __tablename__ = 'app_settings'
    setting_key = Column(String(100), primary_key=True)
    setting_value = Column(Text, nullable=False)
    description = Column(String(255))

class SystemTelemetry(Base):
    __tablename__ = 'system_telemetry'
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    cpu_percent = Column(Float, default=0.0)
    cpu_temp_c = Column(Float, nullable=True)
    ram_total_mb = Column(Float, default=0.0)
    ram_used_mb = Column(Float, default=0.0)
    ram_percent = Column(Float, default=0.0)
    disk_total_gb = Column(Float, default=0.0)
    disk_used_gb = Column(Float, default=0.0)
    disk_free_gb = Column(Float, default=0.0)
    db_size_mb = Column(Float, default=0.0)
    gpu_name = Column(String(100), nullable=True)
    gpu_util_percent = Column(Float, nullable=True)
    gpu_mem_used_mb = Column(Float, nullable=True)
    gpu_mem_total_mb = Column(Float, nullable=True)
    gpu_temp_c = Column(Float, nullable=True)
    gpu_power_w = Column(Float, nullable=True)
    llm_tokens_prompt = Column(Integer, default=0)
    llm_tokens_eval = Column(Integer, default=0)
    llm_tokens_total = Column(Integer, default=0)

class WebAccessLog(Base):
    __tablename__ = 'web_access_log'
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    username = Column(String(255), nullable=False)
    client_ip = Column(String(100), nullable=False)
    browser = Column(String(100))
    os_name = Column(String(100))
    device_type = Column(String(50))
    location = Column(String(255))
    user_agent = Column(Text)
    action = Column(String(100), nullable=False)
    details = Column(Text)
    status = Column(String(50), default="SIKERES")

class HostIPLog(Base):
    __tablename__ = 'host_ip_history'
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    ip_address = Column(String(100), nullable=False)
    hostname = Column(String(255))
    details = Column(Text)

class ActiveSession(Base):
    __tablename__ = 'active_web_sessions'
    session_id = Column(String(100), primary_key=True)
    username = Column(String(255), nullable=False)
    login_time = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_activity = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    client_ip = Column(String(100))
    browser = Column(String(100))
    os_name = Column(String(100))
    device_type = Column(String(50))
    location = Column(String(255))
    user_agent = Column(Text)

# ========================================================
# EASY PROJECT INTEGRÁCIÓS MODELLEK
# ========================================================

class EPProject(Base):
    __tablename__ = "ep_projects"
    id = Column(Integer, primary_key=True, index=True)
    ep_id = Column(Integer, unique=True, index=True)
    name = Column(String(255), nullable=False)
    identifier = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    status = Column(Integer, default=1)
    is_public = Column(Boolean, default=False)
    created_on = Column(DateTime, nullable=True)
    updated_on = Column(DateTime, nullable=True)
    synced_at = Column(DateTime, default=datetime.utcnow)

class EPUser(Base):
    __tablename__ = "ep_users"
    id = Column(Integer, primary_key=True, index=True)
    ep_id = Column(Integer, unique=True, index=True)
    login = Column(String(100), index=True)
    firstname = Column(String(100), nullable=True)
    lastname = Column(String(100), nullable=True)
    mail = Column(String(255), index=True)
    status = Column(Integer, default=1)
    synced_at = Column(DateTime, default=datetime.utcnow)

class EPTask(Base):
    __tablename__ = "ep_tasks"
    id = Column(Integer, primary_key=True, index=True)
    ep_id = Column(Integer, unique=True, index=True)
    project_id = Column(Integer, nullable=True, index=True)
    project_name = Column(String(255), nullable=True)
    tracker_name = Column(String(100), nullable=True)
    status_name = Column(String(100), nullable=True)
    priority_name = Column(String(100), nullable=True)
    subject = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    assigned_to_id = Column(Integer, nullable=True)
    assigned_to_name = Column(String(255), nullable=True)
    assigned_to_mail = Column(String(255), nullable=True, index=True)
    done_ratio = Column(Integer, default=0)
    estimated_hours = Column(Float, nullable=True)
    spent_hours = Column(Float, nullable=True)
    created_on = Column(DateTime, nullable=True)
    updated_on = Column(DateTime, nullable=True)
    due_date = Column(DateTime, nullable=True)
    synced_at = Column(DateTime, default=datetime.utcnow)

class EPSyncHistory(Base):
    __tablename__ = "ep_sync_history"
    id = Column(Integer, primary_key=True, index=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, default=0.0)
    status = Column(String(50), default="FOLYAMATBAN")
    trigger_type = Column(String(50), default="MANUAL")
    projects_count = Column(Integer, default=0)
    tasks_count = Column(Integer, default=0)
    users_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
