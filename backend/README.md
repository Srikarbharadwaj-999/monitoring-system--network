# Network Device Ping Monitoring System

A real-time network device ping monitoring application that monitors local network devices, records uptime/downtime event history, generates system reports, and updates the frontend instantly using FastAPIs and WebSockets.

## Key Features

- **Live Dashboard**: Real-time status cards showing online count, offline count, and average network response latency.
- **WebSocket Synchronization**: Live updates broadcasted directly to browser clients every few seconds. No manual page refresh required.
- **Dynamic Net Scanner**: Discovers active local devices in parallel utilizing Python's native subprocess execution with an IP validation parser (fully secure against command injection).
- **Downtime & SLA Tracking**: Automated downtime tracking that calculates recovery durations and registers outage timestamps in an SQLite database.
- **Reports Export**: Generates uptime analytics and exports device, check logs, and downtime datasets directly to downloadable CSV attachments.
- **Premium UI**: Glassmorphic elements, modern Google Fonts (Outfit), Lucide SVG icons, Chart.js response trends, light/dark themes, and toast popups.

## Project Structure

```text
network-monitor/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI Application & Router Setup
│   │   ├── database.py        # SQLAlchemy SQLite initialization
│   │   ├── models.py          # SQLAlchemy Models (User, Device, Logs)
│   │   ├── schemas.py         # Pydantic Schemas & IP Validators
│   │   ├── auth.py            # User Sign In & JWT Cookie management
│   │   ├── ping_service.py    # Subprocess-based Async Ping Engine
│   │   ├── scanner.py         # Async Subnet IP Scanner & ARP MAC resolver
│   │   ├── monitor.py         # Background monitoring daemon
│   │   ├── reports.py         # Outage Calculator & CSV Writers
│   │   ├── websocket_manager.py # WebSocket connections list
│   │   └── config.py          # Environment settings loader
│   ├── templates/             # Jinja2 Layout Templates
│   │   ├── base.html
│   │   ├── login.html
│   │   ├── dashboard.html
│   │   ├── devices.html
│   │   ├── device_detail.html
│   │   ├── logs.html
│   │   ├── reports.html
│   │   └── settings.html
│   ├── static/                # Static assets (Theme CSS & App JS)
│   │   ├── style.css
│   │   └── app.js
│   ├── requirements.txt
│   ├── .env
│   └── README.md
```

## Setup Instructions (Windows)

### 1. Prerequisite
Ensure you have Python 3.10+ installed.

### 2. Install Dependencies
Open PowerShell/CMD in the `network-monitor/backend` directory:
```powershell
pip install -r requirements.txt
```

### 3. Run Application
Run the FastAPI development server:
```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
FastAPI will initialize the SQLite database schema automatically on startup and seed a default administrator user:
- **Username**: `admin`
- **Password**: `admin123`

### 4. Open Application
Go to: [http://127.0.0.1:8000](http://127.0.0.1:8000)

## Security Features
- **IP Format Validation**: Employs standard Python `ipaddress` validation before ping execution, preventing raw command shell injection.
- **Admin Authentication**: JWT authorization token is stored using secure HTTP-only cookies, preventing cross-site scripting (XSS) token extraction.
