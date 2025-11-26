(() => {
    const scriptBase = (window.APP_BASE_PATH || '').replace(/\/$/, '');
    const buildUrl = (path) => (scriptBase ? `${scriptBase}${path}` : path);

    const mapElement = document.getElementById('trayMap');
    if (!mapElement) {
        return;
    }

    const map = L.map('trayMap').setView([0, 0], 2);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);

    const markers = new Map();
    let shouldFitBounds = true;
    let trayCache = [];
    let currentFilter = 'active_now';

    const trayListElement = document.getElementById('trayList');
    const filterForm = document.getElementById('trayFilters');

    function getTrayKey(tray) {
        if (tray.key) {
            return tray.key;
        }
        const topic = tray.topic || 'global';
        return `${topic}::${tray.tray_id}`;
    }

    function getLastOnTimestamp(tray) {
        return tray.last_on_at || tray.activated_at || tray.updated_at;
    }

    function hoursSince(timestamp) {
        if (!timestamp) {
            return Number.POSITIVE_INFINITY;
        }
        const updated = new Date(timestamp);
        const diffMs = Date.now() - updated.getTime();
        return diffMs / (1000 * 60 * 60);
    }

    function getActivityAgeHours(tray) {
        return hoursSince(getLastOnTimestamp(tray));
    }

    function getActivityBucket(tray) {
        if (tray.is_active) {
            return 'now';
        }
        const age = getActivityAgeHours(tray);
        if (age <= 6) {
            return '6h';
        }
        if (age <= 12) {
            return '12h';
        }
        if (age <= 24) {
            return '24h';
        }
        return '24plus';
    }

    function bucketLabel(bucket) {
        switch (bucket) {
            case 'now':
                return 'Active';
            case '6h':
                return '≤6 hrs';
            case '12h':
                return '≤12 hrs';
            case '24h':
                return '≤24 hrs';
            case '24plus':
            default:
                return '>24 hrs';
        }
    }

    function createIcon(tray) {
        const classNames = ['tray-marker'];
        const bucket = getActivityBucket(tray);
        classNames.push(`bucket-${bucket}`);
        if (bucket === 'now') {
            classNames.push('marker-blink');
        }
        return L.divIcon({
            className: classNames.join(' '),
            iconSize: [18, 18]
        });
    }

    function buildMarker(tray) {
        return L.marker([tray.latitude, tray.longitude], {
            icon: createIcon(tray)
        });
    }

    function renderMarker(tray) {
        const key = getTrayKey(tray);
        let marker = markers.get(key);
        if (!marker) {
            marker = buildMarker(tray).addTo(map);
            markers.set(key, marker);
        } else {
            marker.setLatLng([tray.latitude, tray.longitude]);
            marker.setIcon(createIcon(tray));
        }

        const statusText = bucketLabel(getActivityBucket(tray));
        marker.bindPopup(`
            <strong>${tray.tray_id}</strong><br>
            ${tray.location_label || ''}<br>
            Topic: ${tray.topic || 'n/a'}<br>
            Status: ${statusText}<br>
            Updated: ${tray.updated_at}
        `);
    }

    function focusOnTray(trayKey) {
        if (!trayKey) {
            return;
        }
        const marker = markers.get(trayKey);
        if (marker) {
            map.setView(marker.getLatLng(), Math.max(map.getZoom(), 15), {animate: true});
            marker.openPopup();
        }
    }

    function matchesFilter(tray) {
        const ageHours = getActivityAgeHours(tray);
        switch (currentFilter) {
            case 'active_6h':
                return ageHours <= 6;
            case 'active_12h':
                return ageHours <= 12;
            case 'active_24_plus':
                return ageHours >= 24;
            case 'active_now':
            default:
                return tray.is_active;
        }
    }

    function renderPanel(trays) {
        if (!trayListElement) {
            return;
        }
        trayListElement.innerHTML = '';
        if (!trays.length) {
            const empty = document.createElement('li');
            empty.className = 'empty-state';
            empty.textContent = trayListElement.dataset.empty || 'No trays match.';
            trayListElement.appendChild(empty);
            return;
        }
        trays.forEach((tray) => {
            const item = document.createElement('li');
            const bucket = getActivityBucket(tray);
            const lastOn = getLastOnTimestamp(tray);
            item.innerHTML = `
                <div>
                    <strong>${tray.tray_id}</strong><br>
                    <small>${tray.location_label || 'Unknown location'}</small><br>
                    <small>Last ON: ${lastOn ? new Date(lastOn).toLocaleString() : 'Unknown'}</small>
                </div>
                <span class="status-pill status-${bucket}">
                    ${bucketLabel(bucket)}
                </span>
                <button type="button" class="tray-focus-btn" data-tray-focus="${getTrayKey(tray)}">
                    Show
                </button>
            `;
            trayListElement.appendChild(item);
        });
    }

    function updateMarkers(trays) {
        const seen = new Set();
        const bounds = [];
        trays.forEach((tray) => {
            const key = getTrayKey(tray);
            renderMarker(tray);
            seen.add(key);
            bounds.push([tray.latitude, tray.longitude]);
        });
        markers.forEach((marker, markerKey) => {
            if (!seen.has(markerKey)) {
                map.removeLayer(marker);
                markers.delete(markerKey);
            }
        });
        if (shouldFitBounds && bounds.length) {
            shouldFitBounds = false;
            map.fitBounds(bounds, {padding: [30, 30]});
        }
    }

    function applyFilterAndRender() {
        const filtered = trayCache.filter(matchesFilter);
        renderPanel(filtered);
        updateMarkers(filtered);
    }

    function refreshTrays() {
        fetch(buildUrl('/api/tray-status/'))
            .then((response) => response.json())
            .then((data) => {
                trayCache = data.trays || [];
                applyFilterAndRender();
            })
            .catch((err) => console.error('Failed to load tray data', err));
    }

    refreshTrays();
    setInterval(refreshTrays, 5000);

    document.addEventListener('click', (event) => {
        const btn = event.target.closest('[data-tray-focus]');
        if (!btn) {
            return;
        }
        event.preventDefault();
        focusOnTray(btn.dataset.trayFocus);
    });

    if (filterForm) {
        filterForm.addEventListener('change', (event) => {
            if (event.target.name !== 'activity_filter') {
                return;
            }
            currentFilter = event.target.value;
            shouldFitBounds = true;
            applyFilterAndRender();
        });
    }
})();
