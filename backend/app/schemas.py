from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
import ipaddress

# Token schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None

# User schemas
class UserBase(BaseModel):
    username: str
    role: str = "admin"

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Device schemas
class DeviceBase(BaseModel):
    device_name: str
    ip_address: str
    mac_address: Optional[str] = None
    hostname: Optional[str] = None
    device_type: str = "Laptop"  # Laptop, PC, Printer, Router, Camera, Server, Mobile
    location: Optional[str] = None

    @field_validator('ip_address')
    @classmethod
    def validate_ip(cls, value: str) -> str:
        try:
            ipaddress.ip_address(value)
        except ValueError:
            raise ValueError('Invalid IP address format')
        return value

    @field_validator('device_type')
    @classmethod
    def validate_device_type(cls, value: str) -> str:
        allowed = ["Laptop", "PC", "Printer", "Router", "Camera", "Server", "Mobile"]
        if value not in allowed:
            raise ValueError(f'Device type must be one of {allowed}')
        return value

class DeviceCreate(DeviceBase):
    pass

class DeviceUpdate(BaseModel):
    device_name: Optional[str] = None
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    hostname: Optional[str] = None
    device_type: Optional[str] = None
    location: Optional[str] = None

    @field_validator('ip_address')
    @classmethod
    def validate_ip(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        try:
            ipaddress.ip_address(value)
        except ValueError:
            raise ValueError('Invalid IP address format')
        return value

    @field_validator('device_type')
    @classmethod
    def validate_device_type(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        allowed = ["Laptop", "PC", "Printer", "Router", "Camera", "Server", "Mobile"]
        if value not in allowed:
            raise ValueError(f'Device type must be one of {allowed}')
        return value

class DeviceResponse(DeviceBase):
    id: int
    current_status: str
    last_latency_ms: Optional[float] = None
    last_seen: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Ping Log schema
class PingLogResponse(BaseModel):
    id: int
    device_id: int
    ip_address: str
    status: str
    latency_ms: Optional[float] = None
    packet_loss: float
    checked_at: datetime

    class Config:
        from_attributes = True

# Downtime Log schema
class DowntimeLogResponse(BaseModel):
    id: int
    device_id: int
    went_down_at: datetime
    came_up_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    reason_prediction: Optional[str] = None
    device_name: Optional[str] = None  # Helper for reports

    class Config:
        from_attributes = True

# Dashboard Stats schema
class DashboardStats(BaseModel):
    total_devices: int
    online_devices: int
    offline_devices: int
    avg_latency_ms: float
    last_scan_time: Optional[datetime] = None

# Scanner schemas
class SubnetScanRequest(BaseModel):
    subnet: str

    @field_validator('subnet')
    @classmethod
    def validate_subnet(cls, value: str) -> str:
        try:
            ipaddress.ip_network(value, strict=False)
        except ValueError:
            raise ValueError('Invalid Subnet range format (e.g. 192.168.1.0/24)')
        return value

class ScanResultDevice(BaseModel):
    ip_address: str
    mac_address: Optional[str] = None
    hostname: Optional[str] = None
    status: str
    latency_ms: Optional[float] = None
