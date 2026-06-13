import platform
import re
import asyncio
import ipaddress
from typing import Tuple, Optional

def is_valid_ip(ip: str) -> bool:
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

def parse_ping_output(output: str, system: str) -> Tuple[str, Optional[float], float]:
    """
    Parses the stdout of a ping command.
    Returns (status, latency_ms, packet_loss_percent).
    """
    system = system.lower()
    latency_ms = None
    packet_loss = 100.0
    status = "Offline"

    if "windows" in system:
        # Extract packet loss
        # e.g., "Packets: Sent = 1, Received = 1, Lost = 0 (0% loss),"
        loss_match = re.search(r"Lost\s*=\s*\d+\s*\((\d+)%\s*loss\)", output)
        if loss_match:
            packet_loss = float(loss_match.group(1))

        # Check if received packets > 0
        recv_match = re.search(r"Received\s*=\s*(\d+)", output)
        received = int(recv_match.group(1)) if recv_match else 0
        
        # If we received packets, let's extract latency
        if received > 0:
            status = "Online"
            # Check "Average = Xms"
            avg_match = re.search(r"Average\s*=\s*(\d+)ms", output)
            if avg_match:
                latency_ms = float(avg_match.group(1))
            else:
                # Alternatively look for "time=Xms" or "time<Xms"
                time_match = re.search(r"time[=<]([\d\.]+)ms", output)
                if time_match:
                    latency_ms = float(time_match.group(1))
                else:
                    latency_ms = 0.0  # default fallback
        else:
            status = "Offline"
            latency_ms = None

    else:  # Linux / macOS
        # Extract packet loss: e.g., "0% packet loss"
        loss_match = re.search(r"(\d+)%\s*packet\s*loss", output)
        if loss_match:
            packet_loss = float(loss_match.group(1))

        # Check if received packets > 0
        # e.g., "1 packets transmitted, 1 received, 0% packet loss"
        recv_match = re.search(r"(\d+)\s*(?:packets\s*)?received", output)
        received = int(recv_match.group(1)) if recv_match else 0

        if received > 0:
            status = "Online"
            # Extract latency: "rtt min/avg/max/mdev = 0.032/0.032/0.032/0.000 ms"
            rtt_match = re.search(r"(?:rtt|round-trip)\s*min/avg/max/(?:mdev|stddev|std-dev)\s*=\s*([\d\.]+)/([\d\.]+)/([\d\.]+)/([\d\.]+)", output)
            if rtt_match:
                latency_ms = float(rtt_match.group(2))
            else:
                time_match = re.search(r"time=([\d\.]+)\s*ms", output)
                if time_match:
                    latency_ms = float(time_match.group(1))
                else:
                    latency_ms = 0.0
        else:
            status = "Offline"
            latency_ms = None

    return status, latency_ms, packet_loss

async def ping_ip(ip: str, timeout_ms: int = 1000) -> Tuple[str, Optional[float], float]:
    """
    Asynchronously pings an IP and returns (status, latency_ms, packet_loss).
    """
    if not is_valid_ip(ip):
        return "Offline", None, 100.0

    sys_name = platform.system()
    if sys_name.lower() == "windows":
        cmd = ["ping", "-n", "1", "-w", str(timeout_ms), ip]
    else:
        timeout_sec = str(max(1, timeout_ms // 1000))
        cmd = ["ping", "-c", "1", "-W", timeout_sec, ip]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        encoding = "cp850" if sys_name.lower() == "windows" else "utf-8"
        output_str = stdout.decode(encoding, errors="ignore")
        return parse_ping_output(output_str, sys_name)
    except Exception:
        return "Offline", None, 100.0
