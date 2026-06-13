import asyncio
from datetime import datetime
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Device, PingLog, DowntimeLog
from app.ping_service import ping_ip
from app.websocket_manager import manager
from app.config import settings

async def monitor_cycle():
    db = SessionLocal()
    try:
        devices = db.query(Device).all()
        if not devices:
            # Broadcast empty stats if no devices exist
            await manager.broadcast({
                "type": "stats_update",
                "total_devices": 0,
                "online_devices": 0,
                "offline_devices": 0,
                "avg_latency_ms": 0.0,
                "last_scan_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "devices": []
            })
            return

        now = datetime.now()
        
        async def ping_and_update(device: Device):
            status, latency, loss = await ping_ip(device.ip_address)
            prev_status = device.current_status
            
            # Update device properties
            device.current_status = status
            device.last_latency_ms = latency
            if status == "Online":
                device.last_seen = now
            device.updated_at = now
            
            # Create PingLog entry
            ping_log = PingLog(
                device_id=device.id,
                ip_address=device.ip_address,
                status=status,
                latency_ms=latency,
                packet_loss=loss,
                checked_at=now
            )
            db.add(ping_log)
            
            # Downtime Logic
            if prev_status == "Online" and status == "Offline":
                # Add went-down downtime entry
                dt_log = DowntimeLog(
                    device_id=device.id,
                    went_down_at=now,
                    reason_prediction="Ping failure"
                )
                db.add(dt_log)
                
                # Broadcast real-time down alert
                await manager.broadcast({
                    "type": "alert",
                    "device_id": device.id,
                    "device_name": device.device_name,
                    "ip_address": device.ip_address,
                    "status": "Offline",
                    "message": f"Device '{device.device_name}' ({device.ip_address}) went offline!"
                })
                
            elif prev_status == "Offline" and status == "Online":
                # Close the latest open downtime log
                dt_log = db.query(DowntimeLog)\
                    .filter(DowntimeLog.device_id == device.id, DowntimeLog.came_up_at.is_(None))\
                    .order_by(DowntimeLog.went_down_at.desc())\
                    .first()
                if dt_log:
                    dt_log.came_up_at = now
                    dt_log.duration_seconds = (now - dt_log.went_down_at).total_seconds()
                
                # Broadcast recovery alert
                await manager.broadcast({
                    "type": "alert",
                    "device_id": device.id,
                    "device_name": device.device_name,
                    "ip_address": device.ip_address,
                    "status": "Online",
                    "message": f"Device '{device.device_name}' ({device.ip_address}) is back online."
                })
        
        # Execute all pings in parallel
        tasks = [ping_and_update(d) for d in devices]
        await asyncio.gather(*tasks)
        
        db.commit()
        
        # Fetch active outages to get went_offline_at timestamps
        active_outages = {log.device_id: log.went_down_at for log in db.query(DowntimeLog).filter(DowntimeLog.came_up_at.is_(None)).all()}

        # Recalculate and broadcast metrics
        total_count = len(devices)
        online_count = sum(1 for d in devices if d.current_status == "Online")
        offline_count = total_count - online_count
        
        latencies = [d.last_latency_ms for d in devices if d.current_status == "Online" and d.last_latency_ms is not None]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        
        stats = {
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
        }
        await manager.broadcast(stats)
        
    except Exception as e:
        print(f"Error in monitor cycle: {e}")
        db.rollback()
    finally:
        db.close()

async def start_monitoring_loop():
    print("Starting background monitoring service...")
    while True:
        try:
            await monitor_cycle()
        except Exception as e:
            print(f"Monitor cycle crashed: {e}")
        await asyncio.sleep(settings.PING_INTERVAL)
