"""
main.py
=======
Lanzador del Taller 6 en MicroPython para Raspberry Pi Pico WH 1 (Thonny).
Mide el voltaje de la batería 18650 conectada al cargador TP4056 a través de un
divisor de voltaje conectado al pin GP28 (ADC2), y publica el valor digital por MQTT.
"""

import machine
import time
from analog_in import AnalogIn
from mqtt_client import PubSubMQTT
from scheduler import Scheduler
from wifi_manager import WiFiManager

# ----------------------------------------------------
# CONFIGURACIÓN
# ----------------------------------------------------
SSID = "TU_WIFI_AQUI"
PASSWORD = "TU_PASSWORD_AQUI"
MQTT_BROKER = "broker.hivemq.com"
PORT = 1883
PREFIX = "UDFJC/iot_ws/robot0/"

unique_id = machine.unique_id().hex()
NODE_NAME = f"emb_node_{unique_id[-4:]}"


def main():
    print("==================================================")
    print("🔋 TALLER 6: MONITOREO DE BATERÍA 18650 Y ADC")
    print("==================================================")

    # 1. Conexión Wi-Fi
    wifi = WiFiManager(ssid=SSID, password=PASSWORD)
    if not wifi.connect():
        return

    # 2. Conexión MQTT
    mqtt = PubSubMQTT(client_id=NODE_NAME, broker=MQTT_BROKER, port=PORT, prefix=PREFIX)
    mqtt.connect()

    # 3. Inicializar Scheduler y Tarea Analógica
    scheduler = Scheduler()

    # Configurar AnalogIn en el pin GP28 (ADC2) con lectura cada 1000 ms (1 segundo)
    analog_task = AnalogIn(
        scheduler=scheduler,
        pubsub=mqtt,
        gpio="GP28",
        period_ms=1000,
    )

    print("\n[+] Sistema listo:")
    print("    - Pin ADC: GP28")
    print(f"    - Tópico MQTT: {PREFIX}AnalogIn_u16/GP28")
    print("    - Periodo de muestreo: 1000 ms")
    print("Iniciando Scheduler...\n")

    # 4. Ejecutar el Scheduler
    scheduler.run()


if __name__ == "__main__":
    main()
