(() => {
    if (typeof window.Chart === 'undefined') {
        return;
    }

    const chartStates = {};
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
        const chart = builder(canvas, payload);
        if (chart) {
            chartStates[id] = { chart, payload };
        }
    };

    withChart('dashboardVolumeChart', (canvas, data) => {
        return new Chart(canvas.getContext('2d'), {
            type: 'bar',
            data: {
                labels: data.labels || [],
                datasets: data.datasets || [],
            },
            options: {
                maintainAspectRatio: false,
                responsive: true,
                scales: {
                    x: {
                        stacked: true,
                    },
                    y: {
                        beginAtZero: true,
                        stacked: true,
                        title: { display: true, text: 'Activations' },
                    },
                },
            },
        });
    });

    withChart('dashboardDurationTrend', (canvas, data) => {
        return new Chart(canvas.getContext('2d'), {
            type: 'line',
            data: {
                labels: data.labels || [],
                datasets: [
                    {
                        label: 'Median (min)',
                        data: data.median || [],
                        borderColor: '#4b9cd3',
                        backgroundColor: 'rgba(75, 156, 211, 0.1)',
                        tension: 0.2,
                        fill: false,
                    },
                    {
                        label: 'p90 (min)',
                        data: data.p90 || [],
                        borderColor: '#ff6b6b',
                        backgroundColor: 'rgba(255, 107, 107, 0.15)',
                        tension: 0.2,
                        fill: false,
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
            },
        });
    });

    withChart('dashboardOutlierChart', (canvas, data) => {
        return new Chart(canvas.getContext('2d'), {
            type: 'line',
            data: {
                labels: data.labels || [],
                datasets: [
                    {
                        label: 'Outlier rate (%)',
                        data: data.rates || [],
                        borderColor: '#ffc857',
                        backgroundColor: 'rgba(255, 200, 87, 0.2)',
                        fill: true,
                        tension: 0.2,
                    },
                ],
            },
            options: {
                maintainAspectRatio: false,
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { callback: (value) => `${value}%` },
                        title: { display: true, text: 'Percent of activations' },
                    },
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            afterLabel(context) {
                                const index = context.dataIndex;
                                const numerator = data.numerators?.[index] || 0;
                                const denominator = data.denominators?.[index] || 0;
                                return ` ${numerator}/${denominator} activations`;
                            },
                        },
                    },
                },
            },
        });
    });

    withChart('dashboardTrayComparison', (canvas, data) => {
        const chart = new Chart(canvas.getContext('2d'), {
            type: 'bar',
            data: {
                labels: data.labels || [],
                datasets: [
                    {
                        label: 'Median duration (min)',
                        data: data.median || [],
                        backgroundColor: '#4b9cd3',
                        borderRadius: 6,
                    },
                ],
            },
            options: {
                maintainAspectRatio: false,
                responsive: true,
                indexAxis: 'y',
                scales: {
                    x: {
                        beginAtZero: true,
                        title: { display: true, text: 'Minutes' },
                    },
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            afterLabel(context) {
                                const count = data.counts?.[context.dataIndex] || 0;
                                return ` Sessions: ${count}`;
                            },
                        },
                    },
                },
            },
        });
        chartStates[canvas.id] = { chart, payload: data, mode: 'median' };
        return null;
    });

    withChart('dashboardTrayScatter', (canvas, data) => {
        const points = (data.points || []).map((point) => ({
            x: point.utilization,
            y: point.median,
            r: Math.max(6, Math.min(14, Math.sqrt(point.count || 1) * 2)),
            tray: point.tray,
            location: point.location,
            count: point.count,
            p90: point.p90,
        }));
        return new Chart(canvas.getContext('2d'), {
            type: 'bubble',
            data: {
                datasets: [
                    {
                        label: 'Trays',
                        data: points,
                        backgroundColor: 'rgba(108, 92, 231, 0.4)',
                        borderColor: '#6c5ce7',
                    },
                ],
            },
            options: {
                maintainAspectRatio: false,
                responsive: true,
                scales: {
                    x: {
                        beginAtZero: true,
                        max: 100,
                        title: { display: true, text: 'Utilization (%)' },
                    },
                    y: {
                        beginAtZero: true,
                        title: { display: true, text: 'Median duration (min)' },
                    },
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            label(context) {
                                const raw = context.raw;
                                return `${raw.tray} (${raw.location})`;
                            },
                            afterLabel(context) {
                                const raw = context.raw;
                                return [
                                    `Median: ${raw.y.toFixed(1)} min`,
                                    `p90: ${raw.p90?.toFixed ? raw.p90.toFixed(1) : raw.p90} min`,
                                    `Sessions: ${raw.count}`,
                                ];
                            },
                        },
                    },
                },
            },
        });
    });

    withChart('dashboardHeatmap', (canvas, data) => {
        const dayLabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
        const points = (data.points || []).map((point) => ({
            x: point.hour,
            y: point.weekday,
            r: Math.max(3, Math.min(12, point.median / 5)),
            v: point.median,
            count: point.count,
        }));
        return new Chart(canvas.getContext('2d'), {
            type: 'bubble',
            data: {
                datasets: [
                    {
                        label: 'Duration',
                        data: points,
                        backgroundColor: points.map((point) => {
                            const intensity = Math.min(1, point.v / 120);
                            return `rgba(255, 107, 107, ${Math.max(0.2, intensity)})`;
                        }),
                    },
                ],
            },
            options: {
                maintainAspectRatio: false,
                responsive: true,
                scales: {
                    x: {
                        title: { display: true, text: 'Hour of day' },
                        ticks: { callback: (value) => `${value}:00` },
                        min: 0,
                        max: 23,
                    },
                    y: {
                        title: { display: true, text: 'Day of week' },
                        ticks: { callback: (value) => dayLabels[value] || '' },
                        min: 0,
                        max: 6,
                    },
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            label(context) {
                                const raw = context.raw;
                                const day = dayLabels[Math.round(raw.y)] || '';
                                return `${day} ${raw.x}:00`;
                            },
                            afterLabel(context) {
                                const raw = context.raw;
                                return [`Median: ${raw.v.toFixed(1)} min`, `Sessions: ${raw.count}`];
                            },
                        },
                    },
                },
            },
        });
    });

    document.querySelectorAll('[data-toggle-chart]').forEach((button) => {
        button.addEventListener('click', () => {
            const target = button.dataset.toggleChart;
            const state = chartStates[target];
            if (!state || !state.payload?.median) {
                return;
            }
            const mode = state.mode === 'p90' ? 'median' : 'p90';
            state.mode = mode;
            const dataset = state.chart.data.datasets[0];
            if (mode === 'p90') {
                dataset.data = state.payload.p90 || [];
                dataset.label = 'p90 duration (min)';
                button.textContent = 'Show median';
            } else {
                dataset.data = state.payload.median || [];
                dataset.label = 'Median duration (min)';
                button.textContent = 'Show p90';
            }
            state.chart.update();
        });
    });
})();
