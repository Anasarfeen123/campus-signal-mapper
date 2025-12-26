// ================== CONFIG ==================
const API_BASE = "https://vitc-signal-mapper.onrender.com";

// ================== CAMPUS POLYGON (MUST MATCH BACKEND) ==================
const VIT_POLYGON_COORDS = [
    [12.8455, 80.1532],
    [12.8447, 80.1587],
    [12.8435, 80.1589],
    [12.8395, 80.1560],
    [12.8387, 80.1545],
    [12.8419, 80.1515],
    [12.8425, 80.1510],
    [12.8456, 80.1518]
];

const VIT_POLYGON = L.polygon(VIT_POLYGON_COORDS, {
    color: "#2563eb",
    weight: 2,
    opacity: 0.9,
    fillColor: "#2563eb",
    fillOpacity: 0.08,
    dashArray: "6 4",
    interactive: false,
    className: "campus-boundary"
});

const CAMPUS_POLYGON_POINTS = VIT_POLYGON.getLatLngs()[0];
const VIT_BOUNDS = VIT_POLYGON.getBounds();

// ================== MAP ==================
const map = L.map("map", {
    maxBounds: VIT_BOUNDS,
    maxBoundsViscosity: 0.8,
    minZoom: 15,
    maxZoom: 19
}).setView([12.8406, 80.1534], 17);

map.on("drag", () => {
    map.panInsideBounds(VIT_BOUNDS, { animate: false });
});

VIT_POLYGON.addTo(map);

L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "© OpenStreetMap"
}).addTo(map);

// ================== HEATMAP ==================
const heatLayer = L.heatLayer([], {
    radius: 15,
    blur: 10,
    maxZoom: 17
}).addTo(map);

// ================== DOM ==================
const carrierSelect = document.getElementById("carrier-select");
const networkSelect = document.getElementById("network");
const heatmapDataSelect = document.getElementById("heatmap-data");
const statusLight = document.getElementById("status-light");
const statusText = document.getElementById("status-text");
const locateBtn = document.getElementById("locate-btn");
const offlineIndicator = document.getElementById("offline-indicator");
const toast = document.getElementById("toast");

// ================== UI HELPERS ==================
function setStatus(state, text) {
    statusLight.className = "";
    statusLight.classList.add(state);
    statusText.textContent = text;
}

function showToast(msg, type = "info") {
    toast.textContent = msg;
    toast.className = `toast show ${type}`;
    setTimeout(() => toast.classList.remove("show"), 2500);
}

function setOutsideCampusUI(isOutside) {
    document.getElementById("map").classList.toggle("map-dim", isOutside);
}

// ================== GEO ==================
function pointInPolygon(point, polygon) {
    let inside = false;
    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
        const xi = polygon[i].lng, yi = polygon[i].lat;
        const xj = polygon[j].lng, yj = polygon[j].lat;
        const intersect =
            (yi > point.lat) !== (yj > point.lat) &&
            point.lng < ((xj - xi) * (point.lat - yi)) / (yj - yi) + xi;
        if (intersect) inside = !inside;
    }
    return inside;
}

// ================== NORMALIZATION ==================
function dbmToWeight(dbm) {
    if (typeof dbm !== "number") return 0.15;
    return (Math.max(-120, Math.min(-50, dbm)) + 120) / 70;
}

function speedToWeight(mbps) {
    if (typeof mbps !== "number") return 0;
    return Math.min(100, Math.max(0, mbps)) / 100;
}

// ================== DATA ==================
async function fetchSamples() {
    const qs = new URLSearchParams();
    if (carrierSelect.value) qs.set("carrier", carrierSelect.value);
    if (networkSelect.value) qs.set("network_type", networkSelect.value);
    qs.set("limit", "200");

    setStatus("loading", "Loading…");

    try {
        const res = await fetch(`${API_BASE}/api/samples?${qs.toString()}`);
        if (!res.ok) throw new Error();

        const data = await res.json();

        const points = data
            .map(s => {
                if (!s.lat || !s.lng) return null;
                const latlng = L.latLng(s.lat, s.lng);
                if (!pointInPolygon(latlng, CAMPUS_POLYGON_POINTS)) return null;

                const weight =
                    heatmapDataSelect.value === "dbm"
                        ? dbmToWeight(s.signal_strength)
                        : speedToWeight(s.download_speed);

                return [s.lat, s.lng, weight];
            })
            .filter(Boolean);

        heatLayer.setLatLngs(points);
        setStatus("live", "Live");
    } catch {
        setStatus("disconnected", "Offline");
    }
}

// ================== EVENTS ==================
carrierSelect.addEventListener("change", fetchSamples);
networkSelect.addEventListener("change", fetchSamples);
heatmapDataSelect.addEventListener("change", fetchSamples);

// ================== SOCKET.IO ==================
const socket = io(API_BASE, { transports: ["websocket"] });

socket.on("connect", () => setStatus("live", "Live"));
socket.on("disconnect", () => setStatus("disconnected", "Offline"));

socket.on("new_data_point", s => {
    if (!s?.lat || !s?.lng) return;
    if (carrierSelect.value && s.carrier !== carrierSelect.value) return;
    if (networkSelect.value && s.network_type !== networkSelect.value) return;

    const latlng = L.latLng(s.lat, s.lng);
    if (!pointInPolygon(latlng, CAMPUS_POLYGON_POINTS)) return;

    const weight =
        heatmapDataSelect.value === "dbm"
            ? dbmToWeight(s.signal_strength)
            : speedToWeight(s.download_speed);

    heatLayer.addLatLng([s.lat, s.lng, weight]);
});

// ================== LOCATION ==================
let userMarker = null;

locateBtn.addEventListener("click", () => {
    if (!navigator.geolocation) {
        showToast("Geolocation not supported", "error");
        return;
    }

    locateBtn.disabled = true;
    locateBtn.textContent = "⌛ Locating…";

    navigator.geolocation.getCurrentPosition(
        ({ coords }) => {
            const latlng = L.latLng(coords.latitude, coords.longitude);

            if (coords.accuracy > 50) {
                showToast("GPS accuracy too low", "error");
                locateBtnReset();
                return;
            }

            if (!pointInPolygon(latlng, CAMPUS_POLYGON_POINTS)) {
                setStatus("disconnected", "Outside campus");
                setOutsideCampusUI(true);
                heatLayer.setLatLngs([]);
                showToast("Outside VIT Chennai campus", "error");
                locateBtnReset();
                return;
            }

            setOutsideCampusUI(false);
            setStatus("live", "Inside campus");

            if (userMarker) map.removeLayer(userMarker);
            userMarker = L.marker(latlng).addTo(map).bindPopup("📍 Inside campus").openPopup();

            map.setView(latlng, Math.max(map.getZoom(), 18));
            locateBtnReset();
        },
        locateBtnReset,
        { enableHighAccuracy: true, timeout: 10000 }
    );
});

function locateBtnReset() {
    locateBtn.textContent = "📍 Show My Location";
    locateBtn.disabled = false;
}

// ================== OFFLINE ==================
function updateOfflineUI() {
    offlineIndicator.style.display = navigator.onLine ? "none" : "block";
}
window.addEventListener("online", updateOfflineUI);
window.addEventListener("offline", updateOfflineUI);
updateOfflineUI();

// ================== INIT ==================
fetchSamples();
