import json
import machine
import time
from machine import PWM, Pin

# ==========================================================
# 1. ACTUADOR SERVOMOTOR SG90 (PWM EN GP12)
# ==========================================================
class ServoActuator:
    """
    Controlador PWM para el servomotor TowerPro SG90.
    Escucha en el tópico relativo 'servo/pos' y modula el ancho de pulso.
    """
    def __init__(self, pubsub, gpio_servo=12):
        self.pubsub = pubsub
        self.servo = PWM(Pin(gpio_servo))
        self.servo.freq(50)  # Frecuencia estándar del SG90 (periodo = 20 ms)
        self.pubsub.subscribe("servo/pos", self._on_servo_cmd)
        
        # Posición inicial por defecto: 0° (neutro / pulso de 1.5 ms)
        self.set_angle(0)
        print(f"Actuador Servo SG90 activo en GP{gpio_servo} (Frecuencia: 50 Hz).")

    def set_angle(self, angle):
        """
        Mapea el ángulo [-90, 90] a su correspondiente ancho de pulso:
          -90° -> 1000 us (1.0 ms)
            0° -> 1500 us (1.5 ms)
           90° -> 2000 us (2.0 ms)
        """
        # Restricción de límites mecánicos de seguridad
        angle = max(-90, min(90, angle))
        
        # Mapeo lineal a microsegundos
        pulse_us = int(1500 + (angle / 90.0) * 500)
        
        # Aplicación directa en nanosegundos (1 us = 1000 ns)
        self.servo.duty_ns(pulse_us * 1000)
        print(f"[SERVO GP12] Ángulo: {angle}° -> Ancho de pulso: {pulse_us} us")

    def _on_servo_cmd(self, *args, **kwargs):
        """Callback ejecutado al recibir un mensaje en 'servo/pos'."""
        try:
            msg = args[0] if len(args) > 0 else kwargs.get("msg", {})
            if isinstance(msg, (str, bytes)):
                data = json.loads(msg)
            elif isinstance(msg, dict):
                data = msg
            else:
                data = {"value": int(msg)}

            angle = int(data.get("value", 0))
            self.set_angle(angle)
        except Exception as e:
            print(f"[SERVO ERROR] Error al decodificar carga útil: {e}")


# ==========================================================
# 2. LANZADOR PRINCIPAL
# ==========================================================
if __name__ == "__main__":
    from node import Node
    from pubsub_mqtt import PubSubMQTT
    from scheduler import Scheduler
    from watchdog_task import WatchdogTask
    from wifi_manager import WiFiManager

    # Parámetros de red y Broker MQTT
    SSID = "PruebaPi"
    PASSWORD = "444555666777"
    MQTT_BROKER = "broker.hivemq.com"

    # Identificador único de sesión
    unique_hw = machine.unique_id().hex()[-4:]
    session_salt = str(time.ticks_ms() % 10000)
    NODE_NAME = f"servo_node_{unique_hw}_{session_salt}"
    PREFIX = "UDFJC/iot_ws/robot0/"

    # Instanciación de componentes base
    scheduler = Scheduler()
    wifi = WiFiManager(ssid=SSID, password=PASSWORD)
    node = Node(prefix=PREFIX, node_name=NODE_NAME)

    # Cliente MQTT periódico
    mqtt_task = PubSubMQTT(
        client_id=NODE_NAME,
        broker=MQTT_BROKER,
        scheduler=scheduler,
        node=node,
        period_ms=100,
        prefix=PREFIX,
    )

    # Watchdog de reconexión Wi-Fi
    WatchdogTask(scheduler=scheduler, pubsub=node, wifi=wifi, period_ms=9000)

    # Registro exclusivo del servomotor en GP12
    ServoActuator(node, gpio_servo=12)

    print(f"Pico W lista. Nodo activo: '{NODE_NAME}'")
    scheduler.run()