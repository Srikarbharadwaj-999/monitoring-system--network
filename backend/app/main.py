import os
import asyncio
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, status, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from jose import jwt
from pydantic import BaseModel

from app.config import settings
from app.database import engine, Base, SessionLocal, get_db
from app.models import User, Device, PingLog, DowntimeLog
from app.schemas import (
    DeviceCreate, DeviceUpdate, DeviceResponse, PingLogResponse, 
    DowntimeLogResponse, SubnetScanRequest, DashboardStats
)
from app.auth import get_current_user, verify_password, create_access_token, get_password_hash
from app.ping_service import is_valid_ip
from app.scanner import scan_subnet, get_suggested_subnet
from app.monitor import start_monitoring_loop
from app.reports import (
    calculate_uptime_stats, generate_devices_csv, 
    generate_ping_logs_csv, generate_downtime_logs_csv
)
from app.websocket_manager import manager

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure tables exist
    Base.metadata.create_all(bind=engine)
    
    # Seed default users
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            db.add(User(
                username="admin",
                password_hash=get_password_hash("admin123"),
                role="admin"
            ))
            db.commit()
            print("Default admin user seeded successfully: admin / admin123")

        manager = db.query(User).filter(User.username == "manager").first()
        if not manager:
            db.add(User(
                username="manager",
                password_hash=get_password_hash("manager123"),
                role="manager"
            ))
            db.commit()
            print("Default manager user seeded successfully: manager / manager123")

        # Seed default common target devices
        device_count = db.query(Device).count()
        if device_count == 0:
            db.add_all([
                Device(
                    device_name="Google Public DNS",
                    ip_address="8.8.8.8",
                    hostname="dns.google",
                    device_type="Server",
                    location="Global Network",
                    current_status="Offline"
                ),
                Device(
                    device_name="Cloudflare DNS",
                    ip_address="1.1.1.1",
                    hostname="one.one.one.one",
                    device_type="Server",
                    location="Global Network",
                    current_status="Offline"
                ),
                Device(
                    device_name="Quad9 DNS",
                    ip_address="9.9.9.9",
                    hostname="dns.quad9.net",
                    device_type="Server",
                    location="Global Network",
                    current_status="Offline"
                ),
                Device(
                    device_name="Local Loopback",
                    ip_address="127.0.0.1",
                    hostname="localhost",
                    device_type="Server",
                    location="Localhost",
                    current_status="Offline"
                )
            ])
            db.commit()
            print("Default common servers seeded successfully: 8.8.8.8, 1.1.1.1, 9.9.9.9, 127.0.0.1")
    except Exception as e:
        print(f"Error seeding default users/devices: {e}")
    finally:
        db.close()
    
    # Start background ping monitoring task
    monitor_task = asyncio.create_task(start_monitoring_loop())
    
    yield
    
    # Shutdown: Cancel background tasks
    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass
    print("Background monitoring task stopped.")

app = FastAPI(
    title="Network Device Ping Monitoring System",
    description="Real-time network ping monitoring dashboard using FastAPI & WebSockets",
    version="1.0.0",
    lifespan=lifespan
)

# Global Redirect Handler for Page Authentication Failures
@app.exception_handler(HTTPException)
async def http_exception_redirect_handler(request: Request, exc: HTTPException):
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        # If the route is an API, return standard JSON 401
        if request.url.path.startswith("/api/") or request.url.path.startswith("/auth/"):
            return JSONResponse(
                status_code=exc.status_code, 
                content={"detail": exc.detail},
                headers=exc.headers
            )
        # Otherwise redirect web pages to /login
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Administrator privileges required."
        )
    return current_user

# Mount static and templates folders
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# --- Authentication APIs ---

class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/auth/login")
def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == login_data.username).first()
    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect username or password"
        )
    
    access_token = create_access_token(data={"sub": user.username, "role": user.role})
    response = JSONResponse(content={"message": "Login successful", "access_token": access_token})
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=False
    )
    return response

@app.post("/auth/logout")
def logout():
    response = JSONResponse(content={"message": "Logged out successfully"})
    response.delete_cookie("access_token")
    return response

# --- WebSocket Endpoints ---

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Maintain connection, parse heartbeat or queries
            data = await websocket.receive_text()
            # Respond to ping or request for statistics
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

# --- UI Page Routes ---

@app.get("/")
def read_root(request: Request):
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/login")
def login_page(request: Request):
    token = request.cookies.get("access_token")
    if token:
        try:
            if token.startswith("Bearer "):
                token = token.split(" ")[1]
            jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
        except Exception:
            pass
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/dashboard")
def dashboard_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": user})

@app.get("/devices")
def devices_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("devices.html", {"request": request, "user": user})

@app.get("/devices/{id}")
def device_detail_page(id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    device = db.query(Device).filter(Device.id == id).first()
    if not device:
        return RedirectResponse(url="/devices", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse("device_detail.html", {"request": request, "user": user, "device": device})

@app.get("/logs")
def logs_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("logs.html", {"request": request, "user": user})

@app.get("/reports")
def reports_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("reports.html", {"request": request, "user": user})

@app.get("/settings")
def settings_page(request: Request, user: User = Depends(get_current_user)):
    suggested = get_suggested_subnet()
    return templates.TemplateResponse("settings.html", {"request": request, "user": user, "suggested_subnet": suggested})

# --- Devices API Endpoints ---

@app.get("/api/devices", response_model=List[DeviceResponse])
def get_devices(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Device).all()

@app.get("/api/devices/{id}", response_model=DeviceResponse)
def get_device(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    device = db.query(Device).filter(Device.id == id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device

@app.post("/api/devices", response_model=DeviceResponse)
def add_device(device: DeviceCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Check IP duplicates
    dup = db.query(Device).filter(Device.ip_address == device.ip_address).first()
    if dup:
        raise HTTPException(status_code=400, detail="Device with this IP already registered.")
    
    new_device = Device(
        device_name=device.device_name,
        ip_address=device.ip_address,
        mac_address=device.mac_address,
        hostname=device.hostname,
        device_type=device.device_type,
        location=device.location,
        current_status="Offline"
    )
    db.add(new_device)
    db.commit()
    db.refresh(new_device)
    return new_device

@app.put("/api/devices/{id}", response_model=DeviceResponse)
def update_device(id: int, dev_update: DeviceUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    device = db.query(Device).filter(Device.id == id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    data = dev_update.dict(exclude_unset=True)
    if "ip_address" in data and data["ip_address"] != device.ip_address:
        dup = db.query(Device).filter(Device.ip_address == data["ip_address"]).first()
        if dup:
            raise HTTPException(status_code=400, detail="Device with this IP already registered.")
            
    for key, val in data.items():
        setattr(device, key, val)
        
    db.commit()
    db.refresh(device)
    return device

@app.delete("/api/devices/{id}")
def delete_device(id: int, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    device = db.query(Device).filter(Device.id == id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    db.delete(device)
    db.delete(device)
    db.commit()
    return {"message": "Device deleted successfully"}

@app.post("/api/devices/{id}/ping")
async def force_ping_device(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    device = db.query(Device).filter(Device.id == id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    from app.ping_service import ping_ip
    status, latency, loss = await ping_ip(device.ip_address)
    prev_status = device.current_status
    now = datetime.now()
    
    device.current_status = status
    device.last_latency_ms = latency
    if status == "Online":
        device.last_seen = now
    device.updated_at = now
    
    ping_log = PingLog(
        device_id=device.id,
        ip_address=device.ip_address,
        status=status,
        latency_ms=latency,
        packet_loss=loss,
        checked_at=now
    )
    db.add(ping_log)
    
    # Downtime Logs management
    if prev_status == "Online" and status == "Offline":
        dt_log = DowntimeLog(
            device_id=device.id,
            went_down_at=now,
            reason_prediction="Manual check failed"
        )
        db.add(dt_log)
    elif prev_status == "Offline" and status == "Online":
        dt_log = db.query(DowntimeLog)\
            .filter(DowntimeLog.device_id == device.id, DowntimeLog.came_up_at.is_(None))\
            .order_by(DowntimeLog.went_down_at.desc())\
            .first()
        if dt_log:
            dt_log.came_up_at = now
            dt_log.duration_seconds = (now - dt_log.went_down_at).total_seconds()
            
    db.commit()
    
    # Broadcast updated stats
    try:
        devices = db.query(Device).all()
        total_count = len(devices)
        online_count = sum(1 for d in devices if d.current_status == "Online")
        offline_count = total_count - online_count
        latencies = [d.last_latency_ms for d in devices if d.current_status == "Online" and d.last_latency_ms is not None]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        
        active_outages = {log.device_id: log.went_down_at for log in db.query(DowntimeLog).filter(DowntimeLog.came_up_at.is_(None)).all()}

        await manager.broadcast({
            "type": "stats_update",
            "total_devices": total_count,
            "online_devices": online_count,
            "offline_devices": offline_count,
            "avg_latency_ms": round(avg_latency, 2),
            "last_scan_time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "devices": [
                {
                    "id": d.id,
                    "device_name": d.device_name,
                    "ip_address": d.ip_address,
                    "device_type": d.device_type,
                    "current_status": d.current_status,
                    "last_latency_ms": d.last_latency_ms,
                    "last_seen": d.last_seen.strftime("%Y-%m-%d %H:%M:%S") if d.last_seen else "Never",
                    "went_offline_at": active_outages.get(d.id).strftime("%Y-%m-%d %H:%M:%S") if d.id in active_outages else None,
                    "updated_at": d.updated_at.strftime("%Y-%m-%d %H:%M:%S") if d.updated_at else None
                } for d in devices
            ]
        })
    except Exception as e:
        print(f"Error broadcasting after force ping: {e}")

    return {
        "status": status,
        "latency_ms": latency,
        "packet_loss": loss,
        "last_seen": device.last_seen.strftime("%Y-%m-%d %H:%M:%S") if device.last_seen else "Never"
    }

@app.get("/api/devices/{id}/history")
def get_device_history(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    device = db.query(Device).filter(Device.id == id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    ping_logs = db.query(PingLog).filter(PingLog.device_id == id).order_by(PingLog.checked_at.desc()).limit(30).all()
    ping_logs.reverse()
    
    downtime_logs = db.query(DowntimeLog).filter(DowntimeLog.device_id == id).order_by(DowntimeLog.went_down_at.desc()).limit(15).all()
    
    return {
        "ping_history": [
            {
                "checked_at": log.checked_at.strftime("%H:%M:%S"),
                "status": log.status,
                "latency_ms": log.latency_ms
            } for log in ping_logs
        ],
        "downtime_history": [
            {
                "id": log.id,
                "went_down_at": log.went_down_at.strftime("%Y-%m-%d %H:%M:%S"),
                "came_up_at": log.came_up_at.strftime("%Y-%m-%d %H:%M:%S") if log.came_up_at else "Still Offline",
                "duration_seconds": round(log.duration_seconds, 1) if log.duration_seconds else None,
                "reason_prediction": log.reason_prediction
            } for log in downtime_logs
        ]
    }

# --- Network Scan APIs ---

@app.get("/api/scan/suggest")
def suggest_subnet(current_user: User = Depends(get_current_user)):
    return {"subnet": get_suggested_subnet()}

@app.post("/api/scan")
async def trigger_subnet_scan(req: SubnetScanRequest, current_user: User = Depends(get_current_user)):
    try:
        return await scan_subnet(req.subnet)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scanning failed: {str(e)}")

# --- Logs & Reports APIs ---

@app.get("/api/logs")
def get_logs(page: int = 1, limit: int = 50, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    offset = (page - 1) * limit
    total = db.query(PingLog).count()
    logs = db.query(PingLog).order_by(PingLog.checked_at.desc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "logs": [
            {
                "id": log.id,
                "device_id": log.device_id,
                "ip_address": log.ip_address,
                "status": log.status,
                "latency_ms": log.latency_ms,
                "packet_loss": log.packet_loss,
                "checked_at": log.checked_at.strftime("%Y-%m-%d %H:%M:%S")
            } for log in logs
        ]
    }

@app.get("/api/reports/uptime")
def get_uptime_report(days: int = 1, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return calculate_uptime_stats(db, days)

@app.get("/api/reports/csv/{report_type}")
def get_csv_report(report_type: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if report_type == "devices":
        csv_data = generate_devices_csv(db)
        filename = "devices_report.csv"
    elif report_type == "ping_logs":
        csv_data = generate_ping_logs_csv(db)
        filename = "ping_logs_report.csv"
    elif report_type == "downtime_logs":
        csv_data = generate_downtime_logs_csv(db)
        filename = "downtime_report.csv"
    else:
        raise HTTPException(status_code=400, detail="Invalid report type.")

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# --- Settings APIs ---

class SettingsUpdateRequest(BaseModel):
    ping_interval: int
    default_subnet: str

@app.get("/api/settings")
def get_api_settings(current_user: User = Depends(get_current_user)):
    return {
        "ping_interval": settings.PING_INTERVAL,
        "default_subnet": settings.DEFAULT_SUBNET
    }

@app.post("/api/settings")
def update_api_settings(req: SettingsUpdateRequest, current_user: User = Depends(require_admin)):
    if req.ping_interval < 5 or req.ping_interval > 300:
        raise HTTPException(status_code=400, detail="Ping interval must be between 5 and 300 seconds.")
    try:
        import ipaddress
        ipaddress.ip_network(req.default_subnet, strict=False)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid default subnet format.")
        
    settings.PING_INTERVAL = req.ping_interval
    settings.DEFAULT_SUBNET = req.default_subnet
    
    # Save settings back to .env file
    env_path = os.path.join(BASE_DIR, ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r") as f:
                lines = f.readlines()
            new_lines = []
            for line in lines:
                if line.startswith("PING_INTERVAL="):
                    new_lines.append(f"PING_INTERVAL={req.ping_interval}\n")
                elif line.startswith("DEFAULT_SUBNET="):
                    new_lines.append(f"DEFAULT_SUBNET={req.default_subnet}\n")
                else:
                    new_lines.append(line)
            with open(env_path, "w") as f:
                f.writelines(new_lines)
        except Exception as e:
            print(f"Failed to persist settings in .env: {e}")
            
    return {
        "message": "Settings updated successfully",
        "settings": {
            "ping_interval": settings.PING_INTERVAL,
            "default_subnet": settings.DEFAULT_SUBNET
        }
    }
