"""
flet.main
=========
Interfaz Gráfica del Taller 3 (Flet).
Demuestra:
1. Conexión y publicación MQTT mediante el módulo flet.mqtt.
2. Uso de la estructura de datos definida en common.messages.create_schedule.
3. Validación en tiempo real de los mensajes recibidos desde la Raspberry Pi Pico WH.
"""

from datetime import datetime
import json
import random
import flet as ft

from common.messages import (
    create_command,
    create_schedule,
    validate_schedule_message,
)
from flet.mqtt import MqttClientHandler


def main(page: ft.Page):
    page.title = "Taller 3 - Arquitectura IoT & Validación de Datos"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 20
    page.scroll = ft.ScrollMode.ALWAYS

    client_id = f"flet_taller3_{random.randint(1000, 9999)}"
    prefix = "UDFJC/iot_ws/robot0/"

    # ----------------------------------------------------
    # Panel 1: Conexión MQTT
    # ----------------------------------------------------
    broker_input = ft.TextField(label="Broker", value="broker.hivemq.com", width=260)
    port_input = ft.TextField(label="Puerto", value="1883", width=100)

    icon_status = ft.Icon(ft.Icons.CLOUD_OFF, color=ft.Colors.RED_400, size=20)
    text_status = ft.Text("Desconectado", color=ft.Colors.RED_400, weight=ft.FontWeight.W_600)
    status_row = ft.Row([icon_status, text_status])

    btn_connect = ft.Button(content="Conectar", icon=ft.Icons.POWER_SETTINGS_NEW)

    def on_conn_change(connected: bool, info: str):
        if connected:
            icon_status.name = ft.Icons.CLOUD_DONE
            icon_status.color = ft.Colors.GREEN_400
            text_status.value = "En línea"
            text_status.color = ft.Colors.GREEN_400
            btn_connect.content = "Desconectar"
            btn_connect.icon = ft.Icons.POWER_OFF
            btn_send_schedule.disabled = False
            btn_led_on.disabled = False
            btn_led_off.disabled = False

            # Suscribir a todos los sub-tópicos del robot
            mqtt_handler.subscribe(prefix + "#")
            add_log("SISTEMA", f"Conectado y suscrito a {prefix}#", ft.Colors.GREEN_300)
        else:
            icon_status.name = ft.Icons.CLOUD_OFF
            icon_status.color = ft.Colors.RED_400
            text_status.value = info
            text_status.color = ft.Colors.RED_400
            btn_connect.content = "Conectar"
            btn_connect.icon = ft.Icons.POWER_SETTINGS_NEW
            btn_send_schedule.disabled = True
            btn_led_on.disabled = True
            btn_led_off.disabled = True
            add_log("SISTEMA", "Desconectado del broker", ft.Colors.RED_300)
        page.update()

    def on_msg_received(topic: str, payload_str: str):
        tag_color = ft.Colors.CYAN_300
        # Verificar si el payload es un mensaje de tipo schedule o comando
        try:
            data = json.loads(payload_str)
            if isinstance(data, dict) and data.get("action") == "schedule":
                is_valid = validate_schedule_message(data)
                valid_txt = "✅ VÁLIDO" if is_valid else "❌ INVÁLIDO"
                add_log(topic, f"{payload_str} [{valid_txt}]", ft.Colors.AMBER_300 if is_valid else ft.Colors.RED_400)
                return
        except Exception:
            pass

        add_log(topic, payload_str, tag_color)
        page.update()

    mqtt_handler = MqttClientHandler(
        client_id=client_id,
        on_connect_callback=on_conn_change,
        on_message_callback=on_msg_received,
    )

    def toggle_connection(e):
        if not mqtt_handler.is_connected:
            text_status.value = "Conectando..."
            text_status.color = ft.Colors.AMBER_400
            icon_status.name = ft.Icons.CLOUD_SYNC
            icon_status.color = ft.Colors.AMBER_400
            page.update()
            try:
                mqtt_handler.connect(
                    broker=broker_input.value.strip() or "broker.hivemq.com",
                    port=int(port_input.value.strip() or 1883),
                )
            except Exception as err:
                on_conn_change(False, f"Error: {err}")
        else:
            mqtt_handler.disconnect()
            on_conn_change(False, "Desconectado")

    btn_connect.on_click = toggle_connection

    card_connection = ft.Card(
        content=ft.Container(
            content=ft.Column([
                ft.Text("1. Conexión MQTT", size=18, weight=ft.FontWeight.BOLD),
                broker_input,
                port_input,
                btn_connect,
                status_row,
            ], spacing=10),
            padding=16,
        ),
        width=300,
    )

    # ----------------------------------------------------
    # Panel 2: Generador de Estructura de Datos (Schedule)
    # ----------------------------------------------------
    task_name_input = ft.TextField(label="Nombre de Tarea", value="blink_sequence", width=300)
    delay_input = ft.TextField(label="Retardo (segundos)", value="5.0", width=140)

    json_preview = ft.Text(
        value="Vista previa JSON...",
        size=11,
        color=ft.Colors.GREY_300,
        selectable=True,
    )

    def preview_json(e):
        try:
            delay = float(delay_input.value)
            msg = create_schedule(task_name_input.value.strip() or "task", delay)
            json_preview.value = json.dumps(msg, indent=2)
        except Exception as err:
            json_preview.value = f"Error: {err}"
        page.update()

    btn_preview = ft.Button(content="Generar Preview", icon=ft.Icons.DATA_OBJECT, on_click=preview_json)

    def send_schedule(e):
        try:
            delay = float(delay_input.value)
            name = task_name_input.value.strip() or "task"
            msg = create_schedule(name, delay)
            topic = prefix + "schedule"
            mqtt_handler.publish(topic, msg)
            add_log("SALIDA", f"Publicado schedule '{name}' en {topic}", ft.Colors.GREEN_400)
        except Exception as err:
            add_log("ERROR", f"Fallo al publicar: {err}", ft.Colors.RED_400)
        page.update()

    btn_send_schedule = ft.Button(
        content="Publicar Tarea (MQTT)",
        icon=ft.Icons.SEND,
        disabled=True,
        on_click=send_schedule,
    )

    card_schedule = ft.Card(
        content=ft.Container(
            content=ft.Column([
                ft.Text("2. Programación (Schedule)", size=18, weight=ft.FontWeight.BOLD),
                task_name_input,
                delay_input,
                ft.Row([btn_preview, btn_send_schedule], wrap=True),
                ft.Text("Estructura JSON generada:", size=12, color=ft.Colors.GREY_400),
                ft.Container(
                    content=json_preview,
                    bgcolor=ft.Colors.BLACK54,
                    padding=10,
                    border_radius=6,
                ),
            ], spacing=10),
            padding=16,
        ),
        width=340,
    )

    # ----------------------------------------------------
    # Panel 3: Control Rápido de Actuadores
    # ----------------------------------------------------
    def send_cmd_led(val: int):
        cmd = create_command(action="set", value=val, target="led")
        topic = prefix + "led/LED"
        mqtt_handler.publish(topic, cmd)
        add_log("SALIDA", f"Comando enviado a {topic} -> {cmd}", ft.Colors.BLUE_300)
        page.update()

    btn_led_on = ft.Button(
        content="Encender LED",
        icon=ft.Icons.LIGHTBULB,
        disabled=True,
        on_click=lambda e: send_cmd_led(1),
    )

    btn_led_off = ft.Button(
        content="Apagar LED",
        icon=ft.Icons.LIGHTBULB_OUTLINE,
        disabled=True,
        on_click=lambda e: send_cmd_led(0),
    )

    card_actuators = ft.Card(
        content=ft.Container(
            content=ft.Column([
                ft.Text("3. Control Directo", size=18, weight=ft.FontWeight.BOLD),
                ft.Text("Comandos inmediatos al robot:", size=12, color=ft.Colors.GREY_400),
                ft.Row([btn_led_on, btn_led_off], wrap=True),
            ], spacing=10),
            padding=16,
        ),
        width=280,
    )

    # ----------------------------------------------------
    # Panel 4: Monitor y Verificación en Tiempo Real
    # ----------------------------------------------------
    logs_list = ft.ListView(expand=True, spacing=6, auto_scroll=True, height=260)

    def clear_logs(e):
        logs_list.controls.clear()
        page.update()

    btn_clear = ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, tooltip="Limpiar Log", on_click=clear_logs)

    def add_log(tag: str, msg: str, color=ft.Colors.WHITE70):
        hora = datetime.now().strftime("%H:%M:%S")
        entry = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text(f"[{hora}]", size=11, color=ft.Colors.GREY_500, weight=ft.FontWeight.BOLD),
                    ft.Text(f"[{tag}]", size=11, color=color, weight=ft.FontWeight.BOLD),
                ], spacing=6),
                ft.Text(msg, size=12, color=ft.Colors.WHITE),
            ], spacing=2),
            bgcolor=ft.Colors.WHITE10,
            padding=6,
            border_radius=6,
        )
        logs_list.controls.append(entry)
        if len(logs_list.controls) > 100:
            logs_list.controls.pop(0)

    card_monitor = ft.Card(
        content=ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("4. Monitor de Mensajes", size=18, weight=ft.FontWeight.BOLD),
                    btn_clear,
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                logs_list,
            ], spacing=10),
            padding=16,
        ),
        width=560,
    )

    # ----------------------------------------------------
    # Montaje General
    # ----------------------------------------------------
    page.add(
        ft.Column([
            ft.Text(
                "🚀 TALLER 3: ARQUITECTURA IoT & PROCESO DE DISEÑO",
                size=22,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.CYAN_300,
            ),
            ft.Text(
                "Estructuras de datos JSON, pruebas automatizadas y comunicación MQTT",
                size=13,
                color=ft.Colors.GREY_400,
            ),
            ft.Row(
                [card_connection, card_schedule, card_actuators],
                wrap=True,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
            card_monitor,
        ], spacing=16)
    )


if __name__ == "__main__":
    ft.run(main)
