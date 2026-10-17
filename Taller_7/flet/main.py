"""
flet/main.py
============
Panel de Control Gráfico IoT para Servomotor 180° y Actuadores PWM (Taller 7 / Taller 8).
Desarrollado para Universidad Distrital Francisco José de Caldas (UDFJC).

Características Principales:
1. Campo de texto EDITABLE para los grados (ft.TextField), permitiendo ingresar
   cualquier ángulo exacto (0.0° a 180.0°) tal como lo solicitó el docente.
2. Control deslizante sincronizado (ft.Slider) en tiempo real.
3. Botones de presets rápidos (0°, 45°, 90°, 135°, 180°).
4. Modo de barrido oscilatorio continuo para verificación mecánica.
5. Telemetría en vivo: Ángulo confirmado, Ancho de pulso (µs) y Ciclo de trabajo (duty_u16).
6. Panel complementario para cinemática diferencial de motores DC con L298N.
7. Terminal de historial de eventos con timestamps.
"""

from datetime import datetime
import json
import random
import threading
import time
import flet as ft
from mqtt import MqttManager

# ================= CONFIGURACIÓN MQTT =================
BROKER = "broker.hivemq.com"
PORT = 1883
PREFIX = "UDFJC/iot_ws/robot0/"

TOPIC_SERVO_CMD = f"{PREFIX}servo/angle"
TOPIC_SERVO_STATUS = f"{PREFIX}servo/status"
TOPIC_ROBOT_CMD = f"{PREFIX}cmd"
TOPIC_ROBOT_STATUS = f"{PREFIX}status"

CLIENT_ID = f"flet_servo_dashboard_{random.randint(1000, 9999)}"


def main(page: ft.Page):
    page.title = "UDFJC IoT - Control de Servomotor 180° (PWM) & Robot"
    page.window_width = 620
    page.window_height = 860
    page.window_resizable = True
    page.padding = 16
    page.theme_mode = ft.ThemeMode.DARK

    # Estado interno
    current_angle = 90.0
    sweep_active = False
    sweep_thread = None

    # --- Indicador de Conexión MQTT ---
    mqtt_icon = ft.Icon(ft.Icons.CLOUD_OFF, color=ft.Colors.RED_400, size=20)
    mqtt_status_label = ft.Text("Conectando a HiveMQ...", size=12, color=ft.Colors.GREY_400)

    # --- Terminal de Logs ---
    logs_list = ft.ListView(expand=True, spacing=4, auto_scroll=True)

    def log_event(mensaje: str, color=ft.Colors.WHITE70):
        hora = datetime.now().strftime("%H:%M:%S")
        logs_list.controls.append(
            ft.Row(
                controls=[
                    ft.Text(f"[{hora}]", size=11, color=ft.Colors.GREY_500, weight=ft.FontWeight.BOLD),
                    ft.Text(mensaje, size=11, color=color, expand=True),
                ],
                spacing=6,
            )
        )
        page.update()

    # --- Telemetría en Vivo ---
    txt_telemetry_angle = ft.Text("90.0°", size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_300)
    txt_telemetry_pulse = ft.Text("1500 µs", size=13, color=ft.Colors.WHITE70)
    txt_telemetry_duty = ft.Text("Duty: 4915 / 65535", size=13, color=ft.Colors.WHITE70)
    progress_servo = ft.ProgressBar(value=0.5, color=ft.Colors.CYAN_400, bgcolor=ft.Colors.GREY_800, height=8)
    txt_device_id = ft.Text("Dispositivo: Esperando conexión...", size=11, color=ft.Colors.GREY_400)

    # --- Callback de Telemetría MQTT ---
    def on_mqtt_message(topic: str, data: dict | str):
        nonlocal current_angle
        try:
            if topic == TOPIC_SERVO_STATUS:
                if isinstance(data, dict):
                    angle = data.get("angle")
                    pulse = data.get("pulse_us")
                    duty = data.get("duty_u16")
                    device = data.get("device", "Pico W")
                    event = data.get("event")

                    if angle is not None:
                        current_angle = float(angle)
                        txt_telemetry_angle.value = f"{current_angle:.1f}°"
                        progress_servo.value = max(0.0, min(1.0, current_angle / 180.0))
                        if pulse is not None:
                            txt_telemetry_pulse.value = f"{float(pulse):.1f} µs"
                        if duty is not None:
                            txt_telemetry_duty.value = f"Duty: {duty} / 65535"
                        txt_device_id.value = f"Dispositivo: {device} | Estado: OK"
                        log_event(f"Pico W Servo: {current_angle:.1f}° ({pulse} µs)", ft.Colors.GREEN_300)
                    elif event == "ready":
                        init_ang = data.get("initial_angle", 90.0)
                        txt_device_id.value = f"Dispositivo: {device} (Iniciado a {init_ang}°)"
                        log_event(f"Pico W conectada y lista. Ángulo inicial: {init_ang}°", ft.Colors.CYAN_300)

            elif topic == TOPIC_ROBOT_STATUS:
                if isinstance(data, dict):
                    state = data.get("state", "")
                    msg = data.get("message", "")
                    log_event(f"Robot L298N [{state}]: {msg}", ft.Colors.AMBER_300)
            page.update()
        except Exception as err:
            log_event(f"Error procesando mensaje: {err}", ft.Colors.RED_400)

    def on_mqtt_connect(connected: bool, info: str):
        if connected:
            mqtt_icon.name = ft.Icons.CLOUD_DONE
            mqtt_icon.color = ft.Colors.GREEN_400
            mqtt_status_label.value = f"En línea ({BROKER})"
            mqtt_status_label.color = ft.Colors.GREEN_400
            mqtt.subscribe(TOPIC_SERVO_STATUS)
            mqtt.subscribe(TOPIC_ROBOT_STATUS)
            log_event(f"Conexión exitosa a {BROKER}. Tópico: {PREFIX}", ft.Colors.BLUE_300)
        else:
            mqtt_icon.name = ft.Icons.CLOUD_OFF
            mqtt_icon.color = ft.Colors.RED_400
            mqtt_status_label.value = f"Desconectado ({info})"
            mqtt_status_label.color = ft.Colors.RED_400
            log_event(f"Estado MQTT: {info}", ft.Colors.RED_400)
        page.update()

    # Iniciar cliente MQTT
    mqtt = MqttManager(
        client_id=CLIENT_ID,
        on_connect_cb=on_mqtt_connect,
        on_message_cb=on_mqtt_message,
    )
    threading.Thread(target=lambda: mqtt.connect(BROKER, PORT), daemon=True).start()

    # --- Función para Despachar Ángulo al Servomotor ---
    def set_angle(angle_val: float, update_controls: bool = True):
        nonlocal current_angle
        # Clampeo estricto entre 0.0 y 180.0 grados
        clamped = max(0.0, min(180.0, round(float(angle_val), 1)))
        current_angle = clamped

        # Publicar por MQTT a la Pico W
        payload = {"angle": clamped, "source": "flet_ui"}
        mqtt.publish(TOPIC_SERVO_CMD, payload)

        if update_controls:
            angle_input.value = str(clamped)
            angle_slider.value = clamped
            angle_input.error_text = None

        # Estimación local para retroalimentación instantánea
        pulse_est = 500.0 + (clamped / 180.0) * 2000.0
        duty_est = int((pulse_est / 20000.0) * 65535)
        txt_telemetry_angle.value = f"{clamped:.1f}°"
        txt_telemetry_pulse.value = f"~{pulse_est:.1f} µs"
        txt_telemetry_duty.value = f"Duty: {duty_est} / 65535"
        progress_servo.value = clamped / 180.0

        log_event(f"Comando enviado -> Ángulo: {clamped}°", ft.Colors.CYAN_200)
        page.update()

    # --- Elementos de Control del Servomotor ---
    # 1. Campo de texto EDITABLE (Requisito explícito del profesor)
    def on_angle_input_submit(e):
        try:
            val = float(angle_input.value.strip())
            if 0.0 <= val <= 180.0:
                angle_input.error_text = None
                set_angle(val, update_controls=True)
            else:
                angle_input.error_text = "Ingresa entre 0.0° y 180.0°"
                page.update()
        except ValueError:
            angle_input.error_text = "Valor numérico inválido"
            page.update()

    angle_input = ft.TextField(
        value="90.0",
        label="Ángulo Manual (°)",
        hint_text="Ej: 0, 45, 73.5, 180",
        suffix_text="°",
        width=170,
        text_align=ft.TextAlign.RIGHT,
        keyboard_type=ft.KeyboardType.NUMBER,
        on_submit=on_angle_input_submit,
    )

    btn_apply_angle = ft.Button(
        "Aplicar",
        icon=ft.Icons.CHECK_CIRCLE,
        on_click=on_angle_input_submit,
    )

    # 2. Control deslizante (ft.Slider)
    def on_slider_change(e):
        val = round(float(e.control.value), 1)
        angle_input.value = str(val)
        angle_input.error_text = None
        set_angle(val, update_controls=False)

    angle_slider = ft.Slider(
        min=0.0,
        max=180.0,
        divisions=180,
        value=90.0,
        label="{value}°",
        on_change=on_slider_change,
        expand=True,
    )

    # 3. Presets Rápidos
    def make_preset_btn(degrees: float, label: str):
        return ft.Button(
            label,
            on_click=lambda _: set_angle(degrees),
        )

    row_presets = ft.Row(
        controls=[
            make_preset_btn(0.0, "0° (Mín)"),
            make_preset_btn(45.0, "45°"),
            make_preset_btn(90.0, "90° (Centro)"),
            make_preset_btn(135.0, "135°"),
            make_preset_btn(180.0, "180° (Máx)"),
        ],
        alignment=ft.MainAxisAlignment.SPACE_EVENLY,
        wrap=True,
    )

    # 4. Modo Barrido Automático (Sweep)
    btn_sweep = ft.Button(
        "Iniciar Barrido Automático (0° ⟷ 180°)",
        icon=ft.Icons.SWAP_HORIZ,
    )

    def sweep_worker():
        nonlocal sweep_active
        step = 5.0
        current = 0.0
        direction = 1
        while sweep_active:
            set_angle(current, update_controls=True)
            time.sleep(0.12)
            current += direction * step
            if current >= 180.0:
                current = 180.0
                direction = -1
                time.sleep(0.2)
            elif current <= 0.0:
                current = 0.0
                direction = 1
                time.sleep(0.2)

    def toggle_sweep(_):
        nonlocal sweep_active, sweep_thread
        sweep_active = not sweep_active
        if sweep_active:
            btn_sweep.content = "Detener Barrido Automático"
            btn_sweep.icon = ft.Icons.STOP
            log_event("Modo de barrido automático INICIADO", ft.Colors.AMBER_300)
            sweep_thread = threading.Thread(target=sweep_worker, daemon=True)
            sweep_thread.start()
        else:
            btn_sweep.content = "Iniciar Barrido Automático (0° ⟷ 180°)"
            btn_sweep.icon = ft.Icons.SWAP_HORIZ
            log_event("Modo de barrido automático DETENIDO", ft.Colors.GREY_400)
        page.update()

    btn_sweep.on_click = toggle_sweep

    # --- Tarjeta Principal de Control del Servomotor ---
    card_servo = ft.Card(
        content=ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.ROTATE_RIGHT, color=ft.Colors.CYAN_400, size=24),
                            ft.Text("CONTROL ANGULAR DE SERVOMOTOR (180°)", size=14, weight=ft.FontWeight.BOLD),
                        ],
                        spacing=8,
                    ),
                    ft.Text(
                        "Ingresa cualquier ángulo exacto en el campo editable o usa el deslizador / presets:",
                        size=12,
                        color=ft.Colors.GREY_400,
                    ),
                    ft.Row(
                        controls=[angle_input, btn_apply_angle],
                        alignment=ft.MainAxisAlignment.START,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=10,
                    ),
                    ft.Row(
                        controls=[
                            ft.Text("0°", size=11, color=ft.Colors.GREY_400),
                            angle_slider,
                            ft.Text("180°", size=11, color=ft.Colors.GREY_400),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Text("Posiciones Rápidas:", size=11, weight=ft.FontWeight.W_500, color=ft.Colors.GREY_400),
                    row_presets,
                    ft.Divider(height=10, color=ft.Colors.GREY_800),
                    ft.Row([btn_sweep], alignment=ft.MainAxisAlignment.CENTER),
                ],
                spacing=10,
            ),
            padding=14,
        ),
        elevation=3,
    )

    # --- Tarjeta de Telemetría en Vivo ---
    card_telemetry = ft.Card(
        content=ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text("TELEMETRÍA EN TIEMPO REAL (PICO W)", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_300),
                            ft.Container(
                                content=ft.Text("PWM: 50 Hz", size=10, color=ft.Colors.CYAN_200),
                                bgcolor=ft.Colors.WHITE10,
                                padding=ft.Padding(6, 2, 6, 2),
                                border_radius=4,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Row(
                        controls=[
                            ft.Column(
                                controls=[
                                    ft.Text("ÁNGULO CONFIRMADO", size=10, color=ft.Colors.GREY_500),
                                    txt_telemetry_angle,
                                ],
                                spacing=2,
                            ),
                            ft.Column(
                                controls=[
                                    ft.Text("ANCHO DE PULSO", size=10, color=ft.Colors.GREY_500),
                                    txt_telemetry_pulse,
                                    txt_telemetry_duty,
                                ],
                                spacing=2,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_AROUND,
                    ),
                    progress_servo,
                    txt_device_id,
                ],
                spacing=8,
            ),
            padding=12,
        ),
        elevation=2,
    )

    # --- Sección de Cinemática Robot L298N (Preservada y Mejorada) ---
    def despachar_robot(cmd_dict: dict, desc: str):
        mqtt.publish(TOPIC_ROBOT_CMD, cmd_dict)
        log_event(f"Robot L298N -> {desc}", ft.Colors.AMBER_200)

    btn_fwd = ft.Button("Avanzar 1m Recto", icon=ft.Icons.ARROW_UPWARD, on_click=lambda _: despachar_robot({"action": "straight", "distance": 1.0}, "Avanzar 1m"))
    btn_arc_l = ft.Button("Arco 90° Izq", icon=ft.Icons.TURN_LEFT, on_click=lambda _: despachar_robot({"action": "arc", "direction": "left", "radius": 1.0}, "Arco Izq R=1m"))
    btn_arc_r = ft.Button("Arco 90° Der", icon=ft.Icons.TURN_RIGHT, on_click=lambda _: despachar_robot({"action": "arc", "direction": "right", "radius": 1.0}, "Arco Der R=1m"))
    btn_robot_stop = ft.Button("Parada Motores", icon=ft.Icons.STOP, on_click=lambda _: despachar_robot({"action": "stop"}, "Parada de emergencia"))

    card_robot = ft.Card(
        content=ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.DIRECTIONS_CAR, color=ft.Colors.AMBER_400, size=20),
                            ft.Text("CONTROL MOTORES DC L298N (TRAYECTORIA ROBOT)", size=13, weight=ft.FontWeight.BOLD),
                        ],
                        spacing=8,
                    ),
                    ft.Row([btn_fwd, btn_robot_stop], alignment=ft.MainAxisAlignment.SPACE_EVENLY),
                    ft.Row([btn_arc_l, btn_arc_r], alignment=ft.MainAxisAlignment.SPACE_EVENLY),
                ],
                spacing=8,
            ),
            padding=12,
        ),
        elevation=2,
    )

    # --- Contenedor de Logs ---
    borde_contenedor = ft.Border(
        top=ft.BorderSide(1, ft.Colors.GREY_800),
        bottom=ft.BorderSide(1, ft.Colors.GREY_800),
        left=ft.BorderSide(1, ft.Colors.GREY_800),
        right=ft.BorderSide(1, ft.Colors.GREY_800),
    )

    logs_container = ft.Container(
        content=logs_list,
        border=borde_contenedor,
        border_radius=8,
        padding=8,
        expand=True,
        bgcolor=ft.Colors.BLACK26,
    )

    def limpiar_logs(_):
        logs_list.controls.clear()
        log_event("Historial reiniciado.", ft.Colors.GREY_400)

    # --- Construcción del Layout Principal ---
    page.add(
        ft.Row(
            controls=[
                ft.Column(
                    controls=[
                        ft.Text("UDFJC - Laboratorio IoT", size=18, weight=ft.FontWeight.BOLD),
                        ft.Text("Taller 7 & 8: Modulación PWM, Servomotores y Cinemática", size=11, color=ft.Colors.GREY_400),
                    ],
                    spacing=2,
                ),
                ft.Row([mqtt_icon, mqtt_status_label], spacing=6),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        card_servo,
        card_telemetry,
        card_robot,
        ft.Row(
            controls=[
                ft.Text("Historial de Comunicación MQTT", size=12, weight=ft.FontWeight.BOLD),
                ft.IconButton(icon=ft.Icons.DELETE_SWEEP, tooltip="Limpiar registros", on_click=limpiar_logs),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        logs_container,
    )


if __name__ == "__main__":
    ft.app(target=main)
