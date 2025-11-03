const map = L.map('map').setView([12.9716, 80.2200], 16); // change to campus center
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
}).addTo(map);

const heatLayer = L.heatLayer([], { radius: 25, blur: 15, maxZoom: 17 }).addTo(map);

// Get control elements
const carrierSelect = document.getElementById('carrier');
const networkSelect = document.getElementById('network');
const refreshButton = document.getElementById('refresh');

async function fetchSamples() {
    const carrier = carrierSelect.value;
    const network = networkSelect.value;
    const qs = new URLSearchParams();
    if (carrier) qs.set('carrier', carrier);
    if (network) qs.set('network_type', network);
    qs.set('limit', 2000);

    try {
        const res = await fetch('/api/samples?' + qs.toString());
        if (!res.ok) {
            console.error('Failed to fetch samples:', res.statusText);
            return;
        }
        const data = await res.json();
        // map dbm (-120..-50) to weight (0..1)
        const points = data.map(s => [s.latitude, s.longitude, dbmToWeight(s.dbm)]);
        heatLayer.setLatLngs(points);
    } catch (error) {
        console.error('Error fetching samples:', error);
    }
}

// Add event listeners to controls
refreshButton.addEventListener('click', fetchSamples);
carrierSelect.addEventListener('change', fetchSamples);
networkSelect.addEventListener('change', fetchSamples);

function dbmToWeight(dbm) {
    if (dbm === null || dbm === undefined) return 0.2;
    // clamp and normalize
    const clamped = Math.max(-120, Math.min(-50, dbm));
    return (clamped + 120) / 70; // -120 -> 0, -50 -> 1
}

// live updates via socket.io
const socket = io();
socket.on('connect', () => console.log('socket connected'));

// Handle a single new sample
socket.on('new_sample', (s) => {
    console.log('Got new sample', s);
    const w = dbmToWeight(s.dbm);
    heatLayer.addLatLng([s.latitude, s.longitude, w]);
});

// Handle a batch of new samples
socket.on('new_samples', (samples) => {
    console.log(`Got ${samples.length} new samples`);
    const points = samples.map(s => {
        const w = dbmToWeight(s.dbm);
        return [s.latitude, s.longitude, w];
    });
    heatLayer.addLatLng(points);
});

// initial fetch
fetchSamples();