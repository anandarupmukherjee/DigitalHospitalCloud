(() => {
    const filterForm = document.querySelector('.tray-filter-form');
    if (filterForm) {
        filterForm.addEventListener('change', (event) => {
            if (event.target.tagName === 'SELECT') {
                filterForm.submit();
            }
        });
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
})();
