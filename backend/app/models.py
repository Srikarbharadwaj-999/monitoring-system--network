from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import relationship
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="admin", nullable=False)
    created_at = Column(DateTime, server_default=func.now())

class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    device_name = Column(String, nullable=False)
    ip_address = Column(String, unique=True, index=True, nullable=False)
    mac_address = Column(String, nullable=True)
    hostname = Column(String, nullable=True)
    device_type = Column(String, nullable=False)  # Laptop, PC, Printer, Router, Camera, Server, Mobile
    location = Column(String, nullable=True)
    current_status = Column(String, default="Offline", nullable=False)  # Online, Offline, Warning
    last_latency_ms = Column(Float, nullable=True)
    last_seen = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    ping_logs = relationship("PingLog", back_populates="device", cascade="all, delete-orphan")
    downtime_logs = relationship("DowntimeLog", back_populates="device", cascade="all, delete-orphan")

class PingLog(Base):
    __tablename__ = "ping_logs"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    ip_address = Column(String, nullable=False)
    status = Column(String, nullable=False)  # Online, Offline
    latency_ms = Column(Float, nullable=True)
    packet_loss = Column(Float, default=0.0)
    checked_at = Column(DateTime, server_default=func.now(), index=True)

    # Relationships
    device = relationship("Device", back_populates="ping_logs")

class DowntimeLog(Base):
    __tablename__ = "downtime_logs"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    went_down_at = Column(DateTime, nullable=False)
    came_up_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    reason_prediction = Column(String, nullable=True)

    # Relationships
    device = relationship("Device", back_populates="downtime_logs")
