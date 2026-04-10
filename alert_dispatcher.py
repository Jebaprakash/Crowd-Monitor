import os
import smtplib
import json
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from twilio.rest import Client

COOLDOWN_FILE = "/tmp/email_cooldown.json"
COOLDOWN_SEC = 300

def send_alert(alert_msg, cam_id="default"):
    """
    Sends an alert notification via Email and Twilio SMS with a 300s cooldown per camera.
    """
    now = time.time()
    
    # Per-camera cooldown using a dictionary
    if not hasattr(send_alert, "_cooldowns"):
        send_alert._cooldowns = {}
    
    last_sent = send_alert._cooldowns.get(cam_id, 0)
    if now - last_sent < COOLDOWN_SEC:
        return
    
    send_alert._cooldowns[cam_id] = now

    phone_to = os.getenv("ALERT_TO")
    email_to = os.getenv("EMAIL_TO")
    
    any_success = False

    # --- 1. Email Dispatch (SMTP) ---
    try:
        smtp_user = os.getenv("SMTP_USER")
        smtp_pass = os.getenv("SMTP_PASS")
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))

        if smtp_user and smtp_pass and email_to:
            msg = MIMEMultipart()
            msg['From'] = smtp_user
            msg['To'] = email_to
            msg['Subject'] = "⚠️ CROWD MONITOR ALERT"
            
            body = f"The crowd monitoring system has detected an issue:\n\n{alert_msg}\n\nPlease check the dashboard immediately."
            msg.attach(MIMEText(body, 'plain'))

            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
            print(f"[Dispatcher] Email sent to {email_to}")
            any_success = True
    except Exception as e:
        print(f"[Dispatcher] Email error: {e}")

    # --- 2. SMS Dispatch (Twilio) ---
    try:
        twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
        twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
        twilio_from = os.getenv("TWILIO_PHONE_NUMBER")

        if twilio_sid and twilio_token and twilio_from and phone_to:
            client = Client(twilio_sid, twilio_token)
            client.messages.create(
                body=f"🚨 Crowd Monitor Alert: {alert_msg}",
                from_=twilio_from,
                to=phone_to
            )
            print(f"[Dispatcher] SMS sent to {phone_to} from {twilio_from}")
            any_success = True
        else:
            print("[Dispatcher] SMS skipped: Twilio config or ALERT_TO missing.")
    except Exception as e:
        print(f"[Dispatcher] SMS error (Twilio): {e}")

    # Dispatch logic remains same but now encapsulated in per-cam check
