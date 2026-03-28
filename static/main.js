// ================== CONFIG ==================
const API_BASE = window.location.origin; // Relative — works on any host
const isMobile = window.innerWidth < 600;

// ================== CAMPUS POLYGON ==================
const VIT_POLYGON_COORDS = [
    [12.8455, 80.1532], [12.8447, 80.1587], [12.8435, 80.1589],
    [12.8395, 80.1560], [12.8387, 80.1545], [12.8419, 80.1515],
    [12.8425, 80.1510], [12.8456, 80.1518]
];

const VIT_POLYGON = L.polygon(VIT_POLYGON_COORDS, {
    color: "#38bdf8",
    weight: 2,
    fillOpacity: 0.07,
    fillColor: "#38bdf8",
    dashArray: "8 5",
    interactive: false
});

const VIT_BOUNDS = VIT_POLYGON.getBounds();

// ================== MAP ==================
const map = L.map("map", {
    maxBounds: VIT_BOUNDS.pad(0.15),
    maxBoundsViscosity: 0.9,
    minZoom: 15,
    maxZoom: 19,
    zoomControl: false
}).setView([12.8421, 80.1553], 17);

// Move zoom control to bottom-right to avoid panel overlap
L.control.zoom({ position: "bottomright" }).addTo(map);

VIT_POLYGON.addTo(map);

const TILE_PROVIDERS = [
    {
        url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
    },
    {
        url: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; CARTO',
        subdomains: "abcd"
    }
];

let tileProviderIndex = 0;
let tileErrorCount = 0;
let baseLayer = createBaseLayer(tileProviderIndex).addTo(map);

function createBaseLayer(providerIndex) {
    const provider = TILE_PROVIDERS[providerIndex];
    return L.tileLayer(provider.url, {
        attribution: provider.attribution,
        maxZoom: 19,
        className: "map-tiles",
        subdomains: provider.subdomains
    });
}

function switchTileProvider() {
    if (tileProviderIndex >= TILE_PROVIDERS.length - 1) return;
    const nextProviderIndex = tileProviderIndex + 1;
    const nextLayer = createBaseLayer(nextProviderIndex);
    map.removeLayer(baseLayer);
    baseLayer = nextLayer.addTo(map);
    tileProviderIndex = nextProviderIndex;
    tileErrorCount = 0;
    console.warn("Switched tile provider to fallback:", TILE_PROVIDERS[nextProviderIndex].url);
    showToast("Primary map tiles unavailable. Switched to fallback tiles.", "warn", 4500);
}

baseLayer.on("tileerror", () => {
    tileErrorCount += 1;
    if (tileErrorCount >= 6) switchTileProvider();
});

// ================== HEATMAP ==================
const heatLayer = L.heatLayer([], {
    radius: isMobile ? 15 : 22,
    blur: isMobile ? 12 : 18,
    maxZoom: 17,
    gradient: {
        0.0: "#3b0764",
        0.25: "#1d4ed8",
        0.5: "#06b6d4",
        0.7: "#16a34a",
        0.85: "#ca8a04",
        1.0: "#dc2626"
    }
}).addTo(map);

// ================== DOM ==================
const carrierSelect   = document.getElementById("carrier-select");
const networkSelect   = document.getElementById("network");
const heatmapDataSel  = document.getElementById("heatmap-data");
const statusLight     = document.getElementById("status-light");
const statusText      = document.getElementById("status-text");
const locateBtn       = document.getElementById("locate-btn");
const offlineBar      = document.getElementById("offline-indicator");
const toast           = document.getElementById("toast");
const sampleCount     = document.getElementById("sample-count");
const avgSignal       = document.getElementById("avg-signal");
const avgSpeed        = document.getElementById("avg-speed");

// ================== HELPERS ==================
function setStatus(state, text) {
    statusLight.className = "";
    statusLight.classList.add(state);
    statusText.textContent = text;
}

function showToast(msg, type = "info", duration = 3200) {
    toast.textContent = msg;
    toast.className = `toast show ${type}`;
    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => toast.classList.remove("show"), duration);
}

function formatDbm(v) {
    if (v == null) return "—";
    return `${Math.round(v)} dBm`;
}

function formatMbps(v) {
    if (v == null) return "—";
    return `${v.toFixed(1)} Mbps`;
}

// ================== STATS ==================
async function fetchStats() {
    try {
        const res = await fetch(`${API_BASE}/api/stats`);
        if (!res.ok) return;
        const d = await res.json();
        if (sampleCount) sampleCount.textContent = d.total_samples?.toLocaleString() ?? "—";
        if (avgSignal)   avgSignal.textContent   = formatDbm(d.avg_signal_dbm);
        if (avgSpeed)    avgSpeed.textContent     = formatMbps(d.avg_speed_mbps);
    } catch { /* silently fail — stats are non-critical */ }
}

// ================== DATA ==================
let _allPoints = [];

async function fetchSamples() {
    const qs = new URLSearchParams();
    if (carrierSelect.value)  qs.set("carrier",      carrierSelect.value);
    if (networkSelect.value)  qs.set("network_type", networkSelect.value);

    const pointLimit = isMobile ? "1000" : "5000";
    qs.set("limit", pointLimit);
    
    try {
        setStatus("loading", "Loading…");
        const res = await fetch(`${API_BASE}/api/samples?${qs}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        _allPoints = data;
        renderHeatmap(data);
        setStatus("live", `Live · ${data.length} pts`);
    } catch (err) {
        console.error("fetchSamples:", err);
        setStatus("disconnected", "Offline");
        showToast("Failed to load data", "error");
    }
}

function renderHeatmap(data) {
    const mode = heatmapDataSel?.value ?? "dbm";
    const points = data
        .filter(s => s.lat && s.lng)
        .map(s => {
            let weight;
            if (mode === "dbm") {
                const clamped = Math.max(-120, Math.min(-50, s.signal_strength ?? -120));
                weight = (clamped + 120) / 70;
            } else {
                weight = Math.min(100, s.download_speed ?? 0) / 100;
            }
            return [s.lat, s.lng, weight];
        });

    heatLayer.setLatLngs(points);
}

carrierSelect?.addEventListener("change",  fetchSamples);
networkSelect?.addEventListener("change",  fetchSamples);
heatmapDataSel?.addEventListener("change", () => renderHeatmap(_allPoints));

// ================== SOCKET.IO ==================
const socket = io(API_BASE, {
    transports: ["websocket"],
    reconnectionDelay: 1000,
    reconnectionDelayMax: 10000
});

socket.on("connect",    () => setStatus("live", "Live"));
socket.on("disconnect", () => setStatus("disconnected", "Disconnected"));
socket.on("connect_error", () => setStatus("disconnected", "Reconnecting…"));

socket.on("new_data_point", s => {
    if (!s?.lat || !s?.lng) return;
    _allPoints.push(s);

    const mode = heatmapDataSel?.value ?? "dbm";
    let weight;
    if (mode === "dbm") {
        const clamped = Math.max(-120, Math.min(-50, s.signal_strength ?? -120));
        weight = (clamped + 120) / 70;
    } else {
        weight = Math.min(100, s.download_speed ?? 0) / 100;
    }
    heatLayer.addLatLng([s.lat, s.lng, weight]);
    showToast(`New point: ${s.carrier} ${s.network_type}`, "success", 2000);

    // Update status count
    const currentMatch = statusText.textContent.match(/(\d+) pts/);
    const count = currentMatch ? parseInt(currentMatch[1]) + 1 : "?";
    setStatus("live", `Live · ${count} pts`);
});

// ================== LOCATION ==================
let userMarker    = null;
let accuracyCircle = null;

locateBtn?.addEventListener("click", () => {
    if (!navigator.geolocation) {
        showToast("Geolocation not supported by this browser", "error");
        return;
    }

    locateBtn.disabled = true;
    locateBtn.textContent = "⌛ Locating…";

    navigator.geolocation.getCurrentPosition(
        pos => {
            const { latitude, longitude, accuracy } = pos.coords;
            const latlng = L.latLng(latitude, longitude);

            if (userMarker)    map.removeLayer(userMarker);
            if (accuracyCircle) map.removeLayer(accuracyCircle);

            userMarker = L.circleMarker(latlng, {
                radius: 8,
                color: "#fff",
                weight: 2,
                fillColor: "#3b82f6",
                fillOpacity: 1
            })
            .addTo(map)
            .bindPopup(`<b>Your Location</b><br>Accuracy: ±${Math.round(accuracy)} m`)
            .openPopup();

            accuracyCircle = L.circle(latlng, {
                radius: accuracy,
                color: "#3b82f6",
                fillOpacity: 0.08,
                weight: 1
            }).addTo(map);

            map.setView(latlng, 18, { animate: true, duration: 0.8 });
            showToast(`Location found (±${Math.round(accuracy)} m)`, "success");

            locateBtn.disabled = false;
            locateBtn.textContent = "📍 My Location";
        },
        err => {
            const msgs = {
                1: "Location permission denied",
                2: "Location unavailable",
                3: "Location request timed out"
            };
            showToast(msgs[err.code] ?? err.message, "error");
            locateBtn.disabled = false;
            locateBtn.textContent = "📍 My Location";
        },
        { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 }
    );
});

// ================== OFFLINE UI ==================
function updateOfflineUI() {
    if (offlineBar) offlineBar.style.display = navigator.onLine ? "none" : "block";
}
window.addEventListener("online",  updateOfflineUI);
window.addEventListener("offline", updateOfflineUI);
updateOfflineUI();

// ================== MOBILE PANEL ==================
(function () {
    const panel = document.getElementById("panel");
    const panelInner = document.querySelector(".panel-inner");
    const panelHead = document.querySelector(".panel-head");
    const toggleBtn = document.getElementById("menu-toggle");

    if (!panel || !panelHead || !panelInner) return;

    let isCollapsed = window.innerWidth < 600;
    
    // Swipe state variables
    let startY = 0;
    let currentY = 0;
    let isDragging = false;

    // The maximum distance the panel slides down (matches your CSS: 80vh - 64px)
    function getMaxTranslate() {
        return (window.innerHeight * 0.8) - 64;
    }

    // Applies the current state to the DOM
    function applyState() {
        panel.classList.toggle("collapsed", isCollapsed);
        if (toggleBtn) toggleBtn.textContent = isCollapsed ? "▴" : "▾";
        
        // Wipe any inline styles so your CSS classes take over and animate it
        panelInner.style.transform = '';
        panelInner.style.transition = '';
    }

    // Standard click toggle
    panelHead.addEventListener("click", (e) => {
        // If they just finished a swipe, ignore the click
        if (isDragging) return; 
        isCollapsed = !isCollapsed;
        applyState();
    });

    // ── TOUCH GESTURE LOGIC ──

    panelHead.addEventListener("touchstart", (e) => {
        if (window.innerWidth >= 600) return;
        
        startY = e.touches[0].clientY;
        currentY = startY;
        isDragging = false; 
        
        // Remove CSS transition for instant 1:1 finger tracking
        panelInner.style.transition = "none";
    }, { passive: true });

    panelHead.addEventListener("touchmove", (e) => {
        if (window.innerWidth >= 600) return;
        
        currentY = e.touches[0].clientY;
        const deltaY = currentY - startY;

        // If they barely moved, it might just be a tap.
        if (Math.abs(deltaY) > 5) {
            isDragging = true;
        }
        
        if (!isDragging) return;

        const maxTranslate = getMaxTranslate();
        
        // Calculate where the panel should be based on finger movement
        let newTranslate = isCollapsed ? maxTranslate + deltaY : deltaY;
        
        // Clamp it so they can't drag it out of bounds
        if (newTranslate < 0) newTranslate = 0;
        if (newTranslate > maxTranslate) newTranslate = maxTranslate;
        
        // Apply the movement instantly
        panelInner.style.transform = `translateY(${newTranslate}px)`;
    }, { passive: true });

    panelHead.addEventListener("touchend", () => {
        if (window.innerWidth >= 600 || !isDragging) {
            // If they just tapped, restore CSS and let the click handler take it
            applyState();
            return;
        }

        const deltaY = currentY - startY;
        const threshold = 60; // How many pixels they must swipe to trigger a state change

        if (isCollapsed && deltaY < -threshold) {
            // Swiped UP hard enough from bottom
            isCollapsed = false;
        } else if (!isCollapsed && deltaY > threshold) {
            // Swiped DOWN hard enough from top
            isCollapsed = true;
        }

        // Delay resetting the dragging flag slightly so the click event doesn't fire
        setTimeout(() => { isDragging = false; }, 50);

        // Hand control back to CSS to snap into the final position
        applyState();
    });

    // ── MAP CLICK ──
    map.on("click", () => {
        if (window.innerWidth < 600 && !isCollapsed) {
            isCollapsed = true;
            applyState();
        }
    });

    // ── INIT ──
    if (isCollapsed) applyState();
})();


// ================== OFFLINE MAP DOWNLOADER ==================
const downloadMapBtn = document.getElementById("download-map-btn");

// Math to convert Latitude/Longitude to OpenStreetMap XYZ tile numbers
function lon2tile(lon, zoom) { 
    return (Math.floor((lon + 180) / 360 * Math.pow(2, zoom))); 
}
function lat2tile(lat, zoom) { 
    return (Math.floor((1 - Math.log(Math.tan(lat * Math.PI / 180) + 1 / Math.cos(lat * Math.PI / 180)) / Math.PI) / 2 * Math.pow(2, zoom))); 
}

downloadMapBtn?.addEventListener("click", async () => {
    if (!('caches' in window)) {
        showToast("Offline caching not supported by this browser.", "error");
        return;
    }

    downloadMapBtn.disabled = true;
    downloadMapBtn.textContent = "⌛ Calculating tiles...";

    // Get the North, South, East, and West edges of the campus polygon
    const bounds = VIT_POLYGON.getBounds();
    const n = bounds.getNorth();
    const s = bounds.getSouth();
    const e = bounds.getEast();
    const w = bounds.getWest();

    const tileUrls = [];

    // Loop through zoom levels 15 to 19 (19 provides maximum street-level detail)
    for (let z = 15; z <= 19; z++) {
        const top = lat2tile(n, z);
        const bottom = lat2tile(s, z);
        const left = lon2tile(w, z);
        const right = lon2tile(e, z);

        for (let x = left; x <= right; x++) {
            for (let y = top; y <= bottom; y++) {
                tileUrls.push(`https://tile.openstreetmap.org/${z}/${x}/${y}.png`);
            }
        }
    }

    try {
        // At zoom 19, it will be around 300-400 tiles (roughly 6MB - 8MB)
        showToast(`Downloading ${tileUrls.length} high-res tiles...`, "info", 4000);
        
        const cache = await caches.open("vit-map-tiles-v1");
        
        // Batch the downloads to prevent OpenStreetMap from blocking us for spam
        const BATCH_SIZE = 20; 
        let completed = 0;

        for (let i = 0; i < tileUrls.length; i += BATCH_SIZE) {
            const batch = tileUrls.slice(i, i + BATCH_SIZE);
            
            await Promise.all(batch.map(async (url) => {
                try {
                    // Only fetch if we don't already have it cached
                    const existing = await cache.match(url);
                    if (!existing) {
                        const response = await fetch(url);
                        if (response.ok) await cache.put(url, response);
                    }
                } catch (e) {
                    console.warn("Failed to fetch tile:", url);
                }
            }));
            
            completed += batch.length;
            const percent = Math.round((completed / tileUrls.length) * 100);
            downloadMapBtn.textContent = `⬇️ Downloading... ${percent}%`;
        }

        showToast("✅ High-res map saved for offline use!", "success");
        downloadMapBtn.textContent = "✅ Map Downloaded";
        downloadMapBtn.style.borderStyle = "solid";
        downloadMapBtn.style.color = "var(--green)";
        downloadMapBtn.style.borderColor = "var(--green)";
        
    } catch (err) {
        console.error("Tile download failed:", err);
        showToast("Failed to download map. Check connection.", "error");
        downloadMapBtn.disabled = false;
        downloadMapBtn.textContent = "🗺️ Retry Download";
    }
});

// ================== INIT ==================
fetchSamples();
fetchStats();

// Refresh stats every 30 s
setInterval(fetchStats, 30_000);
