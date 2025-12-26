// static/upload.js

document.addEventListener('DOMContentLoaded', () => {
    const contributeBtn = document.getElementById('contribute-btn');
    const contributionStatus = document.getElementById('contribution-status');
    const carrierSelect = document.getElementById('carrier-select');
    const customCarrierInput = document.getElementById('custom-carrier'); // NEW
    const carrierStatus = document.getElementById('carrier-status');
    const detectBtn = document.getElementById('detect-carrier-btn');

    // Enable button
    contributeBtn.disabled = false;

    // GEOFENCING CONSTANTS
    const VIT_MIN_LAT = 12.839;
    const VIT_MAX_LAT = 12.844;
    const VIT_MIN_LON = 80.151;
    const VIT_MAX_LON = 80.157;

    // --- NEW: Toggle Custom Carrier Input ---
    carrierSelect.addEventListener('change', () => {
        if (carrierSelect.value === 'Other') {
            customCarrierInput.style.display = 'block';
            customCarrierInput.focus();
        } else {
            customCarrierInput.style.display = 'none';
        }
    });

    // --- Carrier Detection Logic ---
    if (detectBtn) {
        detectBtn.addEventListener('click', () => {
            detectBtn.textContent = 'Detecting...';
            detectBtn.disabled = true;
            carrierStatus.textContent = "Detecting your carrier...";
            
            // Hide custom input initially during detection
            customCarrierInput.style.display = 'none';

            const controller = new AbortController();
            const signal = controller.signal;
            const timeoutId = setTimeout(() => {
                controller.abort();
                carrierStatus.textContent = 'Detection timed out.';
                detectBtn.textContent = 'Detect My Carrier';
                detectBtn.disabled = false;
            }, 5000);

            fetch('/api/get-carrier', { signal })
                .then(res => {
                    clearTimeout(timeoutId);
                    if (!res.ok) throw new Error('API failed');
                    return res.json();
                })
                .then(data => {
                    if (data.carrier && data.carrier !== "Unknown (Local IP)") {
                        const carrierExists = [...carrierSelect.options].some(opt => opt.value === data.carrier);
                        if (carrierExists) {
                            carrierSelect.value = data.carrier;
                            carrierStatus.textContent = `Detected ${data.carrier}!`;
                        } else {
                            // If detected carrier isn't in our list, select 'Other' and fill the text box
                            carrierSelect.value = 'Other';
                            customCarrierInput.style.display = 'block';
                            customCarrierInput.value = data.carrier; // Auto-fill the detected name
                            carrierStatus.textContent = `Detected ${data.carrier} (Set to custom).`;
                        }
                    } else {
                        carrierStatus.textContent = 'Could not auto-detect.';
                    }
                })
                .catch(err => {
                    clearTimeout(timeoutId);
                    if (err.name !== 'AbortError') console.error(err);
                    carrierStatus.textContent = 'Detection failed.';
                })
                .finally(() => {
                    detectBtn.textContent = 'Detect My Carrier';
                    detectBtn.disabled = false;
                });
        });
    }

    // --- Submission Logic ---
    contributeBtn.addEventListener('click', () => {
        // 1. WiFi Check
        if (navigator.connection && navigator.connection.type === 'wifi') {
            alert("Please disconnect from WiFi to submit mobile data.");
            return; 
        }

        // 2. Carrier Validation
        let finalCarrier = carrierSelect.value;
        if (!finalCarrier) {
            alert("Please select your carrier.");
            return;
        }
        if (finalCarrier === 'Other') {
            finalCarrier = customCarrierInput.value.trim();
            if (!finalCarrier) {
                alert("Please enter your custom carrier name.");
                customCarrierInput.focus();
                return;
            }
        }

        // 3. Location Check
        if (!navigator.geolocation) {
            alert("Location not supported.");
            return;
        }

        contributionStatus.textContent = "Getting location...";
        contributeBtn.disabled = true;

        navigator.geolocation.getCurrentPosition(
            (position) => handleLocationSuccess(position, finalCarrier), // Pass carrier here
            (error) => {
                alert("Error getting location: " + error.message);
                contributionStatus.textContent = "Location error.";
                contributeBtn.disabled = false;
            }, 
            { enableHighAccuracy: true }
        );
    });

    async function handleLocationSuccess(position, carrierName) {
        const lat = position.coords.latitude;
        const lon = position.coords.longitude;

        if (!(lat >= VIT_MIN_LAT && lat <= VIT_MAX_LAT && lon >= VIT_MIN_LON && lon <= VIT_MAX_LON)) {
            alert("You must be on campus (VIT Chennai) to contribute.");
            contributionStatus.textContent = "Error: Outside campus bounds.";
            contributeBtn.disabled = false;
            return;
        }

        contributionStatus.textContent = "Submitting data...";

        let networkType = "Unknown";
        let downloadSpeed = null;
        
        if (navigator.connection) {
            networkType = navigator.connection.effectiveType ? navigator.connection.effectiveType.toUpperCase() : "Unknown";
            if (navigator.connection.downlink && !isNaN(navigator.connection.downlink)) {
                downloadSpeed = navigator.connection.downlink;
            }
        }

        const sample = {
            'lat': lat,
            'lng': lon,
            'carrier': carrierName, // Use the resolved carrier name
            'network_type': networkType,
            'signal_strength': null,
            'download_speed': downloadSpeed 
        };

        try {
            const res = await fetch('/api/submit', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(sample),
            });
            
            const result = await res.json();
            
            if (!res.ok) throw new Error(result.error || 'Server error');
            
            contributionStatus.textContent = "Success! Data submitted.";
            // Clear custom input after success
            if (carrierSelect.value === 'Other') customCarrierInput.value = '';
            
            setTimeout(() => { contributionStatus.textContent = ""; }, 3000);

        } catch (error) {
            contributionStatus.textContent = "Failed: " + error.message;
        } finally {
            contributeBtn.disabled = false;
        }
    }
});