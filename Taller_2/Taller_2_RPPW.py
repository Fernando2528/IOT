"""
ROBOT PICO WH - FIRMWARE MICROPYTHON (Thonny)
Taller IoT: Robot Control Center
Tarjeta: Raspberry Pi Pico WH 1
"""

import gc
import json
import machine
import network
import time
from machine import ADC, Pin
from umqtt.simple import MQTTClient

# --------------------------------------------------
# CONFIGURACIÓN DE RED Y MQTT
# --------------------------------------------------
SSID = "PruebaPi"          # Modificar con el SSID de tu red Wi-Fi
PASSWORD = "444555666777"  # Modificar con la contraseña Wi-Fi

MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
PREFIX = "UDFJC/iot_ws/robot0/"

# ID único por hardware para evitar colisiones en HiveMQ
unique_id = machine.unique_id().hex()
CLIENT_ID = f"pico_wh_{unique_id[-6:]}"

# Tópicos
TOPIC_LED = PREFIX + "led/LED"
TOPIC_CMD = PREFIX + "cmd"
TOPIC_STATUS = PREFIX + "status"
TOPIC_TELEMETRY = PREFIX + "telemetry"

# --------------------------------------------------
# HARDWARE PICO WH
# --------------------------------------------------
# En la Pico W / WH, el LED onboard se controla mediante "LED" (vía chip CYW43439)
led = Pin("LED", Pin.OUT)
led.value(0)

# Canal ADC 4: Sensor de temperatura interna del RP2040
sensor_temp = ADC(4)


def leer_temperatura():
    """Lee la temperatura interna del microcontrolador."""
    try:
        lectura = sensor_temp.read_u16() * (3.3 / 65535)
        temperatura = 27 - (lectura - 0.706) / 0.001721
        return round(temperatura, 1)
    except Exception:
        return 0.0


# --------------------------------------------------
# CONEXIÓN WI-FI
# --------------------------------------------------
def conectar_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():
        print(f"[*] Conectando a Wi-Fi: {SSID} ...")
        wlan.connect(SSID, PASSWORD)

        intentos = 0
        while not wlan.isconnected():
            led.toggle()
            time.sleep(0.5)
            intentos += 1
            if intentos > 30:
                print("[!] Tiempo de espera agotado al conectar a Wi-Fi.")
                return False

    ip = wlan.ifconfig()[0]
    led.value(0)
    print(f"[+] Wi-Fi conectado exitosamente. IP: {ip}")
    return True


# --------------------------------------------------
# CALLBACK MQTT: PROCESAR MENSAJES RECIBIDOS
# --------------------------------------------------
def on_message(topic_bytes, msg_bytes):
    try:
        topic = topic_bytes.decode("utf-8")
        payload_str = msg_bytes.decode("utf-8")

        print(f"\n[RX MQTT] Tópico: {topic}")
        print(f"          Payload: {payload_str}")

        try:
            data = json.loads(payload_str)
        except Exception:
            data = payload_str

        # 1. Control del LED onboard (Tópico: .../led/LED)
        if topic == TOPIC_LED:
            val = 0
            if isinstance(data, dict):
                val = int(data.get("value", 0))
            else:
                val = 1 if str(data).strip() in ("1", "true", "True", "on", "ON") else 0

            led.value(val)
            estado_txt = "ENCENDIDO" if val == 1 else "APAGADO"
            print(f"[ACTUADOR] LED físico ajustado a: {val} ({estado_txt})")

            # Publicar confirmación hacia el Robot Control Center
            respuesta = {
                "device": CLIENT_ID,
                "actuator": "LED",
                "state": val,
                "msg": f"LED {estado_txt}",
            }
            client.publish(TOPIC_STATUS.encode("utf-8"), json.dumps(respuesta).encode("utf-8"))

        # 2. Comandos generales (Tópico: .../cmd)
        elif topic == TOPIC_CMD:
            action = data.get("action", "") if isinstance(data, dict) else str(data)

            if "ping" in action.lower():
                respuesta = {
                    "device": CLIENT_ID,
                    "status": "online",
                    "uptime_s": time.ticks_ms() // 1000,
                    "led": led.value(),
                    "temp_c": leer_temperatura(),
                }
                client.publish(TOPIC_STATUS.encode("utf-8"), json.dumps(respuesta).encode("utf-8"))
                print("[+] Ping respondido.")

    except Exception as err:
        print(f"[!] Error procesando mensaje: {err}")


# --------------------------------------------------
# CLIENTE MQTT
# --------------------------------------------------
def conectar_mqtt():
    global client
    print(f"[*] Conectando al broker MQTT: {MQTT_BROKER}:{MQTT_PORT} ...")
    client = MQTTClient(
        client_id=CLIENT_ID,
        server=MQTT_BROKER,
        port=MQTT_PORT,
        keepalive=60,
    )
    client.set_callback(on_message)
    client.connect()
    print(f"[+] Conectado a HiveMQ como '{CLIENT_ID}'")

    # Suscribirse a los tópicos de entrada del robot
    client.subscribe(TOPIC_LED.encode("utf-8"))
    client.subscribe(TOPIC_CMD.encode("utf-8"))
    print(f"[+] Suscrito a:\n    - {TOPIC_LED}\n    - {TOPIC_CMD}")

    # Notificar al Robot Control Center que la Pico está en línea
    bienvenida = {
        "device": CLIENT_ID,
        "event": "connected",
        "msg": "Pico WH lista y conectada al Robot Control Center",
    }
    client.publish(TOPIC_STATUS.encode("utf-8"), json.dumps(bienvenida).encode("utf-8"))
    return client


# --------------------------------------------------
# BUCLE PRINCIPAL
# --------------------------------------------------
def main():
    if not conectar_wifi():
        return

    conectar_mqtt()

    # 3 parpadeos de confirmación
    for _ in range(3):
        led.value(1)
        time.sleep(0.1)
        led.value(0)
        time.sleep(0.1)

    print("\n==================================================")
    print("🚀 Pico WH lista. Esperando comandos desde Flet...")
    print("==================================================")

    ultimo_heartbeat = time.ticks_ms()
    INTERVALO_HEARTBEAT_MS = 10000  # Telemetría cada 10 segundos

    while True:
        try:
            # Atender paquetes MQTT entrantes de forma no bloqueante
            client.check_msg()

            # Enviar telemetría periódica al Monitor de Flet
            ahora = time.ticks_ms()
            if time.ticks_diff(ahora, ultimo_heartbeat) >= INTERVALO_HEARTBEAT_MS:
                ultimo_heartbeat = ahora
                gc.collect()

                telemetria = {
                    "device": CLIENT_ID,
                    "uptime_s": ahora // 1000,
                    "led_state": led.value(),
                    "temp_c": leer_temperatura(),
                    "free_ram_bytes": gc.mem_free(),
                }
                client.publish(TOPIC_TELEMETRY.encode("utf-8"), json.dumps(telemetria).encode("utf-8"))
                print(f"[TX Telemetría] Uptime: {ahora // 1000}s | Temp: {leer_temperatura()} °C")

            time.sleep_ms(20)

        except OSError as e:
            print(f"[!] Error de conexión: {e}. Reconectando...")
            time.sleep(2)
            try:
                conectar_wifi()
                conectar_mqtt()
            except Exception as re_err:
                print(f"[!] Falló reconexión: {re_err}")


if __name__ == "__main__":
    main()