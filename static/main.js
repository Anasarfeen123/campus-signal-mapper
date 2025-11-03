const map = L.map('map').setView([12.9716, 80.2200], 16); // change to campus center
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
maxZoom: 19,
}).addTo(map);


const heatLayer = L.heatLayer([], {radius: 25, blur: 15, maxZoom: 17}).addTo(map);


async function fetchSamples(){
const carrier = document.getElementById('carrier').value;
const network = document.getElementById('network').value;
const qs = new URLSearchParams();
if(carrier) qs.set('carrier', carrier);
if(network) qs.set('network_type', network);
qs.set('limit', 2000);
const res = await fetch('/api/samples?' + qs.toString());
const data = await res.json();
// map dbm (-120..-50) to weight (0..1)
const points = data.map(s => [s.latitude, s.longitude, dbmToWeight(s.dbm)]);
heatLayer.setLatLngs(points);
}


document.getElementById('refresh').addEventListener('click', fetchSamples);


function dbmToWeight(dbm){
if(dbm === null || dbm === undefined) return 0.2;
// clamp and normalize
const clamped = Math.max(-120, Math.min(-50, dbm));
return (clamped + 120) / 70; // -120 -> 0, -50 -> 1
}


// live updates via socket.io
const socket = io();
socket.on('connect', ()=> console.log('socket connected'));
socket.on('new_sample', (s)=>{
const w = dbmToWeight(s.dbm);
heatLayer.addLatLng([s.latitude, s.longitude, w]);
});


// initial fetch
fetchSamples();