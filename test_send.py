import paho.mqtt.publish as publish
import json

# Gói dữ liệu cảm biến giả lập
payload_data = {
    "event_id": "EVT-001",
    "timestamp": "2026-06-24T10:00:00Z",
    "device_id": "esp32-lab-a101",
    "temperature_c": 42.5,  # Nhiệt độ > 40 sẽ kích hoạt báo động danger
    "humidity_percent": 60,
    "motion_detected": False
}

# Bắn lên MQTT Broker nội bộ của bạn
publish.single(
    topic="smart-campus/raw/iot/environment",
    payload=json.dumps(payload_data),
    hostname="localhost",
    port=1883,
    auth={"username": "IoT", "password": "lab05pass"}
)

print("🚀 Đã bắn dữ liệu giả lập thành công vào Trạm MQTT!")