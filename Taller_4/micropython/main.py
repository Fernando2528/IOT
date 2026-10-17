"""
main.py
=======
Lanzador del Taller 4 en MicroPython (Raspberry Pi Pico WH 1).
Configura el Scheduler cooperativo y registra las 4 tareas concurrentes:
1. Task Sensores     (100 ms)
2. Task Telemetría   (1000 ms - Watchdog)
3. Task Estado       (50 ms  - Actuador LED)
4. Task MQTT         (20 ms  - Eventos de red)
"""

import machine
import time
from machine import ADC, Pin
from mqtt_client import MicroMQTTClient
from scheduler import Scheduler
from task import Task
from watchdog_task import WatchdogTask
from wifi_manager import WiFiManager

# ----------------------------------------------------
# CONFIGURACIÓN
# ----------------------------------------------------
SSID = "TU_WIFI_AQUI"
PASSWORD = "TU_PASSWORD_AQUI"
BROKER = "broker.hivemq.com"
PORT = 1883
PREFIX = "UDFJC/iot_ws/robot0/"

# Hardware
led = Pin("LED", Pin.OUT)
led.value(0)
adc_sensor = ADC(28)  # Pin GP28 (Entrada Analógica / Sensor)

unique_id = machine.unique_id().hex()
CLIENT_ID = f"pico_wh_{unique_id[-6:]}"

# Variables compartidas de estado
estado_led = 0
ultimo_valor_sensor = 0
simulate_lag_ms = 0


# ====================================================
# DEFINICIÓN DE TAREAS COOPERATIVAS
# ====================================================

# 1. Tarea de Lectura de Sensores (100 ms)
class TaskSensores(Task):
    def __init__(self, scheduler, period_ms=100):
        super().__init__(scheduler, period_ms, name="sensores", priority=3)

    def update(self):
        global ultimo_valor_sensor
        # Simulación o lectura real en GP28
        ultimo_valor_sensor = adc_sensor.read_u16()


# 2. Tarea de Actualización de Estado / Actuadores (50 ms)
class TaskEstadoActuadores(Task):
    def __init__(self, scheduler, period_ms=50):
        super().__init__(scheduler, period_ms, name="estado_actuadores", priority=1)

    def update(self):
        global simulate_lag_ms
        # Si se solicitó simular lentitud para demostrar el Scheduler/Watchdog:
        if simulate_lag_ms > 0:
            time.sleep_ms(simulate_lag_ms)
            simulate_lag_ms = 0

        led.value(estado_led)


# 3. Tarea de Eventos MQTT (20 ms)
class TaskMQTT(Task):
    def __init__(self, scheduler, mqtt_client, period_ms=20):
        super().__init__(scheduler, period_ms, name="mqtt_eventos", priority=1)
        self.mqtt = mqtt_client

    def update(self):
        self.mqtt.check_msg()


# ====================================================
# PROCESAMIENTO DE COMANDOS DESDE FLET
# ====================================================
def on_mqtt_message(topic, data):
    global estado_led, simulate_lag_ms

    print(f"[RX] {topic}: {data}")

    # Control de LED
    if topic.endswith("led/LED"):
        val = data.get("value", 0) if isinstance(data, dict) else int(data)
        estado_led = 1 if val in (1, "1", True) else 0

    # Simular tarea bloqueante (para ver el impacto en las métricas)
    elif topic.endswith("cmd/lag"):
        lag = data.get("ms", 50) if isinstance(data, dict) else int(data)
        simulate_lag_ms = lag
        print(f"[ALERTA] Provocando lag deliberado de {lag} ms en la siguiente vuelta")


# ====================================================
# PROGRAMA PRINCIPAL
# ====================================================
def main():
    print("Iniciando Taller 4: Scheduler y Multitarea Cooperativa...")

    wifi = WiFiManager(SSID, PASSWORD)
    if not wifi.connect():
        return

    mqtt = MicroMQTTClient(CLIENT_ID, broker=BROKER, port=PORT, on_message=on_mqtt_message)
    mqtt.connect()
    mqtt.subscribe(PREFIX + "led/LED")
    mqtt.subscribe(PREFIX + "cmd/lag")
    print(f"[+] Conectado a MQTT y suscrito a {PREFIX}#")

    # Instanciar el Scheduler
    scheduler = Scheduler()

    # Registrar las 4 tareas
    TaskSensores(scheduler, period_ms=100)
    WatchdogTask(scheduler, mqtt, wifi, period_ms=1000, prefix=PREFIX)
    TaskEstadoActuadores(scheduler, period_ms=50)
    TaskMQTT(scheduler, mqtt, period_ms=20)

    print(f"[+] Scheduler inicializado con {len(scheduler.tasks)} tareas.")
    print("Iniciando ejecución continua...")

    # Ejecutar scheduler
    scheduler.run()


if __name__ == "__main__":
    main()
