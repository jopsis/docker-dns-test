class DNSTestClient {
    constructor() {
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 1000;
        this.maxReconnectDelay = 30000;
        this.results = [];
        this.maxResults = 1000;
        this.showFailuresOnly = false;

        // Initialize
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.connect();
    }

    setupEventListeners() {
        // Show failures only checkbox
        document.getElementById('show-failures-only').addEventListener('change', (e) => {
            this.showFailuresOnly = e.target.checked;
            this.updateResultsTable();
        });

        // Clear table button
        document.getElementById('clear-table').addEventListener('click', () => {
            this.results = [];
            this.updateResultsTable();
        });
    }

    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        console.log('Connecting to WebSocket:', wsUrl);
        this.updateConnectionStatus('connecting');

        try {
            this.ws = new WebSocket(wsUrl);

            this.ws.onopen = () => {
                console.log('WebSocket connected');
                this.reconnectAttempts = 0;
                this.reconnectDelay = 1000;
                this.updateConnectionStatus('connected');
            };

            this.ws.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data);
                    this.handleMessage(message);
                } catch (error) {
                    console.error('Error parsing message:', error);
                }
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
            };

            this.ws.onclose = () => {
                console.log('WebSocket closed');
                this.updateConnectionStatus('disconnected');
                this.scheduleReconnect();
            };

        } catch (error) {
            console.error('Error creating WebSocket:', error);
            this.scheduleReconnect();
        }
    }

    scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max reconnection attempts reached');
            return;
        }

        this.reconnectAttempts++;
        const delay = Math.min(
            this.reconnectDelay * Math.pow(1.5, this.reconnectAttempts - 1),
            this.maxReconnectDelay
        );

        console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
        setTimeout(() => this.connect(), delay);
    }

    handleMessage(message) {
        switch (message.type) {
            case 'connection':
                console.log('Connected:', message.message);
                break;

            case 'config':
                this.updateConfig(message.config);
                break;

            case 'test_result':
                this.handleTestResult(message);
                break;

            case 'history':
                this.handleHistory(message.results);
                break;

            default:
                console.log('Unknown message type:', message.type);
        }
    }

    updateConfig(config) {
        // Update domains
        const domainsEl = document.getElementById('config-domains');
        domainsEl.innerHTML = config.domains.map(d => `<span class="tag">${d}</span>`).join(' ');

        // Update DNS servers
        const serversEl = document.getElementById('config-servers');
        serversEl.innerHTML = config.dns_servers
            .map(s => `<span class="tag">${s.name} (${s.ip})</span>`)
            .join(' ');

        // Update intervals
        document.getElementById('config-interval').textContent = `${config.interval_seconds}s`;
        document.getElementById('config-timeout').textContent = `${config.timeout_seconds}s`;
    }

    handleTestResult(message) {
        // Update iteration count
        document.getElementById('iteration-count').textContent = message.iteration;

        // Add results to buffer
        this.results.push(...message.results);

        // Trim buffer if needed
        if (this.results.length > this.maxResults) {
            this.results = this.results.slice(-this.maxResults);
        }

        // Update UI
        this.updateResultsTable();
        this.updateStatistics();
    }

    handleHistory(results) {
        console.log('Received history:', results.length, 'results');
        this.results = results;
        this.updateResultsTable();
        this.updateStatistics();
    }

    updateConnectionStatus(status) {
        const statusEl = document.getElementById('connection-status');
        statusEl.className = `status-badge ${status}`;
        statusEl.textContent = status.charAt(0).toUpperCase() + status.slice(1);
    }

    updateResultsTable() {
        const tbody = document.getElementById('results-tbody');

        // Filter results
        let displayResults = this.results;
        if (this.showFailuresOnly) {
            displayResults = this.results.filter(r => !r.success);
        }

        // Show only last 50 results for performance
        displayResults = displayResults.slice(-50);

        if (displayResults.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="loading">No results to display</td></tr>';
            return;
        }

        // Reverse to show newest first
        displayResults = displayResults.reverse();

        tbody.innerHTML = displayResults.map(result => {
            const timestamp = new Date(result.timestamp).toLocaleTimeString();
            const statusClass = result.success ? 'status-success' : 'status-failure';
            const statusText = result.success ? '✓ Success' : '✗ Failure';
            const responseTime = result.response_time_ms
                ? `${result.response_time_ms} ms`
                : '-';
            const ipAddresses = result.resolved_ips.length > 0
                ? result.resolved_ips.join(', ')
                : '-';
            const error = result.error || '-';

            return `
                <tr class="fade-in">
                    <td>${timestamp}</td>
                    <td>${result.iteration}</td>
                    <td><strong>${result.domain}</strong></td>
                    <td>${result.dns_server.name}</td>
                    <td class="${statusClass}">${statusText}</td>
                    <td class="response-time">${responseTime}</td>
                    <td class="ip-addresses">${ipAddresses}</td>
                    <td class="error-text">${error}</td>
                </tr>
            `;
        }).join('');
    }

    updateStatistics() {
        if (this.results.length === 0) return;

        // Calculate overall statistics
        const total = this.results.length;
        const successful = this.results.filter(r => r.success).length;
        const failed = total - successful;
        const successRate = ((successful / total) * 100).toFixed(1);

        // Calculate average response time
        const responseTimes = this.results
            .filter(r => r.response_time_ms !== null)
            .map(r => r.response_time_ms);
        const avgResponse = responseTimes.length > 0
            ? (responseTimes.reduce((a, b) => a + b, 0) / responseTimes.length).toFixed(2)
            : 0;

        // Update header stats
        document.getElementById('success-rate').textContent = `${successRate}%`;
        document.getElementById('avg-response').textContent = `${avgResponse} ms`;

        // Calculate stats by server
        const serverStats = {};
        this.results.forEach(result => {
            const serverName = result.dns_server.name;
            if (!serverStats[serverName]) {
                serverStats[serverName] = {
                    total: 0,
                    successful: 0,
                    failed: 0,
                    responseTimes: []
                };
            }

            serverStats[serverName].total++;
            if (result.success) {
                serverStats[serverName].successful++;
                if (result.response_time_ms) {
                    serverStats[serverName].responseTimes.push(result.response_time_ms);
                }
            } else {
                serverStats[serverName].failed++;
            }
        });

        // Update server statistics section
        const serverStatsEl = document.getElementById('server-stats');
        serverStatsEl.innerHTML = Object.entries(serverStats).map(([serverName, stats]) => {
            const successRate = ((stats.successful / stats.total) * 100).toFixed(1);
            const avgResponseTime = stats.responseTimes.length > 0
                ? (stats.responseTimes.reduce((a, b) => a + b, 0) / stats.responseTimes.length).toFixed(2)
                : 0;

            return `
                <div class="stat-card">
                    <h4>${serverName}</h4>
                    <div class="stat-row">
                        <span class="stat-label">Total Queries:</span>
                        <span class="stat-value">${stats.total}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Successful:</span>
                        <span class="stat-value success">${stats.successful}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Failed:</span>
                        <span class="stat-value error">${stats.failed}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Success Rate:</span>
                        <span class="stat-value">${successRate}%</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Avg Response:</span>
                        <span class="stat-value">${avgResponseTime} ms</span>
                    </div>
                </div>
            `;
        }).join('');
    }
}

// Toggle collapsible sections
function toggleSection(sectionId) {
    const content = document.getElementById(`${sectionId}-content`);
    const icon = document.getElementById(`${sectionId}-icon`);

    if (content && icon) {
        content.classList.toggle('collapsed');
        icon.classList.toggle('rotated');
    }
}

// Initialize the client when the page loads
document.addEventListener('DOMContentLoaded', () => {
    window.dnsTestClient = new DNSTestClient();
});
