import os
import cv2
import time
import threading
import datetime
import numpy as np
from flask import Flask, Response, jsonify, render_template_string, send_from_directory, request
from dotenv import load_dotenv

load_dotenv()

from detection import detect_persons
from density import compute_density, classify_density
from lstm_model import CrowdLSTM
from alerts import evaluate_alert
from database import init_db, log_entry, log_peak, log_alert_event, get_all_alerts
from alert_dispatcher import send_alert as send_email_alert
from telegram_alert import send_telegram_alert
from device_manager import DeviceManager

app = Flask(__name__)
dm = DeviceManager()

# --- Configuration ---
BLUR_FACES = True
ALERT_COOLDOWN = 300 

# --- Global Dynamic State ---
device_states = {} # device_id -> dict
remote_buffers = {} # device_id -> frame
state_lock = threading.Lock()

def get_device_state(device_id):
    """Initializes device state if not exists."""
    with state_lock:
        if device_id not in device_states:
            device_states[device_id] = {
                "count": 0, "density": 0.0, "density_lbl": "low",
                "alert": False, "alert_msg": "",
                "zone_counts": {"Entry": 0, "Center": 0, "Exit": 0},
                "history": [], "last_alert_time": 0,
                "peak_count": 0, "peak_time": "--:--",
                "last_date": datetime.date.today(),
                "lstm": CrowdLSTM()
            }
        return device_states[device_id]

def reset_daily_peak(device_id, st):
    today = datetime.date.today()
    if st["last_date"] != today:
        st["peak_count"] = 0
        st["peak_time"] = "--:--"
        st["last_date"] = today

def generate_frames(device_id):
    """Generator for a specific device stream."""
    # If it's a local camera device (prefixed with 'local_')
    cap = None
    if device_id.startswith("local_"):
        try:
            source = int(device_id.split("_")[1])
            cap = cv2.VideoCapture(source)
        except: pass

    frame_n = 0
    while True:
        # Pruning check: if device is no longer in dm.devices, stop thread
        if device_id not in dm.devices:
            if cap: cap.release()
            break

        frame = remote_buffers.get(device_id)
        
        if frame is None and cap:
            ok, frame = cap.read()
            if not ok:
                time.sleep(1)
                continue

        if frame is None:
            # Placeholder for inactive streams
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(frame, f"DEVICE {device_id} OFFLINE", (120, 240), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (80, 80, 80), 2)
            _, buf = cv2.imencode(".jpg", frame)
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")
            time.sleep(1)
            continue

        # Processing Pipeline
        frame, count, boxes, zone_counts = detect_persons(frame, blur_faces=BLUR_FACES)
        density = compute_density(boxes, frame)
        density_lbl = classify_density(density)
        
        st = get_device_state(device_id)
        anomaly, reason = st["lstm"].update_and_detect(count)
        alert, alert_msg = evaluate_alert(density_lbl, anomaly, reason)
        
        reset_daily_peak(device_id, st)
        if count > st["peak_count"]:
            st["peak_count"] = count
            st["peak_time"] = datetime.datetime.now().strftime("%H:%M")
            log_peak(device_id, count)

        # Alert Dispatch
        now = time.time()
        if alert and (now - st["last_alert_time"] > ALERT_COOLDOWN):
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"alerts/{device_id}_{timestamp}.jpg"
            cv2.imwrite(filename, frame)
            # Log to DB
            log_alert_event(device_id, count, density, alert_msg, os.path.basename(filename))
            
            threading.Thread(target=send_email_alert, args=(f"[{device_id}] {alert_msg}", device_id), daemon=True).start()
            threading.Thread(target=send_telegram_alert, args=(alert_msg, count, density, device_id), daemon=True).start()
            st["last_alert_time"] = now

        # Update State
        with state_lock:
            st.update(count=count, density=density, density_lbl=density_lbl, 
                      alert=alert, alert_msg=alert_msg, zone_counts=zone_counts)
            st["history"].append(count)
            if len(st["history"]) > 30: st["history"].pop(0)

        frame_n += 1
        if frame_n % 30 == 0: log_entry(device_id, count, density, density_lbl, alert, alert_msg)
        
        if frame_n % 2 != 0: continue # Skip frames for UI performance
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 55])
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")

# --- HTML Templates ---
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Dynamic Crowd Monitor</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root { --bg: #050508; --card: #0e0e15; --text: #e0e0e0; --accent: #00ff88; --border: #1a1a24; }
        body { font-family: -apple-system, sans-serif; background: var(--bg); color: var(--text); margin: 0; }
        header { padding: 1.5rem 2rem; background: var(--card); border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(380px, 1fr)); gap: 1.5rem; padding: 2rem; }
        .cam-card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; display: flex; flex-direction: column; }
        .cam-header { padding: 12px; font-size: 0.8rem; letter-spacing: 0.1em; color: #888; border-bottom: 1px solid var(--border); text-transform: uppercase; }
        .video-box img { width: 100%; aspect-ratio: 16/9; display: block; background: #000; }
        .stats { padding: 15px; display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        .stat-box { background: rgba(255,255,255,0.03); padding: 10px; border-radius: 8px; text-align: center; }
        .val { font-size: 1.8rem; font-weight: 800; color: var(--accent); display: block; }
        .lbl { font-size: 0.6rem; color: #666; text-transform: uppercase; }
        .chart-wrap { height: 120px; padding: 10px; }
        .badge { background: #ff3333; color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; font-weight: bold; float: right; display: none; }
        .alert-on { border-color: #ff3333 !important; box-shadow: 0 0 20px rgba(255,51,51,0.2); }
        .alert-on .badge { display: inline; }
        .capture-info { padding: 2rem; text-align: center; background: #000; color: #888; border-top: 1px solid var(--border); }
        a { color: var(--accent); text-decoration: none; }
    </style>
</head>
<body>
<header>
    <div style="font-weight: 800; letter-spacing: 2px;">CROWD MONITOR <span style="font-weight: 100; color: #555;">v2.0 DYNAMIC</span></div>
    <div style="display: flex; gap: 20px; align-items: center;">
        <a href="/admin" style="font-size: 0.8rem; font-weight: 700; color: #888; text-transform: uppercase; letter-spacing: 1px;">Admin Log</a>
        <div>Active Devices: <span id="device-count">0</span></div>
    </div>
</header>
<div class="grid" id="main-grid">
    <!-- Dynamic Cards Inserted Here -->
</div>
<div class="capture-info">
    Add Wireless Camera: <a href="/capture" target="_blank">{{ ngrok_url }}/capture</a>
</div>
<audio id="beep" src="https://actions.google.com/sounds/v1/alarms/beep_short.ogg"></audio>

<script>
    const charts = {};
    const grid = document.getElementById('main-grid');
    let knownDevices = [];
    let isMuted = false;
    let lastAlertState = false;

    function createCard(id) {
        const div = document.createElement('div');
        div.className = 'cam-card';
        div.id = 'card-' + id;
        div.innerHTML = `
            <div class="cam-header">${id} <span class="badge">ALERT</span></div>
            <div class="video-box"><img src="/video_feed/${id}"></div>
            <div class="stats">
                <div class="stat-box"><span class="lbl">People</span><span class="val" id="cnt-${id}">0</span></div>
                <div class="stat-box"><span class="lbl">Density</span><span class="val" id="den-${id}" style="font-size:1.2rem">LOW</span></div>
            </div>
            <div style="padding: 0 15px; font-size: 0.7rem; color: #555">Zones: <span id="zone-${id}">...</span> | Daily Peak: <span id="peak-${id}">...</span></div>
            <div class="chart-wrap"><canvas id="chart-${id}"></canvas></div>
        `;
        grid.appendChild(div);
        
        const ctx = document.getElementById('chart-' + id).getContext('2d');
        charts[id] = new Chart(ctx, {
            type: 'line', data: { labels: Array(30).fill(''), datasets: [{ data: [], borderColor: '#00ff88', tension: 0.4, pointRadius: 0, borderWidth: 2 }] },
            options: { responsive: true, maintainAspectRatio: false, scales: { x: { display: false }, y: { display: false } }, plugins: { legend: { display: false } } }
        });
    }

    async function update() {
        try {
            const r = await fetch('/status');
            const data = await r.json();
            const deviceIds = Object.keys(data);
            
            document.getElementById('device-count').textContent = deviceIds.length;

            // Add new devices
            deviceIds.forEach(id => {
                if (!knownDevices.includes(id)) {
                    createCard(id);
                    knownDevices.push(id);
                }
            });

            // Remove gone devices
            knownDevices = knownDevices.filter(id => {
                if (!deviceIds.includes(id)) {
                    document.getElementById('card-' + id).remove();
                    delete charts[id];
                    return false;
                }
                return true;
            });

            let globalAlert = false;
            deviceIds.forEach(id => {
                const d = data[id];
                document.getElementById('cnt-'+id).textContent = d.count;
                document.getElementById('den-'+id).textContent = d.density_lbl.toUpperCase();
                document.getElementById('zone-'+id).textContent = `E:${d.zone_counts.Entry} C:${d.zone_counts.Center} X:${d.zone_counts.Exit}`;
                document.getElementById('peak-'+id).textContent = d.peak_count;
                
                const card = document.getElementById('card-'+id);
                if (d.alert) {
                    card.classList.add('alert-on');
                    globalAlert = true;
                } else {
                    card.classList.remove('alert-on');
                }

                charts[id].data.datasets[0].data = d.history;
                charts[id].update('none');
            });

            if (globalAlert && !lastAlertState && !isMuted) document.getElementById('beep').play().catch(()=>{});
            lastAlertState = globalAlert;

        } catch (e) { console.error(e); }
    }
    setInterval(update, 1000);
</script>
</body>
</html>
"""

ADMIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Admin - Alert History</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        :root { 
            --bg: #0a0a0f; 
            --card: #14141d; 
            --text: #ffffff; 
            --accent: #ff3e3e; 
            --secondary: #00ff88;
            --border: #252530; 
        }
        body { 
            font-family: 'Inter', -apple-system, sans-serif; 
            background: var(--bg); 
            color: var(--text); 
            margin: 0; 
            padding-bottom: 50px;
        }
        header { 
            padding: 1.5rem 2rem; 
            background: var(--card); 
            border-bottom: 1px solid var(--border); 
            display: flex; 
            justify-content: space-between; 
            align-items: center;
            position: sticky;
            top: 0;
            z-index: 100;
            backdrop-filter: blur(10px);
        }
        .container { max-width: 1200px; margin: 2rem auto; padding: 0 1rem; }
        h1 { font-size: 1.5rem; margin: 0; font-weight: 800; letter-spacing: -0.5px; }
        .alert-grid { 
            display: grid; 
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); 
            gap: 2rem; 
        }
        .alert-card { 
            background: var(--card); 
            border-radius: 16px; 
            border: 1px solid var(--border); 
            overflow: hidden; 
            transition: transform 0.2s, box-shadow 0.2s;
            position: relative;
        }
        .alert-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            border-color: var(--accent);
        }
        .screenshot-box {
            width: 100%;
            aspect-ratio: 16/9;
            background: #000;
            position: relative;
            overflow: hidden;
        }
        .screenshot-box img {
            width: 100%;
            height: 100%;
            object-fit: cover;
            transition: transform 0.5s;
        }
        .alert-card:hover .screenshot-box img {
            transform: scale(1.05);
        }
        .alert-content { padding: 1.5rem; }
        .alert-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1rem; }
        .cam-tag { 
            background: rgba(255, 62, 62, 0.1); 
            color: var(--accent); 
            padding: 4px 10px; 
            border-radius: 6px; 
            font-size: 0.75rem; 
            font-weight: 700;
            text-transform: uppercase;
        }
        .timestamp { font-size: 0.8rem; color: #888; }
        .msg { font-size: 1rem; margin: 0.5rem 0; font-weight: 600; line-height: 1.4; color: #eee; }
        .meta { display: flex; gap: 1rem; margin-top: 1rem; border-top: 1px solid var(--border); padding-top: 1rem; }
        .meta-item { display: flex; flex-direction: column; }
        .meta-val { font-size: 1.1rem; font-weight: 700; color: var(--secondary); }
        .meta-lbl { font-size: 0.6rem; color: #666; text-transform: uppercase; letter-spacing: 0.5px; }
        .no-alerts { text-align: center; padding: 100px; color: #555; font-size: 1.2rem; }
        .back-btn {
            color: var(--secondary);
            text-decoration: none;
            font-size: 0.9rem;
            display: flex;
            align-items: center;
            gap: 5px;
        }
        .back-btn:hover { text-decoration: underline; }
    </style>
</head>
<body>
<header>
    <h1>ALERT HISTORY LOG</h1>
    <a href="/" class="back-btn">← DASHBOARD</a>
</header>
<div class="container">
    {% if alerts %}
    <div class="alert-grid">
        {% for a in alerts %}
        <div class="alert-card">
            <div class="screenshot-box">
                <img src="/alert_image/{{ a.screenshot }}" alt="Alert Screenshot">
            </div>
            <div class="alert-content">
                <div class="alert-header">
                    <span class="cam-tag">{{ a.cam_id }}</span>
                    <span class="timestamp">{{ a.ts.strftime('%b %d, %H:%M:%S') }}</span>
                </div>
                <div class="msg">{{ a.alert_msg }}</div>
                <div class="meta">
                    <div class="meta-item">
                        <span class="meta-lbl">Count</span>
                        <span class="meta-val">{{ a.count }}</span>
                    </div>
                    <div class="meta-item">
                        <span class="meta-lbl">Density</span>
                        <span class="meta-val">{{ "%.2f"|format(a.density) }}</span>
                    </div>
                </div>
            </div>
        </div>
        {% endfor %}
    </div>
    {% else %}
    <div class="no-alerts">
        <div style="font-size: 4rem; margin-bottom: 20px;">📭</div>
        No alerts have been recorded yet.
    </div>
    {% endif %}
</div>
</body>
</html>
"""

CAPTURE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Register Camera</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { background: #000; color: #fff; text-align: center; padding: 40px; font-family: sans-serif; }
        input { background: #111; border: 1px solid var(--accent); color: #fff; padding: 15px; border-radius: 8px; width: 80%; margin: 10px 0; }
        .btn { background: #00ff88; color: #000; padding: 18px; border-radius: 8px; border: none; width: 80%; font-weight: bold; cursor: pointer; }
        #video { width: 100%; border-radius: 12px; margin-top: 20px; display: none; }
    </style>
</head>
<body>
    <div id="reg-form">
        <h2>Enter Device Name</h2>
        <input type="text" id="dev-name" placeholder="e.g. North_Exit">
        <button class="btn" onclick="register()">REGISTER & START</button>
    </div>
    <div id="stream-ui" style="display:none">
        <h3 id="dev-id-display"></h3>
        <video id="video" autoplay playsinline muted></video>
        <p style="color: #00ff88">LIVE BROADCASTING...</p>
    </div>

    <script>
        let deviceId = null;
        async function register() {
            const name = document.getElementById('dev-name').value;
            const resp = await fetch('/register', { 
                method: 'POST', 
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ name: name })
            });
            const data = await resp.json();
            deviceId = data.device_id;
            
            document.getElementById('reg-form').style.display = 'none';
            document.getElementById('stream-ui').style.display = 'block';
            document.getElementById('dev-id-display').innerText = "Device: " + deviceId;
            startStream();
        }

        async function startStream() {
            const video = document.getElementById('video');
            const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
            video.srcObject = stream;
            video.style.display = 'block';

            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            setInterval(() => {
                canvas.width = video.videoWidth; canvas.height = video.videoHeight;
                ctx.drawImage(video, 0, 0);
                canvas.toBlob((blob) => {
                    const fd = new FormData();
                    fd.append('frame', blob);
                    fetch('/upload_frame/' + deviceId, { method: 'POST', body: fd });
                }, 'image/jpeg', 0.5);
            }, 250);
        }
    </script>
</body>
</html>
"""

# --- Routes ---
@app.route("/")
def dashboard():
    return render_template_string(DASHBOARD_HTML, ngrok_url=app.config.get('NGROK_URL', ''))

@app.route("/admin")
def admin_page():
    alerts = get_all_alerts()
    return render_template_string(ADMIN_HTML, alerts=alerts)

@app.route("/capture")
def capture_page():
    return render_template_string(CAPTURE_HTML)

@app.route("/register", methods=["POST"])
def register():
    name = request.json.get("name")
    ip = request.remote_addr
    did = dm.register_device(ip, name)
    return jsonify({"device_id": did})

@app.route("/upload_frame/<device_id>", methods=["POST"])
def upload_frame(device_id):
    if device_id not in dm.devices: return "Not Registered", 403
    dm.update_heartbeat(device_id)
    file = request.files.get('frame')
    if file:
        nparr = np.frombuffer(file.read(), np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is not None:
            remote_buffers[device_id] = frame
    return "OK", 200

@app.route("/video_feed/<device_id>")
def video_feed(device_id):
    return Response(generate_frames(device_id), mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/status")
def status_all():
    dm.remove_inactive_devices()
    with state_lock:
        active_ids = dm.get_active_devices()
        data = {}
        now = time.time()
        for cid in active_ids:
            st = get_device_state(cid)
            tmp = dict(st)
            tmp.pop("lstm", None); tmp.pop("last_date", None)
            tmp["cooldown_remaining"] = int(max(0, ALERT_COOLDOWN - (now - st.get("last_alert_time", 0))))
            data[cid] = tmp
        return jsonify(data)

@app.route("/alerts")
def get_alerts():
    return jsonify(sorted([f for f in os.listdir("alerts") if f.endswith(".jpg")]))

@app.route("/alert_image/<filename>")
def get_alert_image(filename):
    return send_from_directory("alerts", filename)

if __name__ == "__main__":
    from pyngrok import ngrok
    import qrcode
    
    init_db()
    os.makedirs("alerts", exist_ok=True)
    
    # Register local webcam by default
    dm.register_device("127.0.0.1", "Local_0")

    auth_token = os.getenv("NGROK_AUTH_TOKEN")
    if auth_token:
        ngrok.set_auth_token(auth_token)
        try:
            public_url = ngrok.connect(5000).public_url
            app.config['NGROK_URL'] = public_url
            print(f"\n * Dashboard: {public_url}")
            qrcode.QRCode().add_data(public_url).print_ascii()
        except: pass

    app.run(host="0.0.0.0", port=5000, threaded=True)
