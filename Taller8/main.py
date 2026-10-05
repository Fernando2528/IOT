from datetime import datetime
import json
import random
import threading
import flet as ft
import paho.mqtt.client as mqtt

# ================= CONFIGURACIÓN MQTT =================
BROKER = "broker.hivemq.com"
PORT = 1883
PREFIX = "UDFJC/iot_ws/robot0/"
TOPIC_CMD = f"{PREFIX}cmd"
TOPIC_STATUS = f"{PREFIX}status"

# ID de cliente único para evitar colisiones en HiveMQ
CLIENT_ID = f"flet_l298n_gui_{random.randint(1000, 9999)}"


def main(page: ft.Page):
    page.title = "Control Robot L298N (5V) - Raspberry Pi Pico W"
    page.window_width = 540
    page.window_height = 750
    page.window_resizable = True
    page.padding = 20
    page.theme_mode = ft.ThemeMode.DARK

    # --- Estado de Conexión al Broker ---
    mqtt_status_icon = ft.Icon(ft.Icons.CLOUD_OFF, color=ft.Colors.RED_400, size=18)
    mqtt_status_text = ft.Text("Conectando a HiveMQ...", size=12, color=ft.Colors.GREY_400)

    # --- Tarjeta de Instrucción en Curso ---
    current_task_text = ft.Text(
        "En reposo (Listo)",
        weight=ft.FontWeight.W_600,
        color=ft.Colors.GREEN_400,
        size=14,
    )
    task_spinner = ft.ProgressRing(width=16, height=16, stroke_width=2, visible=False)

    current_task_card = ft.Card(
        content=ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text(
                                "INSTRUCCIÓN EN CURSO",
                                size=11,
                                color=ft.Colors.GREY_400,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Container(
                                content=ft.Text("Driver: L298N @ 5V", size=10, color=ft.Colors.CYAN_300),
                                bgcolor=ft.Colors.WHITE10,
                                # Corregido: uso de ft.Padding con parámetros explícitos
                                padding=ft.Padding(left=6, top=2, right=6, bottom=2),
                                border_radius=4,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Row(
                        controls=[task_spinner, current_task_text],
                        alignment=ft.MainAxisAlignment.START,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                spacing=6,
            ),
            padding=12,
        ),
        elevation=2,
    )

    # --- Lista de Logs de la Sesión ---
    logs_list = ft.ListView(
        expand=True,
        spacing=6,
        auto_scroll=True,
    )

    def agregar_log(mensaje: str, color_texto=ft.Colors.WHITE70):
        hora = datetime.now().strftime("%H:%M:%S")
        logs_list.controls.append(
            ft.Row(
                controls=[
                    ft.Text(f"[{hora}]", size=12, color=ft.Colors.GREY_500, weight=ft.FontWeight.BOLD),
                    ft.Text(mensaje, size=12, color=color_texto, expand=True),
                ],
                spacing=8,
            )
        )
        page.update()

    def set_estado_botones(habilitado: bool):
        for btn in action_buttons:
            btn.disabled = not habilitado
        page.update()

    # --- Manejadores de Eventos MQTT ---
    def on_mqtt_connect(client, userdata, flags, rc, properties=None):
        if rc == 0:
            mqtt_status_icon.name = ft.Icons.CLOUD_DONE
            mqtt_status_icon.color = ft.Colors.GREEN_400
            mqtt_status_text.value = f"En línea ({BROKER})"
            mqtt_status_text.color = ft.Colors.GREEN_400
            client.subscribe(TOPIC_STATUS)
            agregar_log(f"Conexión MQTT establecida. Escuchando: {TOPIC_STATUS}", ft.Colors.BLUE_300)
        else:
            mqtt_status_icon.name = ft.Icons.ERROR
            mqtt_status_icon.color = ft.Colors.RED_400
            mqtt_status_text.value = f"Error conexión ({rc})"
            agregar_log(f"Fallo de conexión al broker MQTT. Código: {rc}", ft.Colors.RED_400)
        page.update()

    def on_mqtt_message(client, userdata, msg):
        """Procesa las notificaciones de estado enviadas por la Pico W"""
        try:
            payload_str = msg.payload.decode("utf-8")
            data = json.loads(payload_str)
            estado = data.get("state", "")
            mensaje = data.get("message", payload_str)

            if estado == "in_progress":
                current_task_text.value = f"Ejecutando: {mensaje}"
                current_task_text.color = ft.Colors.AMBER_400
                task_spinner.visible = True
                set_estado_botones(False)
                agregar_log(f"Pico W: {mensaje}", ft.Colors.AMBER_300)

            elif estado == "completed":
                current_task_text.value = "En reposo (Listo)"
                current_task_text.color = ft.Colors.GREEN_400
                task_spinner.visible = False
                set_estado_botones(True)
                agregar_log(f"Pico W: {mensaje}", ft.Colors.GREEN_300)

            elif estado in ("stopped", "error"):
                current_task_text.value = "En reposo (Detenido)"
                current_task_text.color = ft.Colors.RED_400
                task_spinner.visible = False
                set_estado_botones(True)
                agregar_log(f"Pico W [{estado.upper()}]: {mensaje}", ft.Colors.RED_300)

            page.update()
        except Exception as err:
            agregar_log(f"Error procesando telemetría MQTT: {err}", ft.Colors.RED_400)

    # --- Inicialización del Cliente MQTT ---
    try:
        mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=CLIENT_ID)
    except AttributeError:
        mqtt_client = mqtt.Client(client_id=CLIENT_ID)

    mqtt_client.on_connect = on_mqtt_connect
    mqtt_client.on_message = on_mqtt_message

    def conectar_broker():
        try:
            mqtt_client.connect(BROKER, PORT, keepalive=60)
            mqtt_client.loop_start()
        except Exception as err:
            agregar_log(f"No se pudo conectar al broker: {err}", ft.Colors.RED_400)

    threading.Thread(target=conectar_broker, daemon=True).start()

    # --- Función de Despacho de Comandos ---
    def despachar_comando(comando_dict: dict, descripcion: str):
        try:
            payload = json.dumps(comando_dict)
            mqtt_client.publish(TOPIC_CMD, payload)
            agregar_log(f"Comando enviado: {descripcion}", ft.Colors.CYAN_300)
        except Exception as err:
            agregar_log(f"Error enviando comando: {err}", ft.Colors.RED_400)

    def limpiar_logs(_):
        logs_list.controls.clear()
        agregar_log("Historial reiniciado.", ft.Colors.GREY_400)

    # --- Botones de Control de Trayectoria ---
    btn_recto = ft.ElevatedButton(
        "Avanzar 1 metro recto",
        icon=ft.Icons.ARROW_UPWARD,
        expand=True,
        on_click=lambda _: despachar_comando(
            {"action": "straight", "distance": 1.0},
            "Avanzar 1 metro recto"
        ),
    )

    btn_arco_izq = ft.ElevatedButton(
        "Arco 1m (Izq)",
        icon=ft.Icons.TURN_LEFT,
        expand=True,
        on_click=lambda _: despachar_comando(
            {"action": "arc", "direction": "left", "radius": 1.0},
            "Arco 1/4 círculo Izquierda (R=1m)"
        ),
    )

    btn_arco_der = ft.ElevatedButton(
        "Arco 1m (Der)",
        icon=ft.Icons.TURN_RIGHT,
        expand=True,
        on_click=lambda _: despachar_comando(
            {"action": "arc", "direction": "right", "radius": 1.0},
            "Arco 1/4 círculo Derecha (R=1m)"
        ),
    )

    btn_stop = ft.OutlinedButton(
        "Detener Motores",
        icon=ft.Icons.STOP,
        style=ft.ButtonStyle(color=ft.Colors.RED_300),
        expand=True,
        on_click=lambda _: despachar_comando(
            {"action": "stop"},
            "Parada forzada de motores"
        ),
    )

    action_buttons = [btn_recto, btn_arco_izq, btn_arco_der, btn_stop]

    # --- Borde compatible multi-versión ---
    borde_contenedor = ft.Border(
        top=ft.BorderSide(1, ft.Colors.GREY_800),
        bottom=ft.BorderSide(1, ft.Colors.GREY_800),
        left=ft.BorderSide(1, ft.Colors.GREY_800),
        right=ft.BorderSide(1, ft.Colors.GREY_800),
    )

    # --- Montaje de la Vista ---
    page.add(
        ft.Row(
            controls=[
                ft.Text("Control Robot Autónomo", size=18, weight=ft.FontWeight.BOLD),
                ft.Row([mqtt_status_icon, mqtt_status_text], spacing=6),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        current_task_card,
        ft.Divider(),
        ft.Text("Comandos de Trayectoria:", weight=ft.FontWeight.W_500),
        ft.Row([btn_recto]),
        ft.Row([btn_arco_izq, btn_arco_der]),
        ft.Row([btn_stop]),
        ft.Divider(),
        ft.Row(
            controls=[
                ft.Text("Historial de la Sesión", weight=ft.FontWeight.BOLD, size=14),
                ft.IconButton(
                    icon=ft.Icons.DELETE_SWEEP,
                    tooltip="Limpiar historial",
                    on_click=limpiar_logs,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        ft.Container(
            content=logs_list,
            border=borde_contenedor,
            border_radius=8,
            padding=10,
            expand=True,
            bgcolor=ft.Colors.BLACK26,
        ),
    )


if __name__ == "__main__":
    ft.app(target=main)