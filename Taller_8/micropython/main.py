"""
main.py
=======
Lanzador principal del Proyecto Final (Taller 8: CAR - Cinemática Diferencial)
para Raspberry Pi Pico W.

Integra todos los conceptos desarrollados en el curso:
- Gestor de red Wi-Fi (WiFiManager)
- Planificador cooperativo de tareas en tiempo real (Scheduler + Task)
- Bus de mensajes distribuido (Node + PubSubMQTT)
- Supervisión de salud del sistema (WatchdogTask)
- Control cinemático diferencial de las dos ruedas (Clase CAR en GP19, GP18, GP17, GP16)
- Control PWM de servomotor auxiliar del brazo mecánico (Clase Servo en GP12)
"""

import machine
import time
from car import CAR
from node import Node
from pubsub_mqtt import PubSubMQTT
from scheduler import Scheduler
from servo import Servo
from watchdog_task import WatchdogTask
from wifi_manager import WiFiManager

# ==========================================================
# CONFIGURACIÓN DE RED Y HARDWARE
# ==========================================================
SSID = "PruebaPi"
PASSWORD = "444555666777"
MQTT_BROKER = "broker.hivemq.com"
PORT = 1883
PREFIX = "UDFJC/iot_ws/robot0/"

# Pines del Puente H según el esquema oficial del Taller 8:
# GP19 -> IN1, GP18 -> IN2 (Motor Izquierdo / A)
# GP17 -> IN3, GP16 -> IN4 (Motor Derecho   / B)
PIN_IN1 = "GP19"
PIN_IN2 = "GP18"
PIN_IN3 = "GP17"
PIN_IN4 = "GP16"

# Si utilizas un L298N con jumpers ENA/ENB retirados (6 hilos), puedes definir:
# PIN_ENA = "GP6"
# PIN_ENB = "GP7"
PIN_ENA = None
PIN_ENB = None

# Parámetros físicos del chasis diferencial (ajustables también desde Flet):
HALF_TRACK_D = 0.0675  # Distancia d del centro a cada rueda (m) -> 2*d = 13.5 cm entre ruedas
V_MAX = 0.25           # Rapidez máxima de rueda con batería 18650 a 100% PWM (m/s)
DEADZONE = 0.28        # Compensación de fricción estática para motorreductores TT


def main():
    print("==========================================================")
    print("🚗 PROYECTO FINAL (TALLER 8): SISTEMA INTEGRAL CAR IoT")
    print("==========================================================")

    unique_hw = machine.unique_id().hex()[-4:]
    session_salt = str(time.ticks_ms() % 10000)
    node_name = f"emb_car_{unique_hw}_{session_salt}"

    # 1. Crear Planificador Cooperativo
    scheduler = Scheduler()

    # 2. Conectar a Wi-Fi
    wifi = WiFiManager(ssid=SSID, password=PASSWORD)

    # 3. Inicializar Nodo PicoROS y Transporte MQTT
    node = Node(prefix=PREFIX, node_name=node_name)
    PubSubMQTT(
        client_id=node_name,
        broker=MQTT_BROKER,
        port=PORT,
        scheduler=scheduler,
        node=node,
        period_ms=40,
        prefix=PREFIX,
    )

    # 4. Inicializar Watchdog y Telemetría de Estado
    WatchdogTask(scheduler=scheduler, pubsub=node, wifi=wifi, period_ms=8000)

    # 5. Inicializar Clase CAR (Cinemática Diferencial en GP19, GP18, GP17, GP16)
    CAR(
        scheduler=scheduler,
        pubsub=node,
        in1=PIN_IN1,
        in2=PIN_IN2,
        in3=PIN_IN3,
        in4=PIN_IN4,
        ena=PIN_ENA,
        enb=PIN_ENB,
        d=HALF_TRACK_D,
        v_max=V_MAX,
        deadzone=DEADZONE,
        period_ms=20,
    )

    # 6. Inicializar Servomotor Auxiliar (Brazo Mecánico en GP12)
    Servo(pubsub=node, gpio="GP12")

    # Publicar mensaje de inicio
    node.publish(
        "CAR/status",
        {
            "state": "ready",
            "message": f"Robot CAR en línea ({node_name}) | Pines: {PIN_IN1},{PIN_IN2},{PIN_IN3},{PIN_IN4}",
            "d": HALF_TRACK_D,
            "v_max": V_MAX,
        },
    )

    # 7. Ejecutar bucle principal cooperativo
    scheduler.run()


if __name__ == "__main__":
    main()
