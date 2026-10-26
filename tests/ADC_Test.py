import json
import machine
import time
from machine import ADC, Pin
from task import Task


# ==========================================================
# TAREA DE LECTURA ANALÓGICA (ADC)
# ==========================================================
class AnalogIn(Task):
    def __init__(self, scheduler, pubsub, gpio=28, period_ms=1000):
        self.pubsub = pubsub
        self.gpio = gpio
        # Inicialización del canal ADC
        self.adc = ADC(Pin(gpio))
        super().__init__(scheduler, period_ms=period_ms)
        print(f"Tarea AnalogIn iniciada en GP{gpio} (Periodo: {period_ms} ms)")

    def update(self):
        # Lectura de 16 bits sin signo (0 a 65535)
        raw_val = self.adc.read_u16()
        # Conversión al rango de tensión de referencia (0.0 V a 3.3 V)
        voltage = (raw_val * 3.3) / 65535

        # Registro formateado en la terminal
        print(
            f"[ADC GP{self.gpio}] Raw: {raw_val:<5} | Tensión: {voltage:.3f} V"
        )

        # Publicación hacia el broker MQTT
        payload = {
            "pin": f"GP{self.gpio}",
            "raw": raw_val,
            "voltage": round(voltage, 3),
        }
        self.pubsub.publish(f"adc/GP{self.gpio}", payload)


# ==========================================================
# LANZADOR PRINCIPAL
# ==========================================================
if __name__ == "__main__":
    from node import Node
    from pubsub_mqtt import PubSubMQTT
    from scheduler import Scheduler
    from watchdog_task import WatchdogTask
    from wifi_manager import WiFiManager

    SSID = "PruebaPi"
    PASSWORD = "444555666777"
    MQTT_BROKER = "broker.hivemq.com"

    unique_hw = machine.unique_id().hex()[-4:]
    session_salt = str(time.ticks_ms() % 10000)
    NODE_NAME = f"emb_adc_{unique_hw}_{session_salt}"
    PREFIX = "UDFJC/iot_ws/robot0/"

    scheduler = Scheduler()
    print("Iniciando conexión de red...")

    wifi = WiFiManager(ssid=SSID, password=PASSWORD)
    node = Node(prefix=PREFIX, node_name=NODE_NAME)

    PubSubMQTT(
        client_id=NODE_NAME,
        broker=MQTT_BROKER,
        scheduler=scheduler,
        node=node,
        period_ms=100,
        prefix=PREFIX,
    )

    WatchdogTask(scheduler=scheduler, pubsub=node, wifi=wifi, period_ms=9000)

    # Instanciación de la tarea ADC en GP28 (Pin 34) cada 1 segundo
    AnalogIn(scheduler, node, gpio=28, period_ms=1000)

    print(f"Sistema ADC activo bajo ID: '{NODE_NAME}'. Ejecutando scheduler...")
    scheduler.run()