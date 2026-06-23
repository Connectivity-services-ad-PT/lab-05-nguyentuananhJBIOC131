import os
import json
import csv
import time
import logging
from datetime import datetime
from fastapi import FastAPI
import paho.mqtt.client as mqtt
from pydantic import BaseModel, ValidationError
from typing import Optional
from dotenv import load_dotenv

# --- 1. KHỞI TẠO VÀ ĐỌC CẤU HÌNH TỪ .ENV ---
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title=os.getenv("SERVICE_NAME", "IoT Ingestion Service"))

MQTT_HOST = os.getenv("MQTT_HOST", "26.137.61.149")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")

TOPIC_RAW = "smart-campus/raw/iot/environment"
TOPIC_EVENTS = "smart-campus/events/sensor"

# Quản lý trạng thái
valid_devices = set()
mqtt_client = None
last_status = {}
last_normal_sent_time = {}
THROTTLE_INTERVAL = 60

# --- 2. ĐỌC DEVICE REGISTRY ---
def load_registry():
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        csv_path = os.path.join(current_dir, "device_registry.csv")
        
        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                valid_devices.add(row["device_id"])
        logger.info(f"Đã load {len(valid_devices)} thiết bị từ registry hợp lệ.")
    except Exception as e:
        logger.error(f"Lỗi đọc file device_registry.csv: {e}")

# --- 3. VALIDATE SCHEMA ---
class IoTReading(BaseModel):
    event_id: str
    event_type: str
    device_id: str
    timestamp: datetime
    location: str
    temperature_c: Optional[float] = None
    humidity_percent: Optional[float] = None
    motion_detected: bool
    co2_ppm: Optional[float] = None
    smoke_ppm: Optional[float] = None
    battery_percent: Optional[float] = None
    scenario_hint_for_teacher: Optional[str] = None 

# --- 4. LOGIC PHÂN LOẠI (CLASSIFY) ---
def process_payload(data: IoTReading):
    if data.device_id not in valid_devices:
        return "invalid_device", "high", "unregistered_device_detected"

    if data.temperature_c is None or data.humidity_percent is None:
        return "sensor_error", "high", "missing_temperature_or_humidity_data"

    reasons = []
    
    is_danger = False
    if data.temperature_c >= 40:
        is_danger = True
        reasons.append("temperature_too_high")
    if data.co2_ppm is not None and data.co2_ppm >= 1800:
        is_danger = True
        reasons.append("co2_dangerous_level")
    if data.smoke_ppm is not None and data.smoke_ppm >= 1.0:
        is_danger = True
        reasons.append("smoke_detected")

    if is_danger:
        return "danger", "high", " | ".join(reasons)

    is_warning = False
    if data.temperature_c >= 35:
        is_warning = True
        reasons.append("temperature_warning")
    if data.humidity_percent >= 85:
        is_warning = True
        reasons.append("high_humidity")
    if data.co2_ppm is not None and data.co2_ppm > 1200:
        is_warning = True
        reasons.append("co2_warning_level")
    if data.smoke_ppm is not None and data.smoke_ppm >= 0.5:
        is_warning = True
        reasons.append("smoke_warning")
    if data.battery_percent is not None and data.battery_percent < 20:
        is_warning = True
        reasons.append("low_battery")

    if is_warning:
        return "warning", "medium", " | ".join(reasons)

    return "normal", "low", "environment_normal"

# --- 5. MQTT CALLBACKS ---
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info(f"Kết nối Broker {MQTT_HOST} thành công!")
        client.subscribe(TOPIC_RAW)
    else:
        logger.error(f"Kết nối thất bại với mã lỗi {rc}")

def on_message(client, userdata, msg):
    try:
        raw_payload = json.loads(msg.payload.decode())
        data = IoTReading(**raw_payload)
        status, alert_level, reason = process_payload(data)
        
        dev_id = data.device_id
        current_time = time.time()
        should_send = True

        if dev_id not in last_status:
            last_status[dev_id] = None
            last_normal_sent_time[dev_id] = 0

        if status == "normal":
            if last_status[dev_id] != "normal":
                should_send = True
                last_normal_sent_time[dev_id] = current_time
            else:
                if current_time - last_normal_sent_time[dev_id] < THROTTLE_INTERVAL:
                    should_send = False
                else:
                    should_send = True
                    last_normal_sent_time[dev_id] = current_time
        else:
            should_send = True

        last_status[dev_id] = status

        if not should_send:
            return

        processed_event = {
            "event_type": "sensor.reading.processed",
            "source_service": "team-iot",
            "raw_event_id": data.event_id,
            "device_id": data.device_id,
            "location": data.location,
            "timestamp": data.timestamp.isoformat(), 
            "temperature_c": data.temperature_c,
            "humidity_percent": data.humidity_percent,
            "motion_detected": data.motion_detected,
            "co2_ppm": data.co2_ppm,
            "smoke_ppm": data.smoke_ppm,
            "battery_percent": data.battery_percent,
            "status": status,
            "alert_level": alert_level,
            "reason": reason
        }
        
        client.publish(TOPIC_EVENTS, json.dumps(processed_event))
        logger.info(f"Đã publish sự kiện từ {dev_id} | Status: {status}")

    except ValidationError as e:
        logger.error(f"Lỗi validate schema: {e}")
    except Exception as e:
        logger.error(f"Lỗi xử lý gói tin: {e}")

# --- 6. FASTAPI LẮNG NGHE ---
@app.on_event("startup")
def startup_event():
    global mqtt_client
    load_registry()
    
    mqtt_client = mqtt.Client()
    if MQTT_USERNAME and MQTT_PASSWORD:
        mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    
    try:
        mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
        mqtt_client.loop_start() 
    except Exception as e:
        logger.error(f"Lỗi khởi động MQTT: {e}")

@app.on_event("shutdown")
def shutdown_event():
    if mqtt_client:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()

@app.get("/health")
def health_check():
    return {"status": "ok", "service": os.getenv("SERVICE_NAME")}