const contributeBtn = document.getElementById('contribute-btn');
const contributionStatus = document.getElementById('contribution-status');
const carrierSelect = document.getElementById('carrier-select');
const carrierStatus = document.getElementById('carrier-status'); // New element

// GEOFENCING
const VIT_MIN_LAT = 12.8300;
const VIT_MAX_LAT = 12.8500;
const VIT_MIN_LON = 80.1430;
const VIT_MAX_LON = 80.1630;

// --- NEW: Run carrier detection on page load ---
window.addEventListener('load', detectCarrier);

async function detectCarrier() {
    carrierStatus.textContent = "Detecting your carrier...";
    try {
        const res = await fetch('/api/get-carrier');
        if (!res.ok) {
            throw new Error('Lookup failed');
        }
        const data = await res.json();
        const detectedCarrier = data.carrier;

        // Check if the detected carrier is in our dropdown options
        let found = false;
        for (let option of carrierSelect.options) {
            // Check for partial match (e.g., "Airtel" in "Bharti Airtel")
            if (detectedCarrier.includes(option.value) && option.value !== "") {
                option.selected = true;
                found = true;
                break;
            }
        }

        if (found) {
            carrierStatus.textContent = "Carrier detected: " + detectedCarrier;
            contributeBtn.disabled = false; // Enable submit button
            carrierSelect.disabled = true; // Keep it locked
        } else {
            // Carrier not in our list, let user select
            carrierStatus.textContent = "Could not auto-detect carrier. Please select one.";
            carrierSelect.disabled = false;
            carrierSelect.options[0].textContent = "-- Please select --";
            contributeBtn.disabled = false; // Enable submit button
        }

    } catch (error) {
        console.error("Carrier detection error:", error);
        carrierStatus.textContent = "Auto-detect failed. Please select your carrier.";
        carrierSelect.disabled = false; // Let user select manually
        carrierSelect.options[0].textContent = "-- Please select --";
        contributeBtn.disabled = false; // Enable submit button
    }
}
// --- END NEW FUNCTION ---


contributeBtn.addEventListener('click', contributeData);

function contributeData() {
    
    // --- WIFI CHECK ---
    if (navigator.connection && navigator.connection.type === 'wifi') {
        alert("Error: Please disconnect from WiFi to submit mobile data.");
        contributionStatus.textContent = "Please disconnect from WiFi.";
        return; 
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

    // --- GEOFENCING CHECK ---
    if (!(lat >= VIT_MIN_LAT && lat <= VIT_MAX_LAT && lon >= VIT_MIN_LON && lon <= VIT_MAX_LON)) {
        alert("Error: You must be on campus to contribute data.");
        contributionStatus.textContent = "Error: You must be on campus.";
        return;
    }
    // --- END CHECK ---

    contributionStatus.textContent = "Got location, submitting...";
    const carrier = carrierSelect.value;

    let networkType = "Unknown";
    let downloadSpeed = null;
    if (navigator.connection) {
        networkType = navigator.connection.effectiveType.toUpperCase();
        downloadSpeed = navigator.connection.downlink;
    }

    const sample = {
        'device_id': 'web-contributor',
        'timestamp': Math.floor(Date.now() / 1000),
        'latitude': lat,
        'longitude': lon,
        'carrier': carrier,
        'dbm': null,
        'network_type': networkType,
        'download_mbps': downloadSpeed,
        'upload_mbps': null
    };

    // Send the data
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
            throw new Error(result.message || 'Server rejected the sample.');
        }
        
        contributionStatus.textContent = "Success! Data submitted. Thank you!";
        
        setTimeout(() => { contributionStatus.textContent = ""; }, 4000);

    } catch (error) {
        contributionStatus.textContent = "Submission failed: " + error.message;
        console.error("Submission error:", error);
    }
}