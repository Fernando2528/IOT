"""
flet/main.py
============
Interfaz Gráfica en Flet para el Proyecto Final (Taller 8: CAR - Cinemática Diferencial y Modelo de la Bicicleta).

Comandos Principales Requeridos:
1. Avanzar en línea recta 1 metro (D = 1.0 m).
2. Generar 1/4 de círculo (90°) de 1 metro de radio (R = 1.0 m) a la DERECHA.
3. Generar 1/4 de círculo (90°) de 1 metro de radio (R = 1.0 m) a la IZQUIERDA.

Funcionalidades Adicionales de Ingeniería:
- Panel directo CAR(v, w, t) con campos editables y cálculo en vivo de cinemática inversa:
  v_l = v - w*d, v_r = v + w*d.
- Calibración remota en caliente de los parámetros físicos del chasis (d, v_max, deadzone, trim, inversión).
- Simulador / Calculadora interactiva del Modelo de la Bicicleta (r_d, r_t, arcos, derivadas).
- Control editable en grados para el servomotor del brazo mecánico (GP12).
"""

from datetime import datetime
import math
import os
import random
import sys
import threading
import flet as ft

# Asegurar acceso a common/kinematics.py y flet/mqtt.py
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(CURRENT_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from common.kinematics import BicycleModel, DifferentialKinematics
from mqtt import MqttManager

# ================= CONFIGURACIÓN MQTT =================
BROKER = "broker.hivemq.com"
PORT = 1883
PREFIX = "UDFJC/iot_ws/robot0/"

TOPIC_CAR = f"{PREFIX}CAR"
TOPIC_CAR_CMD = f"{PREFIX}CAR/cmd"
TOPIC_CAR_CONFIG = f"{PREFIX}CAR/config"
TOPIC_CAR_STOP = f"{PREFIX}CAR/stop"
TOPIC_CAR_STATUS = f"{PREFIX}CAR/status"
TOPIC_STATUS = f"{PREFIX}status"
TOPIC_SERVO_ANGLE = f"{PREFIX}servo/angle"
TOPIC_SERVO_STATUS = f"{PREFIX}servo/status"

CLIENT_ID = f"flet_car_final_{random.randint(1000, 9999)}"


def main(page: ft.Page):
    page.title = "UDFJC IoT - Proyecto Final (Taller 8): CAR Cinemática Diferencial"
    page.window_width = 760
    page.window_height = 920
    page.window_resizable = True
    page.padding = 16
    page.theme_mode = ft.ThemeMode.DARK
    page.scroll = ft.ScrollMode.AUTO

    # Instancias de los modelos matemáticos
    kinematics = DifferentialKinematics(half_track_d=0.0675, v_max=0.25)
    bicycle = BicycleModel(wheelbase_L=0.15)
    nominal_speed_v = 0.20

    # --- Estado de Conexión MQTT ---
    mqtt_icon = ft.Icon(ft.Icons.CLOUD_OFF, color=ft.Colors.RED_400, size=20)
    mqtt_status_label = ft.Text("Conectando a HiveMQ...", size=12, color=ft.Colors.GREY_400)

    # --- Terminal de Historial ---
    logs_list = ft.ListView(expand=True, spacing=4, auto_scroll=True, height=150)

    def add_log(msg: str, color=ft.Colors.WHITE70):
        hora = datetime.now().strftime("%H:%M:%S")
        logs_list.controls.append(
            ft.Row(
                controls=[
                    ft.Text(f"[{hora}]", size=11, color=ft.Colors.GREY_500, weight=ft.FontWeight.BOLD),
                    ft.Text(msg, size=11, color=color, expand=True),
                ],
                spacing=6,
            )
        )
        page.update()

    # --- Indicadores de Telemetría Cinemática en Vivo ---
    txt_state_badge = ft.Text("EN REPOSO (IDLE)", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400)
    txt_calc_v = ft.Text("v = 0.000 m/s", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_300)
    txt_calc_w = ft.Text("w = 0.000 rad/s", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_300)
    txt_calc_t = ft.Text("t = 0.00 s", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_300)
    txt_calc_vl = ft.Text("v_l = 0.000 m/s (PWM: 0%)", size=13, color=ft.Colors.GREEN_300)
    txt_calc_vr = ft.Text("v_r = 0.000 m/s (PWM: 0%)", size=13, color=ft.Colors.GREEN_300)
    txt_calc_arcs = ft.Text("Arco centro: 0.00 m | Giro Δα: 0.0°", size=12, color=ft.Colors.GREY_300)

    # --- Campos Editables de Comando Directo CAR(v, w, t) ---
    tf_v = ft.TextField(value="0.20", label="Rapidez v (m/s)", width=145, keyboard_type=ft.KeyboardType.NUMBER)
    tf_w = ft.TextField(value="0.00", label="Vel. Angular w (rad/s)", width=165, keyboard_type=ft.KeyboardType.NUMBER)
    tf_t = ft.TextField(value="5.00", label="Tiempo t (s)", width=135, keyboard_type=ft.KeyboardType.NUMBER)

    # --- Campos Editables de Calibración del Chasis ---
    tf_d = ft.TextField(value="0.0675", label="Semitrocha d (m)", width=135, tooltip="Distancia del centro a cada rueda (2d = separación entre ruedas)")
    tf_vmax = ft.TextField(value="0.25", label="v_max 100% (m/s)", width=135, tooltip="Velocidad máxima de rueda a PWM 100%")
    tf_vnom = ft.TextField(value="0.20", label="v nominal (m/s)", width=135, tooltip="Rapidez lineal usada para los 3 botones de trayectoria")
    tf_deadzone = ft.TextField(value="0.28", label="Zona Muerta PWM", width=135, tooltip="Compensación de fricción estática (0.0 a 0.5)")
    sw_inv_l = ft.Switch(label="Invertir Rueda Izq (IN1/IN2)", value=False)
    sw_inv_r = ft.Switch(label="Invertir Rueda Der (IN3/IN4)", value=False)

    # --- Callbacks MQTT ---
    def on_mqtt_message(topic: str, data: dict | str):
        try:
            if topic in (TOPIC_CAR_STATUS, TOPIC_STATUS):
                if isinstance(data, dict):
                    st = str(data.get("state", "info")).upper()
                    msg = data.get("message", str(data))
                    if st == "IN_PROGRESS":
                        txt_state_badge.value = f"EJECUTANDO: {msg}"
                        txt_state_badge.color = ft.Colors.AMBER_400
                        add_log(f"Pico W [EN CURSO]: {msg}", ft.Colors.AMBER_300)
                    elif st == "COMPLETED":
                        txt_state_badge.value = "COMPLETADO - EN REPOSO"
                        txt_state_badge.color = ft.Colors.GREEN_400
                        add_log(f"Pico W [COMPLETADO]: {msg}", ft.Colors.GREEN_300)
                    elif st == "STOPPED":
                        txt_state_badge.value = "DETENIDO (IDLE)"
                        txt_state_badge.color = ft.Colors.RED_300
                        add_log(f"Pico W [DETENIDO]: {msg}", ft.Colors.RED_300)
                    else:
                        add_log(f"Pico W [{st}]: {msg}", ft.Colors.CYAN_200)
            elif topic == TOPIC_SERVO_STATUS:
                if isinstance(data, dict):
                    ang = data.get("angle", 90.0)
                    pulse = data.get("pulse_us", 1500)
                    add_log(f"Servo GP12 posicionado a {ang}° ({pulse} µs)", ft.Colors.CYAN_300)
            page.update()
        except Exception as err:
            add_log(f"Error en telemetría MQTT: {err}", ft.Colors.RED_400)

    def on_mqtt_connect(connected: bool, info: str):
        if connected:
            mqtt_icon.name = ft.Icons.CLOUD_DONE
            mqtt_icon.color = ft.Colors.GREEN_400
            mqtt_status_label.value = f"Conectado ({BROKER})"
            mqtt_status_label.color = ft.Colors.GREEN_400
            mqtt.subscribe(TOPIC_CAR_STATUS)
            mqtt.subscribe(TOPIC_STATUS)
            mqtt.subscribe(TOPIC_SERVO_STATUS)
            add_log(f"Conectado a {BROKER} | Prefijo: {PREFIX}", ft.Colors.BLUE_300)
        else:
            mqtt_icon.name = ft.Icons.CLOUD_OFF
            mqtt_icon.color = ft.Colors.RED_400
            mqtt_status_label.value = f"Sin conexión ({info})"
            mqtt_status_label.color = ft.Colors.RED_400
        page.update()

    mqtt = MqttManager(
        client_id=CLIENT_ID,
        on_connect_cb=on_mqtt_connect,
        on_message_cb=on_mqtt_message,
    )
    threading.Thread(target=lambda: mqtt.connect(BROKER, PORT), daemon=True).start()

    # --- Sincronización de Parámetros Físicos ---
    def sync_local_params():
        nonlocal nominal_speed_v
        try:
            d_val = max(0.01, float(tf_d.value.strip()))
            vmax_val = max(0.05, float(tf_vmax.value.strip()))
            vnom_val = max(0.02, min(vmax_val, float(tf_vnom.value.strip())))
            kinematics.d = d_val
            kinematics.v_max = vmax_val
            nominal_speed_v = vnom_val
        except ValueError:
            pass

    def update_kinematic_display(cmd: dict):
        tf_v.value = f"{cmd['v']:.3f}"
        tf_w.value = f"{cmd['w']:.3f}"
        tf_t.value = f"{cmd['t']:.2f}"

        txt_calc_v.value = f"v = {cmd['v']:.3f} m/s"
        txt_calc_w.value = f"w = {cmd['w']:.3f} rad/s"
        txt_calc_t.value = f"t = {cmd['t']:.2f} s"
        txt_calc_vl.value = f"v_l = {cmd['v_l']:.3f} m/s (PWM: {cmd['pwm_l']*100:.0f}%)"
        txt_calc_vr.value = f"v_r = {cmd['v_r']:.3f} m/s (PWM: {cmd['pwm_r']*100:.0f}%)"
        txt_calc_arcs.value = (
            f"Trayectoria: {cmd['label']} | Arco central: {cmd['arc_center_m']:.2f} m | "
            f"Giro Δα: {cmd['angle_deg']:.1f}°"
        )
        page.update()

    def send_car_command(cmd: dict):
        update_kinematic_display(cmd)
        # Publicar en el tópico oficial "CAR" y en "CAR/cmd"
        mqtt.publish(TOPIC_CAR, cmd)
        mqtt.publish(TOPIC_CAR_CMD, cmd)
        add_log(
            f"Enviado a CAR -> {cmd['label']}: v={cmd['v']:.3f} m/s, w={cmd['w']:.3f} rad/s, "
            f"t={cmd['t']:.2f} s (v_l={cmd['v_l']:.3f}, v_r={cmd['v_r']:.3f})",
            ft.Colors.CYAN_300,
        )

    # ==================================================================
    # LOS 3 COMANDOS PRINCIPALES SOLICITADOS EN EL TALLER 8
    # ==================================================================
    def on_btn_straight_1m(_):
        """1. Avance en línea recta 1 metro (D = 1.0 m)."""
        sync_local_params()
        cmd = kinematics.command_straight(distance_m=1.0, speed_v=nominal_speed_v)
        send_car_command(cmd)

    def on_btn_quarter_circle_right(_):
        """2a. Genere 1/4 de círculo (90°) de 1 metro de radio a la DERECHA."""
        sync_local_params()
        cmd = kinematics.command_quarter_circle(
            radius_m=1.0, direction="right", speed_v=nominal_speed_v
        )
        send_car_command(cmd)

    def on_btn_quarter_circle_left(_):
        """2b. Genere 1/4 de círculo (90°) de 1 metro de radio a la IZQUIERDA."""
        sync_local_params()
        cmd = kinematics.command_quarter_circle(
            radius_m=1.0, direction="left", speed_v=nominal_speed_v
        )
        send_car_command(cmd)

    def on_btn_stop(_):
        """Parada inmediata de emergencia."""
        mqtt.publish(TOPIC_CAR_STOP, {"action": "stop"})
        mqtt.publish(TOPIC_CAR, {"action": "stop", "v": 0.0, "w": 0.0, "t": 0.0})
        txt_state_badge.value = "PARADA SOLICITADA"
        txt_state_badge.color = ft.Colors.RED_400
        add_log("Parada de emergencia enviada a CAR", ft.Colors.RED_300)
        page.update()

    # --- Envío Manual de (v, w, t) Editables ---
    def on_send_custom_vwt(_):
        sync_local_params()
        try:
            v_val = float(tf_v.value.strip())
            w_val = float(tf_w.value.strip())
            t_val = float(tf_t.value.strip())
            cmd = kinematics.create_command(
                v=v_val, w=w_val, t=t_val, label="Comando Manual (v,w,t)"
            )
            send_car_command(cmd)
        except ValueError:
            add_log("Error: Verifica que v, w y t sean números válidos.", ft.Colors.RED_400)

    # --- Envío de Calibración a la Pico W ---
    def on_apply_calibration(_):
        sync_local_params()
        try:
            dz = float(tf_deadzone.value.strip())
            cfg = {
                "d": kinematics.d,
                "v_max": kinematics.v_max,
                "deadzone": dz,
                "invert_left": sw_inv_l.value,
                "invert_right": sw_inv_r.value,
            }
            mqtt.publish(TOPIC_CAR_CONFIG, cfg)
            add_log(
                f"Calibración enviada -> d={kinematics.d}m, v_max={kinematics.v_max}m/s, "
                f"deadzone={dz}, inv=({sw_inv_l.value},{sw_inv_r.value})",
                ft.Colors.GREEN_300,
            )
        except ValueError:
            add_log("Error en valores de calibración.", ft.Colors.RED_400)

    # --- Calculadora del Modelo de la Bicicleta + Control de Servo Auxiliar ---
    tf_bike_L = ft.TextField(value="0.15", label="Distancia Ejes L (m)", width=140)
    tf_bike_alpha = ft.TextField(value="30.0", label="Ángulo Timón α (°)", width=140)
    tf_bike_beta = ft.TextField(value="90.0", label="Ángulo Barrido β (°)", width=145)
    txt_bike_result = ft.Text(
        "r_t = 0.260 m | r_d = 0.300 m | Arco Trasero = 0.408 m | Arco Delantero = 0.471 m",
        size=12,
        color=ft.Colors.CYAN_200,
    )

    def on_calc_bicycle(_):
        try:
            L_val = float(tf_bike_L.value.strip())
            alpha_deg = float(tf_bike_alpha.value.strip())
            beta_deg = float(tf_bike_beta.value.strip())
            bicycle.L = L_val
            alpha_rad = math.radians(alpha_deg)
            beta_rad = math.radians(beta_deg)
            r_t, r_d = bicycle.turning_radii(alpha_rad)
            arc_t, arc_d = bicycle.wheel_arcs(alpha_rad, beta_rad)
            txt_bike_result.value = (
                f"r_t = {r_t:.3f} m | r_d = {r_d:.3f} m | "
                f"Arco Trasero (β·r_t) = {arc_t:.3f} m | Arco Delantero (β·r_d) = {arc_d:.3f} m"
            )
            page.update()
        except Exception as err:
            txt_bike_result.value = f"Error en cálculo: {err}"
            page.update()

    # Control del Servomotor del Brazo Mecánico (Editable en grados)
    tf_servo_deg = ft.TextField(
        value="90.0",
        label="Ángulo Servo Brazo GP12 (°)",
        suffix_text="°",
        width=185,
    )

    def set_arm_servo(deg_val: float):
        clamped = max(0.0, min(180.0, round(float(deg_val), 1)))
        tf_servo_deg.value = str(clamped)
        servo_slider.value = clamped
        mqtt.publish(TOPIC_SERVO_ANGLE, {"angle": clamped})
        add_log(f"Servo Brazo (GP12) -> {clamped}°", ft.Colors.CYAN_200)
        page.update()

    def on_servo_submit(_):
        try:
            set_arm_servo(float(tf_servo_deg.value.strip()))
        except ValueError:
            pass

    tf_servo_deg.on_submit = on_servo_submit
    servo_slider = ft.Slider(
        min=0.0,
        max=180.0,
        divisions=180,
        value=90.0,
        label="{value}°",
        on_change=lambda e: set_arm_servo(e.control.value),
        expand=True,
    )

    # --- Construcción de Tarjetas Visuales ---
    card_trajectories = ft.Card(
        content=ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.ROUTE, color=ft.Colors.CYAN_400, size=24),
                            ft.Text(
                                "1. COMANDOS OFICIALES DE TRAYECTORIA (CLASE CAR)",
                                size=14,
                                weight=ft.FontWeight.BOLD,
                            ),
                        ],
                        spacing=8,
                    ),
                    ft.Text(
                        "Calcula automáticamente (v, w, t) mediante cinemática diferencial inversa y los publica a la Pico W:",
                        size=12,
                        color=ft.Colors.GREY_400,
                    ),
                    ft.Row(
                        controls=[
                            ft.Button(
                                "⬆️ Avanzar en Línea Recta 1 Metro",
                                icon=ft.Icons.STRAIGHT,
                                on_click=on_btn_straight_1m,
                                expand=True,
                            ),
                            ft.Button(
                                "🛑 DETENER CARRO",
                                icon=ft.Icons.STOP_CIRCLE,
                                on_click=on_btn_stop,
                            ),
                        ],
                        spacing=10,
                    ),
                    ft.Row(
                        controls=[
                            ft.Button(
                                "↩️ 1/4 de Círculo (R = 1 m) a IZQUIERDA",
                                icon=ft.Icons.TURN_LEFT,
                                on_click=on_btn_quarter_circle_left,
                                expand=True,
                            ),
                            ft.Button(
                                "↪️ 1/4 de Círculo (R = 1 m) a DERECHA",
                                icon=ft.Icons.TURN_RIGHT,
                                on_click=on_btn_quarter_circle_right,
                                expand=True,
                            ),
                        ],
                        spacing=10,
                    ),
                ],
                spacing=10,
            ),
            padding=14,
        ),
        elevation=3,
    )

    card_direct_vwt = ft.Card(
        content=ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.SPEED, color=ft.Colors.AMBER_400, size=22),
                            ft.Text(
                                "2. CONTROL CINEMÁTICO DIRECTO CAR(v, w, t) Y TELEMETRÍA",
                                size=13,
                                weight=ft.FontWeight.BOLD,
                            ),
                        ],
                        spacing=8,
                    ),
                    ft.Row(
                        controls=[
                            tf_v,
                            tf_w,
                            tf_t,
                            ft.Button(
                                "Ejecutar (v, w, t)",
                                icon=ft.Icons.PLAY_ARROW,
                                on_click=on_send_custom_vwt,
                            ),
                        ],
                        wrap=True,
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Divider(height=8, color=ft.Colors.GREY_800),
                    ft.Row(
                        controls=[txt_state_badge],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Row(
                        controls=[txt_calc_v, txt_calc_w, txt_calc_t],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Row(
                        controls=[txt_calc_vl, txt_calc_vr],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    txt_calc_arcs,
                ],
                spacing=8,
            ),
            padding=14,
        ),
        elevation=2,
    )

    card_calibration = ft.Card(
        content=ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.TUNE, color=ft.Colors.GREEN_400, size=20),
                            ft.Text(
                                "3. CALIBRACIÓN FÍSICA DEL CHASIS Y PUENTE H (GP19, GP18, GP17, GP16)",
                                size=13,
                                weight=ft.FontWeight.BOLD,
                            ),
                        ],
                        spacing=8,
                    ),
                    ft.Row(
                        controls=[tf_d, tf_vmax, tf_vnom, tf_deadzone],
                        wrap=True,
                        spacing=10,
                    ),
                    ft.Row(
                        controls=[
                            sw_inv_l,
                            sw_inv_r,
                            ft.Button(
                                "Aplicar Calibración a Pico W",
                                icon=ft.Icons.SAVE,
                                on_click=on_apply_calibration,
                            ),
                        ],
                        wrap=True,
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                ],
                spacing=8,
            ),
            padding=12,
        ),
        elevation=2,
    )

    card_bicycle_and_servo = ft.Card(
        content=ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.DIRECTIONS_BIKE, color=ft.Colors.PURPLE_300, size=20),
                            ft.Text(
                                "4. MODELO DE LA BICICLETA & SERVOMOTOR DEL BRAZO MECÁNICO (GP12)",
                                size=13,
                                weight=ft.FontWeight.BOLD,
                            ),
                        ],
                        spacing=8,
                    ),
                    ft.Row(
                        controls=[
                            tf_bike_L,
                            tf_bike_alpha,
                            tf_bike_beta,
                            ft.Button("Calcular Bicicleta", icon=ft.Icons.CALCULATE, on_click=on_calc_bicycle),
                        ],
                        wrap=True,
                        spacing=10,
                    ),
                    txt_bike_result,
                    ft.Divider(height=8, color=ft.Colors.GREY_800),
                    ft.Row(
                        controls=[
                            tf_servo_deg,
                            ft.Button("Mover Servo", icon=ft.Icons.ROTATE_RIGHT, on_click=on_servo_submit),
                            servo_slider,
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                spacing=8,
            ),
            padding=12,
        ),
        elevation=2,
    )

    borde_logs = ft.Border(
        top=ft.BorderSide(1, ft.Colors.GREY_800),
        bottom=ft.BorderSide(1, ft.Colors.GREY_800),
        left=ft.BorderSide(1, ft.Colors.GREY_800),
        right=ft.BorderSide(1, ft.Colors.GREY_800),
    )

    page.add(
        ft.Row(
            controls=[
                ft.Column(
                    controls=[
                        ft.Text("UDFJC - Proyecto Final IoT (Taller 8: CAR)", size=18, weight=ft.FontWeight.BOLD),
                        ft.Text(
                            "Cinemática Diferencial (v, w, t), Modelo de la Bicicleta y Control Dual de Ruedas",
                            size=11,
                            color=ft.Colors.GREY_400,
                        ),
                    ],
                    spacing=2,
                ),
                ft.Row([mqtt_icon, mqtt_status_label], spacing=6),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        card_trajectories,
        card_direct_vwt,
        card_calibration,
        card_bicycle_and_servo,
        ft.Row(
            controls=[
                ft.Text("Registro de Eventos y Telemetría MQTT", size=12, weight=ft.FontWeight.BOLD),
                ft.IconButton(
                    icon=ft.Icons.DELETE_SWEEP,
                    tooltip="Limpiar historial",
                    on_click=lambda _: (logs_list.controls.clear(), page.update()),
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        ft.Container(
            content=logs_list,
            border=borde_logs,
            border_radius=8,
            padding=8,
            bgcolor=ft.Colors.BLACK26,
        ),
    )


if __name__ == "__main__":
    ft.app(target=main)
