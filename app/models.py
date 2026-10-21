from sqlalchemy import Column, String, Boolean, DateTime, Text, Table, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from database import Base
import uuid
from datetime import datetime

group_memberships = Table(
    'ad_group_members',
    Base.metadata,
    Column('user_guid', UUID(as_uuid=True), ForeignKey('ad_users.object_guid', ondelete='CASCADE'), primary_key=True),
    Column('group_guid', UUID(as_uuid=True), ForeignKey('ad_groups.object_guid', ondelete='CASCADE'), primary_key=True),
    Column('assigned_at', DateTime(timezone=True), default=datetime.utcnow)
)

class ADUser(Base):
    __tablename__ = "ad_users"

    object_guid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sam_account_name = Column(String(100), unique=True, nullable=False, index=True)
    display_name = Column(String(255))
    mail = Column(String(255))
    telephone_number = Column(String(100))
    mobile = Column(String(100))
    office = Column(String(100))
    title = Column(String(100))
    department = Column(String(100))
    company = Column(String(100))
    description = Column(Text)
    object_sid = Column(String(100))
    distinguished_name = Column(Text)
    is_enabled = Column(Boolean, default=True)
    when_created = Column(DateTime(timezone=True))
    when_changed = Column(DateTime(timezone=True))
    last_synced_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Új PowerShell attribútumok
    last_logon_date = Column(DateTime(timezone=True), nullable=True)
    user_status = Column(String(100), nullable=True)
    ou_path = Column(Text, nullable=True)

    groups = relationship("ADGroup", secondary=group_memberships, back_populates="members")

class ADGroup(Base):
    __tablename__ = "ad_groups"

    object_guid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sam_account_name = Column(String(100), unique=True, nullable=False, index=True)
    distinguished_name = Column(Text)
    description = Column(Text)
    group_type = Column(String(50))
    object_sid = Column(String(100))
    when_created = Column(DateTime(timezone=True))
    when_changed = Column(DateTime(timezone=True))
    last_synced_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    members = relationship("ADUser", secondary=group_memberships, back_populates="groups")

class ADAuditLog(Base):
    __tablename__ = "ad_audit_log"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    entity_type = Column(String(50), nullable=False)
    entity_name = Column(String(255), nullable=False)
    change_type = Column(String(50), nullable=False)
    details = Column(Text)
    raw_diff = Column(Text, nullable=True)

class SyncHistory(Base):
    __tablename__ = "sync_history"

    id = Column(Integer, primary_key=True, index=True)
    started_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    trigger_type = Column(String(50), default="Ütemezett")
    status = Column(String(50), default="FOLYAMATBAN")
    changes_detected = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)

class SystemSetting(Base):
    __tablename__ = "app_settings"

    setting_key = Column(String(100), primary_key=True)
    setting_value = Column(Text, nullable=False)
    description = Column(String(255), nullable=True)
