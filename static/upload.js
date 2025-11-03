const contributeBtn = document.getElementById('contribute-btn');
const contributionStatus = document.getElementById('contribution-status');
const carrierSelect = document.getElementById('carrier');

// --- GEOFENCING BOUNDING BOX (must match app.py) ---
const VIT_MIN_LAT = 12.8300;
const VIT_MAX_LAT = 12.8500;
const VIT_MIN_LON = 80.1430;
const VIT_MAX_LON = 80.1630;
// --- END GEOFENCING ---

contributeBtn.addEventListener('click', contributeData);

function contributeData() {
    
    // --- THIS IS THE WIFI CHECK YOU WERE MISSING ---
    if (navigator.connection && navigator.connection.type === 'wifi') {
        alert("Error: Please disconnect from WiFi to submit mobile data.");
        contributionStatus.textContent = "Please disconnect from WiFi.";
        return; // This stops the function from continuing
    }
    // --- END WIFI CHECK ---

    if (!navigator.geolocation) {
        alert("Error: Location is not supported by your browser.");
        contributionStatus.textContent = "Location not supported.";
        return;
    }

    const carrier = carrierSelect.value;
    if (!carrier) {
        alert("Please select your carrier from the dropdown first.");
        contributionStatus.textContent = "Please select your carrier.";
        return;
    }

    contributionStatus.textContent = "Getting your location...";
    navigator.geolocation.getCurrentPosition(handleLocationSuccess, handleLocationError, { enableHighAccuracy: true });
}

function handleLocationError(error) {
    alert("Error getting location: " + error.message);
    contributionStatus.textContent = "Error: " + error.message;
    console.error(error);
}

async function handleLocationSuccess(position) {
    const lat = position.coords.latitude;
    const lon = position.coords.longitude;

    // --- CLIENT-SIDE GEOFENCING CHECK ---
    if (!(lat >= VIT_MIN_LAT && lat <= VIT_MAX_LAT && lon >= VIT_MIN_LON && lon <= VIT_MAX_LON)) {
        alert("Error: You must be on campus to contribute data.");
        contributionStatus.textContent = "Error: You must be on campus.";
        return;
    }
    // --- END CHECK ---

    contributionStatus.textContent = "Got location, submitting...";
    const carrier = carrierSelect.value;

    // Get network info from the browser's Connection API
    let networkType = "Unknown";
    let downloadSpeed = null;
    if (navigator.connection) {
        networkType = navigator.connection.effectiveType.toUpperCase(); // e.g., "4G"
        downloadSpeed = navigator.connection.downlink; // Estimated Mbps
    }

    const sample = {
        'device_id': 'web-contributor',
        'timestamp': Math.floor(Date.now() / 1000),
        'latitude': lat,
        'longitude': lon,
        'carrier': carrier,
        'dbm': null, // We CANNOT get this from a browser
        'network_type': networkType,
        'download_mbps': downloadSpeed,
        'upload_mbps': null // We can't easily get this
    };

    // Send the data to the same API endpoint
    try {
        const res = await fetch('/api/submit', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(sample),
        });
        
        const result = await res.json();
        
        if (!res.ok) {
            // Show the server's error message (e.g., "Rate limit exceeded")
            throw new Error(result.message || 'Server rejected the sample.');
        }
        
        contributionStatus.textContent = "Success! Data submitted. Thank you!";
        
        // Clear the message after a few seconds
        setTimeout(() => { contributionStatus.textContent = ""; }, 4000);

    } catch (error) {
        contributionStatus.textContent = "Submission failed: " + error.message;
        console.error("Submission error:", error);
    }
}