import paho.mqtt.client as mqtt
import os
import ssl

HOST = os.getenv("MQTT_BROKER", "f6f78e87db4a4c189dd3d706745a5e93.s1.eu.hivemq.cloud")
PORT = int(os.getenv("MQTT_PORT", 8883))
USER = os.getenv("MQTT_USERNAME", "DVKN_IOT_2026")
PASS = os.getenv("MQTT_PASSWORD", "ThaiBao12A@")
TOPIC = os.getenv("OUT_TOPIC", "smart-campus/events/sensor")

def on_message(c, u, msg): 
    print(f"📊 NHẬN DỮ LIỆU THỰC TẾ (TỪ CLOUD):\n{msg.payload.decode()}\n")

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(USER, PASS)

# BẬT LẠI TLS
client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)

client.on_connect = lambda c, u, f, rc, p=None: c.subscribe(TOPIC) if rc == 0 else print(f"Lỗi kết nối: {rc}")
client.on_message = on_message

print(f"✅ Đang kết nối môi trường THỰC TẾ HiveMQ Cloud ({HOST}:{PORT}) và chờ dữ liệu...")
client.connect(HOST, PORT)
client.loop_forever()