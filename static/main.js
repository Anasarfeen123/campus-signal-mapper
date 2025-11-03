// Set map to VIT Chennai coordinates and zoom in closer
const map = L.map('map').setView([12.8406, 80.1534], 17);
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
}).addTo(map);

// You can adjust radius and blur as needed
const heatLayer = L.heatLayer([], { radius: 15, blur: 10, maxZoom: 17 }).addTo(map);

// Get control elements
const carrierSelect = document.getElementById('carrier');
const networkSelect = document.getElementById('network');
const heatmapDataSelect = document.getElementById('heatmap-data');
const statusLight = document.getElementById('status-light');
const statusText = document.getElementById('status-text');

// Function to update status
function setStatus(state, text) {
    statusLight.className = state; // 'live', 'loading', 'disconnected'
    statusText.textContent = text;
}

async function fetchSamples() {
    const carrier = carrierSelect.value;
    const network = networkSelect.value;
    const heatmapType = heatmapDataSelect.value;
    const qs = new URLSearchParams();
    if (carrier) qs.set('carrier', carrier);
    if (network) qs.set('network_type', network);
    qs.set('limit', 200); // You can adjust this limit

    setStatus('loading', 'Loading...');
    try {
        const res = await fetch('/api/samples?' + qs.toString());
        if (!res.ok) {
            console.error('Failed to fetch samples:', res.statusText);
            setStatus('disconnected', 'Error');
            return;
        }
        const data = await res.json();
        
        const points = data.map(s => {
            let weight;
            if (heatmapType === 'dbm') {
                // *** FIX: Use signal_strength ***
                weight = dbmToWeight(s.signal_strength);
            } else { // 'download'
                // *** FIX: Use download_speed ***
                weight = speedToWeight(s.download_speed);
            }
            // *** FIX: Use lat and lng ***
            return [s.lat, s.lng, weight];
        });
        
        heatLayer.setLatLngs(points);
        setStatus('live', 'Live');
    } catch (error) {
        console.error('Error fetching samples:', error);
        setStatus('disconnected', 'Offline');
    }
}

// Add event listeners to controls
carrierSelect.addEventListener('change', fetchSamples);
networkSelect.addEventListener('change', fetchSamples);
heatmapDataSelect.addEventListener('change', fetchSamples);

function dbmToWeight(dbm) {
    if (dbm === null || dbm === undefined) return 0.2; // Show null values faintly
    // clamp and normalize (-120 -> 0, -50 -> 1)
    const clamped = Math.max(-120, Math.min(-50, dbm));
    return (clamped + 120) / 70;
}

function speedToWeight(mbps) {
    if (mbps === null || mbps === undefined) return 0.0;
    // clamp and normalize (0Mbps -> 0, 100+Mbps -> 1)
    const clamped = Math.max(0, Math.min(100, mbps));
    return clamped / 100;
}

// --- Live updates via socket.io ---
const socket = io();

socket.on('connect', () => {
    console.log('socket connected');
    setStatus('live', 'Live');
});

socket.on('disconnect', () => {
    console.log('socket disconnected');
    setStatus('disconnected', 'Offline');
});

function addSampleToMap(s) {
    const heatmapType = heatmapDataSelect.value;
    let weight;
    if (heatmapType === 'dbm') {
        // *** FIX: Use signal_strength ***
        weight = dbmToWeight(s.signal_strength);
    } else { // 'download'
        // *** FIX: Use download_speed ***
        weight = speedToWeight(s.download_speed);
    }
    // *** FIX: Use lat and lng ***
    heatLayer.addLatLng([s.lat, s.lng, weight]);
}

// *** FIX: Listen for 'new_data_point' not 'new_sample' ***
socket.on('new_data_point', (s) => {
    console.log('Got new data point', s);
    
    // Check if the new point matches the current filters
    const currentCarrier = carrierSelect.value;
    const currentNetwork = networkSelect.value;

    const carrierMatch = !currentCarrier || (s.carrier === currentCarrier);
    const networkMatch = !currentNetwork || (s.network_type === currentNetwork);

    if (carrierMatch && networkMatch) {
        addSampleToMap(s);
    }
});

// initial fetch
fetchSamples();