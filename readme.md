# VIT Chennai Signal Mapper

A real-time, crowd-sourced heatmap of mobile carrier performance across the VIT Chennai campus.

This tool provides a live visualization of mobile network quality, allowing users to see the best and worst spots for signal and data speed. Data can be filtered by carrier and network type, and any user on campus can contribute their own data.


*(Suggestion: Add a screenshot of your map here!)*

---

## ✨ Core Features

* **Dual-Data Heatmap:** Visualize both **Signal Strength (dBm)** and **Download Speed (Mbps)**.
* **Real-Time Updates:** The map updates live for all connected users via WebSockets as new data is submitted.
* **Public Data Contribution:** A dedicated `/upload` page allows any user to contribute data from their phone's browser.
* **Automatic Carrier Detection:** Auto-detects the user's carrier (Airtel, Jio, etc.) on the contribution page by calling a server-side API (`/api/get-carrier`).
* **Dynamic Filtering:** Filter the map data by carrier (Airtel, Jio, VI, BSNL) and network type (3G, 4G, 5G).
* **Spam & Abuse Protection:**
    * **Geofencing:** The server only accepts data points originating from within the VIT Chennai campus bounds.
    * **Rate Limiting:** Protects the `/api/submit` endpoint from spam bots.
    * **WiFi Blocking:** The contribution page intelligently alerts users and blocks submissions if they are connected to WiFi.

---

## 🛠️ Technology Stack

* **Backend:** Python, Flask, Flask-SocketIO, Flask-Limiter, Requests
* **Frontend:** JavaScript, Leaflet.js, Leaflet.heat
* **Database:** SQLite

---

## 🚀 Getting Started

Follow these steps to get the project running on your local machine.

1.  **Clone the Repository**
    ```bash
    git clone [https://github.com/your-username/campus-signal-mapper.git](https://github.com/your-username/campus-signal-mapper.git)
    cd campus-signal-mapper
    ```

2.  **Create and Activate a Virtual Environment**
    ```bash
    # Create the environment
    python -m venv venv
    # Activate (macOS/Linux)
    source venv/bin/activate
    # Activate (Windows)
    .\venv\Scripts\activate
    ```

3.  **Install Dependencies**
    Make sure you have installed all the new requirements.
    ```bash
    pip install -r requirements.txt
    ```

4.  **Initialize the Database**
    This script creates the `signals.db` file with the correct tables.
    ```bash
    python db_init.py
    ```

5.  **Set the Flask Secret Key**
    (This is needed for secure sessions)
    ```bash
    # macOS/Linux
    export FLASK_SECRET_KEY='your-very-secure-random-string'
    # Windows
    set FLASK_SECRET_KEY='your-very-secure-random-string'
    ```

6.  **Run the Server**
    ```bash
    python app.py
    ```
    The server will be running at `http://localhost:5000`.

7.  **View and Contribute**
    * **View the Map:** Open `http://localhost:5000`
    * **Contribute Data:** Open `http://localhost:5000/upload`

8.  **(Optional) Send Test Data**
    To populate the map with 100 random data points, run the test script in a separate terminal:
    ```bash
    python sample_sender.py
    ```

---

## 📁 Project Structure

├── app.py # Main Flask server (API routes, Socket.IO) 
├── db_init.py # Script to initialize the database 
├── sample_sender.py # Script to send fake test data 
├── requirements.txt # Python dependencies 
├── signals.db # SQLite database 
├── .gitignore # Files to ignore
├── static/ 
│ ├── main.js # JavaScript for the map page 
│ └── upload.js # JavaScript for the contribution page  
└── templates/
  ├── index.html # HTML for the main map
  └── upload.html # HTML for the contribution page

---

## ⚙️ API Endpoints

* `GET /`: Serves the main heatmap page.
* `GET /upload`: Serves the data contribution page.
* `GET /api/get-carrier`: Detects the user's carrier from their IP address.
* `GET /api/samples`: Gets all samples from the DB (with filters) to draw the map.
* `POST /api/submit`: Submits a single or batch of new data points.

---

## 📄 License

This project is open-source. Feel free to use and modify it as you wish.