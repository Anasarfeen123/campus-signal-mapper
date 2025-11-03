# Campus Signal Mapper

This project maps cellular signal strength (dBm) across a campus using a simple Flask server and a Leaflet.js heatmap.

## Features

* **API:** A Flask API to submit and query signal samples.
* **Real-time:** Uses Socket.IO to update the map live as new samples are submitted.
* **Visualization:** A heatmap overlay on an OpenStreetMap tile layer shows signal strength.
* **Filtering:** Filter map data by cellular carrier and network type (3G, 4G, 5G).

## Setup

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd campus-signal-mapper
    ```

2.  **Create a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Initialize the database:**
    ```bash
    python db_init.py
    ```

5.  **Set the Flask Secret Key:**
    ```bash
    export FLASK_SECRET_KEY='your-very-secure-random-string'
    ```

## Running the Application

1.  **Start the server:**
    ```bash
    python app.py
    ```
    The server will be running at `http://localhost:5000`.

2.  **View the map:**
    Open `http://localhost:5000` in your browser.

3.  **(Optional) Send test data:**
    In a separate terminal, run the `sample_sender.py` script to populate the map with random data.
    ```bash
    python sample_sender.py
    ```