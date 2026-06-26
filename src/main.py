from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import os
import json
import logging
import psycopg2
import csv
import ssl
from datetime import datetime
import paho.mqtt.client as mqtt


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="IoT Ingestion Service", version=os.getenv("SERVICE_VERSION", "v1.0.0"))

MQTT_HOST = os.getenv("MQTT_BROKER", "f6f78e87db4a4c189dd3d706745a5e93.s1.eu.hivemq.cloud")
MQTT_PORT = int(os.getenv("MQTT_PORT", 8883))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "DVKN_IOT_2026")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "ThaiBao12A@")
IN_TOPIC = os.getenv("IN_TOPIC", "smart-campus/raw/iot/environment")
OUT_TOPIC = os.getenv("OUT_TOPIC", "smart-campus/events/sensor")

valid_devices_cache = {}

def load_device_registry_to_cache():
    global valid_devices_cache
    valid_devices_cache.clear()
    csv_path = "src/IoT_device_registry.csv"
    
    if os.path.exists(csv_path):
        try:
            with open(csv_path, mode='r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                reader.fieldnames = [str(name).strip().lower() for name in reader.fieldnames] if reader.fieldnames else []
                
                for row in reader:
                    if 'device_id' in row and row['device_id']:
                        valid_devices_cache[row['device_id'].strip()] = {
                            "location": row.get('location', 'unknown_location').strip(),
                            "room": row.get('room', 'unknown_room').strip(),
                            "device_type": row.get('device_type', 'sensor').strip()
                        }
            logger.info(f"Đã nạp {len(valid_devices_cache)} thiết bị vào bộ nhớ đệm (RAM).")
        except Exception as e:
            logger.error(f"Lỗi đọc file CSV: {e}")
    else:
        logger.error(f"Không tìm thấy file {csv_path}. Không thể nạp cache.")

def check_device_in_registry(device_id: str) -> bool:
    return device_id in valid_devices_cache

def init_db():
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("POSTGRES_DB", "iot_db"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", "postgres"),
            host=os.getenv("POSTGRES_SERVER", "db"),
            port="5432"
        )
        conn.autocommit = True
        cur = conn.cursor()
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS device_registry (
                device_id VARCHAR(100) PRIMARY KEY,
                device_type VARCHAR(100),
                location VARCHAR(100),
                room VARCHAR(50),
                status VARCHAR(50)
            );
        """)
        
        csv_path = "src/IoT_device_registry.csv"
        if os.path.exists(csv_path):
            with open(csv_path, mode='r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                reader.fieldnames = [str(field).strip().lower() for field in reader.fieldnames] if reader.fieldnames else []
                
                for row in reader:
                    cur.execute("""
                        INSERT INTO device_registry (device_id, device_type, location, room, status)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (device_id) DO NOTHING;
                    """, (
                        row.get('device_id', '').strip(), 
                        row.get('device_type', 'sensor').strip(), 
                        row.get('location', 'unknown').strip(), 
                        row.get('room', 'unknown').strip(), 
                        row.get('status', 'active').strip()
                    ))
            logger.info("Đã nạp dữ liệu từ CSV vào Database thành công.")
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Lỗi khởi tạo Database: {e}")

def is_valid_number(value) -> bool:
    """Kiểm tra giá trị là số thực sự (loại trừ bool lọt qua isinstance)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)

def classify_environment(payload: dict, is_device_valid: bool) -> tuple:
    temp = payload.get("temperature_c")
    hum = payload.get("humidity_percent")
    co2 = payload.get("co2_ppm", 0)
    smoke = payload.get("smoke_ppm", 0)
    batt = payload.get("battery_percent", 100)

    if not is_device_valid:
        return "invalid_device", "high", "device_id_not_found_in_registry"

    # FIX: dùng is_valid_number để loại trừ bool (True/False) bị nhận nhầm là số
    if temp is None or hum is None or not is_valid_number(temp) or not is_valid_number(hum):
        return "sensor_error", "medium", "missing_or_invalid_temperature_humidity_data"

    reasons = []
    if temp >= 40: reasons.append("temp_>=_40")
    if co2 >= 1800: reasons.append("co2_>=_1800")
    if smoke >= 1.0: reasons.append("smoke_>=_1.0")
    if reasons:
        return "danger", "high", " | ".join(reasons)

    if temp >= 35: reasons.append("temp_>=_35")
    if hum >= 85: reasons.append("humidity_>=_85")
    if co2 > 1200: reasons.append("co2_>_1200")
    if smoke >= 0.5: reasons.append("smoke_>=_0.5")
    if batt < 20: reasons.append("battery_<_20")
    if reasons:
        # FIX: đổi "medium" → "high" cho warning để nhất quán với tài liệu
        return "warning", "high", " | ".join(reasons)

    # FIX: đổi "none" → "low" để Core Business không nhận giá trị ngoài schema
    return "normal", "low", "conditions_normal"

def process_mqtt_message(client, userdata, msg):
    try:
        raw_payload = json.loads(msg.payload.decode())
        
        # FIX: thêm event_type vào required_fields theo tài liệu nghiệp vụ
        required_fields = ["event_id", "event_type", "timestamp", "device_id", "temperature_c", "humidity_percent", "motion_detected"]
        for field in required_fields:
            if field not in raw_payload or raw_payload[field] is None:
                logger.error(f"VALIDATE FAILED: Thiếu hoặc null trường bắt buộc '{field}'. Đã hủy payload.")
                return

        # FIX: validate timestamp đúng ISO 8601 trước khi publish sang Core Business
        raw_ts = raw_payload.get("timestamp", "")
        try:
            datetime.fromisoformat(str(raw_ts).replace("Z", "+00:00"))
            normalized_timestamp = str(raw_ts)
        except (ValueError, TypeError):
            logger.error(f"VALIDATE FAILED: Timestamp '{raw_ts}' không đúng định dạng ISO 8601. Đã hủy payload.")
            return

        device_id = raw_payload["device_id"]
        is_valid = check_device_in_registry(device_id)

        device_info = valid_devices_cache.get(device_id, {})
        location = device_info.get("location", "unknown_location") if is_valid else "unknown_location"
        room = device_info.get("room", "unknown_room") if is_valid else "unknown_room"

        status, alert_level, reason = classify_environment(raw_payload, is_valid)

        processed_event = {
            "event_type": "sensor.reading.processed",
            "source_service": "team-iot",
            "raw_event_id": raw_payload.get("event_id"),
            "device_id": device_id,
            "location": location,      
            "room": room,              
            "temperature_c": raw_payload.get("temperature_c"),
            "humidity_percent": raw_payload.get("humidity_percent"),
            "motion_detected": raw_payload.get("motion_detected", False),
            "co2_ppm": raw_payload.get("co2_ppm", 0),
            "smoke_ppm": raw_payload.get("smoke_ppm", 0),
            "battery_percent": raw_payload.get("battery_percent", 100),
            "status": status,
            "alert_level": alert_level,
            "reason": reason,
            "timestamp": normalized_timestamp
        }

        client.publish(OUT_TOPIC, json.dumps(processed_event))
        logger.info(f"PRODUCED EVENT: {device_id} | Status: {status} | Level: {alert_level} | Room: {room}")
        
    except json.JSONDecodeError:
        logger.error("VALIDATE FAILED: Payload không đúng định dạng JSON.")
    except Exception as e:
        logger.error(f"Lỗi xử lý MQTT: {e}")

def start_mqtt_client():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, protocol=mqtt.MQTTv5)
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    
    # BẬT LẠI TLS ĐỂ KẾT NỐI LÊN CLOUD
    client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT) 
    
    client.on_connect = lambda c, u, f, rc, props=None: c.subscribe(IN_TOPIC, qos=1) if rc == 0 else logger.error(f"Lỗi kết nối: {rc}")
    client.on_message = process_mqtt_message
    
    try:
        client.connect(MQTT_HOST, MQTT_PORT)
        client.loop_start()
        logger.info(f"MQTT Client đã kết nối thực tế tới {MQTT_HOST}:{MQTT_PORT} & đang lắng nghe!")
    except Exception as e:
        logger.error(f"Lỗi kết nối MQTT: {e}")

@app.on_event("startup")
def startup_event():
    load_device_registry_to_cache() 
    init_db()
    start_mqtt_client()

@app.get("/health")
def health_check():
    return {"status": "ok"}