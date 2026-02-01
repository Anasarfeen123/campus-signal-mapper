// ================== CONFIG ==================
const API_BASE = "https://vitc-signal-mapper.onrender.com";

// ================== CAMPUS POLYGON ==================
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
    fillOpacity: 0.08,
    dashArray: "6 4",
    interactive: false
});

const VIT_BOUNDS = VIT_POLYGON.getBounds();

// ================== MAP ==================
const map = L.map("map", {
    maxBounds: VIT_BOUNDS,
    maxBoundsViscosity: 0.8,
    minZoom: 15,
    maxZoom: 19
}).setView([12.8406, 80.1534], 17);

VIT_POLYGON.addTo(map);

L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19
}).addTo(map);

// ================== HEATMAP ==================
const heatLayer = L.heatLayer([], {
    radius: 15,
    blur: 10
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
    setTimeout(() => toast.classList.remove("show"), 3000);
}

// ================== DATA ==================
async function fetchSamples() {
    const qs = new URLSearchParams();
    if (carrierSelect.value) qs.set("carrier", carrierSelect.value);
    if (networkSelect.value) qs.set("network_type", networkSelect.value);

    try {
        setStatus("loading", "Loading…");
        const res = await fetch(`${API_BASE}/api/samples?${qs}`);
        const data = await res.json();

        const points = data
            .filter(s => s.lat && s.lng)
            .map(s => {
                const weight =
                    heatmapDataSelect.value === "dbm"
                        ? (Math.max(-120, Math.min(-50, s.signal_strength)) + 120) / 70
                        : Math.min(100, s.download_speed || 0) / 100;

                return [s.lat, s.lng, weight];
            });

        heatLayer.setLatLngs(points);
        setStatus("live", "Live");
    } catch {
        setStatus("disconnected", "Offline");
    }
}

carrierSelect.addEventListener("change", fetchSamples);
networkSelect.addEventListener("change", fetchSamples);
heatmapDataSelect.addEventListener("change", fetchSamples);

// ================== SOCKET.IO ==================
const socket = io(API_BASE, { transports: ["websocket"] });

socket.on("connect", () => setStatus("live", "Live"));
socket.on("disconnect", () => setStatus("disconnected", "Offline"));

socket.on("new_data_point", s => {
    if (!s?.lat || !s?.lng) return;
    heatLayer.addLatLng([s.lat, s.lng, 0.5]);
});

// ================== LOCATION (LOCKED ONCE) ==================
let userMarker = null;
let accuracyCircle = null;
let isLocationLocked = false;

locateBtn.addEventListener("click", () => {
    if (!navigator.geolocation) {
        showToast("Geolocation not supported", "error");
        return;
    }

    // reset lock if user clicks again
    isLocationLocked = false;

    locateBtn.disabled = true;
    locateBtn.textContent = "⌛ Locating…";

    navigator.geolocation.getCurrentPosition(
        pos => {
            if (isLocationLocked) return;

            const { latitude, longitude, accuracy } = pos.coords;
            const latlng = L.latLng(latitude, longitude);

            console.log("LOCKED LOCATION:", latitude, longitude, "±", accuracy);

            // Lock immediately
            isLocationLocked = true;

            if (userMarker) map.removeLayer(userMarker);
            if (accuracyCircle) map.removeLayer(accuracyCircle);

            userMarker = L.marker(latlng)
                .addTo(map)
                .bindPopup(`📍 Locked location<br>±${Math.round(accuracy)}m`)
                .openPopup();

            accuracyCircle = L.circle(latlng, {
                radius: accuracy,
                color: "#2563eb",
                fillOpacity: 0.15
            }).addTo(map);

            map.setView(latlng, 18);

            setStatus("live", "Location locked");
            showToast("Location locked");

            locateBtn.disabled = false;
            locateBtn.textContent = "📍 Show My Location";
        },
        err => {
            console.error("GEO ERROR:", err);
            showToast(err.message, "error");
            locateBtn.disabled = false;
            locateBtn.textContent = "📍 Show My Location";
        },
        {
            enableHighAccuracy: true,
            timeout: 20000,
            maximumAge: 0
        }
    );
});

// ================== OFFLINE ==================
function updateOfflineUI() {
    offlineIndicator.style.display = navigator.onLine ? "none" : "block";
}
window.addEventListener("online", updateOfflineUI);
window.addEventListener("offline", updateOfflineUI);
updateOfflineUI();

// ================== INIT ==================
fetchSamples();
