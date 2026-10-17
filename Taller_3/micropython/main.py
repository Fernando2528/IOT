"""
micropython.main
================
Firmware principal para Raspberry Pi Pico WH 1 (Thonny).
Taller 3: Arquitectura IoT, recepción de tareas programadas (Schedule) y actuadores.
"""

import gc
import machine
import network
import time
from machine import Pin
from mqtt import MicroMQTTClient

# ----------------------------------------------------
# CONFIGURACIÓN
# ----------------------------------------------------
SSID = "TU_WIFI_AQUI"          # Modificar con el SSID de tu red Wi-Fi
PASSWORD = "TU_PASSWORD_AQUI"  # Modificar con la contraseña Wi-Fi
BROKER = "broker.hivemq.com"
PORT = 1883
PREFIX = "UDFJC/iot_ws/robot0/"

# ID único de hardware
unique_id = machine.unique_id().hex()
CLIENT_ID = f"pico_wh_{unique_id[-6:]}"

# Hardware: LED Onboard en la Pico WH
led = Pin("LED", Pin.OUT)
led.value(0)

# Lista de tareas programadas pendientes: [{"name": str, "target_epoch_s": int, "action": str}]
pending_schedules = []


def conectar_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():
        print(f"[*] Conectando a Wi-Fi: {SSID}...")
        wlan.connect(SSID, PASSWORD)
        intentos = 0
        while not wlan.isconnected():
            led.toggle()
            time.sleep(0.5)
            intentos += 1
            if intentos > 30:
                print("[!] Error: No se pudo conectar al Wi-Fi.")
                return False

    led.value(0)
    print(f"[+] Wi-Fi OK. IP asignada: {wlan.ifconfig()[0]}")
    return True


def on_message_handler(topic, data):
    print(f"\n[RX MQTT] Tópico: {topic}")
    print(f"          Datos:  {data}")

    # 1. Mensaje de programación de tareas (Schedule)
    if topic == PREFIX + "schedule" and isinstance(data, dict):
        action = data.get("action")
        name = data.get("name", "tarea_sin_nombre")
        target_s = data.get("next_exec_epoch_s", 0)

        if action == "schedule" and target_s > 0:
            pending_schedules.append({
                "name": name,
                "target_epoch_s": target_s,
            })
            print(f"[SCHEDULE] Tarea '{name}' agendada para epoch {target_s}s")

            # Confirmar recepción de tarea
            mqtt_client.publish(PREFIX + "status", {
                "device": CLIENT_ID,
                "event": "schedule_accepted",
                "task": name,
                "target_epoch_s": target_s,
            })

    # 2. Comando directo de Actuador LED
    elif topic == PREFIX + "led/LED":
        val = 0
        if isinstance(data, dict):
            val = int(data.get("value", 0))
        else:
            val = 1 if str(data).strip() in ("1", "true", "on", "ON") else 0

        led.value(val)
        print(f"[ACTUADOR] LED físico ajustado a: {val}")

        mqtt_client.publish(PREFIX + "status", {
            "device": CLIENT_ID,
            "actuator": "LED",
            "state": val,
        })


def main():
    global mqtt_client

    if not conectar_wifi():
        return

    print(f"[*] Conectando al broker MQTT {BROKER}...")
    mqtt_client = MicroMQTTClient(
        client_id=CLIENT_ID,
        broker=BROKER,
        port=PORT,
        on_message=on_message_handler,
    )
    mqtt_client.connect()
    print(f"[+] MQTT conectado como '{CLIENT_ID}'")

    # Suscribirse a tópicos del robot
    mqtt_client.subscribe(PREFIX + "schedule")
    mqtt_client.subscribe(PREFIX + "led/LED")
    print(f"[+] Suscrito a:\n    - {PREFIX}schedule\n    - {PREFIX}led/LED")

    # 3 parpadeos de confirmación
    for _ in range(3):
        led.value(1)
        time.sleep(0.1)
        led.value(0)
        time.sleep(0.1)

    print("\n==================================================")
    print("🚀 Pico WH (Taller 3) lista y escuchando eventos...")
    print("==================================================")

    last_heartbeat = time.time()

    while True:
        try:
            # Procesar mensajes entrantes (no bloqueante)
            mqtt_client.check_msg()

            # Revisar si alguna tarea programada debe ejecutarse
            current_time = time.time()
            for sched in list(pending_schedules):
                if current_time >= sched["target_epoch_s"]:
                    print(f"\n[EJECUCIÓN] ¡Ejecutando tarea programada: '{sched['name']}'!")

                    # Acción demostrativa: parpadeo rápido del LED
                    for _ in range(4):
                        led.value(1)
                        time.sleep(0.1)
                        led.value(0)
                        time.sleep(0.1)

                    # Notificar finalización de la tarea
                    mqtt_client.publish(PREFIX + "status", {
                        "device": CLIENT_ID,
                        "event": "schedule_executed",
                        "task": sched["name"],
                        "executed_at_epoch_s": current_time,
                    })

                    pending_schedules.remove(sched)

            # Heartbeat periódico cada 10 segundos
            if current_time - last_heartbeat >= 10:
                last_heartbeat = current_time
                gc.collect()
                mqtt_client.publish(PREFIX + "status", {
                    "device": CLIENT_ID,
                    "event": "heartbeat",
                    "uptime_s": current_time,
                    "pending_tasks": len(pending_schedules),
                })

            time.sleep_ms(20)

        except OSError as e:
            print(f"[!] Error de conexión: {e}. Reintentando en 3s...")
            time.sleep(3)
            try:
                conectar_wifi()
                mqtt_client.connect()
                mqtt_client.subscribe(PREFIX + "schedule")
                mqtt_client.subscribe(PREFIX + "led/LED")
            except Exception:
                pass


if __name__ == "__main__":
    main()
