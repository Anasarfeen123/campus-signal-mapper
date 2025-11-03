// Set map to VIT Chennai coordinates and zoom in closer
const map = L.map('map').setView([12.8406, 80.1534], 17);
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
}).addTo(map);

// Reduced radius from 25 to 10 and blur from 15 to 5 for a "super small" look
const heatLayer = L.heatLayer([], { radius: 10, blur: 5, maxZoom: 17 }).addTo(map);

// Get control elements
const carrierSelect = document.getElementById('carrier');
const networkSelect = document.getElementById('network');
const heatmapDataSelect = document.getElementById('heatmap-data'); // New control
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
    const heatmapType = heatmapDataSelect.value; // Get current heatmap type
    const qs = new URLSearchParams();
    if (carrier) qs.set('carrier', carrier);
    if (network) qs.set('network_type', network);
    qs.set('limit', 2000);

    setStatus('loading', 'Loading...'); // Set loading state
    try {
        const res = await fetch('/api/samples?' + qs.toString());
        if (!res.ok) {
            console.error('Failed to fetch samples:', res.statusText);
            setStatus('disconnected', 'Error'); // Show error
            return;
        }
        const data = await res.json();
        
        // Dynamically create points based on selected data type
        const points = data.map(s => {
            let weight;
            if (heatmapType === 'dbm') {
                weight = dbmToWeight(s.dbm);
            } else { // 'download'
                weight = speedToWeight(s.download_mbps);
            }
            return [s.latitude, s.longitude, weight];
        });
        
        heatLayer.setLatLngs(points);
        setStatus('live', 'Live'); // Set back to live
    } catch (error) {
        console.error('Error fetching samples:', error);
        setStatus('disconnected', 'Offline');
    }
}

// Add event listeners to controls
carrierSelect.addEventListener('change', fetchSamples);
networkSelect.addEventListener('change', fetchSamples);
heatmapDataSelect.addEventListener('change', fetchSamples); // Add listener for new control

function dbmToWeight(dbm) {
    if (dbm === null || dbm === undefined) return 0.2;
    // clamp and normalize (-120 -> 0, -50 -> 1)
    const clamped = Math.max(-120, Math.min(-50, dbm));
    return (clamped + 120) / 70;
}

// New function to convert download speed to a weight
function speedToWeight(mbps) {
    if (mbps === null || mbps === undefined) return 0.0;
    // clamp and normalize (0Mbps -> 0, 100+Mbps -> 1)
    const clamped = Math.max(0, Math.min(100, mbps));
    return clamped / 100;
}


// live updates via socket.io
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
        weight = dbmToWeight(s.dbm);
    } else { // 'download'
        weight = speedToWeight(s.download_mbps);
    }
    heatLayer.addLatLng([s.latitude, s.longitude, weight]);
}

// Handle a single new sample
socket.on('new_sample', (s) => {
    console.log('Got new sample', s);
    addSampleToMap(s);
});

// Handle a batch of new samples
socket.on('new_samples', (samples) => {
    console.log(`Got ${samples.length} new samples`);
    samples.forEach(addSampleToMap); // Use the same helper
});

// initial fetch
fetchSamples();
