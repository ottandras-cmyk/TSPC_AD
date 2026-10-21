from sqlalchemy import Column, String, Boolean, DateTime, BigInteger, ForeignKey, Table, JSON, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from database import Base

class SystemSetting(Base):
    __tablename__ = "app_settings"
    setting_key = Column(String(50), primary_key=True)
    setting_value = Column(Text, nullable=True)
    description = Column(String(255))

# ÚJ: Szinkronizációs napló (Folyamat, időtartam, eredmény)
class SyncHistory(Base):
    __tablename__ = "sync_history"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(BigInteger, nullable=True)
    trigger_type = Column(String(50))   # "Manuális" vagy "Ütemezett"
    status = Column(String(50))         # "FOLYAMATBAN", "SIKERES", "HIBA"
    changes_detected = Column(BigInteger, default=0)
    error_message = Column(Text, nullable=True)

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
    
    telephone_number = Column(String(255))
    mobile = Column(String(255))
    object_sid = Column(String(100))
    when_created = Column(DateTime(timezone=True))
    when_changed = Column(DateTime(timezone=True))

    last_synced_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    groups = relationship("ADGroup", secondary=group_memberships, back_populates="members")

class ADGroup(Base):
    __tablename__ = "ad_groups"
    object_guid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sam_account_name = Column(String(255), unique=True, index=True, nullable=False)
    distinguished_name = Column(Text, nullable=False)
    description = Column(Text)
    group_type = Column(String(50))
    object_sid = Column(String(100))
    when_created = Column(DateTime(timezone=True))
    when_changed = Column(DateTime(timezone=True))
    
    last_synced_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    members = relationship("ADUser", secondary=group_memberships, back_populates="groups")

class ADAuditLog(Base):
    __tablename__ = "ad_audit_log"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    entity_type = Column(String(50), nullable=False)
    entity_name = Column(String(255), nullable=False)
    change_type = Column(String(50), nullable=False)
    details = Column(Text)
    raw_diff = Column(JSON)
