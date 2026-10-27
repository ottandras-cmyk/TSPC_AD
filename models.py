import uuid
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Float, ForeignKey, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, synonym
from sqlalchemy.sql import func
from database import Base

# ========================================================
# RENDSZER BEÁLLÍTÁSOK
# ========================================================
class SystemSetting(Base):
    __tablename__ = "app_settings"
    setting_key = Column(String(100), primary_key=True, index=True)
    setting_value = Column(Text, nullable=True)
    description = Column(String(255), nullable=True)

    key = synonym("setting_key")
    value = synonym("setting_value")

AppSetting = SystemSetting

# ========================================================
# ACTIVE DIRECTORY MODELLEK
# ========================================================
group_memberships = Table(
    'ad_group_members',
    Base.metadata,
    Column('user_guid', UUID(as_uuid=True), ForeignKey('ad_users.object_guid', ondelete="CASCADE"), primary_key=True),
    Column('group_guid', UUID(as_uuid=True), ForeignKey('ad_groups.object_guid', ondelete="CASCADE"), primary_key=True),
    Column('assigned_at', DateTime(timezone=True), server_default=func.now())
)

class ADUser(Base):
    __tablename__ = "ad_users"
    object_guid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sam_account_name = Column(String(100), unique=True, index=True, nullable=False)
    display_name = Column(String(255), index=True)
    mail = Column(String(255), index=True)
    title = Column(String(255))
    department = Column(String(255))
    telephone_number = Column(String(100))
    distinguished_name = Column(String(500), unique=True)
    user_principal_name = Column(String(255))
    user_account_control = Column(Integer)
    is_enabled = Column(Boolean, default=True)
    pwd_last_set = Column(DateTime, nullable=True)
    last_logon_timestamp = Column(DateTime, nullable=True)
    when_created = Column(DateTime, nullable=True)
    when_changed = Column(DateTime, nullable=True)
    first_seen_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)

    groups = relationship('ADGroup', secondary=group_memberships, back_populates='members')

class ADGroup(Base):
    __tablename__ = "ad_groups"
    object_guid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sam_account_name = Column(String(100), unique=True, index=True, nullable=False)
    distinguished_name = Column(String(500), unique=True)
    description = Column(String(255))
    group_scope = Column(String(50))
    first_seen_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)

    members = relationship('ADUser', secondary=group_memberships, back_populates='groups')

class ADAuditLog(Base):
    __tablename__ = "ad_audit_log"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    entity_type = Column(String(50), nullable=False, default="USER")
    entity_dn = Column(String(500), nullable=True, default="")
    entity_name = Column(String(255), nullable=True, default="")
    change_type = Column(String(100), nullable=False, default="")
    attribute_name = Column(String(100), nullable=True, default="")
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    details = Column(Text, nullable=True)

class SyncHistory(Base):
    __tablename__ = "sync_history"
    id = Column(Integer, primary_key=True, index=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, default=0.0)
    status = Column(String(50), default="IN_PROGRESS")
    trigger_type = Column(String(50), default="SCHEDULED")
    changes_detected = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)

class WebAccessLog(Base):
    __tablename__ = "web_access_log"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    username = Column(String(100), nullable=False, index=True)
    client_ip = Column(String(50), nullable=False)
    user_agent = Column(String(255), nullable=True)
    device_type = Column(String(50), nullable=True)
    browser = Column(String(50), nullable=True)
    os_name = Column(String(50), nullable=True)
    action = Column(String(100), nullable=False)
    details = Column(Text, nullable=True)
    status = Column(String(50), default="SUCCESS")

class SystemTelemetry(Base):
    __tablename__ = "system_telemetry"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    cpu_percent = Column(Float)
    cpu_freq_mhz = Column(Float, nullable=True)
    cpu_cores_logical = Column(Integer)
    ram_total_gb = Column(Float)
    ram_used_gb = Column(Float)
    ram_percent = Column(Float)
    swap_total_gb = Column(Float)
    swap_used_gb = Column(Float)
    swap_percent = Column(Float)
    disk_total_gb = Column(Float)
    disk_used_gb = Column(Float)
    disk_free_gb = Column(Float)
    disk_percent = Column(Float)
    net_bytes_sent_mb = Column(Float, nullable=True)
    net_bytes_recv_mb = Column(Float, nullable=True)
    uptime_hours = Column(Float, nullable=True)
    process_count = Column(Integer, nullable=True)
    system_load_1m = Column(Float, nullable=True)

class HostIpHistory(Base):
    __tablename__ = "host_ip_history"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    interface_name = Column(String(50))
    ip_address = Column(String(50))
    ip_version = Column(String(10), default="IPv4")

class ActiveWebSession(Base):
    __tablename__ = "active_web_sessions"
    id = Column(Integer, primary_key=True, index=True)
    session_token = Column(String(128), unique=True, index=True, nullable=False)
    username = Column(String(100), nullable=False)
    client_ip = Column(String(50), nullable=False)
    user_agent = Column(String(255), nullable=True)
    device_type = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_activity_at = Column(DateTime, default=datetime.utcnow)

# ========================================================
# EASY PROJECT & HELPDESK MODELLEK
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
    hd_serial = Column(String(100), nullable=True)
    inventory_number = Column(String(100), nullable=True)
    phone = Column(String(100), nullable=True)
    location = Column(String(255), nullable=True)
    category = Column(String(255), nullable=True)
    contact_method = Column(String(100), nullable=True)
    ticket_desc_html = Column(Text, nullable=True)
    solution_html = Column(Text, nullable=True)
    raw_json = Column(Text, nullable=True)
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
    changes_count = Column(Integer, default=0)
    sync_type = Column(String(50), default="GENERAL")
    error_message = Column(Text, nullable=True)

class EPAuditLog(Base):
    __tablename__ = "ep_audit_log"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    entity_type = Column(String(50), default="TASK")
    entity_id = Column(Integer, index=True)
    entity_name = Column(String(500))
    project_name = Column(String(255), nullable=True)
    change_type = Column(String(100), index=True)
    old_value = Column(String(255), nullable=True)
    new_value = Column(String(255), nullable=True)
    details = Column(Text, nullable=True)
    assigned_mail = Column(String(255), nullable=True, index=True)

class EPHelpdeskTicket(Base):
    __tablename__ = "ep_tickets"
    id = Column(Integer, primary_key=True, index=True)
    ep_id = Column(Integer, unique=True, index=True)
    project_id = Column(Integer, default=2403, index=True)
    project_name = Column(String(255), default="Helpdesk Kezelő")
    subject = Column(String(500), nullable=False)
    status_id = Column(Integer, nullable=True)
    status_name = Column(String(100), index=True)
    priority_name = Column(String(100), index=True)
    tracker_name = Column(String(100), index=True)

    author_id = Column(Integer, nullable=True)
    author_name = Column(String(255), index=True)
    assigned_to_id = Column(Integer, nullable=True)
    assigned_to_name = Column(String(255), index=True)
    assigned_to_mail = Column(String(255), nullable=True)

    done_ratio = Column(Integer, default=0)
    created_on = Column(DateTime, nullable=True, index=True)
    updated_on = Column(DateTime, nullable=True)
    due_date = Column(DateTime, nullable=True)

    hd_serial = Column(String(100), nullable=True, index=True)
    inventory_number = Column(String(100), nullable=True, index=True)
    phone = Column(String(100), nullable=True)
    location = Column(String(255), nullable=True, index=True)
    category = Column(String(255), nullable=True, index=True)
    contact_method = Column(String(100), nullable=True)
    ticket_desc_html = Column(Text, nullable=True)
    solution_html = Column(Text, nullable=True)

    raw_json = Column(Text, nullable=True)
    synced_at = Column(DateTime, default=datetime.utcnow)
