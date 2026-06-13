import asyncio
from app.ping_service import ping_ip

async def test():
    print("Testing ping parsing...")
    print("Pinging 127.0.0.1 (Should be Online):")
    status, latency, loss = await ping_ip("127.0.0.1")
    print(f"Result -> Status: {status}, Latency: {latency} ms, Loss: {loss}%\n")

    print("Pinging 192.0.2.1 (Should be Offline):")
    status_down, latency_down, loss_down = await ping_ip("192.0.2.1", timeout_ms=500)
    print(f"Result -> Status: {status_down}, Latency: {latency_down} ms, Loss: {loss_down}%\n")

if __name__ == "__main__":
    asyncio.run(test())
