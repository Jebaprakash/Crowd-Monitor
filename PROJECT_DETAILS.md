# Distributed AI Crowd Monitoring System

## 1. Overview
This project is an end-to-end crowd monitoring solution that uses **YOLOv8** for real-time person detection, **LSTM (Long Short-Term Memory)** neural networks for anomaly detection, and a **Distributed Capture System** that allows any smartphone to act as a wireless camera.

## 2. Key Features
- **Multi-Camera Support**: Monitor up to 3 feeds simultaneously in a grid layout.
- **Wireless Phone Integration**: Use any phone as a camera by visiting the `/capture` route.
- **Zone-Based Detection**: Frames are divided into **Entry, Center, and Exit** zones to track movement.
- **AI Anomaly Detection**: An LSTM model learns crowd patterns and flags sudden spikes (spontaneous gatherings).
- **Automated Alerts**:
    - **Telegram**: Instant notifications via Bot API.
    - **Email**: Detailed alerts sent via SMTP.
    - **Audio**: Siren/Beep plays on the dashboard when an alert is triggered.
- **Smart Privacy**: Automated **Face Blurring** using Haar cascades to protect individual privacy.
- **Crowd Density Analysis**: Calculates the physical area occupied by people to classify density as Low, Medium, or High.
- **Interactive Dashboard**:
    - Real-time **Chart.js** line graphs for population tracking.
    - **Day/Night Mode** toggle.
    - **Snapshot Gallery**: Shows the last 5 alert screenshots.
- **Peak History**: Tracks the highest person count of the day with timestamps.

## 3. Technology Stack
- **Backend**: Python, Flask
- **Computer Vision**: OpenCV, Ultralytics YOLOv8
- **Deep Learning**: TensorFlow/Keras (LSTM)
- **Database**: MySQL (for long-term logging and peak logs)
- **Frontend**: HTML5, Vanilla CSS, JavaScript (Chart.js)
- **Deployment**: Ngrok (for public URL and QR code access)

## 4. System Architecture
1. **Data Ingest**: Frames are received from either the local webcam or remote phones via HTTP POST.
2. **Detection Pipeline**:
    - **YOLOv8** identifies person bounding boxes.
    - **OpenCV** detects faces within those boxes and applies Gaussian Blur.
    - **Zones** are calculated based on the center-X coordinate of each person.
3. **Analysis Pipeline**:
    - **Density Module** calculates the frame coverage ratio.
    - **LSTM Module** compares the current count to predicted trends.
4. **Output Pipeline**:
    - **Database** logs events if density or count thresholds are met.
    - **Alert Dispatcher** sends Telegram/Email messages.
    - **Dashboard** updates via a 1-second polling mechanism.

## 5. File Structure
- `app.py`: Main Flask server, dashboard logic, and frame distributor.
- `detection.py`: YOLOv8 detection and Face Blurring logic.
- `density.py`: Area-based density calculation.
- `lstm_model.py`: Neural network for crowd flow prediction.
- `alerts.py`: Business logic for when an alert should be high priority.
- `database.py`: MySQL connection and logging functions.
- `telegram_alert.py`: Telegram Bot API integration.
- `alert_dispatcher.py`: Email and SMS (Twilio) support.

## 6. How to Run
1. Activate environment: `source .venv/bin/activate`
2. Start project: `python app.py`
3. Scan the **QR Code** in the terminal to view the dashboard on your phone.
4. Go to `/capture` on your phones to start the wireless camera feeds.
