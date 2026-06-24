import time
import json
import random
import uuid
from datetime import datetime, timezone
import paho.mqtt.client as mqtt

# Cấu hình trạm phát Radmin của bạn
HOST = "26.79.10.201"
PORT = 1883
USER = "IoT"
PASS = "lab05pass"
TOPIC = "smart-campus/raw/iot/environment"

# Danh sách thiết bị (có cả thật và giả để test đủ các cảnh báo)
devices = ["esp32-hall-b201", "esp32-lab-a101", "esp32-fake-device-999"]

def generate_payload():
    """Tạo ngẫu nhiên một bản tin giống hệ thống của giảng viên"""
    return {
        "event_id": f"raw-iot-{uuid.uuid4().hex[:6]}",
        "event_type": "iot.environment.sampled",
        "source_service": "pi-iot-simulator-auto",
        "device_id": random.choice(devices),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "temperature_c": round(random.uniform(20.0, 45.0), 1),  # Random từ 20 đến 45 độ
        "humidity_percent": round(random.uniform(40.0, 95.0), 1),
        "motion_detected": random.choice([True, False]),
        "co2_ppm": random.randint(400, 2000),
        "smoke_ppm": round(random.uniform(0.0, 1.2), 2),
        "battery_percent": random.randint(10, 100)
    }

def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        print("✅ Simulator đã kết nối thành công tới Broker! Bắt đầu nã đạn...")
    else:
        print(f"❌ Lỗi kết nối: {reason_code}")

# Khởi tạo súng bắn
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(USER, PASS)
client.on_connect = on_connect

client.connect(HOST, PORT)
client.loop_start()

# Vòng lặp bắn tự động mỗi 5 giây
try:
    while True:
        payload = generate_payload()
        client.publish(TOPIC, json.dumps(payload))
        print(f"🚀 Đã bắn: {payload['device_id']} | Nhiệt độ: {payload['temperature_c']}°C")
        time.sleep(5) # Nghỉ 5 giây trước khi bắn tiếp
except KeyboardInterrupt:
    print("\n🛑 Đã dừng cỗ máy bắn tự động.")
    client.loop_stop()
    client.disconnect()