"""
main.py
=======
Lanzador principal en MicroPython para la Raspberry Pi Pico W
Proyecto de Segundo Corte: Coreografía y Gemelo Virtual (`robot12`)

Instrucciones de carga en la Raspberry Pi Pico W (Thonny):
    Copia TODOS los archivos dentro de `IOT_Corte_2/micropython/` directamente a la
    raíz `/` de la Raspberry Pi Pico W y ejecuta `main.py`.

Evaluaciones cubiertas:
1. Control del Carrobot por tópicos `motion/state` y `motion/sequence` (`motionTopics.md`).
2. Ejecución de línea recta (1 m) y 1/4 de círculo (R = 1 m).
3. Ubicación de los servos del brazo (`alpha1_deg`, `alpha2_deg`) con la demora asignada (`duration_s`).
4. Pantalla OLED SSD1306 mostrando la información del Watchdog con scroll controlado por potenciómetro.
5. Sincronización en vivo con el Gemelo Virtual Individual y Grupal para `robot12` (`even.json`).
"""

import machine
import time
from car import CAR
from motion_controller import CarrobotMotionTask
from node import Node
from oled_watchdog import OledWatchdogTask
from pubsub_mqtt import PubSubMQTT
from scheduler import Scheduler
from servo import Servo
from watchdog_task import WatchdogTask
from wifi_manager import WiFiManager

# ==============================================================================
# 1. IDENTIDAD DEL ROBOT Y RED MQTT (Grupo Materia 1, Grupo Proyecto 2 -> 12)
# ==============================================================================
SSID = "PruebaPi"
PASSWORD = "444555666777"
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883

ROBOT_ID = 12
BASE_PREFIX = "UDFJC/carrrobot"
PREFIX = f"{BASE_PREFIX}/robot{ROBOT_ID}/"

# ==============================================================================
# 2. PINES VERIFICADOS DEL PUENTE H L298N (RUEDAS IZQUIERDA Y DERECHA)
# ==============================================================================
PIN_IN1 = "GP16"  # Motor Izquierdo (Canal A) IN1
PIN_IN2 = "GP17"  # Motor Izquierdo (Canal A) IN2
PIN_IN3 = "GP18"  # Motor Derecho   (Canal B) IN3
PIN_IN4 = "GP19"  # Motor Derecho   (Canal B) IN4
PIN_ENA = "GP6"   # PWM Velocidad Motor Izquierdo (ENA)
PIN_ENB = "GP7"   # PWM Velocidad Motor Derecho   (ENB)

HALF_TRACK_D = 0.0675  # Semitrocha d (m) -> separación entre ruedas 2d = 13.5 cm
V_MAX = 0.25           # Velocidad lineal máxima de rueda a 100% PWM (m/s)
DEADZONE = 0.55        # Compensación de zona muerta de motorreductores (garantiza giro en coreografía)

# ==============================================================================
# 3. PINES DEL BRAZO ROBÓTICO (SERVOS SG90), POTENCIÓMETRO Y PANTALLA OLED I2C
# ==============================================================================
PIN_SERVO_ALPHA1 = "GP12"  # Servo Hombro (alpha1_deg)
PIN_SERVO_ALPHA2 = "GP13"  # Servo Codo   (alpha2_deg)
PIN_POT = "GP28"           # Potenciómetro ADC para scroll del Watchdog en OLED
PIN_OLED_SDA = "GP4"       # Pin SDA I2C para OLED SSD1306 (con auto-detección si está en otro par)
PIN_OLED_SCL = "GP5"       # Pin SCL I2C para OLED SSD1306


def main():
    print("==================================================================")
    print(f"🤖 PROYECTO CORTE 2: COREOGRAFÍA CARROBOT - ROBOT {ROBOT_ID} (PAR)")
    print(f"📡 Prefijo MQTT: {PREFIX}")
    print("==================================================================")

    unique_hw = machine.unique_id().hex()[-4:]
    session_salt = str(time.ticks_ms() % 10000)
    node_name = f"carrobot{ROBOT_ID}_{unique_hw}_{session_salt}"

    # 1. Crear Planificador Cooperativo
    scheduler = Scheduler()

    # 2. Conectar a Wi-Fi y sincronizar hora UTC por NTP
    wifi = WiFiManager(ssid=SSID, password=PASSWORD)
    if not wifi.is_connected():
        print("[!] No se pudo conectar a Wi-Fi. Verifica el hotspot 2.4 GHz.")
        return

    # 3. Inicializar Nodo PicoROS y Transporte MQTT
    node = Node(prefix=PREFIX, node_name=node_name)
    PubSubMQTT(
        client_id=node_name,
        broker=MQTT_BROKER,
        port=MQTT_PORT,
        scheduler=scheduler,
        node=node,
        period_ms=35,
        prefix=PREFIX,
        alias_prefixes=[
            f"UDFJC/carrrobot/robot{ROBOT_ID}/",
            f"UDFJC/carrobot/robot{ROBOT_ID}/",
            f"UDFJC/iot_ws/robot{ROBOT_ID}/",
        ],
    )

    # 4. Inicializar Chasis Diferencial (CAR)
    car = CAR(
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

    # 5. Inicializar Servomotores del Brazo (alpha1_deg y alpha2_deg)
    servo_alpha1 = Servo(pubsub=node, gpio=PIN_SERVO_ALPHA1, name="alpha1", center_offset_deg=90.0)
    servo_alpha2 = Servo(pubsub=node, gpio=PIN_SERVO_ALPHA2, name="alpha2", center_offset_deg=90.0)

    # 6. Inicializar Controlador de Coreografía y Estados (`motion/state` y `motion/sequence`)
    CarrobotMotionTask(
        scheduler=scheduler,
        pubsub=node,
        car=car,
        servo_alpha1=servo_alpha1,
        servo_alpha2=servo_alpha2,
        period_ms=20,
    )

    # 7. Inicializar Pantalla OLED SSD1306 con Scroll de Watchdog por Potenciómetro
    OledWatchdogTask(
        scheduler=scheduler,
        pubsub=node,
        pot_gpio=PIN_POT,
        sda_gpio=PIN_OLED_SDA,
        scl_gpio=PIN_OLED_SCL,
        period_ms=120,
        robot_label=f"robot{ROBOT_ID}",
    )

    # 8. Inicializar Watchdog (publica `watchdog/stats` cada 2 segundos para Gemelo Virtual y OLED)
    WatchdogTask(
        scheduler=scheduler,
        pubsub=node,
        wifi=wifi,
        period_ms=2000,
    )

    # 9. Ejecutar el planificador en tiempo real
    print(f"[+] Robot {ROBOT_ID} en línea. Esperando comandos en {PREFIX}motion/state y {PREFIX}motion/sequence...")
    scheduler.run()


if __name__ == "__main__":
    main()
