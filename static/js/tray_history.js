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

    const canvas = document.getElementById('trayHistoryChart');
    if (!canvas) {
        return;
    }
    const payload = canvas.dataset.chart;
    if (!payload) {
        return;
    }
    let parsed;
    try {
        parsed = JSON.parse(payload);
    } catch (err) {
        console.error('Invalid tray history chart data', err);
        return;
    }
    const labels = (parsed.labels || []).map((label) =>
        new Date(label).toLocaleString()
    );
    const data = parsed.data || [];
    const ctx = canvas.getContext('2d');
    new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [
                {
                    label: 'Collection time (minutes)',
                    data,
                    borderColor: '#ff4b5c',
                    backgroundColor: 'rgba(255, 75, 92, 0.2)',
                    tension: 0.25,
                    fill: true,
                },
            ],
        },
        options: {
            maintainAspectRatio: false,
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Minutes',
                    },
                },
            },
        },
    });

    const summaryCanvas = document.getElementById('traySummaryChart');
    if (!summaryCanvas) {
        return;
    }
    const summaryPayload = summaryCanvas.dataset.chart;
    if (!summaryPayload) {
        return;
    }
    let summaryData;
    try {
        summaryData = JSON.parse(summaryPayload);
    } catch (err) {
        console.error('Invalid summary chart data', err);
        return;
    }
    if (!summaryData || !summaryData.avg_minutes) {
        return;
    }
    const whiskerPlugin = {
        id: 'summaryWhisker',
        afterDatasetsDraw: (chart) => {
            const stats = chart.options.summaryStats;
            if (!stats) {
                return;
            }
            const ctx = chart.ctx;
            const yScale = chart.scales.y;
            const meta = chart.getDatasetMeta(0);
            if (!meta || !meta.data.length) {
                return;
            }
            const element = meta.data[0];
            const centerX = element.x;
            const minY = yScale.getPixelForValue(stats.min_minutes);
            const maxY = yScale.getPixelForValue(stats.max_minutes);
            const q1Y = yScale.getPixelForValue(stats.q1_minutes);
            const q3Y = yScale.getPixelForValue(stats.q3_minutes);
            const boxWidth = 24;
            const whiskerWidth = 18;

            ctx.save();
            ctx.strokeStyle = '#1c3d5a';
            ctx.lineWidth = 2;

            ctx.beginPath();
            ctx.moveTo(centerX, maxY);
            ctx.lineTo(centerX, minY);
            ctx.moveTo(centerX - whiskerWidth / 2, maxY);
            ctx.lineTo(centerX + whiskerWidth / 2, maxY);
            ctx.moveTo(centerX - whiskerWidth / 2, minY);
            ctx.lineTo(centerX + whiskerWidth / 2, minY);
            ctx.stroke();

            ctx.fillStyle = 'rgba(28, 61, 90, 0.15)';
            ctx.beginPath();
            ctx.rect(centerX - boxWidth / 2, q3Y, boxWidth, q1Y - q3Y);
            ctx.fill();
            ctx.stroke();
            ctx.restore();
        },
    };

    new Chart(summaryCanvas.getContext('2d'), {
        type: 'bar',
        data: {
            labels: ['Avg duration'],
            datasets: [
                {
                    label: 'Average (minutes)',
                    data: [summaryData.avg_minutes],
                    backgroundColor: '#4b9cd3',
                    borderRadius: 6,
                },
            ],
        },
        options: {
            maintainAspectRatio: false,
            responsive: true,
            summaryStats: summaryData,
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Minutes',
                    },
                },
            },
            plugins: {
                legend: {
                    display: false,
                },
            },
        },
        plugins: [whiskerPlugin],
    });
})();
