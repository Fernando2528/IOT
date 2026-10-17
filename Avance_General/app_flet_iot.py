import json
import flet as ft
import paho.mqtt.client as mqtt

BROKER = "broker.hivemq.com"
PORT = 1883
PREFIX = "UDFJC/iot_ws/robot0/"
TOPIC_SUB = PREFIX + "#"


def main(page: ft.Page):
    page.title = "Taller IoT - Pico W Dashboard"
    page.padding = 20
    page.scroll = ft.ScrollMode.ALWAYS

    # Buffer para limitar el log a un número fijo de líneas
    log_history = ["Esperando datos..."]

    # -----------------------------
    # Container 1 - Configuración
    # -----------------------------
    name_field = ft.TextField(label="Nombre", value="robot0", width=250)
    name_result = ft.Text("Configurado: robot0")

    def save_name(e):
        name_result.value = f"Nombre: {name_field.value}"
        page.update()

    save_button = ft.Button(content="Guardar", on_click=save_name)

    configuration = ft.Container(
        content=ft.Column([
            ft.Text("Configuración", size=20),
            name_field,
            save_button,
            name_result,
        ]),
        width=280,
        padding=10,
    )

    # -----------------------------
    # Container 2 - Monitor (Telemetría + Log rotativo)
    # -----------------------------
    gpio_label = ft.Text("GP1 (Digital): Desconocido", size=15)
    adc_label = ft.Text("GP28 (ADC): Esperando...", size=15)
    adc_progress = ft.ProgressBar(value=0, width=320)

    log_box = ft.Text(
        value="Esperando datos...",
        size=11,
    )

    monitor = ft.Container(
        content=ft.Column([
            ft.Text("Monitor", size=20),
            gpio_label,
            adc_label,
            adc_progress,
            ft.Text("Últimos mensajes:", size=13),
            log_box,
        ]),
        width=380,
        padding=10,
    )

    # -----------------------------
    # Container 3 - Acción (Control LED)
    # -----------------------------
    action_text = ft.Text("Estado LED: Esperando comando")

    def set_led(state: int):
        payload = json.dumps({"value": state})
        topic_led = PREFIX + "led/LED"
        mqtt_client.publish(topic_led, payload)
        action_text.value = f"Comando enviado: LED = {state}"
        page.update()

    btn_on = ft.Button(content="Encender LED", on_click=lambda e: set_led(1))
    btn_off = ft.Button(content="Apagar LED", on_click=lambda e: set_led(0))

    action = ft.Container(
        content=ft.Column([
            ft.Text("Control LED", size=20),
            ft.Row([btn_on, btn_off]),
            action_text,
        ]),
        width=280,
        padding=10,
    )

    # Montaje horizontal con alineación fija al inicio
    page.add(
        ft.Row(
            [configuration, monitor, action],
            vertical_alignment=ft.CrossAxisAlignment.START,
            wrap=True,
        )
    )

    # -----------------------------
    # Cliente MQTT
    # -----------------------------
    def on_connect(client, userdata, flags, rc, properties=None):
        if rc == 0:
            client.subscribe(TOPIC_SUB)
            log_history.clear()
            log_history.append("Conectado a HiveMQ")
            log_box.value = "\n".join(log_history)
            page.update()

    def on_message(client, userdata, msg):
        topic_recibido = msg.topic.replace(PREFIX, "")
        payload_recibido = msg.payload.decode("utf-8")

        # Filtrar estadísticas del watchdog para no saturar
        if topic_recibido == "watchdog/stats":
            return

        # Actualizar visualización de Entrada Digital
        if topic_recibido == "gpio/GP1":
            try:
                data = json.loads(payload_recibido)
                val = data.get("value", 0)
                gpio_label.value = f"GP1 (Digital): {'ALTO (1)' if val == 1 else 'BAJO (0)'}"
            except Exception:
                pass

        # Actualizar visualización del ADC
        elif topic_recibido == "AnalogIn_u16/GP28":
            try:
                data = json.loads(payload_recibido)
                raw_val = data.get("value", 0)
                volts = (raw_val / 65535.0) * 3.3
                adc_label.value = f"GP28 (ADC): {raw_val} ({volts:.2f} V)"
                adc_progress.value = min(max(raw_val / 65535.0, 0.0), 1.0)
            except Exception:
                pass

        # Actualizar buffer rotativo (máximo 8 líneas)
        log_history.append(f"[{topic_recibido}]: {payload_recibido}")
        if len(log_history) > 8:
            log_history.pop(0)

        log_box.value = "\n".join(log_history)
        page.update()

    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message

    mqtt_client.connect(BROKER, PORT, 60)
    mqtt_client.loop_start()


ft.run(main)