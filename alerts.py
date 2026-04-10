def evaluate_alert(density_label, anomaly, anomaly_reason):
    """Return (alert: bool, message: str)."""
    # Logic: Only alert if (High Density) OR (Medium Density AND Anomaly)
    if density_label == "high":
        msg = "high crowd density"
        if anomaly:
            msg += f" | {anomaly_reason}"
        return True, "ALERT: " + msg
        
    if density_label == "medium" and anomaly:
        return True, "ALERT: medium density anomaly | " + anomaly_reason
        
    return False, ""
