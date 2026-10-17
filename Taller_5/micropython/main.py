"""
main.py
=======
Lanzador del Taller 5 en MicroPython para Raspberry Pi Pico WH 1 (Thonny).
Integra:
1. GPIOOut en "LED": Actuador de Sirena / LED onboard.
2. GPIOIn en GP1: Sensor digital de puerta (Reed Switch o botón con pull-up).
3. IRIn en GP2: Receptor Infrarrojo de 38 kHz (Protocolo NEC).
"""

import gc
import machine
import time
from gpio_in import GPIOIn
from gpio_out import GPIOOut
from ir_in import IRIn
from mqtt_client import PubSubMQTT
from wifi_manager import WiFiManager

# ----------------------------------------------------
# CONFIGURACIÓN
# ----------------------------------------------------
SSID = "TU_WIFI_AQUI"
PASSWORD = "TU_PASSWORD_AQUI"
BROKER = "broker.hivemq.com"
PORT = 1883
PREFIX = "UDFJC/iot_ws/robot0/"

unique_id = machine.unique_id().hex()
CLIENT_ID = f"pico_alarm_{unique_id[-6:]}"


def main():
    print("==================================================")
    print("🚨 TALLER 5: CONTROL DE ACCESO, GPIOs & SENSOR IR")
    print("==================================================")

    # 1. Conexión Wi-Fi
    wifi = WiFiManager(SSID, PASSWORD)
    if not wifi.connect():
        return

    # 2. Conexión MQTT
    mqtt = PubSubMQTT(client_id=CLIENT_ID, broker=BROKER, port=PORT, prefix=PREFIX)
    mqtt.connect()

    # 3. Inicializar Periféricos de Hardware
    # Salida: LED Onboard actúa como Sirena de Alarma
    sirena_led = GPIOOut(pubsub=mqtt, gpio="LED")

    # Entrada: Sensor de Puerta en GP1 (Pull-up interno)
    sensor_puerta = GPIOIn(pubsub=mqtt, gpio="GP1", debounce_ms=40, invert=True)

    # Entrada: Receptor IR en GP2 (Demodulación 38 kHz)
    receptor_ir = IRIn(pubsub=mqtt, gpio=2, cooldown_ms=250)

    print("\n[+] Periféricos listos:")
    print("    - Salida (Sirena): LED Onboard")
    print("    - Entrada (Puerta): GP1")
    print("    - Entrada (Control IR): GP2")
    print("Esperando eventos...\n")

    last_heartbeat = time.time()

    # 4. Bucle principal no bloqueante
    while True:
        try:
            # Atender mensajes MQTT entrantes
            mqtt.check_msg()

            # Sondear cambios en la puerta física
            sensor_puerta.update()

            # Sondear señales del control remoto infrarrojo
            receptor_ir.update()

            # Heartbeat periódico cada 10 segundos
            now = time.time()
            if now - last_heartbeat >= 10:
                last_heartbeat = now
                gc.collect()
                mqtt.publish("status", {
                    "device": CLIENT_ID,
                    "event": "heartbeat",
                    "door_physical": sensor_puerta.value(),
                    "free_ram": gc.mem_free(),
                })

            time.sleep_ms(5)

        except OSError as e:
            print(f"[!] Error de red: {e}. Reconectando...")
            time.sleep(2)
            try:
                wifi.connect()
                mqtt.connect()
            except Exception:
                pass


if __name__ == "__main__":
    main()
