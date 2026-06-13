import re
import socket
import asyncio
import platform
import ipaddress
from typing import List, Dict, Optional
from app.ping_service import ping_ip

def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def get_suggested_subnet() -> str:
    ip = get_local_ip()
    if ip == "127.0.0.1":
        return "192.168.1.0/24"
    parts = ip.split(".")
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
    return "192.168.1.0/24"

async def get_arp_cache() -> Dict[str, str]:
    sys_name = platform.system().lower()
    arp_dict = {}
    try:
        if "windows" in sys_name:
            proc = await asyncio.create_subprocess_exec(
                "arp", "-a",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
        else:
            proc = await asyncio.create_subprocess_exec(
                "arp", "-an",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
        stdout, stderr = await proc.communicate()
        encoding = "cp850" if "windows" in sys_name else "utf-8"
        output = stdout.decode(encoding, errors="ignore")
        
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            ip_match = re.search(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", line)
            mac_match = re.search(r"(([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2})", line)
            if ip_match and mac_match:
                ip = ip_match.group(1)
                mac = mac_match.group(1).replace("-", ":").lower()
                arp_dict[ip] = mac
    except Exception:
        pass
    return arp_dict

async def resolve_hostname(ip: str) -> Optional[str]:
    try:
        loop = asyncio.get_running_loop()
        res = await loop.run_in_executor(None, socket.gethostbyaddr, ip)
        return res[0]
    except Exception:
        return None

async def scan_subnet(subnet_str: str) -> List[Dict]:
    network = ipaddress.ip_network(subnet_str, strict=False)
    hosts = [str(ip) for ip in network.hosts()]
    
    # Concurrent scanning throttle
    sem = asyncio.Semaphore(50)
    results = []

    async def scan_host(ip: str):
        async with sem:
            # Short timeout of 500ms for scans
            status, latency, loss = await ping_ip(ip, timeout_ms=500)
            if status == "Online":
                hostname = await resolve_hostname(ip)
                results.append({
                    "ip_address": ip,
                    "status": "Online",
                    "latency_ms": latency,
                    "hostname": hostname
                })

    tasks = [scan_host(ip) for ip in hosts]
    await asyncio.gather(*tasks)

    # Resolve MAC addresses
    arp_cache = await get_arp_cache()
    for res in results:
        res["mac_address"] = arp_cache.get(res["ip_address"])

    return results
