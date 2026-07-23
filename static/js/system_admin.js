(() => {
    const dataEl = document.getElementById('system-metrics-data');
    if (!dataEl || typeof Chart === 'undefined') {
        return;
    }

    let initial;
    try {
        initial = JSON.parse(dataEl.textContent);
    } catch (err) {
        console.error('Invalid system metrics payload', err);
        return;
    }

    const basePath = (window.APP_BASE_PATH || '').replace(/\/$/, '');
    const endpoint = `${basePath}/api/system-metrics/`;
    const refreshSeconds = Number((document.getElementById('m-refresh') || {}).textContent) || 15;

    // ---- helpers -----------------------------------------------------------
    const setText = (id, value) => {
        const el = document.getElementById(id);
        if (el) el.textContent = value;
    };
    const fmtNum = (n) => (n === null || n === undefined ? '—' : Number(n).toLocaleString());
    const fmtDuration = (seconds) => {
        if (seconds === null || seconds === undefined || Number.isNaN(seconds)) return '—';
        seconds = Math.max(0, Math.round(seconds));
        const d = Math.floor(seconds / 86400);
        const h = Math.floor((seconds % 86400) / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        if (d > 0) return `${d}d ${h}h`;
        if (h > 0) return `${h}h ${m}m`;
        if (m > 0) return `${m}m`;
        return `${seconds}s`;
    };
    const pctColor = (value, warn, danger, invert = false) => {
        // invert=false: high is good (green). invert=true: high is bad (red).
        if (!invert) {
            if (value >= warn) return '#2ecc71';
            if (value >= danger) return '#ffc857';
            return '#e74c3c';
        }
        if (value < warn) return '#2ecc71';
        if (value < danger) return '#ffc857';
        return '#e74c3c';
    };

    // ---- gauges ------------------------------------------------------------
    const centerText = {
        id: 'centerText',
        afterDraw(chart) {
            const { ctx, chartArea } = chart;
            const value = chart.$value;
            if (value === null || value === undefined) return;
            const cx = (chartArea.left + chartArea.right) / 2;
            const cy = chartArea.bottom - 6;
            ctx.save();
            ctx.textAlign = 'center';
            ctx.fillStyle = '#1c3d5a';
            ctx.font = '700 26px sans-serif';
            ctx.fillText(`${value}%`, cx, cy);
            ctx.restore();
        },
    };

    const makeGauge = (canvasId, value, color) => {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return null;
        const safe = Math.max(0, Math.min(100, value || 0));
        const chart = new Chart(canvas.getContext('2d'), {
            type: 'doughnut',
            data: {
                datasets: [{
                    data: [safe, 100 - safe],
                    backgroundColor: [color, '#e9eef3'],
                    borderWidth: 0,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                rotation: -90,
                circumference: 180,
                cutout: '72%',
                plugins: { legend: { display: false }, tooltip: { enabled: false } },
            },
            plugins: [centerText],
        });
        chart.$value = Math.round(safe);
        return chart;
    };

    const updateGauge = (chart, value, color) => {
        if (!chart) return;
        const safe = Math.max(0, Math.min(100, value || 0));
        chart.data.datasets[0].data = [safe, 100 - safe];
        chart.data.datasets[0].backgroundColor = [color, '#e9eef3'];
        chart.$value = Math.round(safe);
        chart.update();
    };

    // ---- line + bar charts -------------------------------------------------
    const ingestionCanvas = document.getElementById('ingestionChart');
    const ingestionChart = ingestionCanvas && new Chart(ingestionCanvas.getContext('2d'), {
        type: 'line',
        data: { labels: [], datasets: [{
            label: 'Events',
            data: [],
            borderColor: '#4b9cd3',
            backgroundColor: 'rgba(75, 156, 211, 0.2)',
            fill: true,
            tension: 0.25,
            pointRadius: 0,
        }] },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: { y: { beginAtZero: true, title: { display: true, text: 'Events / 15 min' } } },
            plugins: { legend: { display: false } },
        },
    });

    const uptimeCanvas = document.getElementById('uptimeChart');
    const uptimeChart = uptimeCanvas && new Chart(uptimeCanvas.getContext('2d'), {
        type: 'bar',
        data: { labels: [], datasets: [{ label: 'Uptime %', data: [], backgroundColor: [] }] },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            scales: { x: { beginAtZero: true, max: 100, title: { display: true, text: '% of 24h' } } },
            plugins: { legend: { display: false } },
        },
    });

    // ---- render ------------------------------------------------------------
    const gauges = {
        availability: makeGauge('gaugeAvailability', initial.fleet.availability_pct, '#2ecc71'),
        database: makeGauge('gaugeDatabase', initial.database.usage_pct, '#2ecc71'),
        retention: makeGauge('gaugeRetention', initial.retention.window_usage_pct, '#2ecc71'),
    };

    const render = (m) => {
        // pipeline pill
        const pill = document.getElementById('m-pipeline-pill');
        if (pill) pill.className = `pipeline-pill status-${m.pipeline.status}`;
        setText('m-pipeline-status', String(m.pipeline.status).toUpperCase());
        setText('m-seconds-since', m.pipeline.seconds_since_last ?? '—');
        setText('m-server-time', m.server_time);

        // KPI tiles
        setText('m-rate', m.pipeline.rate_per_min_recent);
        setText('m-events-24h', fmtNum(m.pipeline.events_last_24h));
        setText('m-online', m.fleet.online);
        setText('m-total', m.fleet.total);
        setText('m-active', m.fleet.active_now);
        setText('m-app-uptime', fmtDuration(m.process.app_uptime_seconds));
        setText('m-container-uptime', fmtDuration(m.process.container_uptime_seconds));
        setText('m-db-size', m.database.size_mb ?? '—');
        setText('m-hb-count', fmtNum(m.database.counts.tray_heartbeat_event));
        setText('m-outside', fmtNum(m.retention.events_outside_window));
        setText('m-alerts', m.alerts.sent_last_24h);
        setText('m-last-alert', m.alerts.last_alert_at || 'never');
        setText('m-oldest-age', m.retention.oldest_age_days);

        // data-store counts
        setText('m-c-status', fmtNum(m.database.counts.tray_status));
        setText('m-c-event', fmtNum(m.database.counts.tray_event));
        setText('m-c-heartbeat', fmtNum(m.database.counts.tray_heartbeat));
        setText('m-c-hbevent', fmtNum(m.database.counts.tray_heartbeat_event));

        // gauges
        updateGauge(gauges.availability, m.fleet.availability_pct, pctColor(m.fleet.availability_pct, 90, 60));
        updateGauge(gauges.database, m.database.usage_pct || 0, pctColor(m.database.usage_pct || 0, 70, 90, true));
        updateGauge(gauges.retention, m.retention.window_usage_pct, pctColor(m.retention.window_usage_pct, 80, 100, true));

        // ingestion chart
        if (ingestionChart) {
            const series = m.ingestion_series || [];
            ingestionChart.data.labels = series.map((p) =>
                new Date(p.t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
            ingestionChart.data.datasets[0].data = series.map((p) => p.count);
            ingestionChart.update();
        }

        // uptime chart + table
        const trays = m.fleet.trays || [];
        if (uptimeChart) {
            uptimeChart.data.labels = trays.map((t) => t.tray_id);
            uptimeChart.data.datasets[0].data = trays.map((t) => t.uptime_pct_24h);
            uptimeChart.data.datasets[0].backgroundColor = trays.map((t) => pctColor(t.uptime_pct_24h, 99, 95));
            uptimeChart.update();
        }
        const body = document.getElementById('tray-table-body');
        if (body) {
            if (!trays.length) {
                body.innerHTML = '<tr><td colspan="7">No trays have reported yet.</td></tr>';
            } else {
                body.innerHTML = trays.map((t) => `
                    <tr>
                        <td>${t.tray_id}</td>
                        <td>${t.location}</td>
                        <td>${t.is_alive ? 'Alive' : 'Down'}</td>
                        <td>${t.is_active ? 'Yes' : 'No'}</td>
                        <td>${t.seconds_since ?? '—'}</td>
                        <td>${t.uptime_pct_24h}%</td>
                        <td>${t.down_incidents_24h}</td>
                    </tr>`).join('');
            }
        }
    };

    render(initial);

    const refresh = () => {
        fetch(endpoint, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
            .then((m) => render(m))
            .catch((err) => console.warn('metrics refresh failed', err));
    };

    setInterval(refresh, refreshSeconds * 1000);
    refresh();
})();
