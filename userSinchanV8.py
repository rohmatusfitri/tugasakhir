import socket
import threading
import os
import time
import paho.mqtt.client as mqtt
import firebase_admin
from firebase_admin import credentials, db

# ----- Configuration -----
LISTEN_HOST = ''  # Bind ke semua interface
LISTEN_PORT = 9000
SAVE_DIR = 'received_images'
MQTT_BROKER = 'mustang.rmq.cloudamqp.com'
MQTT_PORT = 1883
MQTT_USERNAME = 'twjbbaoj:twjbbaoj'
MQTT_PASSWORD = 'yCgqaI_C9R482QBOoxmnTomAOLvNfdgQ'
TOPIC_SIREN = 'bts/siren'
TOPIC_ALERT = 'bts/alert'

# Firebase credentials
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://semhasinchan-default-rtdb.asia-southeast1.firebasedatabase.app'
})

os.makedirs(SAVE_DIR, exist_ok=True)

# ----- Helper Function to Receive Line -----
def recv_line(conn):
    buf = b''
    while True:
        chunk = conn.recv(1)
        if not chunk or chunk == b'\n':
            break
        buf += chunk
    return buf.decode('utf-8')

# ----- Socket Server Handler -----
def handle_client(conn, addr):
    print(f"Connection from {addr}")
    try:
        alert_msg = recv_line(conn)
        print("Received alert:", alert_msg)

        header = recv_line(conn)
        size = int(header.replace('SIZE:', ''))
        data = b''
        remaining = size
        while remaining > 0:
            chunk = conn.recv(min(4096, remaining))
            if not chunk:
                break
            data += chunk
            remaining -= len(chunk)

        filename = os.path.join(SAVE_DIR, f"intruder_{int(time.time())}.jpg")
        with open(filename, 'wb') as imgf:
            imgf.write(data)
        print(f"Image saved to {filename}")

    except Exception as e:
        print(f"Error handling client: {e}")
    finally:
        conn.close()

# ----- Socket Server -----
def start_socket_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((LISTEN_HOST, LISTEN_PORT))
        server.listen(5)
        print(f"Socket server listening on {LISTEN_HOST or '0.0.0.0'}:{LISTEN_PORT}")
        while True:
            conn, addr = server.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

# ----- MQTT Callback -----
def on_connect(client, userdata, flags, rc):
    print("Connected to MQTT broker with code", rc)
    client.subscribe([(TOPIC_ALERT, 0), (TOPIC_SIREN, 0)])

def on_message(client, userdata, msg):
    payload = msg.payload.decode('utf-8')
    print(f"[MQTT] Topic: {msg.topic}, Message: {payload}")

# ----- MQTT Setup -----
mqtt_client = mqtt.Client()
mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)

# ----- Firebase Monitoring (Optional) -----
def monitor_firebase():
    ref = db.reference('bts_intrusion')
    print("Monitoring Firebase for new intrusions...")
    while True:
        data = ref.get()
        if data:
            latest = list(data.items())[-1][1]
            print("Latest Firebase Entry:", latest)
        time.sleep(10)

# ----- Main Entry -----
if __name__ == '__main__':
    threading.Thread(target=start_socket_server, daemon=True).start()
    threading.Thread(target=monitor_firebase, daemon=True).start()
    mqtt_client.loop_forever()
