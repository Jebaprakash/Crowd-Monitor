import time
import uuid
import threading

class DeviceManager:
    def __init__(self):
        self.devices = {} # device_id: metadata
        self.lock = threading.Lock()
        self.timeout = 30 # seconds before considering a device inactive

    def register_device(self, ip_address, custom_name=None):
        with self.lock:
            device_id = str(uuid.uuid4())[:8]
            if custom_name:
                device_id = custom_name.replace(" ", "_")
            
            # If name exists, append random suffix
            orig_id = device_id
            count = 1
            while device_id in self.devices:
                device_id = f"{orig_id}_{count}"
                count += 1

            self.devices[device_id] = {
                "id": device_id,
                "ip": ip_address,
                "registered_at": time.time(),
                "last_seen": time.time(),
                "status": "active"
            }
            return device_id

    def update_heartbeat(self, device_id):
        with self.lock:
            if device_id in self.devices:
                self.devices[device_id]["last_seen"] = time.time()
                self.devices[device_id]["status"] = "active"

    def get_active_devices(self):
        self.remove_inactive_devices()
        with self.lock:
            return list(self.devices.keys())

    def remove_inactive_devices(self):
        with self.lock:
            now = time.time()
            to_remove = []
            for did, meta in self.devices.items():
                if now - meta["last_seen"] > self.timeout:
                    to_remove.append(did)
            
            for did in to_remove:
                # We don't necessarily delete them instantly, just mark inactive
                # or remove from the active rotation
                self.devices[did]["status"] = "inactive"
                # For "unlimited dynamic", we might want to prune them
                del self.devices[did]

    def get_metadata(self, device_id):
        with self.lock:
            return self.devices.get(device_id)
