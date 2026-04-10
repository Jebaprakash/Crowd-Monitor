import mysql.connector
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "user":     os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASS", "7868"),
    "database": os.getenv("DB_NAME", "crowd_monitor"),
}

_CREATE_CROWD_LOG = """
CREATE TABLE IF NOT EXISTS crowd_log (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    ts          DATETIME NOT NULL,
    cam_id      VARCHAR(50) NOT NULL,
    count       INT NOT NULL,
    density     FLOAT NOT NULL,
    density_lbl VARCHAR(10) NOT NULL,
    alert       TINYINT(1) NOT NULL,
    alert_msg   VARCHAR(255)
);
"""

_CREATE_PEAK_LOG = """
CREATE TABLE IF NOT EXISTS peak_log (
    id      INT AUTO_INCREMENT PRIMARY KEY,
    ts      DATETIME NOT NULL,
    cam_id  VARCHAR(10) NOT NULL,
    count   INT NOT NULL
);
"""

_CREATE_ALERTS_LOG = """
CREATE TABLE IF NOT EXISTS alerts_log (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    ts          DATETIME NOT NULL,
    cam_id      VARCHAR(50) NOT NULL,
    count       INT NOT NULL,
    density     FLOAT NOT NULL,
    alert_msg   VARCHAR(255),
    screenshot  VARCHAR(255)
);
"""


def get_conn():
    return mysql.connector.connect(**DB_CONFIG)


def init_db():
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute(_CREATE_CROWD_LOG)
        cur.execute(_CREATE_PEAK_LOG)
        cur.execute(_CREATE_ALERTS_LOG)
        conn.commit()
        conn.close()
        print("[DB] Tables ready.")
    except Exception as e:
        print(f"[DB] init failed: {e}")


def log_entry(cam_id, count, density, density_lbl, alert, alert_msg):
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute(
            "INSERT INTO crowd_log (ts, cam_id, count, density, density_lbl, alert, alert_msg) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (datetime.now(), cam_id, count, density, density_lbl, int(alert), alert_msg),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB] log_entry failed: {e}")


def log_peak(cam_id: str, count: int):
    """Record a new peak count for a camera in peak_log."""
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute(
            "INSERT INTO peak_log (ts, cam_id, count) VALUES (%s, %s, %s)",
            (datetime.now(), cam_id, count),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB] log_peak failed: {e}")


def log_alert_event(cam_id, count, density, alert_msg, screenshot):
    """Record a specific alert event with screenshot info."""
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute(
            "INSERT INTO alerts_log (ts, cam_id, count, density, alert_msg, screenshot) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (datetime.now(), cam_id, count, density, alert_msg, screenshot),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB] log_alert_event failed: {e}")


def get_all_alerts():
    """Fetch all alerts for the admin page."""
    try:
        conn = get_conn()
        cur  = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM alerts_log ORDER BY ts DESC")
        rows = cur.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"[DB] get_all_alerts failed: {e}")
        return []
