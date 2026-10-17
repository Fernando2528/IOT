from datetime import datetime
import json
import random
import flet as ft
import paho.mqtt.client as mqtt


def main(page: ft.Page):
    page.title = "Robot Control Center - Taller IoT"
    page.padding = 20
    page.theme_mode = ft.ThemeMode.DARK
    page.scroll = ft.ScrollMode.ALWAYS

    mqtt_client: mqtt.Client | None = None
    is_connected = False
    message_count = 0
    client_id = f"flet_robot_center_{random.randint(1000, 9999)}"

    # ==================================================
    # CONTENEDOR 1: Configuración y Conexión MQTT
    # ==================================================
    broker_field = ft.TextField(
        label="Broker MQTT",
        value="broker.hivemq.com",
        width=280,
    )

    port_field = ft.TextField(
        label="Puerto",
        value="1883",
        width=120,
    )

    prefix_field = ft.TextField(
        label="Prefijo / ID Robot",
        value="UDFJC/iot_ws/robot0/",
        width=280,
    )

    status_icon = ft.Icon(ft.Icons.CLOUD_OFF, color=ft.Colors.RED_400, size=20)
    status_text = ft.Text("Desconectado", color=ft.Colors.RED_400, weight=ft.FontWeight.W_600)
    status_row = ft.Row([status_icon, status_text], vertical_alignment=ft.CrossAxisAlignment.CENTER)

    connect_btn = ft.Button(
        content="Conectar",
        icon=ft.Icons.POWER_SETTINGS_NEW,
    )

    def toggle_connection(e):
        nonlocal is_connected, mqtt_client

        if not is_connected:
            broker = broker_field.value.strip() or "broker.hivemq.com"
            try:
                port = int(port_field.value.strip() or "1883")
            except ValueError:
                port = 1883

            status_text.value = "Conectando..."
            status_text.color = ft.Colors.AMBER_400
            status_icon.name = ft.Icons.CLOUD_SYNC
            status_icon.color = ft.Colors.AMBER_400
            page.update()

            try:
                mqtt_client = mqtt.Client(
                    mqtt.CallbackAPIVersion.VERSION2,
                    client_id=client_id,
                )
                mqtt_client.on_connect = on_connect
                mqtt_client.on_disconnect = on_disconnect
                mqtt_client.on_message = on_message

                mqtt_client.connect(broker, port, keepalive=60)
                mqtt_client.loop_start()

                is_connected = True
                connect_btn.content = "Desconectar"
                connect_btn.icon = ft.Icons.POWER_OFF
                broker_field.disabled = True
                port_field.disabled = True
                subscribe_btn.disabled = False
                publish_btn.disabled = False
                btn_led_on.disabled = False
                btn_led_off.disabled = False
                btn_ping.disabled = False

            except Exception as err:
                status_text.value = f"Error: {err}"
                status_text.color = ft.Colors.RED_400
                status_icon.name = ft.Icons.ERROR
                status_icon.color = ft.Colors.RED_400
                is_connected = False
            page.update()

        else:
            if mqtt_client is not None:
                try:
                    mqtt_client.loop_stop()
                    mqtt_client.disconnect()
                except Exception:
                    pass

            is_connected = False
            status_text.value = "Desconectado"
            status_text.color = ft.Colors.RED_400
            status_icon.name = ft.Icons.CLOUD_OFF
            status_icon.color = ft.Colors.RED_400
            connect_btn.content = "Conectar"
            connect_btn.icon = ft.Icons.POWER_SETTINGS_NEW
            broker_field.disabled = False
            port_field.disabled = False
            subscribe_btn.disabled = True
            publish_btn.disabled = True
            btn_led_on.disabled = True
            btn_led_off.disabled = True
            btn_ping.disabled = True
            page.update()

    connect_btn.on_click = toggle_connection

    container_config = ft.Card(
        content=ft.Container(
            content=ft.Column([
                ft.Text("1. Configuración & Conexión", size=18, weight=ft.FontWeight.BOLD),
                broker_field,
                port_field,
                prefix_field,
                connect_btn,
                status_row,
            ], spacing=12),
            padding=16,
        ),
        width=320,
    )

    # ==================================================
    # CONTENEDOR 2: Monitor y Suscripción en Tiempo Real
    # ==================================================
    sub_topic_field = ft.TextField(
        label="Tópico de Suscripción",
        value="UDFJC/iot_ws/robot0/#",
        width=380,
    )

    sub_status_label = ft.Text("Suscripción activa: Ninguna", size=12, color=ft.Colors.GREY_400)
    messages_count_label = ft.Text("Mensajes recibidos: 0", size=12, color=ft.Colors.CYAN_300)

    logs_list = ft.ListView(
        expand=True,
        spacing=6,
        auto_scroll=True,
        height=260,
    )

    def subscribe_to_topic(e):
        if not is_connected or mqtt_client is None:
            return
        topic = sub_topic_field.value.strip()
        if topic:
            mqtt_client.subscribe(topic)
            sub_status_label.value = f"Suscrito a: {topic}"
            sub_status_label.color = ft.Colors.GREEN_400
            add_log_entry("SISTEMA", f"Suscrito a {topic}", ft.Colors.BLUE_300)
            page.update()

    subscribe_btn = ft.Button(
        content="Suscribirse",
        icon=ft.Icons.PLAY_ARROW,
        disabled=True,
        on_click=subscribe_to_topic,
    )

    def clear_logs(e):
        nonlocal message_count
        logs_list.controls.clear()
        message_count = 0
        messages_count_label.value = "Mensajes recibidos: 0"
        page.update()

    clear_btn = ft.IconButton(
        icon=ft.Icons.DELETE_OUTLINE,
        tooltip="Limpiar Monitor",
        on_click=clear_logs,
    )

    def add_log_entry(topic: str, payload: str, color=ft.Colors.WHITE70):
        hora = datetime.now().strftime("%H:%M:%S")
        entry = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text(f"[{hora}]", size=11, color=ft.Colors.GREY_500, weight=ft.FontWeight.BOLD),
                    ft.Text(f"Topic: {topic}", size=11, color=ft.Colors.CYAN_300, weight=ft.FontWeight.BOLD),
                ], spacing=6),
                ft.Text(f"Payload: {payload}", size=12, color=color),
            ], spacing=2),
            bgcolor=ft.Colors.WHITE10,
            padding=6,
            border_radius=6,
        )
        logs_list.controls.append(entry)
        if len(logs_list.controls) > 100:
            logs_list.controls.pop(0)

    container_monitor = ft.Card(
        content=ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("2. Monitor de Recepción", size=18, weight=ft.FontWeight.BOLD),
                    clear_btn,
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                sub_topic_field,
                ft.Row([subscribe_btn, sub_status_label]),
                messages_count_label,
                logs_list,
            ], spacing=10),
            padding=16,
        ),
        width=420,
    )

    # ==================================================
    # CONTENEDOR 3: Publicación y Acciones del Robot
    # ==================================================
    pub_topic_field = ft.TextField(
        label="Tópico de Publicación",
        value="UDFJC/iot_ws/robot0/led/LED",
        width=300,
    )

    pub_payload_field = ft.TextField(
        label="Payload (Mensaje / JSON)",
        value='{"value": 1}',
        width=300,
    )

    last_action_text = ft.Text("Esperando acción...", size=12, color=ft.Colors.GREY_400)

    def publish_manual(e):
        if not is_connected or mqtt_client is None:
            return
        topic = pub_topic_field.value.strip()
        payload = pub_payload_field.value.strip()

        if topic:
            mqtt_client.publish(topic, payload)
            last_action_text.value = f"Publicado en {topic}"
            last_action_text.color = ft.Colors.GREEN_400
            page.update()

    publish_btn = ft.Button(
        content="Publicar Mensaje",
        icon=ft.Icons.SEND,
        disabled=True,
        on_click=publish_manual,
    )

    # Botones de Acción Rápida para la Raspberry Pi Pico WH
    def send_quick_command(topic_suffix: str, payload_obj: dict | str):
        if not is_connected or mqtt_client is None:
            return
        prefix = prefix_field.value.strip()
        full_topic = prefix + topic_suffix
        payload_str = json.dumps(payload_obj) if isinstance(payload_obj, dict) else str(payload_obj)

        mqtt_client.publish(full_topic, payload_str)
        last_action_text.value = f"Comando enviado a {full_topic}"
        last_action_text.color = ft.Colors.CYAN_300
        page.update()

    btn_led_on = ft.Button(
        content="Encender LED",
        icon=ft.Icons.LIGHTBULB,
        disabled=True,
        on_click=lambda e: send_quick_command("led/LED", {"value": 1}),
    )

    btn_led_off = ft.Button(
        content="Apagar LED",
        icon=ft.Icons.LIGHTBULB_OUTLINE,
        disabled=True,
        on_click=lambda e: send_quick_command("led/LED", {"value": 0}),
    )

    btn_ping = ft.Button(
        content="Ping Estado",
        icon=ft.Icons.REFRESH,
        disabled=True,
        on_click=lambda e: send_quick_command("cmd", {"action": "ping"}),
    )

    container_action = ft.Card(
        content=ft.Container(
            content=ft.Column([
                ft.Text("3. Publicación & Acciones", size=18, weight=ft.FontWeight.BOLD),
                pub_topic_field,
                pub_payload_field,
                publish_btn,
                ft.Divider(),
                ft.Text("Control Rápido Robot (Pico WH):", size=13, weight=ft.FontWeight.W_600),
                ft.Row([btn_led_on, btn_led_off], wrap=True),
                btn_ping,
                last_action_text,
            ], spacing=10),
            padding=16,
        ),
        width=340,
    )

    # --------------------------------------------------
    # Montaje Horizontal de la Interfaz
    # --------------------------------------------------
    page.add(
        ft.Column([
            ft.Text("🤖 ROBOT CONTROL CENTER", size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_300),
            ft.Text("Consola de Control y Monitoreo IoT - Modelo Publish / Subscribe", size=13, color=ft.Colors.GREY_400),
            ft.Row(
                [container_config, container_monitor, container_action],
                vertical_alignment=ft.CrossAxisAlignment.START,
                wrap=True,
                spacing=16,
            ),
        ], spacing=16)
    )

    # --------------------------------------------------
    # Callbacks de MQTT
    # --------------------------------------------------
    def on_connect(client, userdata, flags, rc, properties=None):
        if rc == 0:
            status_text.value = f"En línea ({broker_field.value})"
            status_text.color = ft.Colors.GREEN_400
            status_icon.name = ft.Icons.CLOUD_DONE
            status_icon.color = ft.Colors.GREEN_400

            initial_topic = sub_topic_field.value.strip()
            if initial_topic:
                client.subscribe(initial_topic)
                sub_status_label.value = f"Suscrito a: {initial_topic}"
                sub_status_label.color = ft.Colors.GREEN_400
                add_log_entry("SISTEMA", f"Conectado y suscrito a {initial_topic}", ft.Colors.GREEN_300)
        else:
            status_text.value = f"Fallo conexión ({rc})"
            status_text.color = ft.Colors.RED_400
            status_icon.name = ft.Icons.ERROR
            status_icon.color = ft.Colors.RED_400
            add_log_entry("ERROR", f"Fallo de conexión al broker. Código: {rc}", ft.Colors.RED_300)
        page.update()

    def on_disconnect(client, userdata, flags, rc, properties=None):
        status_text.value = "Desconectado del broker"
        status_text.color = ft.Colors.RED_400
        status_icon.name = ft.Icons.CLOUD_OFF
        status_icon.color = ft.Colors.RED_400
        page.update()

    def on_message(client, userdata, msg):
        nonlocal message_count
        topic = msg.topic
        try:
            payload = msg.payload.decode("utf-8")
        except UnicodeDecodeError:
            payload = str(msg.payload)

        message_count += 1
        messages_count_label.value = f"Mensajes recibidos: {message_count}"
        add_log_entry(topic, f"{payload}  ({len(msg.payload)} bytes)")
        page.update()


if __name__ == "__main__":
    ft.run(main)