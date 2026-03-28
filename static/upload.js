// static/upload.js — updated with contributor_id and i18n
"use strict";

const VIT_POLYGON = [
    [12.8455, 80.1532], [12.8447, 80.1587], [12.8435, 80.1589],
    [12.8395, 80.1560], [12.8387, 80.1545], [12.8419, 80.1515],
    [12.8425, 80.1510], [12.8456, 80.1518]
];

const OFFLINE_QUEUE_KEY = "vit_signal_offline_queue_v2";
const CONTRIBUTOR_KEY   = "vit_contributor_id";

// ────────────────────────────────────────────
// CONTRIBUTOR ID — anonymous, browser-persistent UUID
// ────────────────────────────────────────────

function getOrCreateContributorId() {
    let id = localStorage.getItem(CONTRIBUTOR_KEY);
    if (!id) {
        // Generate a UUID v4-like random string
        id = "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, c => {
            const r = (Math.random() * 16) | 0;
            return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
        });
        localStorage.setItem(CONTRIBUTOR_KEY, id);
    }
    return id;
}

const CONTRIBUTOR_ID = getOrCreateContributorId();

// ────────────────────────────────────────────
// HELPERS
// ────────────────────────────────────────────

function isPointInPolygon(lat, lng, poly) {
    let inside = false;
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
        const [xi, yi] = poly[i];
        const [xj, yj] = poly[j];
        const intersect = ((yi > lng) !== (yj > lng)) &&
            (lat < (xj - xi) * (lng - yi) / (yj - yi) + xi);
        if (intersect) inside = !inside;
    }
    return inside;
}

async function performSpeedTest() {
    const t0 = performance.now();
    try {
        const res = await fetch(`/api/speed-test-payload?_=${t0}`);
        if (!res.ok) throw new Error("non-2xx");
        const blob = await res.blob();
        const dt = (performance.now() - t0) / 1000;
        return parseFloat(((blob.size * 8) / dt / 1_048_576).toFixed(2));
    } catch (e) {
        console.warn("Speed test failed:", e);
        return null;
    }
}

// ────────────────────────────────────────────
// OFFLINE QUEUE
// ────────────────────────────────────────────

function getQueue() {
    try { return JSON.parse(localStorage.getItem(OFFLINE_QUEUE_KEY) || "[]"); }
    catch { return []; }
}

function saveQueue(q) {
    try { localStorage.setItem(OFFLINE_QUEUE_KEY, JSON.stringify(q)); }
    catch { console.warn("localStorage unavailable"); }
}

function enqueue(sample) {
    const q = getQueue();
    q.push({ ...sample, _queued_at: Date.now() });
    saveQueue(q);
}

async function flushQueue() {
    if (!navigator.onLine) return 0;
    const queue = getQueue();
    if (!queue.length) return 0;

    const remaining = [];
    for (const sample of queue) {
        const { _queued_at, ...payload } = sample;
        try {
            const res = await fetch("/api/submit", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ...payload, contributor_id: CONTRIBUTOR_ID })
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
        } catch {
            remaining.push(sample);
        }
    }
    saveQueue(remaining);
    return queue.length - remaining.length;
}

// ────────────────────────────────────────────
// SIGNAL STRENGTH VALIDATION
// ────────────────────────────────────────────

function parseSignalStrength(raw) {
    if (raw === "" || raw == null) return null;
    const v = parseInt(raw, 10);
    if (isNaN(v) || v < -140 || v > -20) return null;
    return v;
}

// ────────────────────────────────────────────
// STATUS / UI HELPERS
// ────────────────────────────────────────────

function setContribStatus(msg, type = "info") {
    const el = document.getElementById("contribution-status");
    if (!el) return;
    el.textContent = msg;
    el.className = `status-msg ${type}`;
    // Accessibility: announce to screen readers
    el.setAttribute("role", msg ? "alert" : "");
}

function setCarrierStatus(msg) {
    const el = document.getElementById("carrier-status");
    if (el) {
        el.textContent = msg;
        el.setAttribute("role", msg ? "status" : "");
    }
}

// ────────────────────────────────────────────
// CONTRIBUTOR BADGE
// ────────────────────────────────────────────

function renderContributorBadge() {
    const badge = document.getElementById("contributor-badge");
    if (!badge) return;
    const shortId = `VIT-${CONTRIBUTOR_ID.slice(0, 8).toUpperCase()}`;
    badge.textContent = `Your ID: ${shortId}`;
    badge.title = "Your anonymous contributor ID. Check the leaderboard!";
}

// ────────────────────────────────────────────
// MAIN
// ────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {

    const contributeBtn      = document.getElementById("contribute-btn");
    const carrierSelect      = document.getElementById("carrier-select");
    const customCarrierInput = document.getElementById("custom-carrier");
    const detectBtn          = document.getElementById("detect-carrier-btn");
    const networkSelect      = document.getElementById("network-select");
    const signalInput        = document.getElementById("signal-input");
    const queueBadge         = document.getElementById("queue-badge");
    const langToggle         = document.getElementById("lang-toggle");

    renderContributorBadge();

    // ── Language toggle ──
    if (langToggle) {
        langToggle.addEventListener("click", () => {
            const next = currentLang() === "en" ? "ta" : "en";
            setLang(next);
            langToggle.textContent = next === "ta" ? "EN" : "தமிழ்";
        });
        langToggle.textContent = currentLang() === "ta" ? "EN" : "தமிழ்";
    }

    // ── Queue badge ──
    function refreshQueueBadge() {
        const q = getQueue();
        if (!queueBadge) return;
        queueBadge.textContent = q.length ? `${q.length} queued offline` : "";
        queueBadge.style.display = q.length ? "block" : "none";
        queueBadge.setAttribute("aria-hidden", q.length ? "false" : "true");
    }
    refreshQueueBadge();

    // ── Online event ──
    window.addEventListener("online", async () => {
        setContribStatus("Back online. Syncing…", "info");
        const synced = await flushQueue();
        refreshQueueBadge();
        if (synced) {
            setContribStatus(`✅ Synced ${synced} offline submission(s).`, "success");
            setTimeout(() => setContribStatus(""), 4000);
        } else {
            setContribStatus("", "info");
        }
    });

    // ── Carrier select toggle ──
    carrierSelect?.addEventListener("change", () => {
        if (customCarrierInput) {
            const show = carrierSelect.value === "Other";
            customCarrierInput.style.display = show ? "block" : "none";
            if (show) customCarrierInput.focus();
        }
    });

    // ── Auto-detect carrier ──
    detectBtn?.addEventListener("click", async () => {
        detectBtn.disabled = true;
        detectBtn.setAttribute("aria-busy", "true");
        setCarrierStatus("Detecting…");
        try {
            const res  = await fetch("/api/get-carrier");
            const data = await res.json();
            const c    = data.carrier;

            if (c && c !== "Unknown" && c !== "Unknown (Local IP)") {
                const opts = Array.from(carrierSelect.options).map(o => o.value);
                if (opts.includes(c)) {
                    carrierSelect.value = c;
                    if (customCarrierInput) customCarrierInput.style.display = "none";
                } else {
                    carrierSelect.value = "Other";
                    if (customCarrierInput) {
                        customCarrierInput.style.display = "block";
                        customCarrierInput.value = c;
                    }
                }
                setCarrierStatus(`✅ Detected: ${c}`);
            } else {
                setCarrierStatus("⚠️ Couldn't auto-detect. Please select manually.");
            }
        } catch {
            setCarrierStatus("❌ Detection error. Please select manually.");
        } finally {
            detectBtn.disabled = false;
            detectBtn.removeAttribute("aria-busy");
        }
    });

    // ── Signal strength live validation ──
    signalInput?.addEventListener("input", () => {
        const v = signalInput.value;
        if (v === "") { signalInput.setCustomValidity(""); return; }
        const parsed = parseSignalStrength(v);
        signalInput.setCustomValidity(
            parsed === null ? "Enter a value between -140 and -20 dBm" : ""
        );
        signalInput.reportValidity();
    });

    // ── Submit ──
    contributeBtn?.addEventListener("click", () => {
        if (navigator.connection?.type === "wifi") {
            alert("⚠️  Please disconnect from Wi-Fi to submit mobile network data.");
            return;
        }

        let carrier = carrierSelect?.value ?? "";
        if (!carrier) { alert("Please select your carrier."); return; }
        if (carrier === "Other") {
            carrier = customCarrierInput?.value.trim() ?? "";
            if (!carrier) { alert("Please enter your carrier name."); return; }
        }

        setContribStatus("Getting location…", "info");
        contributeBtn.disabled = true;
        contributeBtn.setAttribute("aria-busy", "true");

        navigator.geolocation.getCurrentPosition(
            pos => handleLocation(pos, carrier),
            err => {
                const msgs = {
                    1: "Location permission was denied.",
                    2: "Location is currently unavailable.",
                    3: "Location request timed out."
                };
                alert(msgs[err.code] ?? err.message);
                setContribStatus("");
                contributeBtn.disabled = false;
                contributeBtn.removeAttribute("aria-busy");
            },
            { enableHighAccuracy: true, timeout: 12000, maximumAge: 0 }
        );
    });

    async function handleLocation(position, carrier) {
        const { latitude: lat, longitude: lon } = position.coords;

        if (!isPointInPolygon(lat, lon, VIT_POLYGON)) {
            alert("🚫 You appear to be outside the VIT Chennai campus boundary.");
            setContribStatus("");
            contributeBtn.disabled = false;
            contributeBtn.removeAttribute("aria-busy");
            return;
        }

        let networkType = networkSelect?.value || "";
        if (!networkType && navigator.connection) {
            const et = navigator.connection.effectiveType;
            networkType = { "4g": "4G", "3g": "3G", "2g": "2G", "slow-2g": "2G" }[et] || "";
        }
        if (!networkType) networkType = "Unknown";

        const signalStrength = parseSignalStrength(signalInput?.value);

        let downloadSpeed = null;
        if (navigator.onLine) {
            setContribStatus("Running speed test… (~1–2 s)", "info");
            downloadSpeed = await performSpeedTest();
        }
        if (!downloadSpeed && navigator.connection?.downlink > 0) {
            downloadSpeed = navigator.connection.downlink;
        }

        const payload = {
            lat,
            lng: lon,
            carrier,
            network_type: networkType,
            signal_strength: signalStrength,
            download_speed:  downloadSpeed,
            contributor_id:  CONTRIBUTOR_ID,
        };

        if (!navigator.onLine) {
            enqueue(payload);
            refreshQueueBadge();
            setContribStatus("📴 Offline — saved locally, will sync later.", "warn");
            contributeBtn.disabled = false;
            contributeBtn.removeAttribute("aria-busy");
            return;
        }

        try {
            setContribStatus("Submitting…", "info");
            const res    = await fetch("/api/submit", {
                method:  "POST",
                headers: { "Content-Type": "application/json" },
                body:    JSON.stringify(payload)
            });
            const result = await res.json();

            if (!res.ok) {
                if (result.error === "OUT_OF_CAMPUS") {
                    alert("🚫 Server rejected the point as outside campus.");
                    setContribStatus("");
                } else {
                    throw new Error(result.message || `HTTP ${res.status}`);
                }
                return;
            }

            let msg = "✅ Submitted!";
            if (downloadSpeed) msg += ` Speed: ${downloadSpeed} Mbps.`;
            if (signalStrength) msg += ` Signal: ${signalStrength} dBm.`;
            setContribStatus(msg, "success");

        } catch (err) {
            console.error("Submit error:", err);
            enqueue(payload);
            refreshQueueBadge();
            setContribStatus("📴 Connection error — saved locally.", "warn");
        } finally {
            contributeBtn.disabled = false;
            contributeBtn.removeAttribute("aria-busy");
        }
    }

    flushQueue().then(refreshQueueBadge);
});