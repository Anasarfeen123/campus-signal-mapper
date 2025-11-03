const contributeBtn = document.getElementById('contribute-btn');
const contributionStatus = document.getElementById('contribution-status');
const carrierSelect = document.getElementById('carrier');

contributeBtn.addEventListener('click', contributeData);

function contributeData() {
    if (!navigator.geolocation) {
        contributionStatus.textContent = "Location not supported.";
        return;
    }

    const carrier = carrierSelect.value;
    if (!carrier) {
        contributionStatus.textContent = "Please select your carrier first!";
        return;
    }

    contributionStatus.textContent = "Getting your location...";
    navigator.geolocation.getCurrentPosition(handleLocationSuccess, handleLocationError);
}

function handleLocationError(error) {
    contributionStatus.textContent = "Error: " + error.message;
    console.error(error);
}

async function handleLocationSuccess(position) {
    contributionStatus.textContent = "Got location, submitting...";
    
    const lat = position.coords.latitude;
    const lon = position.coords.longitude;
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
        
        if (!res.ok) {
            throw new Error('Server rejected the sample.');
        }
        
        contributionStatus.textContent = "Success! Data submitted. Thank you!";
        
        // Clear the message after a few seconds
        setTimeout(() => { contributionStatus.textContent = ""; }, 4000);

    } catch (error) {
        contributionStatus.textContent = "Submission failed.";
        console.error("Submission error:", error);
    }
}