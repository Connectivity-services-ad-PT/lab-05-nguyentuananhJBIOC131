import time
import json
import ssl
from paho.mqtt import client as mqtt

MQTT_HOST = "f6f78e87db4a4c189dd3d706745a5e93.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
TOPIC = "smart-campus/raw/iot/environment"

# Khởi tạo Client MQTT kết nối lên Vân mây HiveMQ
client = mqtt.Client(protocol=mqtt.MQTTv5)
client.username_pw_set("DVKN_IOT_2026", "ThaiBao12A@")
client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)

print("Đang kết nối tới HiveMQ Cloud...")
client.connect(MQTT_HOST, MQTT_PORT)
client.loop_start()

# Kịch bản 1: Thiết bị hợp lệ gửi dữ liệu bình thường (Trạng thái NORMAL)
payload_normal = {
    "event_id": "evt-normal-1001",
    "timestamp": "2026-06-24T09:20:00Z",
    "device_id": "esp32-lab-a101",  # Khớp với DB của bạn
    "temperature_c": 28.5,
    "humidity_percent": 60.0,
    "motion_detected": True,
    "co2_ppm": 450,
    "smoke_ppm": 0.05,
    "battery_percent": 90,
    "location": "Lab A101"
}

# Kịch bản 2: Thiết bị hợp lệ kích hoạt báo động (Trạng thái DANGER do nhiệt độ và khói cao)
payload_danger = {
    "event_id": "evt-danger-1002",
    "timestamp": "2026-06-24T09:20:05Z",
    "device_id": "esp32-lab-a102",  # Khớp với DB của bạn
    "temperature_c": 45.0,         # Kích hoạt ngưỡng >= 40
    "humidity_percent": 55.0,
    "motion_detected": True,
    "co2_ppm": 1900,                # Kích hoạt ngưỡng >= 1800
    "smoke_ppm": 1.2,               # Kích hoạt ngưỡng >= 1.0
    "battery_percent": 85,
    "location": "Lab A102"
}

print("Đang bắn gói tin kiểm tra lên HiveMQ Cloud...")
client.publish(TOPIC, json.dumps(payload_normal), qos=1)
time.sleep(2)
client.publish(TOPIC, json.dumps(payload_danger), qos=1)
time.sleep(2)

client.loop_stop()
client.disconnect()
print("Bắn dữ liệu giả lập thành công!")