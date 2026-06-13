// ==========================================================================
// Common Servers Auto-Fill Mapping
// ==========================================================================
const COMMON_SERVERS = {
    '8.8.8.8': { name: 'Google Public DNS', hostname: 'dns.google', type: 'Server', location: 'Global Network' },
    '8.8.4.4': { name: 'Google Public DNS Secondary', hostname: 'dns.google', type: 'Server', location: 'Global Network' },
    '1.1.1.1': { name: 'Cloudflare DNS', hostname: 'one.one.one.one', type: 'Server', location: 'Global Network' },
    '1.0.0.1': { name: 'Cloudflare DNS Secondary', hostname: 'one.one.one.one', type: 'Server', location: 'Global Network' },
    '9.9.9.9': { name: 'Quad9 DNS', hostname: 'dns.quad9.net', type: 'Server', location: 'Global Network' },
    '149.112.112.112': { name: 'Quad9 DNS Secondary', hostname: 'dns.quad9.net', type: 'Server', location: 'Global Network' },
    '127.0.0.1': { name: 'Local Loopback', hostname: 'localhost', type: 'Server', location: 'Localhost' },
    '208.67.222.222': { name: 'OpenDNS Primary', hostname: 'dns.opendns.com', type: 'Server', location: 'Global Network' },
    '208.67.220.220': { name: 'OpenDNS Secondary', hostname: 'dns.opendns.com', type: 'Server', location: 'Global Network' },
    '4.2.2.1': { name: 'Level3 DNS Primary', hostname: 'level3.dns', type: 'Server', location: 'Global Network' },
    '4.2.2.2': { name: 'Level3 DNS Secondary', hostname: 'level3.dns', type: 'Server', location: 'Global Network' },
    '8.26.56.26': { name: 'Comodo Secure DNS', hostname: 'dns.comodo.com', type: 'Server', location: 'Global Network' },
    '8.20.247.20': { name: 'Comodo Secure DNS Secondary', hostname: 'dns.comodo.com', type: 'Server', location: 'Global Network' },
    '94.140.14.14': { name: 'AdGuard DNS Primary', hostname: 'dns.adguard.com', type: 'Server', location: 'Global Network' },
    '94.140.15.15': { name: 'AdGuard DNS Secondary', hostname: 'dns.adguard.com', type: 'Server', location: 'Global Network' }
};

// ==========================================================================
// Theme Management & Global Initialization
// ==========================================================================
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initGlobalEvents();
    setupWebSocket();
    routePageLogic();
});

function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);

    const toggleBtn = document.getElementById('theme-toggle');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', () => {
            const currentTheme = document.documentElement.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
        });
    }
}

function initGlobalEvents() {
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async () => {
            if (confirm('Are you sure you want to log out?')) {
                try {
                    const res = await fetch('/auth/logout', { method: 'POST' });
                    if (res.ok) {
                        window.location.href = '/login';
                    }
                } catch (err) {
                    console.error('Logout error:', err);
                }
            }
        });
    }
}

// ==========================================================================
// Real-Time WebSockets Client & Broadcast Handling
// ==========================================================================
let ws = null;
let wsReconnectTimeout = null;
let devicesCache = []; // Global cache of active devices for filtering

function setupWebSocket() {
    const wsScheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const wsUrl = `${wsScheme}://${window.location.host}/ws`;

    ws = new WebSocket(wsUrl);

    const wsBadge = document.getElementById('ws-badge');
    const wsBadgeText = document.getElementById('ws-badge-text');

    ws.onopen = () => {
        console.log('WebSocket connection established.');
        if (wsReconnectTimeout) clearTimeout(wsReconnectTimeout);
        if (wsBadge) {
            wsBadge.classList.remove('offline');
            wsBadge.classList.add('online');
        }
        if (wsBadgeText) wsBadgeText.innerText = 'Connected';
    };

    ws.onmessage = (event) => {
        try {
            const message = JSON.parse(event.data);
            if (message.type === 'stats_update') {
                updateDashboardKPIs(message);
                devicesCache = message.devices;

                // If on dashboard, update monitored devices table
                const dashboardTable = document.getElementById('devices-table');
                if (dashboardTable) {
                    renderDashboardTable(message.devices);
                }

                // If on devices page, dynamically update grid statuses without losing edit/delete context
                const mgmtTable = document.getElementById('devices-mgmt-table');
                if (mgmtTable) {
                    // Update cache and re-apply filters so status tags change in real time
                    applyDeviceFilters();
                }
            } else if (message.type === 'alert') {
                showToastAlert(message.status === 'Offline' ? 'Device Offline Alert' : 'Device Restored Alert', message.message, message.status);
            }
        } catch (e) {
            console.error('Error parsing WebSocket payload:', e);
        }
    };

    ws.onclose = () => {
        console.warn('WebSocket connection lost. Retrying in 3 seconds...');
        if (wsBadge) {
            wsBadge.classList.remove('online');
            wsBadge.classList.add('offline');
        }
        if (wsBadgeText) wsBadgeText.innerText = 'Disconnected';

        wsReconnectTimeout = setTimeout(setupWebSocket, 3000);
    };

    ws.onerror = (err) => {
        console.error('WebSocket encountered an error:', err);
        ws.close();
    };
}

// Spawns premium warning toasts dynamically on dashboard
function showToastAlert(title, message, status) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${status === 'Offline' ? 'toast-danger' : 'toast-success'}`;

    const icon = status === 'Offline' ? 'alert-triangle' : 'check-circle';
    const iconColor = status === 'Offline' ? 'text-danger' : 'text-success';
    const bgLight = status === 'Offline' ? 'bg-danger-light' : 'bg-success-light';

    toast.innerHTML = `
        <div class="toast-icon-box ${bgLight}">
            <i data-lucide="${icon}" class="${iconColor}"></i>
        </div>
        <div class="toast-content">
            <h4 class="toast-title">${title}</h4>
            <p class="toast-desc">${message}</p>
        </div>
        <button class="toast-close" onclick="this.parentElement.remove()"><i data-lucide="x"></i></button>
    `;

    container.appendChild(toast);
    lucide.createIcons();

    setTimeout(() => {
        if (toast.parentElement) {
            toast.remove();
        }
    }, 5000);
}

// Update KPI counters
function updateDashboardKPIs(data) {
    const total = document.getElementById('stat-total-devices');
    const online = document.getElementById('stat-online-devices');
    const offline = document.getElementById('stat-offline-devices');
    const avgLatency = document.getElementById('stat-avg-latency');

    if (total) total.innerText = data.total_devices;
    if (online) online.innerText = data.online_devices;
    if (offline) offline.innerText = data.offline_devices;
    if (avgLatency) avgLatency.innerText = `${data.avg_latency_ms} ms`;
}

// Render Dashboard Devices Table
function renderDashboardTable(devices) {
    const tbody = document.getElementById('devices-table-body');
    if (!tbody) return;

    if (devices.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="text-center text-muted py-6">
                    No devices added. Scan subnet or add devices manually to start monitoring.
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = devices.map(dev => {
        const badgeClass = dev.current_status === 'Online' ? 'badge-success' : 'badge-danger';
        const latencyText = dev.current_status === 'Online' ? `${dev.last_latency_ms} ms` : '--';
        const typeIcon = getDeviceTypeIcon(dev.device_type);

        return `
            <tr>
                <td><a href="http://${dev.ip_address}" target="_blank" class="ip-link"><code>${dev.ip_address}</code></a></td>
                <td>
                    <span class="type-pill">
                        <i data-lucide="${typeIcon}"></i>
                        <span>${dev.device_type}</span>
                    </span>
                </td>
                <td><span class="badge ${badgeClass}">${dev.current_status}</span></td>
                <td class="font-semibold text-warning">${latencyText}</td>
                <td><span class="text-sm text-secondary">${dev.last_seen}</span></td>
                <td>
                    <a href="/devices/${dev.id}" class="btn btn-secondary btn-sm btn-icon" title="View details">
                        <i data-lucide="eye"></i>
                    </a>
                </td>
            </tr>
        `;
    }).join('');

    lucide.createIcons();
}

// Helper: Get icon name for device type
function getDeviceTypeIcon(type) {
    switch (type) {
        case 'Server': return 'hard-drive';
        case 'Router': return 'router';
        case 'Printer': return 'printer';
        case 'Camera': return 'video';
        case 'Mobile': return 'smartphone';
        default: return 'laptop';
    }
}

// Helper: escapeHTML
function escapeHTML(str) {
    if (!str) return '';
    return str.replace(/[&<>'"]/g,
        tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag)
    );
}

// ==========================================================================
// Page Routing & Page-specific Scripts
// ==========================================================================
function routePageLogic() {
    const path = window.location.pathname;

    if (document.getElementById('devices-table')) {
        initDashboardPage();
    } else if (document.getElementById('devices-mgmt-table')) {
        initDevicesMgmtPage();
    } else if (document.getElementById('logs-table')) {
        initLogsPage();
    } else if (document.getElementById('reports-table')) {
        initReportsPage();
    } else if (document.getElementById('settings-form')) {
        initSettingsPage();
    } else if (document.getElementById('latencyChart')) {
        initDeviceDetailPage();
    }
}

// --- Dashboard Logic ---
function initDashboardPage() {
    // Load suggested subnet range
    fetch('/api/scan/suggest')
        .then(res => res.json())
        .then(data => {
            const subnetInput = document.getElementById('scan-subnet');
            if (subnetInput && data.subnet) {
                subnetInput.value = data.subnet;
            }
        });

    const scanForm = document.getElementById('dashboard-scan-form');
    if (scanForm) {
        scanForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const subnet = document.getElementById('scan-subnet').value;
            const progress = document.getElementById('scan-progress');
            const resultsBox = document.getElementById('scan-results-box');
            const scanBtn = document.getElementById('scan-btn');

            progress.classList.remove('hidden');
            resultsBox.classList.add('hidden');
            scanBtn.disabled = true;
            scanBtn.querySelector('span').innerText = 'Scanning Subnet...';

            try {
                const res = await fetch('/api/scan', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ subnet })
                });

                if (!res.ok) throw new Error('Scan command failed.');

                const discovered = await res.json();
                renderDiscoveredDevices(discovered);
            } catch (err) {
                alert('Scanning subnet failed. Make sure subnet format is correct (e.g. 192.168.1.0/24).');
            } finally {
                progress.classList.add('hidden');
                scanBtn.disabled = false;
                scanBtn.querySelector('span').innerText = 'Scan Subnet';
            }
        });
    }

    // Handle import device form submit
    const importForm = document.getElementById('import-device-form');
    if (importForm) {
        importForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const ip = document.getElementById('import-ip').value;
            document.getElementById('import-name').value = ip;
            const payload = {
                device_name: ip,
                ip_address: ip,
                mac_address: document.getElementById('import-mac').value || null,
                device_type: document.getElementById('import-type').value,
                location: document.getElementById('import-location').value || null
            };

            try {
                const res = await fetch('/api/devices', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                if (res.ok) {
                    closeImportModal();
                    showToastAlert('Import Successful', `Device ${payload.device_name} has been added to monitoring.`, 'Online');
                } else {
                    const data = await res.json();
                    alert(data.detail || 'Import failed.');
                }
            } catch (err) {
                alert('Network error while saving imported device.');
            }
        });
    }
}

function renderDiscoveredDevices(list) {
    const box = document.getElementById('scan-results-box');
    const counter = document.getElementById('discovered-count');
    const listContainer = document.getElementById('discovered-list');

    counter.innerText = list.length;
    listContainer.innerHTML = '';

    if (list.length === 0) {
        listContainer.innerHTML = '<p class="text-center text-muted">No online devices discovered.</p>';
    } else {
        list.forEach(dev => {
            const div = document.createElement('div');
            div.className = 'discovered-item';
            div.innerHTML = `
                <div class="discovered-info">
                    <p class="disc-ip">${dev.ip_address}</p>
                </div>
                <button class="btn btn-secondary btn-sm" onclick="openImportModal('${dev.ip_address}', '${escapeHTML(dev.hostname)}', '${dev.mac_address || ''}')">Import</button>
            `;
            listContainer.appendChild(div);
        });
    }
    box.classList.remove('hidden');
}

window.openImportModal = (ip, hostname, mac) => {
    document.getElementById('import-ip').value = ip;
    document.getElementById('import-mac').value = mac;
    
    const common = COMMON_SERVERS[ip];
    if (common) {
        document.getElementById('import-name').value = common.name;
        document.getElementById('import-type').value = common.type;
        document.getElementById('import-location').value = common.location;
    } else {
        document.getElementById('import-name').value = (hostname && hostname !== 'undefined' && hostname !== 'null') ? hostname : '';
        document.getElementById('import-type').value = 'PC';
        document.getElementById('import-location').value = '';
    }
    
    document.getElementById('import-modal').classList.remove('hidden');
    lucide.createIcons();
};

window.closeImportModal = () => {
    document.getElementById('import-modal').classList.add('hidden');
};


// --- Devices Management Logic ---
function initDevicesMgmtPage() {
    fetchDevicesMgmt();

    // Listen to changes in search and filter options
    document.getElementById('device-search').addEventListener('input', applyDeviceFilters);
    document.getElementById('filter-status').addEventListener('change', applyDeviceFilters);
    document.getElementById('filter-type').addEventListener('change', applyDeviceFilters);

    // Auto-fill common servers on IP input
    const addIpInput = document.getElementById('add-ip');
    if (addIpInput) {
        addIpInput.addEventListener('input', (e) => {
            const ip = e.target.value.trim();
            const common = COMMON_SERVERS[ip];
            if (common) {
                const nameField = document.getElementById('add-name');
                const hostField = document.getElementById('add-hostname');
                const typeField = document.getElementById('add-type');
                const locField = document.getElementById('add-location');
                
                if (nameField && !nameField.value) nameField.value = common.name;
                if (hostField && !hostField.value) hostField.value = common.hostname;
                if (typeField) typeField.value = common.type;
                if (locField && !locField.value) locField.value = common.location;
            }
        });
    }

    const editIpInput = document.getElementById('edit-ip');
    if (editIpInput) {
        editIpInput.addEventListener('input', (e) => {
            const ip = e.target.value.trim();
            const common = COMMON_SERVERS[ip];
            if (common) {
                const nameField = document.getElementById('edit-name');
                const hostField = document.getElementById('edit-hostname');
                const typeField = document.getElementById('edit-type');
                const locField = document.getElementById('edit-location');
                
                if (nameField && !nameField.value) nameField.value = common.name;
                if (hostField && !hostField.value) hostField.value = common.hostname;
                if (typeField) typeField.value = common.type;
                if (locField && !locField.value) locField.value = common.location;
            }
        });
    }

    // Setup Create Device Submit Form
    const addForm = document.getElementById('add-device-form');
    if (addForm) {
        addForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const errBox = document.getElementById('add-error');
            errBox.classList.add('hidden');

            const ip = document.getElementById('add-ip').value;
            document.getElementById('add-name').value = ip;

            const payload = {
                device_name: ip,
                ip_address: ip,
                hostname: document.getElementById('add-hostname').value || null,
                mac_address: document.getElementById('add-mac').value || null,
                device_type: document.getElementById('add-type').value,
                location: document.getElementById('add-location').value || null
            };

            try {
                const res = await fetch('/api/devices', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                if (res.ok) {
                    closeAddModal();
                    fetchDevicesMgmt();
                } else {
                    const data = await res.json();
                    errBox.innerText = data.detail || 'Failed to save device.';
                    errBox.classList.remove('hidden');
                }
            } catch (err) {
                errBox.innerText = 'Network error occurred.';
                errBox.classList.remove('hidden');
            }
        });
    }

    // Setup Edit Device Submit Form
    const editForm = document.getElementById('edit-device-form');
    if (editForm) {
        editForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const errBox = document.getElementById('edit-error');
            errBox.classList.add('hidden');
            const id = document.getElementById('edit-id').value;

            const ip = document.getElementById('edit-ip').value;
            document.getElementById('edit-name').value = ip;

            const payload = {
                device_name: ip,
                ip_address: ip,
                hostname: document.getElementById('edit-hostname').value || null,
                mac_address: document.getElementById('edit-mac').value || null,
                device_type: document.getElementById('edit-type').value,
                location: document.getElementById('edit-location').value || null
            };

            try {
                const res = await fetch(`/api/devices/${id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                if (res.ok) {
                    closeEditModal();
                    fetchDevicesMgmt();
                } else {
                    const data = await res.json();
                    errBox.innerText = data.detail || 'Failed to update device.';
                    errBox.classList.remove('hidden');
                }
            } catch (err) {
                errBox.innerText = 'Network error occurred.';
                errBox.classList.remove('hidden');
            }
        });
    }
}

async function fetchDevicesMgmt() {
    try {
        const res = await fetch('/api/devices');
        if (res.ok) {
            devicesCache = await res.json();
            applyDeviceFilters();
        }
    } catch (e) {
        console.error('Failed to load devices inventory:', e);
    }
}

function applyDeviceFilters() {
    const query = document.getElementById('device-search').value.toLowerCase();
    const status = document.getElementById('filter-status').value;
    const type = document.getElementById('filter-type').value;

    const filtered = devicesCache.filter(dev => {
        const matchesSearch =
            dev.device_name.toLowerCase().includes(query) ||
            dev.ip_address.toLowerCase().includes(query) ||
            (dev.hostname && dev.hostname.toLowerCase().includes(query)) ||
            (dev.mac_address && dev.mac_address.toLowerCase().includes(query)) ||
            (dev.location && dev.location.toLowerCase().includes(query));

        const matchesStatus = status === 'all' || dev.current_status === status;
        const matchesType = type === 'all' || dev.device_type === type;

        return matchesSearch && matchesStatus && matchesType;
    });

    renderDevicesMgmtTable(filtered);
}

function renderDevicesMgmtTable(devices) {
    const tbody = document.getElementById('devices-mgmt-body');
    if (!tbody) return;

    if (devices.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="text-center text-muted py-6">
                    No devices match the specified filters.
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = devices.map(dev => {
        const badgeClass = dev.current_status === 'Online' ? 'badge-success' : 'badge-danger';
        const typeIcon = getDeviceTypeIcon(dev.device_type);
        const latencyText = dev.current_status === 'Online' && dev.last_latency_ms !== null ? `${dev.last_latency_ms} ms` : '--';

        return `
            <tr>
                <td><a href="http://${dev.ip_address}" target="_blank" class="ip-link"><code>${dev.ip_address}</code></a></td>
                <td>
                    <span class="type-pill">
                        <i data-lucide="${typeIcon}"></i>
                        <span>${dev.device_type}</span>
                    </span>
                </td>
                <td><span class="text-muted">${escapeHTML(dev.location || '--')}</span></td>
                <td><span class="badge ${badgeClass}">${dev.current_status}</span></td>
                <td class="font-semibold text-warning">${latencyText}</td>
                <td>
                    <div class="flex gap-2">
                        <a href="/devices/${dev.id}" class="btn btn-secondary btn-sm btn-icon" title="Details">
                            <i data-lucide="eye"></i>
                        </a>
                        <button class="btn btn-secondary btn-sm btn-icon" onclick="openEditModal(${dev.id})" title="Edit">
                            <i data-lucide="edit-3"></i>
                        </button>
                        ${window.currentUserRole === 'admin' ? `
                        <button class="btn btn-danger-light btn-sm btn-icon" onclick="deleteDevice(${dev.id})" title="Delete">
                            <i data-lucide="trash-2"></i>
                        </button>
                        ` : ''}
                    </div>
                </td>
            </tr>
        `;
    }).join('');
    lucide.createIcons();
}

window.openAddModal = () => {
    document.getElementById('add-device-form').reset();
    document.getElementById('add-error').classList.add('hidden');
    document.getElementById('add-modal').classList.remove('hidden');
};

window.closeAddModal = () => {
    document.getElementById('add-modal').classList.add('hidden');
};

window.openEditModal = (id) => {
    const dev = devicesCache.find(d => d.id === id);
    if (!dev) return;

    document.getElementById('edit-error').classList.add('hidden');
    document.getElementById('edit-id').value = dev.id;
    document.getElementById('edit-name').value = dev.device_name;
    document.getElementById('edit-ip').value = dev.ip_address;
    document.getElementById('edit-hostname').value = dev.hostname || '';
    document.getElementById('edit-mac').value = dev.mac_address || '';
    document.getElementById('edit-type').value = dev.device_type;
    document.getElementById('edit-location').value = dev.location || '';

    document.getElementById('edit-modal').classList.remove('hidden');
    lucide.createIcons();
};

window.closeEditModal = () => {
    document.getElementById('edit-modal').classList.add('hidden');
};

window.deleteDevice = async (id) => {
    if (confirm('Are you sure you want to delete this device and delete all its associated logs?')) {
        try {
            const res = await fetch(`/api/devices/${id}`, { method: 'DELETE' });
            if (res.ok) {
                fetchDevicesMgmt();
            } else {
                alert('Failed to delete device.');
            }
        } catch (err) {
            alert('Error deleting device.');
        }
    }
};

// --- Logs Page Logic ---
let logPage = 1;
const logLimit = 50;

function initLogsPage() {
    fetchLogs();

    document.getElementById('btn-prev').addEventListener('click', () => {
        if (logPage > 1) {
            logPage--;
            fetchLogs();
        }
    });

    document.getElementById('btn-next').addEventListener('click', () => {
        logPage++;
        fetchLogs();
    });

    document.getElementById('log-ip-search').addEventListener('input', () => {
        logPage = 1;
        fetchLogs();
    });

    document.getElementById('log-status-filter').addEventListener('change', () => {
        logPage = 1;
        fetchLogs();
    });
}

async function fetchLogs() {
    const ipSearch = document.getElementById('log-ip-search').value.toLowerCase();
    const statusFilter = document.getElementById('log-status-filter').value;

    // We retrieve the paginated data.
    // To support status filtering and IP search on logs page dynamically,
    // let's fetch everything or perform filtering on retrieved entries.
    // Given logs databases can get large, let's fetch raw page logs and do simple client filter, or fetch directly.
    // For simplicity, we query backend logs.
    try {
        const res = await fetch(`/api/logs?page=${logPage}&limit=${logLimit}`);
        if (!res.ok) return;

        const data = await res.json();

        // Let's filter on the frontend for responsiveness
        let logs = data.logs;

        if (ipSearch) {
            logs = logs.filter(l => l.ip_address.toLowerCase().includes(ipSearch));
        }
        if (statusFilter !== 'all') {
            logs = logs.filter(l => l.status === statusFilter);
        }

        const totalEntries = data.total;
        document.getElementById('pag-total').innerText = totalEntries;

        const start = totalEntries === 0 ? 0 : (logPage - 1) * logLimit + 1;
        const end = Math.min(logPage * logLimit, totalEntries);
        document.getElementById('pag-start').innerText = start;
        document.getElementById('pag-end').innerText = end;

        document.getElementById('btn-prev').disabled = logPage === 1;
        document.getElementById('btn-next').disabled = end >= totalEntries;
        document.getElementById('page-num-indicator').innerText = `Page ${logPage}`;

        renderLogsTable(logs);
    } catch (e) {
        console.error('Failed to load logs:', e);
    }
}

function renderLogsTable(logs) {
    const tbody = document.getElementById('logs-table-body');
    if (!tbody) return;

    if (logs.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="text-center text-muted py-6">No logs match selection.</td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = logs.map(log => {
        const badgeClass = log.status === 'Online' ? 'badge-success' : 'badge-danger';
        const latencyText = log.latency_ms !== null ? `${log.latency_ms} ms` : '--';
        return `
            <tr>
                <td><code>#${log.id}</code></td>
                <td><span class="text-muted">Device #${log.device_id}</span></td>
                <td><code>${log.ip_address}</code></td>
                <td><span class="badge ${badgeClass}">${log.status}</span></td>
                <td class="font-semibold text-warning">${latencyText}</td>
                <td><span class="text-muted">${log.packet_loss}%</span></td>
                <td><span class="text-sm text-secondary">${log.checked_at}</span></td>
            </tr>
        `;
    }).join('');
    lucide.createIcons();
}

// --- Reports Page Logic ---
function initReportsPage() {
    fetchUptimeStats();

    document.getElementById('report-days').addEventListener('change', () => {
        fetchUptimeStats();
    });
}

async function fetchUptimeStats() {
    const days = document.getElementById('report-days').value;
    try {
        const res = await fetch(`/api/reports/uptime?days=${days}`);
        if (!res.ok) return;

        const stats = await res.json();
        renderReportsTable(stats);
    } catch (e) {
        console.error('Failed to query reports metrics:', e);
    }
}

function renderReportsTable(stats) {
    const tbody = document.getElementById('reports-table-body');
    if (!tbody) return;

    if (stats.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="text-center text-muted py-6">No monitored device uptime statistics available.</td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = stats.map(st => {
        let slaBadge = 'badge-danger';
        let slaText = 'Critical';
        if (st.uptime_percentage >= 99.9) {
            slaBadge = 'badge-success';
            slaText = 'Excellent (SLA)';
        } else if (st.uptime_percentage >= 99.0) {
            slaBadge = 'badge-info';
            slaText = 'Satisfactory';
        } else if (st.uptime_percentage >= 95.0) {
            slaBadge = 'badge-warning';
            slaText = 'Warning';
        }

        // Format downtime seconds to readable hours/minutes/seconds
        const durationText = formatDuration(st.downtime_seconds);

        return `
            <tr>
                <td><a href="http://${st.ip_address}" target="_blank" class="ip-link"><code>${st.ip_address}</code></a></td>
                <td><span class="type-pill">${st.device_type}</span></td>
                <td class="font-semibold text-success">${st.uptime_percentage}%</td>
                <td><span class="text-danger font-semibold">${durationText}</span></td>
                <td class="font-semibold text-warning">${st.avg_latency_ms} ms</td>
                <td><span class="badge ${slaBadge}">${slaText}</span></td>
            </tr>
        `;
    }).join('');
    lucide.createIcons();
}

function formatDuration(sec) {
    if (sec <= 0) return '0s';
    if (sec < 60) return `${sec}s`;
    const min = Math.floor(sec / 60);
    const s = Math.round(sec % 60);
    if (min < 60) return `${min}m ${s}s`;
    const hrs = Math.floor(min / 60);
    const m = Math.round(min % 60);
    return `${hrs}h ${m}m`;
}

// --- Settings Page Logic ---
function initSettingsPage() {
    // Check role restriction
    if (window.currentUserRole !== 'admin') {
        setTimeout(() => {
            const inputs = document.querySelectorAll('#settings-form input, #settings-form button[type="submit"]');
            inputs.forEach(input => input.disabled = true);
            const errBox = document.getElementById('settings-error');
            if (errBox) {
                errBox.innerText = "Notice: Settings are read-only for Manager accounts.";
                errBox.classList.remove('hidden');
                errBox.style.backgroundColor = 'var(--primary-light)';
                errBox.style.color = 'var(--primary)';
                errBox.style.borderColor = 'var(--primary)';
            }
        }, 100);
    }

    // Populate form fields
    fetch('/api/settings')
        .then(res => res.json())
        .then(data => {
            document.getElementById('settings-interval').value = data.ping_interval;
            document.getElementById('settings-subnet').value = data.default_subnet;
        });

    // Populate env details
    document.getElementById('system-os').innerText = navigator.platform || 'Unknown Windows';
    setInterval(() => {
        const timeBox = document.getElementById('system-time');
        if (timeBox) {
            timeBox.innerText = new Date().toLocaleTimeString();
        }
    }, 1000);

    const settingsForm = document.getElementById('settings-form');
    if (settingsForm) {
        settingsForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const successBox = document.getElementById('settings-success');
            const errorBox = document.getElementById('settings-error');
            const saveBtn = document.getElementById('save-settings-btn');

            successBox.classList.add('hidden');
            errorBox.classList.add('hidden');
            saveBtn.disabled = true;
            saveBtn.querySelector('span').innerText = 'Saving Configurations...';

            const payload = {
                ping_interval: parseInt(document.getElementById('settings-interval').value),
                default_subnet: document.getElementById('settings-subnet').value
            };

            try {
                const res = await fetch('/api/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                if (res.ok) {
                    successBox.classList.remove('hidden');
                } else {
                    const data = await res.json();
                    errorBox.innerText = data.detail || 'Failed to save settings.';
                    errorBox.classList.remove('hidden');
                }
            } catch (err) {
                errorBox.innerText = 'Network error occurred.';
                errorBox.classList.remove('hidden');
            } finally {
                saveBtn.disabled = false;
                saveBtn.querySelector('span').innerText = 'Save Configurations';
            }
        });
    }
}

// --- Device Details Page Logic ---
let latencyChartInstance = null;

async function initDeviceDetailPage() {
    const devId = window.currentDeviceId;
    if (!devId) return;

    // Set up force ping button listener if it exists and hasn't been set up
    const forcePingBtn = document.getElementById('force-ping-btn');
    if (forcePingBtn && !forcePingBtn.dataset.listenerAttached) {
        forcePingBtn.dataset.listenerAttached = 'true';
        forcePingBtn.addEventListener('click', async () => {
            forcePingBtn.disabled = true;
            const btnSpan = forcePingBtn.querySelector('span');
            const btnIcon = forcePingBtn.querySelector('i');
            const originalText = btnSpan ? btnSpan.innerText : 'Ping Now';
            if (btnSpan) btnSpan.innerText = 'Pinging...';
            if (btnIcon) btnIcon.classList.add('animate-spin');

            try {
                const res = await fetch(`/api/devices/${devId}/ping`, { method: 'POST' });
                if (res.ok) {
                    const result = await res.json();
                    
                    // Show success toast
                    showToastAlert(
                        result.status === 'Online' ? 'Ping Successful' : 'Ping Failed',
                        `Device returned status: ${result.status} (Latency: ${result.latency_ms} ms)`,
                        result.status
                    );

                    // Update UI elements
                    const statusBadge = document.getElementById('detail-status');
                    if (statusBadge) {
                        statusBadge.innerText = result.status;
                        statusBadge.className = `badge ${result.status === 'Online' ? 'badge-success' : 'badge-danger'} text-sm`;
                    }

                    const lastSeenField = document.getElementById('detail-last-seen');
                    if (lastSeenField) {
                        lastSeenField.innerText = result.last_seen;
                    }

                    const latencyField = document.getElementById('detail-latency');
                    if (latencyField) {
                        latencyField.innerText = result.latency_ms !== null ? `${result.latency_ms} ms` : 'N/A';
                    }

                    // Reload chart and downtime history
                    await initDeviceDetailPage();
                } else {
                    alert('Force ping request failed.');
                }
            } catch (err) {
                console.error(err);
                alert('Network error while performing force ping.');
            } finally {
                forcePingBtn.disabled = false;
                if (btnSpan) btnSpan.innerText = originalText;
                if (btnIcon) btnIcon.classList.remove('animate-spin');
            }
        });
    }

    try {
        const res = await fetch(`/api/devices/${devId}/history`);
        if (!res.ok) return;

        const data = await res.json();

        // 1. Draw chart
        renderLatencyChart(data.ping_history);

        // 2. Populate downtime list
        renderDowntimeHistory(data.downtime_history);
    } catch (e) {
        console.error('Failed to load device details metrics:', e);
    }
}

function renderLatencyChart(pingData) {
    const ctx = document.getElementById('latencyChart');
    if (!ctx) return;

    const labels = pingData.map(p => p.checked_at);
    const dataPoints = pingData.map(p => p.status === 'Online' ? p.latency_ms : null);

    // Create point colors (Red dot for offline check, Green dot for online check)
    const pointColors = pingData.map(p => p.status === 'Online' ? '#10B981' : '#EF4444');

    if (latencyChartInstance) {
        latencyChartInstance.destroy();
    }

    latencyChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Ping Response time (ms)',
                data: dataPoints,
                borderColor: '#3B82F6',
                backgroundColor: 'rgba(59, 130, 246, 0.15)',
                borderWidth: 2,
                pointBackgroundColor: pointColors,
                pointBorderColor: pointColors,
                pointRadius: 4,
                tension: 0.25,
                fill: true,
                spanGaps: false
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    title: { display: true, text: 'Latency (ms)' }
                },
                x: {
                    title: { display: true, text: 'Timestamp' }
                }
            },
            plugins: {
                legend: { display: false }
            }
        }
    });
}

function renderDowntimeHistory(downtimes) {
    const tbody = document.getElementById('downtime-history-body');
    if (!tbody) return;

    if (downtimes.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" class="text-center text-muted py-6">
                    No downtime events recorded for this device.
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = downtimes.map(dt => {
        const durationText = dt.duration_seconds ? formatDuration(dt.duration_seconds) : '<span class="badge badge-danger animate-pulse">Offline</span>';
        const recoveryText = dt.came_up_at || 'Still Offline';
        return `
            <tr>
                <td><code>#${dt.id}</code></td>
                <td><span class="text-secondary font-semibold">${dt.went_down_at}</span></td>
                <td><span class="text-secondary font-semibold">${recoveryText}</span></td>
                <td><span class="font-semibold">${durationText}</span></td>
                <td><span class="text-muted text-sm">${escapeHTML(dt.reason_prediction || 'N/A')}</span></td>
            </tr>
        `;
    }).join('');
    lucide.createIcons();
}
