// ================== CAMPUS POLYGON (MUST MATCH BACKEND) ==================
const VIT_POLYGON_COORDS = [
    [12.8455, 80.1532], // North-West
    [12.8447, 80.1587], // North-East
    [12.8435, 80.1589], // East
    [12.8395, 80.1560], // South-East
    [12.8387, 80.1545], // South
    [12.8419, 80.1515], // South-West
    [12.8425, 80.1510], // West
    [12.8456, 80.1518]  // Close loop
];

const VIT_POLYGON = L.polygon(VIT_POLYGON_COORDS, {
    color: '#2563eb',
    weight: 2,
    opacity: 0.9,
    fillColor: '#2563eb',
    fillOpacity: 0.08,
    dashArray: '6 4',
    interactive: false,
    className: 'campus-boundary'
});


function showToast(msg, type = 'info') {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.className = `toast show ${type}`;
    setTimeout(() => t.classList.remove('show'), 2500);
}

function setOutsideCampusUI(isOutside) {
    const mapEl = document.getElementById('map');
    mapEl.classList.toggle('map-dim', isOutside);
}

function setLocateButtonState(state) {
    const textEl = locateBtn.querySelector('.text');
    if (!textEl) return;

    if (state === 'outside') {
        textEl.textContent = 'Outside Campus';
        locateBtn.classList.remove('btn-primary');
        locateBtn.classList.add('btn-secondary');
    } else {
        textEl.textContent = 'Show My Location';
        locateBtn.classList.add('btn-primary');
        locateBtn.classList.remove('btn-secondary');
    }
}

const CAMPUS_POLYGON_POINTS = VIT_POLYGON.getLatLngs()[0];
const VIT_BOUNDS = VIT_POLYGON.getBounds();

// ================== MAP SETUP ==================
const map = L.map('map', {
    maxBounds: VIT_BOUNDS,
    maxBoundsViscosity: 0.8,
    minZoom: 15,
    maxZoom: 19
}).setView([12.8406, 80.1534], 17);

map.on('drag', () => {
    map.panInsideBounds(VIT_BOUNDS, { animate: false });
});

VIT_POLYGON.addTo(map);

L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '© OpenStreetMap'
}).addTo(map);

// ================== HEATMAP ==================
const heatLayer = L.heatLayer([], {
    radius: 15,
    blur: 10,
    maxZoom: 17
}).addTo(map);

// ================== DOM ELEMENTS ==================
const carrierSelect = document.getElementById('carrier-select');
const networkSelect = document.getElementById('network');
const heatmapDataSelect = document.getElementById('heatmap-data');
const statusLight = document.getElementById('status-light');
const statusText = document.getElementById('status-text');
const locateBtn = document.getElementById('locate-btn');
const offlineIndicator = document.getElementById('offline-indicator');

// ================== STATUS ==================
function setStatus(state, text) {
    statusLight.classList.remove('live', 'loading', 'disconnected');
    statusLight.classList.add(state);
    statusText.textContent = text;
}

// ================== POINT-IN-POLYGON ==================
function pointInPolygon(point, polygon) {
    let x = point.lng;
    let y = point.lat;
    let inside = false;

    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
        const xi = polygon[i].lng, yi = polygon[i].lat;
        const xj = polygon[j].lng, yj = polygon[j].lat;

        const intersect =
            ((yi > y) !== (yj > y)) &&
            (x < (xj - xi) * (y - yi) / (yj - yi) + xi);

        if (intersect) inside = !inside;
    }

    return inside;
}

// ================== NORMALIZATION ==================
function dbmToWeight(dbm) {
    if (typeof dbm !== 'number') return 0.15;
    return (Math.max(-120, Math.min(-50, dbm)) + 120) / 70;
}

function speedToWeight(mbps) {
    if (typeof mbps !== 'number') return 0;
    return Math.min(100, Math.max(0, mbps)) / 100;
}

// ================== FETCH HEATMAP DATA ==================
async function fetchSamples() {
    const qs = new URLSearchParams();

    if (carrierSelect.value) qs.set('carrier', carrierSelect.value);
    if (networkSelect.value) qs.set('network_type', networkSelect.value);
    qs.set('limit', 200);

    setStatus('loading', 'Loading…');

    try {
        const res = await fetch('/api/samples?' + qs.toString());
        if (!res.ok) throw new Error();

        const data = await res.json();

        const points = data
            .map(s => {
                if (!s.lat || !s.lng) return null;

                const latlng = L.latLng(s.lat, s.lng);
                if (!pointInPolygon(latlng, CAMPUS_POLYGON_POINTS)) return null;

                const weight =
                    heatmapDataSelect.value === 'dbm'
                        ? dbmToWeight(s.signal_strength)
                        : speedToWeight(s.download_speed);

                return [s.lat, s.lng, weight];
            })
            .filter(Boolean);

        heatLayer.setLatLngs(points);
        setStatus('live', 'Live');
    } catch {
        setStatus('disconnected', 'Offline');
    }
}

// ================== FILTER EVENTS ==================
carrierSelect.addEventListener('change', fetchSamples);
networkSelect.addEventListener('change', fetchSamples);
heatmapDataSelect.addEventListener('change', fetchSamples);

// ================== SOCKET.IO ==================
const socket = io();
let socketConnected = false;

socket.on('connect', () => {
    socketConnected = true;
    setStatus('live', 'Live');
});

socket.on('disconnect', () => {
    socketConnected = false;
    setStatus('disconnected', 'Offline');
});

socket.on('new_data_point', (s) => {
    if (!s?.lat || !s?.lng) return;
    if (carrierSelect.value && s.carrier !== carrierSelect.value) return;
    if (networkSelect.value && s.network_type !== networkSelect.value) return;

    const latlng = L.latLng(s.lat, s.lng);
    if (!pointInPolygon(latlng, CAMPUS_POLYGON_POINTS)) return;

    const weight =
        heatmapDataSelect.value === 'dbm'
            ? dbmToWeight(s.signal_strength)
            : speedToWeight(s.download_speed);

    heatLayer.addLatLng([s.lat, s.lng, weight]);
});

// ================== GEOLOCATION ==================
let userMarker = null;

if (locateBtn) {
    locateBtn.addEventListener('click', () => {
        if (!navigator.geolocation) {
            showToast("Geolocation not supported","error");
            return;
        }

        const originalText = locateBtn.innerHTML;
        locateBtn.innerHTML = "⌛ Locating…";
        locateBtn.disabled = true;

        navigator.geolocation.getCurrentPosition(
            ({ coords }) => {
                const latlng = L.latLng(coords.latitude, coords.longitude);

                if (coords.accuracy > 50) {
                    showToast("GPS accuracy too low. Move to open area.","error");
                    locateBtn.innerHTML = originalText;
                    locateBtn.disabled = false;
                    return;
                }

                if (!pointInPolygon(latlng, CAMPUS_POLYGON_POINTS)) {
                    showToast("🚫 Outside VIT Chennai campus","error");
                    setStatus('disconnected', 'Outside campus');
                    setOutsideCampusUI(true);

                    locateBtn.innerHTML = originalText;
                    locateBtn.disabled = false;
                    return;
                }


                if (userMarker) map.removeLayer(userMarker);
                setOutsideCampusUI(false);
                setStatus('live', 'Inside campus');

                userMarker = L.marker(latlng)
                    .addTo(map)
                    .bindPopup("📍 You are inside campus")
                    .openPopup();

                map.setView(latlng, Math.max(map.getZoom(), 18));

                locateBtn.innerHTML = "📍 Inside campus";
                locateBtn.disabled = false;

                setTimeout(() => {
                    locateBtn.innerHTML = originalText;
                }, 2500);
            },
            () => {
                locateBtn.innerHTML = originalText;
                locateBtn.disabled = false;
            },
            { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
        );
    });
}

// ================== OFFLINE UI ==================
function updateOfflineUI() {
    if (!offlineIndicator) return;
    offlineIndicator.style.display = navigator.onLine ? 'none' : 'block';
}
function pulseCampus() {
    VIT_POLYGON.setStyle({ fillOpacity: 0.18 });
    setTimeout(() => VIT_POLYGON.setStyle({ fillOpacity: 0.08 }), 400);
}

window.addEventListener('online', updateOfflineUI);
window.addEventListener('offline', updateOfflineUI);
updateOfflineUI();

// ================== INITIAL LOAD ==================
fetchSamples();
