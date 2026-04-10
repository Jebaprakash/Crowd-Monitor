# Crowd Monitor — End-to-End AI System

## Folder Structure

```
crowd_monitor/
├── app.py            # Flask app + routes + video loop
├── detection.py      # YOLOv8 person detection
├── density.py        # Density computation & classification
├── lstm_model.py     # Online LSTM anomaly detection
├── alerts.py         # Alert evaluation logic
├── database.py       # MySQL logging
└── requirements.txt
```

## Setup

### 1. Environment & Dependencies
It is recommended to use a virtual environment to manage dependencies:

```bash
# Create a virtual environment
python3 -m venv .venv

# Activate it
source .venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

> [!NOTE]
> If you are on a system where the `python` command is missing, you can install `python-is-python3` via `sudo apt install python-is-python3` or just use `python3`.

### 2. Database Configuration
The system uses MySQL to log crowd events. 

1. **Create the database**:
   ```sql
   CREATE DATABASE crowd_monitor;
   ```
   *Tables will be automatically initialized on the first run.*

2. **Configure environment variables**:
   Create a `.env` file in the root directory with the following variables:
   ```bash
   DB_HOST=localhost
   DB_USER=root
   DB_PASS=yourpassword
   DB_NAME=crowd_monitor

   # Alerts configuration
   ALERT_TO=+910000000000       # Phone number for SMS notifications
   EMAIL_TO=recipient@example.com # Email for alerts

   # Service accounts
   SMTP_USER=sender@gmail.com
   SMTP_PASS=app-specific-password
   TWILIO_ACCOUNT_SID=sid
   TWILIO_AUTH_TOKEN=token
   TWILIO_PHONE_NUMBER=phone
   ```

### 3. Run the Application
Ensure your virtual environment is active, then run:

```bash
python app.py
```

Open your browser at **http://localhost:5000** to view the dashboard.
it
---

## Video Source
Edit `VIDEO_SOURCE` in `app.py`:
- `0` → webcam
- `"/path/to/video.mp4"` → video file

## MySQL Schema
```sql
CREATE TABLE IF NOT EXISTS crowd_log (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    ts          DATETIME NOT NULL,
    count       INT NOT NULL,
    density     FLOAT NOT NULL,
    density_lbl VARCHAR(10) NOT NULL,
    alert       TINYINT(1) NOT NULL,
    alert_msg   VARCHAR(255)
);
```

## Architecture

```
Webcam/Video
    │
    ▼
detection.py  ──► YOLOv8n (persons only)
    │               bounding boxes + count
    ▼
density.py    ──► density_norm = count / area
    │               classify: low / medium / high
    ▼
lstm_model.py ──► online LSTM (SEQ_LEN=10)
    │               anomaly if residual > 2σ
    ▼
alerts.py     ──► high density OR anomaly → ALERT
    │
    ├──► database.py  (log every 30 frames)
    └──► Flask routes  /  /video_feed  /status
```

## API Endpoints
| Route | Description |
|-------|-------------|
| `GET /` | Dashboard UI |
| `GET /video_feed` | MJPEG stream |
| `GET /status` | JSON: count, density, alert |
# Crowd-Monitor
