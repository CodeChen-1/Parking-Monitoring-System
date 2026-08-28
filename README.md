# Parking Monitoring System

A real-time parking lot monitoring system that uses dual cameras to detect and log vehicle entries and exits via automatic license plate recognition (ALPR).

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend | Flask, Waitress (WSGI server) |
| Database | SQLite |
| Computer Vision | YOLOv8 (Ultralytics), OpenCV |
| OCR | EasyOCR |
| Frontend | Jinja2, Bootstrap 5, Chart.js, Vanilla JavaScript |

## Features

- **Dual Camera Support** — Separate IN and OUT camera feeds for tracking vehicle entry and exit
- **Real-Time License Plate Detection** — YOLOv8 model detects license plates with configurable confidence threshold
- **OCR Text Recognition** — EasyOCR extracts plate text from detected regions
- **Vehicle Entry/Exit Logging** — Automatically records entry time, exit time, and duration
- **Live Camera Feed** — Real-time streaming of both camera feeds via MJPEG
- **Current Car Count** — Displays the number of vehicles currently parked
- **Toast Notifications** — Browser toast alerts when a new plate is detected
- **Vehicle Logs** — Tabular log view with clear and CSV export options
- **Analysis Dashboard** — Bar charts for weekly, monthly, and yearly vehicle entry trends
- **User Authentication** — Login-gated access with session management

## Project Structure

```
Parking-Monitoring-System/
├── app.py              # Flask application (routes, detection, database logic)
├── best.pt             # YOLOv8 trained model weights
├── database.db         # SQLite database (auto-created on first run)
├── requirements.txt    # Python dependencies
├── LICENSE             # MIT License
├── static/
│   ├── style.css       # Custom CSS styles
│   └── scripts.js      # Notification polling, chart rendering, car count
└── templates/
    ├── base.html       # Base layout with navbar and toast component
    ├── login.html      # Login form
    ├── live.html       # Live dual camera feed with car count
    ├── logs.html       # Vehicle log table with clear/download
    └── analysis.html   # Weekly/monthly/yearly chart dashboard
```

## Prerequisites

- Python 3.10+
- Two IP cameras or USB webcams (or use `0` for default webcam)
- YOLOv8 license plate detection model (`best.pt`)

## Setup Instructions

```bash
# 1. Clone the repository
git clone https://github.com/CodeChen-1/Parking-Monitoring-System.git
cd Parking-Monitoring-System

# 2. Create virtual environment
python -m venv venv
# Windows: venv\Scripts\activate  |  macOS/Linux: source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure camera sources in app.py
#    Set ip_in and ip_out to your camera URLs or 0 for default webcam

# 5. Run the application
python app.py
```

The application will start on `http://<your-ip>:5000`.

## Default Credentials

| Username | Password |
|----------|----------|
| admin | password |

> Change these credentials before deploying to production.

## How It Works

1. Two camera feeds (IN and OUT) stream video frames to the application
2. Every 5 seconds, each frame is passed through the YOLOv8 model for license plate detection
3. Detected plates within the red "Detection Zone" are cropped and passed to EasyOCR
4. The extracted plate text is logged to SQLite with a timestamp
5. When a plate is detected on the OUT camera, the system calculates the parking duration
6. Real-time notifications, car count, and analysis charts are updated via API polling

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/live` | Live camera feed page |
| GET | `/video_feed_in` | MJPEG stream from IN camera |
| GET | `/video_feed_out` | MJPEG stream from OUT camera |
| GET | `/current-count` | JSON response with current parked car count |
| GET | `/get_notifications` | JSON response with recently detected plates |
| GET | `/logs` | Vehicle log table page |
| GET | `/get_log` | JSON response of all vehicle logs |
| GET | `/download` | Download vehicle logs as CSV |
| POST | `/clear_logs` | Clear all vehicle logs |
| GET | `/analysis` | Analysis chart dashboard page |
| GET | `/analysis-data` | JSON response with weekly/monthly/yearly data |

