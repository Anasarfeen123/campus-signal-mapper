document.addEventListener('DOMContentLoaded', () => {
    const contributeBtn = document.getElementById('contribute-btn');
    const contributionStatus = document.getElementById('contribution-status');
    const carrierSelect = document.getElementById('carrier-select');
    const carrierStatus = document.getElementById('carrier-status');
    const detectBtn = document.getElementById('detect-carrier-btn');

    // Enable the contribute button by default, let validation handle checks
    contributeBtn.disabled = false;

    // GEOFENCING (Using the stricter bounds from your app.py)
    const VIT_MIN_LAT = 12.839;
    const VIT_MAX_LAT = 12.844;
    const VIT_MIN_LON = 80.151;
    const VIT_MAX_LON = 80.157;
    
    // --- Logic for the "Detect My Carrier" button ---
    if (detectBtn) {
        detectBtn.addEventListener('click', () => {
            detectBtn.textContent = 'Detecting...';
            detectBtn.disabled = true;
            carrierStatus.textContent = "Detecting your carrier...";

            const controller = new AbortController();
            const signal = controller.signal;
            const timeoutId = setTimeout(() => {
                controller.abort();
                carrierStatus.textContent = 'Detection timed out. Please select manually.';
                detectBtn.textContent = 'Detect My Carrier';
                detectBtn.disabled = false;
            }, 5000); // 5-second timeout

            fetch('/api/get-carrier', { signal })
                .then(response => {
                    clearTimeout(timeoutId);
                    if (!response.ok) throw new Error('Detection API failed');
                    return response.json();
                })
                .then(data => {
                    if (data.carrier && data.carrier !== "Unknown (Local IP)") {
                        const carrierExists = [...carrierSelect.options].some(opt => opt.value === data.carrier);
                        if (carrierExists) {
                            carrierSelect.value = data.carrier;
                            carrierStatus.textContent = `Detected ${data.carrier}!`;
                        } else {
                            carrierSelect.value = 'Other';
                            carrierStatus.textContent = `Detected ${data.carrier} (Set to Other).`;
                        }
                    } else {
                        carrierStatus.textContent = 'Could not auto-detect. Please select manually.';
                    }
                    detectBtn.textContent = 'Detect My Carrier';
                    detectBtn.disabled = false;
                })
                .catch(err => {
                    clearTimeout(timeoutId);
                    if (err.name !== 'AbortError') {
                        console.error('Carrier detection error:', err);
                        carrierStatus.textContent = 'Detection failed. Please select manually.';
                    }
                    detectBtn.textContent = 'Detect My Carrier';
                    detectBtn.disabled = false;
                });
        });
    }

    // --- Main submission logic ---
    contributeBtn.addEventListener('click', () => {
        // --- WIFI CHECK ---
        if (navigator.connection && navigator.connection.type === 'wifi') {
            alert("Error: Please disconnect from WiFi to submit mobile data.");
            contributionStatus.textContent = "Please disconnect from WiFi.";
            return; 
        }

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
        contributeBtn.disabled = true;
        navigator.geolocation.getCurrentPosition(handleLocationSuccess, handleLocationError, { enableHighAccuracy: true });
    });

    function handleLocationError(error) {
        alert("Error getting location: " + error.message);
        contributionStatus.textContent = "Error: " + error.message;
        contributeBtn.disabled = false;
        console.error(error);
    }

    async function handleLocationSuccess(position) {
        const lat = position.coords.latitude;
        const lon = position.coords.longitude;

        if (!(lat >= VIT_MIN_LAT && lat <= VIT_MAX_LAT && lon >= VIT_MIN_LON && lon <= VIT_MAX_LON)) {
            alert("Error: You must be on campus to contribute data.");
            contributionStatus.textContent = "Error: You must be on campus.";
            contributeBtn.disabled = false;
            return;
        }

        contributionStatus.textContent = "Got location, submitting...";
        const carrier = carrierSelect.value;

        let networkType = "Unknown";
        let downloadSpeed = null; // Default to null
        if (navigator.connection) {
            networkType = navigator.connection.effectiveType.toUpperCase();
            // Only set downloadSpeed if it's a number, otherwise send null
            if (navigator.connection.downlink && !isNaN(navigator.connection.downlink)) {
                downloadSpeed = navigator.connection.downlink;
            }
        }

        // This sample object now matches app.py and upload.js
        const sample = {
            'lat': lat,
            'lng': lon,
            'carrier': carrier,
            'network_type': networkType,
            'signal_strength': null, // We send null for signal (can't get from web)
            'download_speed': downloadSpeed 
        };

        try {
            const res = await fetch('/api/submit', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(sample),
            });
            
            const result = await res.json();
            
            if (!res.ok) {
                // Use the error message from the server
                throw new Error(result.error || 'Server rejected the sample.');
            }
            
            contributionStatus.textContent = "Success! Data submitted. Thank you!";
            setTimeout(() => { contributionStatus.textContent = ""; }, 4000);

        } catch (error) {
            contributionStatus.textContent = "Submission failed: " + error.message;
            console.error("Submission error:", error);
        } finally {
            contributeBtn.disabled = false;
        }
    }
});