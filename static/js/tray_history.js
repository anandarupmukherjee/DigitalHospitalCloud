(() => {
    const filterForm = document.querySelector('.tray-filter-form');
    if (filterForm) {
        filterForm.addEventListener('change', (event) => {
            if (event.target.tagName === 'SELECT') {
                filterForm.submit();
            }
        });
    }

    const heartbeatSection = document.querySelector('[data-heartbeat-history]');
    const heartbeatToggleBtn = document.querySelector('[data-heartbeat-toggle]');
    if (heartbeatSection && heartbeatToggleBtn) {
        const updateToggleLabel = () => {
            const isCollapsed = heartbeatSection.classList.contains('collapsed');
            heartbeatToggleBtn.textContent = isCollapsed ? 'Show history' : 'Hide history';
        };
        heartbeatToggleBtn.addEventListener('click', () => {
            heartbeatSection.classList.toggle('collapsed');
            updateToggleLabel();
        });
        updateToggleLabel();
    }

    // Live heartbeat status: the server render is a one-off snapshot with a
    // tight (~5s) stale window, so it goes red between beats. Poll the shared
    // tray-status feed to keep the pill accurate, matching the dashboard.
    const heartbeatPill = document.querySelector('[data-heartbeat-live]');
    if (heartbeatPill) {
        const trayId = heartbeatPill.dataset.trayId;
        const topic = heartbeatPill.dataset.topic || '';
        const dot = heartbeatPill.querySelector('.heartbeat-dot');
        const stateEl = heartbeatPill.querySelector('[data-heartbeat-state]');
        const lastSeenEl = heartbeatPill.querySelector('[data-heartbeat-lastseen]');
        const scriptBase = (window.APP_BASE_PATH || '').replace(/\/$/, '');
        const apiUrl = `${scriptBase}/api/tray-status/`;

        const applyRecord = (record) => {
            if (!record) {
                return;
            }
            const alive = Boolean(record.is_alive);
            heartbeatPill.classList.toggle('alive', alive);
            heartbeatPill.classList.toggle('down', !alive);
            if (dot) {
                dot.classList.toggle('alive', alive);
                dot.classList.toggle('down', !alive);
            }
            if (stateEl) {
                stateEl.textContent = alive ? 'Signal alive' : 'No heartbeat';
            }
            if (lastSeenEl && record.last_seen_at) {
                lastSeenEl.textContent = new Date(record.last_seen_at).toLocaleString();
            }
        };

        const refreshHeartbeat = () => {
            fetch(apiUrl)
                .then((response) => response.json())
                .then((data) => {
                    const records = (data.heartbeat && data.heartbeat.records) || [];
                    const match =
                        records.find((r) => r.tray_id === trayId && (r.topic || '') === topic) ||
                        records.find((r) => r.tray_id === trayId);
                    applyRecord(match);
                })
                .catch(() => {});
        };

        refreshHeartbeat();
        setInterval(refreshHeartbeat, 5000);
    }

    // Generic collapsible panels (e.g. Collection sessions, Event log).
    document.querySelectorAll('[data-collapsible]').forEach((section) => {
        const toggle = section.querySelector('[data-collapse-toggle]');
        if (!toggle) {
            return;
        }
        const syncLabel = () => {
            toggle.textContent = section.classList.contains('collapsed') ? 'Show' : 'Hide';
        };
        toggle.addEventListener('click', () => {
            section.classList.toggle('collapsed');
            syncLabel();
        });
        syncLabel();
    });

    const withChart = (id, builder) => {
        const canvas = document.getElementById(id);
        if (!canvas || !canvas.dataset.chart) {
            return;
        }
        let payload;
        try {
            payload = JSON.parse(canvas.dataset.chart);
        } catch (err) {
            console.error(`Invalid data for ${id}`, err);
            return;
        }
        if (!payload) {
            return;
        }
        builder(canvas, payload);
    };

    withChart('trayDurationTrendChart', (canvas, data) => {
        const labels = (data.points || []).map((point) =>
            new Date(point.end).toLocaleString()
        );
        const meta = data.points || [];
        const threshold = data.threshold || 0;
        const median = data.median || 0;
        const outlierData = meta
            .map((point, index) =>
                point.is_outlier
                    ? { x: labels[index], y: point.minutes, meta: point }
                    : null
            )
            .filter(Boolean);
        new Chart(canvas.getContext('2d'), {
            type: 'line',
            data: {
                labels,
                datasets: [
                    {
                        label: 'Duration (min)',
                        data: meta.map((point) => point.minutes),
                        borderColor: '#ff4b5c',
                        backgroundColor: 'rgba(255, 75, 92, 0.15)',
                        tension: 0.25,
                        fill: true,
                    },
                    {
                        label: 'Median',
                        data: labels.map(() => median),
                        borderColor: '#1c3d5a',
                        borderDash: [8, 4],
                        pointRadius: 0,
                    },
                    {
                        label: 'Outlier threshold',
                        data: labels.map(() => threshold),
                        borderColor: '#ffc857',
                        borderDash: [4, 4],
                        pointRadius: 0,
                    },
                    {
                        label: 'Outliers',
                        type: 'scatter',
                        data: outlierData,
                        backgroundColor: '#d7263d',
                        borderColor: '#d7263d',
                        pointStyle: 'triangle',
                        pointRadius: 6,
                        showLine: false,
                    },
                ],
            },
            options: {
                maintainAspectRatio: false,
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: { display: true, text: 'Minutes' },
                    },
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            label(context) {
                                if (context.dataset.label !== 'Duration (min)') {
                                    if (context.dataset.label === 'Outliers') {
                                        return `Outlier: ${context.raw.y.toFixed(1)} min`;
                                    }
                                    return `${context.dataset.label}: ${context.formattedValue}`;
                                }
                                const point = meta[context.dataIndex];
                                const start = new Date(point.start).toLocaleString();
                                const end = new Date(point.end).toLocaleString();
                                return `${context.formattedValue} min (${start} → ${end})`;
                            },
                        },
                    },
                    legend: {
                        labels: { usePointStyle: true },
                    },
                },
            },
        });
    });

    withChart('trayDurationHistogram', (canvas, data) => {
        const buckets = data.buckets || [];
        const plugin = {
            id: 'durationMarkers',
            afterDatasetsDraw(chart) {
                const { ctx, scales } = chart;
                const stats = {
                    Med: data.p50,
                    'p90': data.p90,
                    Max: data.max,
                };
                Object.entries(stats).forEach(([label, value], idx) => {
                    if (!value) {
                        return;
                    }
                    const x = scales.x.getPixelForValue(value);
                    ctx.save();
                    ctx.strokeStyle = idx === 0 ? '#1c3d5a' : idx === 1 ? '#ff8e72' : '#d7263d';
                    ctx.setLineDash(idx === 0 ? [4, 4] : idx === 1 ? [6, 6] : []);
                    ctx.beginPath();
                    ctx.moveTo(x, scales.y.top);
                    ctx.lineTo(x, scales.y.bottom);
                    ctx.stroke();
                    ctx.fillStyle = ctx.strokeStyle;
                    ctx.font = '12px sans-serif';
                    ctx.fillText(label, x + 4, scales.y.top + 14);
                    ctx.restore();
                });
            },
        };
        new Chart(canvas.getContext('2d'), {
            type: 'bar',
            data: {
                labels: buckets.map((bucket) => bucket.label),
                datasets: [
                    {
                        label: 'Sessions',
                        data: buckets.map((bucket) => bucket.count),
                        backgroundColor: '#4b9cd3',
                        borderRadius: 6,
                    },
                ],
            },
            options: {
                maintainAspectRatio: false,
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: { display: true, text: 'Sessions' },
                    },
                },
            },
            plugins: [plugin],
        });
    });

    withChart('trayHourChart', (canvas, data) => {
        const labels = (data.hours || []).map((hour) => `${hour}:00`);
        const counts = data.counts || [];
        const values = data.median || [];
        const maxValue = Math.max(...values, 1);
        new Chart(canvas.getContext('2d'), {
            type: 'bar',
            data: {
                labels,
                datasets: [
                    {
                        label: 'Median duration (min)',
                        data: values,
                        backgroundColor: values.map((value) => {
                            const intensity = Math.max(0.25, value / maxValue);
                            return `rgba(255, 107, 107, ${intensity})`;
                        }),
                    },
                ],
            },
            options: {
                maintainAspectRatio: false,
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: { display: true, text: 'Minutes' },
                    },
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            afterLabel(context) {
                                const count = counts[context.dataIndex] || 0;
                                return `Sessions: ${count}`;
                            },
                        },
                    },
                },
            },
        });
    });

    withChart('trayCycleTimeline', (canvas, data) => {
        const labels = data.labels || [];
        const ranges = data.ranges || [];
        const windowStart = data.window_start ? new Date(data.window_start).getTime() : 0;
        const dataset = ranges.map((range) => {
            const start = new Date(range.start).getTime();
            const end = new Date(range.end).getTime();
            return [(start - windowStart) / 60000, (end - windowStart) / 60000];
        });
        new Chart(canvas.getContext('2d'), {
            type: 'bar',
            data: {
                labels,
                datasets: [
                    {
                        label: 'Cycle duration (min)',
                        data: dataset,
                        backgroundColor: ranges.map((range) =>
                            range.is_outlier ? 'rgba(215, 38, 61, 0.6)' : 'rgba(75, 156, 211, 0.6)'
                        ),
                        borderColor: ranges.map((range) =>
                            range.is_outlier ? '#d7263d' : '#4b9cd3'
                        ),
                        borderWidth: 1,
                    },
                ],
            },
            options: {
                maintainAspectRatio: false,
                responsive: true,
                indexAxis: 'y',
                parsing: true,
                scales: {
                    x: {
                        beginAtZero: true,
                        title: { display: true, text: 'Minutes since range start' },
                    },
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            label(context) {
                                const range = ranges[context.dataIndex];
                                const start = new Date(range.start).toLocaleString();
                                const end = new Date(range.end).toLocaleString();
                                return `${range.minutes.toFixed(1)} min (${start} → ${end})`;
                            },
                        },
                    },
                },
            },
        });
    });

    withChart('trayQueueChart', (canvas, data) => {
        const points = data.points || [];
        const labels = points.map((point) => new Date(point.timestamp).toLocaleString());
        new Chart(canvas.getContext('2d'), {
            type: 'line',
            data: {
                labels,
                datasets: [
                    {
                        label: 'Elapsed minutes',
                        data: points.map((point) => point.minutes),
                        borderColor: '#6c5ce7',
                        backgroundColor: 'rgba(108, 92, 231, 0.2)',
                        fill: true,
                        tension: 0.25,
                    },
                ],
            },
            options: {
                maintainAspectRatio: false,
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: { display: true, text: 'Minutes' },
                    },
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            label(context) {
                                return `${context.formattedValue} min (as of ${context.label})`;
                            },
                        },
                    },
                },
            },
        });
    });
})();
