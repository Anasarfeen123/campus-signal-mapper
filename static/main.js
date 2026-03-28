// static/main.js — updated with i18n, signal history chart, accessibility
"use strict";

// ================== CONFIG ==================
const API_BASE = window.location.origin;
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

// Accessibility: set map title
map.getContainer().setAttribute("role", "application");
map.getContainer().setAttribute("aria-label", "VIT Chennai campus signal strength heatmap");

L.control.zoom({ position: "bottomright" }).addTo(map);

VIT_POLYGON.addTo(map);

const TILE_PROVIDERS = [
    {
        url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
    },
    {
        url: "https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png",
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
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
        className: "map-tiles"
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
const langToggle      = document.getElementById("lang-toggle");
const chartToggleBtn  = document.getElementById("chart-toggle-btn");
const chartSection    = document.getElementById("chart-section");
const chartCanvas     = document.getElementById("signal-chart");

// ================== HELPERS ==================
function setStatus(state, text) {
    statusLight.className = "";
    statusLight.classList.add(state);
    statusText.textContent = text;
    // Accessibility: live region
    const liveRegion = document.getElementById("status-live");
    if (liveRegion) liveRegion.textContent = text;
}

function showToast(msg, type = "info", duration = 3200) {
    toast.textContent = msg;
    toast.className = `toast show ${type}`;
    toast.setAttribute("role", "status");
    toast.setAttribute("aria-live", "polite");
    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => {
        toast.classList.remove("show");
        toast.removeAttribute("role");
    }, duration);
}

function formatDbm(v) {
    if (v == null) return "—";
    return `${Math.round(v)} dBm`;
}

function formatMbps(v) {
    if (v == null) return "—";
    return `${v.toFixed(1)} Mbps`;
}

// ================== LANGUAGE TOGGLE ==================
if (langToggle) {
    langToggle.addEventListener("click", () => {
        const next = currentLang() === "en" ? "ta" : "en";
        setLang(next);
        langToggle.textContent = next === "ta" ? "EN" : "தமிழ்";
        langToggle.setAttribute("aria-label", next === "ta" ? "Switch to English" : "தமிழுக்கு மாறு");
    });
    // Set initial label
    const initLang = currentLang();
    langToggle.textContent = initLang === "ta" ? "EN" : "தமிழ்";
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
    } catch { /* non-critical */ }
}

// ================== DATA ==================
let _allPoints = [];

async function fetchSamples() {
    const qs = new URLSearchParams();
    if (carrierSelect.value)  qs.set("carrier",      carrierSelect.value);
    if (networkSelect.value)  qs.set("network_type", networkSelect.value);
    qs.set("limit", isMobile ? "1000" : "5000");

    try {
        setStatus("loading", t("status.loading") || "Loading…");
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

carrierSelect?.addEventListener("change", () => { fetchSamples(); fetchChart(); });
networkSelect?.addEventListener("change", () => { fetchSamples(); fetchChart(); });
heatmapDataSel?.addEventListener("change", () => renderHeatmap(_allPoints));

// ================== SIGNAL HISTORY CHART ==================
let _chartInstance = null;

async function fetchChart() {
    if (!chartCanvas) return;

    const qs = new URLSearchParams();
    if (carrierSelect?.value) qs.set("carrier", carrierSelect.value);
    if (networkSelect?.value) qs.set("network_type", networkSelect.value);

    try {
        const res = await fetch(`${API_BASE}/api/signal-history?${qs}`);
        if (!res.ok) return;
        const data = await res.json();
        renderChart(data);
    } catch (err) {
        console.error("fetchChart:", err);
    }
}

function renderChart(data) {
    if (!chartCanvas || !window.Chart) return;

    const labels  = data.map(d => {
        const dt = new Date(d.bucket);
        return dt.toLocaleTimeString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
    });
    const signals = data.map(d => d.avg_signal);
    const speeds  = data.map(d => d.avg_speed);

    const chartData = {
        labels,
        datasets: [
            {
                label: t("chart.signal"),
                data: signals,
                borderColor: "#00f0ff",
                backgroundColor: "rgba(0,240,255,0.08)",
                borderWidth: 1.5,
                pointRadius: 0,
                pointHoverRadius: 3,
                tension: 0.4,
                yAxisID: "ySignal",
                fill: true,
            },
            {
                label: t("chart.speed"),
                data: speeds,
                borderColor: "#00ff88",
                backgroundColor: "rgba(0,255,136,0.05)",
                borderWidth: 1.5,
                pointRadius: 0,
                pointHoverRadius: 3,
                tension: 0.4,
                yAxisID: "ySpeed",
                fill: true,
            }
        ]
    };

    const chartOpts = {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
            legend: {
                labels: {
                    color: "rgba(216,228,240,0.6)",
                    font: { family: "'JetBrains Mono', monospace", size: 9 },
                    boxWidth: 10,
                }
            },
            tooltip: {
                backgroundColor: "rgba(2,8,25,0.95)",
                borderColor: "rgba(0,240,255,0.2)",
                borderWidth: 1,
                titleColor: "#00f0ff",
                bodyColor: "#d8e4f0",
                titleFont: { family: "'JetBrains Mono', monospace", size: 9 },
                bodyFont:  { family: "'JetBrains Mono', monospace", size: 9 },
            }
        },
        scales: {
            x: {
                ticks: {
                    color: "rgba(216,228,240,0.35)",
                    font: { family: "'JetBrains Mono', monospace", size: 8 },
                    maxTicksLimit: 8,
                    maxRotation: 0,
                },
                grid: { color: "rgba(255,255,255,0.04)" }
            },
            ySignal: {
                position: "left",
                title: { display: false },
                ticks: {
                    color: "rgba(0,240,255,0.5)",
                    font: { family: "'JetBrains Mono', monospace", size: 8 },
                    callback: v => v ? `${v} dB` : null,
                },
                grid: { color: "rgba(255,255,255,0.04)" }
            },
            ySpeed: {
                position: "right",
                ticks: {
                    color: "rgba(0,255,136,0.5)",
                    font: { family: "'JetBrains Mono', monospace", size: 8 },
                    callback: v => v ? `${v}M` : null,
                },
                grid: { display: false }
            },
        }
    };

    if (_chartInstance) {
        _chartInstance.data = chartData;
        _chartInstance.update("none");
    } else {
        _chartInstance = new Chart(chartCanvas, {
            type: "line",
            data: chartData,
            options: chartOpts
        });
    }
}

// Chart toggle
if (chartToggleBtn && chartSection) {
    chartToggleBtn.addEventListener("click", () => {
        const isOpen = chartSection.style.display !== "none";
        chartSection.style.display = isOpen ? "none" : "block";
        chartSection.setAttribute("aria-hidden", isOpen ? "true" : "false");
        chartToggleBtn.setAttribute("aria-expanded", isOpen ? "false" : "true");
        chartToggleBtn.textContent = isOpen ? "▶" : "▼";
        if (!isOpen && !_chartInstance) fetchChart();
    });
}

// Re-apply chart labels when language changes
document.addEventListener("langchange", () => {
    if (_chartInstance) {
        _chartInstance.data.datasets[0].label = t("chart.signal");
        _chartInstance.data.datasets[1].label = t("chart.speed");
        _chartInstance.update();
    }
});

// ================== SOCKET.IO ==================
const socket = io(API_BASE, {
    transports: ["websocket"],
    reconnectionDelay: 1000,
    reconnectionDelayMax: 10000
});

socket.on("connect",      () => setStatus("live", "Live"));
socket.on("disconnect",   () => setStatus("disconnected", "Disconnected"));
socket.on("connect_error",() => setStatus("disconnected", "Reconnecting…"));

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

    const currentMatch = statusText.textContent.match(/(\d+) pts/);
    const count = currentMatch ? parseInt(currentMatch[1]) + 1 : "?";
    setStatus("live", `Live · ${count} pts`);
});

// ================== LOCATION ==================
let userMarker     = null;
let accuracyCircle = null;

locateBtn?.addEventListener("click", () => {
    if (!navigator.geolocation) {
        showToast("Geolocation not supported by this browser", "error");
        return;
    }
    locateBtn.disabled = true;
    locateBtn.setAttribute("aria-busy", "true");
    locateBtn.textContent = "⌛ Locating…";

    navigator.geolocation.getCurrentPosition(
        pos => {
            const { latitude, longitude, accuracy } = pos.coords;
            const latlng = L.latLng(latitude, longitude);

            if (userMarker)    map.removeLayer(userMarker);
            if (accuracyCircle) map.removeLayer(accuracyCircle);

            userMarker = L.circleMarker(latlng, {
                radius: 8, color: "#fff", weight: 2,
                fillColor: "#3b82f6", fillOpacity: 1
            })
            .addTo(map)
            .bindPopup(`<b>Your Location</b><br>Accuracy: ±${Math.round(accuracy)} m`)
            .openPopup();

            accuracyCircle = L.circle(latlng, {
                radius: accuracy, color: "#3b82f6", fillOpacity: 0.08, weight: 1
            }).addTo(map);

            map.setView(latlng, 18, { animate: true, duration: 0.8 });
            showToast(`Location found (±${Math.round(accuracy)} m)`, "success");

            locateBtn.disabled = false;
            locateBtn.removeAttribute("aria-busy");
            locateBtn.textContent = t("btn.locate") || "📍 My Location";
        },
        err => {
            const msgs = { 1: "Location permission denied", 2: "Location unavailable", 3: "Location request timed out" };
            showToast(msgs[err.code] ?? err.message, "error");
            locateBtn.disabled = false;
            locateBtn.removeAttribute("aria-busy");
            locateBtn.textContent = t("btn.locate") || "📍 My Location";
        },
        { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 }
    );
});

// ================== OFFLINE UI ==================
function updateOfflineUI() {
    if (offlineBar) offlineBar.style.display = navigator.onLine ? "none" : "block";
    offlineBar?.setAttribute("aria-hidden", navigator.onLine ? "true" : "false");
}
window.addEventListener("online",  updateOfflineUI);
window.addEventListener("offline", updateOfflineUI);
updateOfflineUI();

// ================== MOBILE PANEL ==================
(function () {
    const panel      = document.getElementById("panel");
    const panelInner = document.querySelector(".panel-inner");
    const panelHead  = document.querySelector(".panel-head");
    const toggleBtn  = document.getElementById("menu-toggle");

    if (!panel || !panelHead || !panelInner) return;

    let isCollapsed = window.innerWidth < 600;
    let startY = 0, currentY = 0, isDragging = false;

    function getMaxTranslate() { return (window.innerHeight * 0.8) - 64; }

    function applyState() {
        panel.classList.toggle("collapsed", isCollapsed);
        if (toggleBtn) {
            toggleBtn.textContent = isCollapsed ? "▴" : "▾";
            toggleBtn.setAttribute("aria-expanded", isCollapsed ? "false" : "true");
            toggleBtn.setAttribute("aria-label", isCollapsed ? "Expand panel" : "Collapse panel");
        }
        panelInner.style.transform = "";
        panelInner.style.transition = "";
    }

    panelHead.addEventListener("click", (e) => {
        if (isDragging) return;
        isCollapsed = !isCollapsed;
        applyState();
    });

    panelHead.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            isCollapsed = !isCollapsed;
            applyState();
        }
    });

    panelHead.setAttribute("role", "button");
    panelHead.setAttribute("tabindex", "0");

    panelHead.addEventListener("touchstart", (e) => {
        if (window.innerWidth >= 600) return;
        startY = e.touches[0].clientY;
        currentY = startY;
        isDragging = false;
        panelInner.style.transition = "none";
    }, { passive: true });

    panelHead.addEventListener("touchmove", (e) => {
        if (window.innerWidth >= 600) return;
        currentY = e.touches[0].clientY;
        const deltaY = currentY - startY;
        if (Math.abs(deltaY) > 5) isDragging = true;
        if (!isDragging) return;
        const maxTranslate = getMaxTranslate();
        let newTranslate = isCollapsed ? maxTranslate + deltaY : deltaY;
        newTranslate = Math.max(0, Math.min(maxTranslate, newTranslate));
        panelInner.style.transform = `translateY(${newTranslate}px)`;
    }, { passive: true });

    panelHead.addEventListener("touchend", () => {
        if (window.innerWidth >= 600 || !isDragging) { applyState(); return; }
        const deltaY = currentY - startY;
        const threshold = 60;
        if (isCollapsed && deltaY < -threshold)  isCollapsed = false;
        else if (!isCollapsed && deltaY > threshold) isCollapsed = true;
        setTimeout(() => { isDragging = false; }, 50);
        applyState();
    });

    map.on("click", () => {
        if (window.innerWidth < 600 && !isCollapsed) { isCollapsed = true; applyState(); }
    });

    if (isCollapsed) applyState();
})();

// ================== OFFLINE MAP DOWNLOADER ==================
const downloadMapBtn = document.getElementById("download-map-btn");

function lon2tile(lon, zoom) { return Math.floor((lon + 180) / 360 * Math.pow(2, zoom)); }
function lat2tile(lat, zoom) { return Math.floor((1 - Math.log(Math.tan(lat * Math.PI / 180) + 1 / Math.cos(lat * Math.PI / 180)) / Math.PI) / 2 * Math.pow(2, zoom)); }

downloadMapBtn?.addEventListener("click", async () => {
    if (!('caches' in window)) { showToast("Offline caching not supported.", "error"); return; }

    downloadMapBtn.disabled = true;
    downloadMapBtn.setAttribute("aria-busy", "true");
    downloadMapBtn.textContent = "⌛ Calculating tiles...";

    const bounds = VIT_POLYGON.getBounds();
    const { n, s, e, w } = { n: bounds.getNorth(), s: bounds.getSouth(), e: bounds.getEast(), w: bounds.getWest() };
    const tileUrls = [];

    for (let z = 15; z <= 19; z++) {
        const top = lat2tile(n, z), bottom = lat2tile(s, z);
        const left = lon2tile(w, z), right = lon2tile(e, z);
        for (let x = left; x <= right; x++)
            for (let y = top; y <= bottom; y++)
                tileUrls.push(`https://tile.openstreetmap.org/${z}/${x}/${y}.png`);
    }

    try {
        showToast(`Downloading ${tileUrls.length} tiles...`, "info", 4000);
        const cache = await caches.open("vit-map-tiles-v1");
        const BATCH = 20;
        let completed = 0;

        for (let i = 0; i < tileUrls.length; i += BATCH) {
            await Promise.all(tileUrls.slice(i, i + BATCH).map(async url => {
                try {
                    if (!(await cache.match(url))) {
                        const r = await fetch(url);
                        if (r.ok) await cache.put(url, r);
                    }
                } catch { /* tile fetch failed */ }
            }));
            completed += BATCH;
            downloadMapBtn.textContent = `⬇️ Downloading... ${Math.min(100, Math.round(completed / tileUrls.length * 100))}%`;
        }

        showToast("✅ Map saved for offline use!", "success");
        downloadMapBtn.textContent = "✅ Map Downloaded";
        downloadMapBtn.style.color = "var(--green)";
        downloadMapBtn.style.borderColor = "var(--green)";
    } catch (err) {
        showToast("Failed to download map.", "error");
        downloadMapBtn.disabled = false;
        downloadMapBtn.textContent = "🗺️ Retry Download";
    } finally {
        downloadMapBtn.removeAttribute("aria-busy");
    }
});

// ================== INIT ==================
fetchSamples();
fetchStats();
setInterval(fetchStats, 30_000);
