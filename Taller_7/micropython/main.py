"""
main.py
=======
Lanzador del Taller 7 (almacenado en Taller8) para Raspberry Pi Pico WH 1.
Control preciso de Servomotor de 180° (SG90 / MG90S) mediante modulación PWM a 50 Hz.
Recibe cualquier ángulo (0° a 180° o con decimales) vía MQTT y reporta telemetría.
"""

import gc
import machine
import time
from mqtt_client import PubSubMQTT
from servo import Servo
from wifi_manager import WiFiManager

# ----------------------------------------------------
# CONFIGURACIÓN
# ----------------------------------------------------
SSID = "TU_WIFI_AQUI"
PASSWORD = "TU_PASSWORD_AQUI"
BROKER = "broker.hivemq.com"
PORT = 1883
PREFIX = "UDFJC/iot_ws/robot0/"

SERVO_PIN = 12  # Pin GP12 conectado al cable de señal (naranja) del servomotor

unique_id = machine.unique_id().hex()
CLIENT_ID = f"pico_servo_{unique_id[-6:]}"


def main():
    print("==================================================")
    print("🤖 TALLER 7: CONTROL DE SERVOMOTOR 180° Y PWM")
    print("==================================================")

    # 1. Conexión Wi-Fi
    wifi = WiFiManager(SSID, PASSWORD)
    if not wifi.connect():
        return

    # 2. Conexión MQTT
    mqtt = PubSubMQTT(client_id=CLIENT_ID, broker=BROKER, port=PORT, prefix=PREFIX)
    mqtt.connect()

    # 3. Inicializar Servomotor
    # Rango estándar: 500 µs (0°) a 2500 µs (180°) a 50 Hz
    servo = Servo(
        pin=SERVO_PIN,
        min_us=500,
        max_us=2500,
        min_angle=0.0,
        max_angle=180.0,
        freq=50,
    )
    print(f"[+] Servomotor inicializado en GP{SERVO_PIN}. Posición inicial: {servo.get_angle()}°")

    # 4. Callback para recepción de comandos de ángulo
    def on_servo_command(topic, data):
        try:
            if isinstance(data, dict):
                # Soporta {"angle": 45.5} o {"value": 45.5}
                val = data.get("angle", data.get("value", 90.0))
            else:
                val = float(data)

            target_angle = float(val)

            # Ajustar servomotor
            pulse_us, duty = servo.set_angle(target_angle)
            actual_angle = servo.get_angle()

            print(f"[SERVO] Girando a {actual_angle:.1f}° | Pulso: {pulse_us:.0f} µs | Duty: {duty}")

            # Publicar confirmación de telemetría a Flet
            mqtt.publish("servo/status", {
                "device": CLIENT_ID,
                "angle": actual_angle,
                "pulse_us": round(pulse_us, 1),
                "duty_u16": duty,
                "status": "OK",
            })

        except Exception as err:
            print(f"[!] Error procesando comando de servo: {err}")

    # Suscribirse a los tópicos de control
    mqtt.subscribe("servo/angle", on_servo_command)
    mqtt.subscribe("servo/pos", on_servo_command)
    print(f"[+] Suscrito a:\n    - {PREFIX}servo/angle\n    - {PREFIX}servo/pos")

    # Notificar inicio
    mqtt.publish("servo/status", {
        "device": CLIENT_ID,
        "event": "ready",
        "initial_angle": servo.get_angle(),
    })

    last_heartbeat = time.time()

    # 5. Bucle principal no bloqueante
    while True:
        try:
            mqtt.check_msg()

            # Heartbeat periódico
            now = time.time()
            if now - last_heartbeat >= 10:
                last_heartbeat = now
                gc.collect()
                mqtt.publish("status", {
                    "device": CLIENT_ID,
                    "event": "heartbeat",
                    "servo_angle": servo.get_angle(),
                    "free_ram": gc.mem_free(),
                })

            time.sleep_ms(10)

        except OSError as e:
            print(f"[!] Reconectando por error de red: {e}")
            time.sleep(2)
            try:
                wifi.connect()
                mqtt.connect()
                mqtt.subscribe("servo/angle", on_servo_command)
                mqtt.subscribe("servo/pos", on_servo_command)
            except Exception:
                pass


if __name__ == "__main__":
    main()
