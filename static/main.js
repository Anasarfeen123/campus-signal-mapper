// ---------------- MAP SETUP ----------------
const map = L.map('map').setView([12.8406, 80.1534], 17);

L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
}).addTo(map);

const heatLayer = L.heatLayer([], {
    radius: 15,
    blur: 10,
    maxZoom: 17
}).addTo(map);

// ---------------- DOM ELEMENTS ----------------
const carrierSelect = document.getElementById('carrier-select'); // FIXED
const networkSelect = document.getElementById('network');
const heatmapDataSelect = document.getElementById('heatmap-data');
const statusLight = document.getElementById('status-light');
const statusText = document.getElementById('status-text');

// ---------------- STATUS HANDLING ----------------
function setStatus(state, text) {
    statusLight.classList.remove('live', 'loading', 'disconnected');
    statusLight.classList.add(state);
    statusText.textContent = text;
}

// ---------------- DATA FETCH ----------------
async function fetchSamples() {
    const carrier = carrierSelect.value;
    const network = networkSelect.value;
    const heatmapType = heatmapDataSelect.value;

    const qs = new URLSearchParams();
    if (carrier) qs.set('carrier', carrier);
    if (network) qs.set('network_type', network);
    qs.set('limit', 200);

    setStatus('loading', 'Loading…');

    try {
        const res = await fetch('/api/samples?' + qs.toString());
        if (!res.ok) throw new Error(res.statusText);

        const data = await res.json();

        const points = data
            .map(s => {
                if (!s.lat || !s.lng) return null;

                const weight =
                    heatmapType === 'dbm'
                        ? dbmToWeight(s.signal_strength)
                        : speedToWeight(s.download_speed);

                return [s.lat, s.lng, weight];
            })
            .filter(Boolean);

        heatLayer.setLatLngs(points);
        setStatus('live', 'Live');
    } catch (err) {
        console.error(err);
        setStatus('disconnected', 'Offline');
    }
}

// ---------------- NORMALIZATION ----------------
function dbmToWeight(dbm) {
    if (typeof dbm !== 'number') return 0.15;
    const clamped = Math.max(-120, Math.min(-50, dbm));
    return (clamped + 120) / 70;
}

function speedToWeight(mbps) {
    if (typeof mbps !== 'number') return 0;
    const clamped = Math.max(0, Math.min(100, mbps));
    return clamped / 100;
}

// ---------------- EVENTS ----------------
carrierSelect.addEventListener('change', fetchSamples);
networkSelect.addEventListener('change', fetchSamples);
heatmapDataSelect.addEventListener('change', fetchSamples);

// ---------------- SOCKET.IO ----------------
const socket = io();

socket.on('connect', () => {
    console.log('socket connected');
});

socket.on('disconnect', () => {
    setStatus('disconnected', 'Offline');
});

socket.on('new_data_point', (s) => {
    const carrierMatch = !carrierSelect.value || s.carrier === carrierSelect.value;
    const networkMatch = !networkSelect.value || s.network_type === networkSelect.value;

    if (carrierMatch && networkMatch) {
        const weight =
            heatmapDataSelect.value === 'dbm'
                ? dbmToWeight(s.signal_strength)
                : speedToWeight(s.download_speed);

        if (s.lat && s.lng) {
            heatLayer.addLatLng([s.lat, s.lng, weight]);
        }
    }
});

// ---------------- GEOLOCATION ----------------
const locateBtn = document.getElementById('locate-btn');
let userMarker = null;

if (locateBtn) {
    locateBtn.addEventListener('click', () => {
        if (!navigator.geolocation) {
            alert("Geolocation not supported");
            return;
        }

        const original = locateBtn.innerHTML;
        locateBtn.innerHTML = "⌛ Locating…";
        locateBtn.disabled = true;

        navigator.geolocation.getCurrentPosition(
            ({ coords }) => {
                if (userMarker) map.removeLayer(userMarker);

                userMarker = L.marker([coords.latitude, coords.longitude])
                    .addTo(map)
                    .bindPopup("📍 You are here")
                    .openPopup();

                map.setView([coords.latitude, coords.longitude], 18);

                locateBtn.innerHTML = "📍 Found you";
                locateBtn.disabled = false;

                setTimeout(() => {
                    locateBtn.innerHTML = original;
                }, 3000);
            },
            () => {
                alert("Location access denied");
                locateBtn.innerHTML = original;
                locateBtn.disabled = false;
            },
            { enableHighAccuracy: true }
        );
    });
}

// Initial load
fetchSamples();
