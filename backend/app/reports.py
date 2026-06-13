import csv
from io import StringIO
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import Device, PingLog, DowntimeLog

def calculate_uptime_stats(db: Session, days: int = 1):
    start_date = datetime.now() - timedelta(days=days)
    devices = db.query(Device).all()
    stats = []
    now = datetime.now()
    
    total_seconds_in_period = (now - start_date).total_seconds()
    if total_seconds_in_period <= 0:
        total_seconds_in_period = 86400.0

    for dev in devices:
        # Sum downtime durations within range
        downtimes = db.query(DowntimeLog).filter(
            DowntimeLog.device_id == dev.id,
            DowntimeLog.went_down_at >= start_date
        ).all()
        
        total_downtime = 0.0
        for dt in downtimes:
            if dt.came_up_at:
                total_downtime += dt.duration_seconds or 0.0
            else:
                total_downtime += (now - dt.went_down_at).total_seconds()

        total_downtime = min(total_downtime, total_seconds_in_period)
        uptime_pct = ((total_seconds_in_period - total_downtime) / total_seconds_in_period) * 100.0
        
        # Calculate average response latency
        avg_lat_query = db.query(func.avg(PingLog.latency_ms)).filter(
            PingLog.device_id == dev.id,
            PingLog.status == "Online",
            PingLog.checked_at >= start_date
        ).scalar()
        avg_latency = round(avg_lat_query, 2) if avg_lat_query else 0.0

        stats.append({
            "device_id": dev.id,
            "device_name": dev.device_name,
            "ip_address": dev.ip_address,
            "device_type": dev.device_type,
            "uptime_percentage": round(uptime_pct, 2),
            "downtime_seconds": round(total_downtime, 1),
            "avg_latency_ms": avg_latency
        })
    return stats

def generate_devices_csv(db: Session) -> str:
    devices = db.query(Device).all()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Name", "IP Address", "MAC Address", "Hostname", "Type", "Location", "Status", "Last Latency (ms)", "Last Seen"])
    for dev in devices:
        writer.writerow([
            dev.id, dev.device_name, dev.ip_address, dev.mac_address or "", 
            dev.hostname or "", dev.device_type, dev.location or "", 
            dev.current_status, dev.last_latency_ms or "",
            dev.last_seen.strftime("%Y-%m-%d %H:%M:%S") if dev.last_seen else "Never"
        ])
    return output.getvalue()

def generate_ping_logs_csv(db: Session, limit: int = 1000) -> str:
    logs = db.query(PingLog).order_by(PingLog.checked_at.desc()).limit(limit).all()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Device ID", "IP Address", "Status", "Latency (ms)", "Packet Loss (%)", "Timestamp"])
    for log in logs:
        writer.writerow([
            log.id, log.device_id, log.ip_address, log.status, 
            log.latency_ms or "", log.packet_loss, 
            log.checked_at.strftime("%Y-%m-%d %H:%M:%S")
        ])
    return output.getvalue()

def generate_downtime_logs_csv(db: Session) -> str:
    logs = db.query(DowntimeLog, Device.device_name).join(Device, DowntimeLog.device_id == Device.id).order_by(DowntimeLog.went_down_at.desc()).all()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Log ID", "Device ID", "Device Name", "Went Down At", "Came Up At", "Duration (Seconds)", "Predicted Reason"])
    for log, name in logs:
        writer.writerow([
            log.id, log.device_id, name,
            log.went_down_at.strftime("%Y-%m-%d %H:%M:%S"),
            log.came_up_at.strftime("%Y-%m-%d %H:%M:%S") if log.came_up_at else "Still Offline",
            log.duration_seconds or "",
            log.reason_prediction or ""
        ])
    return output.getvalue()
