"""
main.py (Interfaz Flet en PC - Proyecto Segundo Corte: Coreografía)
===================================================================
Interfaz gráfica limpia y en español claro para el control del Carrobot (Robot 12):
- Ejecución con un solo clic de la Coreografía Predeterminada (Robot 12 - Par) con indicador visual paso a paso.
- Trayectorias solicitadas: Línea Recta de 1 Metro y 1/4 de Círculo (R = 1 m) a Izquierda y Derecha.
- Control del Brazo Robótico (Hombro y Codo) con ángulos y tiempo de demora asignado.
- Vista en vivo de la Pantalla OLED SSD1306 (Watchdog + Scroll por Potenciómetro) y estadísticas de tareas.
"""

from datetime import datetime, timedelta, timezone
import json
import os
import sys
import webbrowser
import flet as ft

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from common.kinematics import (
    DifferentialKinematics,
    EVEN_STATES,
    ODD_STATES,
    normalize_motion_state,
)
from mqtt import MqttClient

DEFAULT_BASE_PREFIX = "UDFJC/carrrobot"
DEFAULT_ROBOT_ID = "12"

EVEN_STEP_DESCRIPTIONS = [
    ("Paso 1 (2 s)", "Giro en el sitio a la izquierda (v = 0 dm/s, w = +45 °/s)"),
    ("Paso 2 (2 s)", "Giro en el sitio a la derecha (v = 0 dm/s, w = -45 °/s, brazo a 0°)"),
    ("Paso 3 (5 s)", "Avance en semicírculo hacia adelante (v = 1.57 dm/s, w = +36 °/s)"),
    ("Paso 4 (2 s)", "Pausa de ruedas y pose del brazo (Hombro = +67.5°, Codo = -67.5°)"),
    ("Paso 5 (5 s)", "Retroceso en semicírculo hacia atrás (v = -1.57 dm/s, w = +36 °/s)"),
]


def card_box(content: ft.Control, padding: int = 16, border_color: str = "#30363D") -> ft.Container:
    return ft.Container(
        content=content,
        padding=padding,
        border_radius=12,
        bgcolor="#161B22",
        border=ft.Border(
            top=ft.BorderSide(1, border_color),
            bottom=ft.BorderSide(1, border_color),
            left=ft.BorderSide(1, border_color),
            right=ft.BorderSide(1, border_color),
        ),
    )


def open_url_reliably(url: str):
    """Abre un enlace web en el navegador predeterminado de Windows."""
    try:
        if sys.platform.startswith("win") and hasattr(os, "startfile"):
            os.startfile(url)
            return
    except Exception:
        pass
    webbrowser.open(url, new=2)


def main(page: ft.Page):
    page.title = "UDFJC IoT - Coreografía Carrobot (Robot 12)"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0D1117"
    page.padding = 18
    page.scroll = ft.ScrollMode.AUTO
    page.window.width = 1200
    page.window.height = 940

    kin = DifferentialKinematics(half_track_d=0.0675, v_max=0.25)
    mqtt_client = MqttClient(
        broker="broker.hivemq.com",
        port=1883,
        base_prefix=DEFAULT_BASE_PREFIX,
        robot_id=DEFAULT_ROBOT_ID,
    )

    # ==========================================================================
    # ENCABEZADO Y CONEXIÓN AL GEMELO VIRTUAL WEB
    # ==========================================================================
    status_badge = ft.Container(
        padding=ft.Padding(left=12, right=12, top=6, bottom=6),
        border_radius=8,
        bgcolor="#1F2937",
        content=ft.Text(
            "Conectando al servidor MQTT...",
            color="#D29922",
            weight=ft.FontWeight.BOLD,
            size=13,
        ),
    )
    tf_base_prefix = ft.TextField(label="Prefijo del Curso", value=DEFAULT_BASE_PREFIX, width=220)
    tf_robot_id = ft.TextField(label="Número de Robot", value=DEFAULT_ROBOT_ID, width=180)
    lbl_active_prefix = ft.Text(
        f"Canal MQTT activo: {DEFAULT_BASE_PREFIX}/robot{DEFAULT_ROBOT_ID}/",
        color="#58A6FF",
        weight=ft.FontWeight.BOLD,
        size=14,
    )
    lbl_robot_live_state = ft.Container(
        padding=ft.Padding(left=12, right=12, top=8, bottom=8),
        border_radius=8,
        bgcolor="#0D1117",
        border=ft.Border(
            top=ft.BorderSide(1, "#238636"),
            bottom=ft.BorderSide(1, "#238636"),
            left=ft.BorderSide(4, "#3FB950"),
            right=ft.BorderSide(1, "#238636"),
        ),
        content=ft.Text(
            "Estado actual: Robot en espera de comandos",
            color="#3FB950",
            weight=ft.FontWeight.BOLD,
            size=15,
        ),
    )

    log_list = ft.ListView(height=130, spacing=3, auto_scroll=False)

    def log_event(text: str):
        ts = datetime.now().strftime("%H:%M:%S")
        log_list.controls.insert(
            0,
            ft.Text(f"[{ts}] {text}", font_family="Consolas", size=12, color="#C9D1D9"),
        )
        if len(log_list.controls) > 50:
            log_list.controls.pop()
        page.update()

    def get_individual_twin_url() -> str:
        base = tf_base_prefix.value.strip().strip("/") or DEFAULT_BASE_PREFIX
        rid = tf_robot_id.value.strip() or DEFAULT_ROBOT_ID
        return (
            "https://gerardomunoz.github.io/IoT_ws/coreografia/PubSub_client_web.html"
            f"?transport=mqtt&host=broker.hivemq.com&port=8884&prefix={base}&robot={rid}"
        )

    def get_group_twin_url() -> str:
        return "https://gerardomunoz.github.io/IoT_ws/coreografia/robot_coreografia_mqtt.html"

    tf_url_display = ft.TextField(
        label="Enlace directo al Gemelo Virtual Individual",
        value=get_individual_twin_url(),
        read_only=True,
        width=980,
        text_size=12,
    )

    def apply_prefix_change(e=None):
        base = tf_base_prefix.value.strip() or DEFAULT_BASE_PREFIX
        rid = tf_robot_id.value.strip() or DEFAULT_ROBOT_ID
        mqtt_client.set_prefix(base, rid)
        lbl_active_prefix.value = f"Canal MQTT activo: {mqtt_client.prefix}"
        tf_url_display.value = get_individual_twin_url()
        log_event(f"Canal MQTT cambiado a: {mqtt_client.prefix}")
        page.update()

    def on_open_individual_twin(e):
        url = get_individual_twin_url()
        tf_url_display.value = url
        open_url_reliably(url)
        log_event("Abriendo Gemelo Virtual Individual en el navegador. Recuerda oprimir 'Subscribe Robot' en la página web.")
        page.update()

    def on_open_group_choreo(e):
        url = get_group_twin_url()
        open_url_reliably(url)
        log_event("Abriendo Visualizador de Coreografía Grupal. Recuerda oprimir 'Conectar y escuchar' en la página web.")

    # ==========================================================================
    # SECCIÓN 1: EJECUTAR COREOGRAFÍA PREDETERMINADA (ROBOT 12 - PAR)
    # ==========================================================================
    step_badges = []
    step_rows_controls = []
    for idx, (step_title, step_desc) in enumerate(EVEN_STEP_DESCRIPTIONS, start=1):
        badge = ft.Container(
            content=ft.Text(step_title, size=12, weight=ft.FontWeight.BOLD, color="#F0F6FC"),
            padding=ft.Padding(left=10, right=10, top=4, bottom=4),
            border_radius=6,
            bgcolor="#21262D",
            width=110,
        )
        step_badges.append(badge)
        step_rows_controls.append(
            ft.Row(
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    badge,
                    ft.Text(step_desc, size=13, color="#C9D1D9"),
                ],
            )
        )

    def highlight_active_step(active_idx: int):
        for i, badge in enumerate(step_badges, start=1):
            if i == active_idx:
                badge.bgcolor = "#238636"
            elif active_idx > i:
                badge.bgcolor = "#1F6FEB"
            else:
                badge.bgcolor = "#21262D"

    lbl_seq_status = ft.Text(
        "Lista para iniciar: Coreografía Oficial Par (5 pasos, duración total 16 segundos)",
        color="#58A6FF",
        weight=ft.FontWeight.BOLD,
        size=14,
    )

    def on_run_default_even_choreo(e):
        """Envía y ejecuta de inmediato la coreografía predeterminada even.json para el Robot 12."""
        payload = {
            "action": "create",
            "name": "even",
            "run_at": "now",
            "states": EVEN_STATES,
        }
        topic = mqtt_client.publish("motion/sequence", payload)
        highlight_active_step(1)
        lbl_seq_status.value = "Ejecutando Coreografía Predeterminada 'even' (Robot 12 - Par)..."
        lbl_robot_live_state.content.value = "Estado actual: Ejecutando Coreografía Oficial (Paso 1 de 5)"
        lbl_robot_live_state.content.color = "#58A6FF"
        log_event(f"Coreografía predeterminada 'even' enviada a {topic}")
        page.update()

    def on_stop_robot(e=None):
        st = {
            "v_dm/s": 0.0,
            "w_deg/s": 0.0,
            "alpha0_deg": float(tf_a0.value or 0.0),
            "alpha1_deg": float(tf_a1.value or 0.0),
            "alpha2_deg": float(tf_a2.value or 0.0),
            "duration_s": 0.1,
        }
        mqtt_client.publish("motion/state", st)
        mqtt_client.publish("CAR/stop", {"action": "stop"})
        highlight_active_step(0)
        lbl_robot_live_state.content.value = "Estado actual: Robot detenido por el usuario"
        lbl_robot_live_state.content.color = "#F85149"
        lbl_seq_status.value = "Movimiento detenido."
        log_event("Parada inmediata enviada al robot y al gemelo virtual.")
        page.update()

    # Opciones avanzadas de secuencia (en panel desplegable para no saturar la vista)
    tf_seq_name = ft.TextField(label="Nombre de Secuencia", value="even", width=190)
    tf_run_at = ft.TextField(label="Inicio ('now' o Hora ISO)", value="now", width=260)
    tf_seq_json = ft.TextField(
        label="Pasos de la Secuencia (formato JSON)",
        value=json.dumps(EVEN_STATES, indent=2),
        multiline=True,
        min_lines=6,
        max_lines=10,
        text_style=ft.TextStyle(font_family="Consolas", size=12),
    )

    def load_preset_sequence(seq_type: str):
        is_odd = seq_type.lower() == "odd"
        tf_seq_name.value = "odd" if is_odd else "even"
        states = ODD_STATES if is_odd else EVEN_STATES
        tf_seq_json.value = json.dumps(states, indent=2)
        lbl_seq_status.value = (
            f"Plantilla cargada en el editor: {'Impar (odd.json)' if is_odd else 'Par (even.json - Robot 12)'}"
        )
        page.update()

    def set_iso_plus_10s(e):
        future_utc = datetime.now(timezone.utc) + timedelta(seconds=10)
        tf_run_at.value = future_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        lbl_seq_status.value = f"Hora programada (+10 s en UTC): {tf_run_at.value}"
        page.update()

    def send_sequence_action(action: str, force_run_at: str | None = None):
        name = tf_seq_name.value.strip() or "even"
        run_at_val = force_run_at if force_run_at is not None else (tf_run_at.value.strip() or "now")
        try:
            if action == "create":
                states = json.loads(tf_seq_json.value)
                if not isinstance(states, list) or len(states) == 0:
                    raise ValueError("La lista de pasos JSON no puede estar vacía.")
                payload = {"action": "create", "name": name, "states": states}
                if force_run_at is not None:
                    payload["run_at"] = force_run_at
            elif action == "schedule":
                payload = {"action": "schedule", "name": name, "run_at": run_at_val}
            elif action == "delete":
                payload = {"action": "delete", "name": name}
            else:
                return

            topic = mqtt_client.publish("motion/sequence", payload)
            lbl_seq_status.value = f"Acción '{action}' enviada para la secuencia '{name}'"
            log_event(f"Secuencia '{name}' ({action}) enviada a {topic}")
            page.update()
        except Exception as err:
            lbl_seq_status.value = f"Error en el formato JSON: {err}"
            page.update()

    # ==========================================================================
    # SECCIÓN 2: TRAYECTORIAS SOLICITADAS (LÍNEA RECTA 1m Y 1/4 DE CÍRCULO)
    # ==========================================================================
    tf_v_dms = ft.TextField(label="Velocidad Lineal", value="2.0", width=175, suffix="dm/s")
    tf_w_degs = ft.TextField(label="Velocidad de Giro", value="0.0", width=175, suffix="°/s")
    tf_dur_s = ft.TextField(label="Duración", value="5.0", width=155, suffix="s")

    lbl_motion_preview = ft.Text(
        "Resumen: Velocidad lineal = 2.0 dm/s (0.20 m/s) | Giro = 0.0 °/s | Duración = 5.0 s",
        color="#8B949E",
        size=13,
    )

    def publish_motion_state(state_dict: dict, description: str):
        topic = mqtt_client.publish("motion/state", state_dict)
        norm = normalize_motion_state(state_dict)
        cmd = kin.build_command(norm["v_m_s"], norm["w_rad_s"], norm["duration_s"], label=description)

        tf_v_dms.value = f"{norm['v_dm/s']:.4g}"
        tf_w_degs.value = f"{norm['w_deg/s']:.4g}"
        tf_dur_s.value = f"{norm['duration_s']:.3g}"
        tf_a0.value = f"{norm['alpha0_deg']:.1f}"
        tf_a1.value = f"{norm['alpha1_deg']:.1f}"
        tf_a2.value = f"{norm['alpha2_deg']:.1f}"
        sl_a1.value = max(-90.0, min(90.0, norm["alpha1_deg"]))
        sl_a2.value = max(-90.0, min(90.0, norm["alpha2_deg"]))

        lbl_motion_preview.value = (
            f"{description}: Velocidad = {norm['v_dm/s']} dm/s ({norm['v_m_s']:.2f} m/s) | "
            f"Giro = {norm['w_deg/s']} °/s | Rueda Izq = {cmd.v_l:.2f} m/s, Rueda Der = {cmd.v_r:.2f} m/s | "
            f"Brazo = ({norm['alpha1_deg']}°, {norm['alpha2_deg']}°) | Duración = {norm['duration_s']} s"
        )
        log_event(f"{description} enviado a {topic}")
        page.update()

    def on_straight_1m(e):
        st = kin.straight_line_state(
            distance_m=1.0,
            speed_m_s=0.20,
            alpha0_deg=float(tf_a0.value or 0),
            alpha1_deg=float(tf_a1.value or 0),
            alpha2_deg=float(tf_a2.value or 0),
        )
        publish_motion_state(st, "Avanzar 1 Metro en Línea Recta")

    def on_back_1m(e):
        st = kin.straight_line_state(
            distance_m=-1.0,
            speed_m_s=0.20,
            alpha0_deg=float(tf_a0.value or 0),
            alpha1_deg=float(tf_a1.value or 0),
            alpha2_deg=float(tf_a2.value or 0),
        )
        publish_motion_state(st, "Retroceder 1 Metro en Línea Recta")

    def on_quarter_left(e):
        st = kin.quarter_circle_state(
            radius_m=1.0,
            direction="left",
            speed_m_s=0.20,
            alpha0_deg=float(tf_a0.value or 0),
            alpha1_deg=float(tf_a1.value or 0),
            alpha2_deg=float(tf_a2.value or 0),
        )
        publish_motion_state(st, "1/4 de Círculo (Radio 1 m) a la Izquierda")

    def on_quarter_right(e):
        st = kin.quarter_circle_state(
            radius_m=1.0,
            direction="right",
            speed_m_s=0.20,
            alpha0_deg=float(tf_a0.value or 0),
            alpha1_deg=float(tf_a1.value or 0),
            alpha2_deg=float(tf_a2.value or 0),
        )
        publish_motion_state(st, "1/4 de Círculo (Radio 1 m) a la Derecha")

    def on_custom_state_send(e):
        try:
            st = {
                "v_dm/s": float(tf_v_dms.value or 0.0),
                "w_deg/s": float(tf_w_degs.value or 0.0),
                "alpha0_deg": float(tf_a0.value or 0.0),
                "alpha1_deg": float(tf_a1.value or 0.0),
                "alpha2_deg": float(tf_a2.value or 0.0),
                "duration_s": max(0.05, float(tf_dur_s.value or 1.0)),
            }
            publish_motion_state(st, "Movimiento Manual")
        except Exception as err:
            log_event(f"Error en valores manuales: {err}")

    # ==========================================================================
    # SECCIÓN 3: CONTROL DEL BRAZO ROBÓTICO CON DEMORA ASIGNADA
    # ==========================================================================
    tf_a1 = ft.TextField(label="Hombro Servo 1 (GP12)", value="0.0", width=195, suffix="°")
    tf_a2 = ft.TextField(label="Codo Servo 2 (GP13)", value="0.0", width=195, suffix="°")
    tf_a0 = ft.TextField(label="Base (Opcional)", value="0.0", width=165, suffix="°")
    tf_arm_dur = ft.TextField(label="Demora del Brazo", value="2.0", width=175, suffix="s")

    def on_sl_a1_change(e):
        tf_a1.value = f"{float(sl_a1.value):.1f}"
        page.update()

    def on_sl_a2_change(e):
        tf_a2.value = f"{float(sl_a2.value):.1f}"
        page.update()

    sl_a1 = ft.Slider(min=-90, max=90, divisions=36, value=0, label="{value}°", on_change=on_sl_a1_change, width=320)
    sl_a2 = ft.Slider(min=-90, max=90, divisions=36, value=0, label="{value}°", on_change=on_sl_a2_change, width=320)

    def send_arm_pose(a0: float, a1: float, a2: float, dur: float, label: str):
        tf_a0.value = f"{a0:.1f}"
        tf_a1.value = f"{a1:.1f}"
        tf_a2.value = f"{a2:.1f}"
        tf_arm_dur.value = f"{dur:.1f}"
        sl_a1.value = max(-90.0, min(90.0, a1))
        sl_a2.value = max(-90.0, min(90.0, a2))

        st = {
            "v_dm/s": 0.0,
            "w_deg/s": 0.0,
            "alpha0_deg": round(a0, 2),
            "alpha1_deg": round(a1, 2),
            "alpha2_deg": round(a2, 2),
            "duration_s": round(max(0.1, dur), 2),
        }
        publish_motion_state(st, label)

    def on_send_arm_button(e):
        try:
            a0 = float(tf_a0.value or 0.0)
            a1 = float(tf_a1.value or 0.0)
            a2 = float(tf_a2.value or 0.0)
            dur = max(0.1, float(tf_arm_dur.value or 2.0))
            send_arm_pose(a0, a1, a2, dur, f"Mover Brazo a ({a1:.1f}°, {a2:.1f}°) en {dur:.1f} s")
        except Exception as err:
            log_event(f"Error en ángulos del brazo: {err}")

    # ==========================================================================
    # SECCIÓN 4: PANTALLA OLED WATCHDOG (SCROLL CON POTENCIÓMETRO) Y CALIBRACIÓN
    # ==========================================================================
    oled_header_txt = ft.Text(
        "WDT 01/14 P:00%",
        font_family="Consolas",
        size=14,
        weight=ft.FontWeight.BOLD,
        color="#00F0FF",
    )
    oled_lines_col = ft.Column(
        spacing=2,
        controls=[
            ft.Text("ID:robot12 (PAR)", font_family="Consolas", size=13, color="#39FF14"),
            ft.Text("RSSI:-50dBm #1", font_family="Consolas", size=13, color="#39FF14"),
            ft.Text("RAM L:147K U:52K", font_family="Consolas", size=13, color="#39FF14"),
            ft.Text("Temp:26.6 C", font_family="Consolas", size=13, color="#39FF14"),
            ft.Text("Est:IDLE S:even", font_family="Consolas", size=13, color="#39FF14"),
            ft.Text("Paso:0/5", font_family="Consolas", size=13, color="#39FF14"),
        ],
    )
    lbl_pot_info = ft.Text(
        "Potenciómetro físico (GP28): 0 (0.0%) | Mostrando línea 1 | OLED lista",
        color="#58A6FF",
        size=13,
    )

    def on_remote_pot_change(e):
        val_u16 = int(sl_remote_pot.value)
        mqtt_client.publish("oled/scroll", {"pot_u16": val_u16})

    def on_reset_pot_auto(e):
        mqtt_client.publish("oled/scroll", {"mode": "auto"})
        log_event("Control de scroll OLED devuelto al potenciómetro físico en GP28.")

    sl_remote_pot = ft.Slider(
        min=0,
        max=65535,
        divisions=100,
        value=0,
        label="Scroll: {value}",
        on_change_end=on_remote_pot_change,
        width=280,
    )

    lbl_wdt_summary = ft.Text(
        "Señal Wi-Fi: - dBm | Memoria Libre: - B | Memoria Usada: - B | Temperatura: - °C | Paquetes: 0",
        color="#C9D1D9",
        size=13,
    )
    tasks_table_col = ft.Column(
        spacing=3,
        controls=[ft.Text("Esperando reporte del Watchdog desde la Pico W...", size=12, color="#8B949E")],
    )

    tf_cal_d = ft.TextField(label="Semitrocha d (m)", value="0.0675", width=165)
    tf_cal_vmax = ft.TextField(label="Vel. Máxima (m/s)", value="0.25", width=165)
    tf_cal_dz = ft.TextField(label="Potencia Mín. PWM", value="0.55", width=175)
    sw_inv_l = ft.Switch(label="Invertir Rueda Izquierda", value=False)
    sw_inv_r = ft.Switch(label="Invertir Rueda Derecha", value=False)

    def on_send_calibration(e):
        try:
            d_val = float(tf_cal_d.value or 0.0675)
            vmax_val = float(tf_cal_vmax.value or 0.25)
            dz_val = float(tf_cal_dz.value or 0.55)
            kin.d = d_val
            kin.v_max = vmax_val
            cfg = {
                "d": d_val,
                "v_max": vmax_val,
                "deadzone": dz_val,
                "invert_left": bool(sw_inv_l.value),
                "invert_right": bool(sw_inv_r.value),
            }
            topic = mqtt_client.publish("CAR/config", cfg)
            log_event(f"Calibración de motores enviada a {topic}")
        except Exception as err:
            log_event(f"Error en calibración: {err}")

    # ==========================================================================
    # RECEPCIÓN DE MENSAJES MQTT DESDE LA RASPBERRY PI PICO W
    # ==========================================================================
    def on_mqtt_status(connected: bool, text: str):
        status_badge.content.value = text
        status_badge.content.color = "#3FB950" if connected else "#F85149"
        page.update()

    def on_mqtt_message(local_topic: str, data):
        if not isinstance(data, dict):
            return

        if local_topic == "motion/status":
            msg_txt = data.get("message", "")
            state_str = str(data.get("state", "idle")).lower()
            seq_name = str(data.get("sequence", ""))
            step_num = int(data.get("step", 0))

            if state_str == "running":
                lbl_robot_live_state.content.value = f"Estado actual: EN MOVIMIENTO - {msg_txt}"
                lbl_robot_live_state.content.color = "#58A6FF"
                if seq_name == "even":
                    highlight_active_step(step_num)
            elif state_str == "completed":
                lbl_robot_live_state.content.value = f"Estado actual: COMPLETADO - {msg_txt}"
                lbl_robot_live_state.content.color = "#3FB950"
                if seq_name == "even":
                    highlight_active_step(6)
            else:
                lbl_robot_live_state.content.value = f"Estado actual: {msg_txt}"
            lbl_seq_status.value = msg_txt

        elif local_topic == "CAR/status":
            msg_txt = data.get("message", "")
            st = str(data.get("state", "")).lower()
            if st == "stopped":
                lbl_robot_live_state.content.value = f"Estado actual: DETENIDO - {msg_txt}"
                lbl_robot_live_state.content.color = "#F85149"

        elif local_topic == "oled/status":
            pot_u16 = data.get("pot_u16", 0)
            pot_pct = data.get("pot_pct", 0.0)
            s_idx = data.get("scroll_index", 0)
            total_l = data.get("total_lines", 1)
            vis = data.get("visible_lines", [])
            i2c_inf = data.get("i2c_info", "")

            oled_header_txt.value = f"WDT {s_idx + 1:02d}/{total_l:02d} P:{int(pot_pct):02d}%"
            oled_lines_col.controls = [
                ft.Text(str(line), font_family="Consolas", size=13, color="#39FF14") for line in vis
            ]
            lbl_pot_info.value = (
                f"Potenciómetro (GP28): {pot_u16} ({pot_pct:.1f}%) | "
                f"Línea OLED: {s_idx + 1} de {total_l} | Bus OLED: {i2c_inf}"
            )

        elif local_topic == "watchdog/stats":
            rssi = data.get("rssi", "-")
            m_free = data.get("mem_free_bytes", "-")
            m_used = data.get("mem_used_bytes", "-")
            temp = data.get("temperature_c", "-")
            sended = data.get("sended", 0)
            lbl_wdt_summary.value = (
                f"Señal Wi-Fi: {rssi} dBm | Memoria Libre: {m_free} B | "
                f"Memoria Usada: {m_used} B | Temperatura: {temp} °C | Paquete #{sended}"
            )

            rows = []
            for k, v in data.items():
                if isinstance(v, dict) and "min" in v and "max" in v and "avg" in v:
                    period = max(1.0, float(v.get("period", 100.0)))
                    cpu_use = (float(v["avg"]) / period) / 10.0
                    rows.append(
                        ft.Text(
                            f"Tarea {k:<13} -> Mín: {int(v['min']):>5} us | Máx: {int(v['max']):>6} us | "
                            f"Prom: {float(v['avg']):>6.1f} us | Uso CPU: {cpu_use:>4.1f}%",
                            font_family="Consolas",
                            size=12,
                            color="#C9D1D9",
                        )
                    )
            if rows:
                tasks_table_col.controls = rows

        page.update()

    mqtt_client.on_status_cb = on_mqtt_status
    mqtt_client.on_message_cb = on_mqtt_message
    mqtt_client.start()

    # ==========================================================================
    # TARJETAS DE LA INTERFAZ GRÁFICA
    # ==========================================================================
    header_card = card_box(
        padding=22,
        content=ft.Column(
            spacing=16,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Column(
                            spacing=4,
                            controls=[
                                ft.Text(
                                    "UDFJC IoT - Proyecto Segundo Corte: Coreografía Carrobot",
                                    size=22,
                                    weight=ft.FontWeight.BOLD,
                                    color="#F0F6FC",
                                ),
                                lbl_active_prefix,
                            ],
                        ),
                        status_badge,
                    ],
                ),
                ft.Row(
                    wrap=True,
                    spacing=14,
                    run_spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        tf_base_prefix,
                        tf_robot_id,
                        ft.Button("Actualizar Canal", icon=ft.Icons.CHECK_CIRCLE_OUTLINE, on_click=apply_prefix_change),
                        ft.Button(
                            "Abrir Gemelo Virtual Individual (Robot 12)",
                            icon=ft.Icons.OPEN_IN_BROWSER,
                            bgcolor="#1F6FEB",
                            color="#FFFFFF",
                            on_click=on_open_individual_twin,
                        ),
                        ft.Button(
                            "Abrir Escenario de Coreografía Grupal",
                            icon=ft.Icons.GROUPS,
                            on_click=on_open_group_choreo,
                        ),
                    ],
                ),
                tf_url_display,
                ft.Text(
                    "Nota para el Gemelo Virtual Web: Al abrir la página web individual, baja hasta el panel 'Virtual twin' y haz clic en el botón 'Subscribe Robot' para ver el robot 3D.",
                    size=12,
                    color="#D29922",
                ),
                lbl_robot_live_state,
            ],
        ),
    )

    section_choreo = card_box(
        border_color="#238636",
        content=ft.Column(
            spacing=12,
            controls=[
                ft.Text(
                    "1. COREOGRAFÍA PREDETERMINADA DEL ROBOT 12 (PAR)",
                    size=16,
                    weight=ft.FontWeight.BOLD,
                    color="#3FB950",
                ),
                ft.Text(
                    "Como tu código de robot es el 12 (número par), tu coreografía asignada es 'even.json'. "
                    "Oprime el botón verde para enviarla y ejecutarla inmediatamente en el carro físico y en el Gemelo Virtual:",
                    size=13,
                    color="#C9D1D9",
                ),
                ft.Row(
                    wrap=True,
                    spacing=14,
                    controls=[
                        ft.Button(
                            "INICIAR COREOGRAFÍA PREDETERMINADA (Robot 12 - Par)",
                            icon=ft.Icons.PLAY_CIRCLE_FILL,
                            bgcolor="#238636",
                            color="#FFFFFF",
                            on_click=on_run_default_even_choreo,
                        ),
                        ft.Button(
                            "DETENER ROBOT INMEDIATAMENTE",
                            icon=ft.Icons.STOP_CIRCLE,
                            bgcolor="#DA3633",
                            color="#FFFFFF",
                            on_click=on_stop_robot,
                        ),
                    ],
                ),
                lbl_seq_status,
                ft.Container(
                    padding=12,
                    border_radius=8,
                    bgcolor="#0D1117",
                    content=ft.Column(
                        spacing=6,
                        controls=[
                            ft.Text("Pasos que realiza la Coreografía Predeterminada (even.json):", size=13, weight=ft.FontWeight.BOLD, color="#58A6FF"),
                            *step_rows_controls,
                        ],
                    ),
                ),
                ft.ExpansionTile(
                    title=ft.Text("Opciones Avanzadas de Secuencia (Programar Hora, Coreografía Impar o Editar JSON)", size=13, color="#8B949E"),
                    controls=[
                        ft.Container(
                            padding=10,
                            content=ft.Column(
                                spacing=10,
                                controls=[
                                    ft.Row(
                                        wrap=True,
                                        spacing=10,
                                        controls=[
                                            tf_seq_name,
                                            tf_run_at,
                                            ft.Button("Fijar Hora +10s", icon=ft.Icons.SCHEDULE, on_click=set_iso_plus_10s),
                                            ft.Button("Cargar Plantilla Par (even)", icon=ft.Icons.DESCRIPTION, on_click=lambda e: load_preset_sequence("even")),
                                            ft.Button("Cargar Plantilla Impar (odd)", icon=ft.Icons.DESCRIPTION, on_click=lambda e: load_preset_sequence("odd")),
                                        ],
                                    ),
                                    ft.Row(
                                        wrap=True,
                                        spacing=10,
                                        controls=[
                                            ft.Button("Guardar Secuencia en el Robot", icon=ft.Icons.SAVE, on_click=lambda e: send_sequence_action("create", force_run_at=None)),
                                            ft.Button("Ejecutar Secuencia Guardada Ahora", icon=ft.Icons.PLAY_ARROW, on_click=lambda e: send_sequence_action("schedule", force_run_at="now")),
                                            ft.Button("Programar en la Hora Indicada", icon=ft.Icons.EVENT_AVAILABLE, on_click=lambda e: send_sequence_action("schedule", force_run_at=None)),
                                            ft.Button("Eliminar Secuencia", icon=ft.Icons.DELETE_OUTLINE, on_click=lambda e: send_sequence_action("delete")),
                                        ],
                                    ),
                                    tf_seq_json,
                                ],
                            ),
                        )
                    ],
                ),
            ],
        ),
    )

    section_trajectories = card_box(
        ft.Column(
            spacing=10,
            controls=[
                ft.Text(
                    "2. TRAYECTORIAS SOLICITADAS: LÍNEA RECTA (1 METRO) Y 1/4 DE CÍRCULO (RADIO 1 METRO)",
                    size=15,
                    weight=ft.FontWeight.BOLD,
                    color="#58A6FF",
                ),
                ft.Row(
                    wrap=True,
                    spacing=10,
                    controls=[
                        ft.Button("Avanzar 1 Metro en Línea Recta", icon=ft.Icons.ARROW_UPWARD, on_click=on_straight_1m),
                        ft.Button("Retroceder 1 Metro en Línea Recta", icon=ft.Icons.ARROW_DOWNWARD, on_click=on_back_1m),
                        ft.Button("1/4 de Círculo (R = 1 m) a la Izquierda", icon=ft.Icons.TURN_LEFT, on_click=on_quarter_left),
                        ft.Button("1/4 de Círculo (R = 1 m) a la Derecha", icon=ft.Icons.TURN_RIGHT, on_click=on_quarter_right),
                        ft.Button(
                            "Detener Carro",
                            icon=ft.Icons.STOP_CIRCLE,
                            bgcolor="#DA3633",
                            color="#FFFFFF",
                            on_click=on_stop_robot,
                        ),
                    ],
                ),
                ft.Divider(color="#30363D", height=8),
                ft.Row(
                    wrap=True,
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        tf_v_dms,
                        tf_w_degs,
                        tf_dur_s,
                        ft.Button("Enviar Movimiento Manual", icon=ft.Icons.SEND, on_click=on_custom_state_send),
                    ],
                ),
                lbl_motion_preview,
            ],
        )
    )

    section_arm = card_box(
        ft.Column(
            spacing=10,
            controls=[
                ft.Text(
                    "3. CONTROL DEL BRAZO ROBÓTICO CON ÁNGULOS Y DEMORA ASIGNADA",
                    size=15,
                    weight=ft.FontWeight.BOLD,
                    color="#D2A8FF",
                ),
                ft.Row(
                    wrap=True,
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        tf_a1,
                        tf_a2,
                        tf_a0,
                        tf_arm_dur,
                        ft.Button(
                            "Ubicar Brazo con Demora Asignada",
                            icon=ft.Icons.PRECISION_MANUFACTURING,
                            on_click=on_send_arm_button,
                        ),
                    ],
                ),
                ft.Row(
                    wrap=True,
                    spacing=20,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Row(
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[ft.Text("Hombro Servo 1 (-90° a +90°):", size=13), sl_a1],
                        ),
                        ft.Row(
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[ft.Text("Codo Servo 2 (-90° a +90°):", size=13), sl_a2],
                        ),
                    ],
                ),
                ft.Row(
                    wrap=True,
                    spacing=8,
                    controls=[
                        ft.Button(
                            "Posición Neutra (0°, 0° en 2 s)",
                            icon=ft.Icons.RESTORE,
                            on_click=lambda e: send_arm_pose(0.0, 0.0, 0.0, 2.0, "Brazo en Posición Neutra (0°, 0°)"),
                        ),
                        ft.Button(
                            "Pose Coreografía Par (+67.5°, -67.5° en 2 s)",
                            icon=ft.Icons.STAR_BORDER,
                            on_click=lambda e: send_arm_pose(90.0, 67.5, -67.5, 2.0, "Brazo en Pose de Coreografía (+67.5°, -67.5°)"),
                        ),
                        ft.Button(
                            "Brazo Extendido (+45°, +30° en 3 s)",
                            icon=ft.Icons.OPEN_IN_FULL,
                            on_click=lambda e: send_arm_pose(0.0, 45.0, 30.0, 3.0, "Brazo Extendido (+45°, +30°)"),
                        ),
                        ft.Button(
                            "Brazo Recogido (-45°, +45° en 1.5 s)",
                            icon=ft.Icons.CLOSE_FULLSCREEN,
                            on_click=lambda e: send_arm_pose(0.0, -45.0, 45.0, 1.5, "Brazo Recogido (-45°, +45°)"),
                        ),
                    ],
                ),
            ],
        )
    )

    oled_screen_box = ft.Container(
        width=285,
        height=180,
        padding=12,
        border_radius=8,
        bgcolor="#05080C",
        border=ft.Border(
            top=ft.BorderSide(2, "#58A6FF"),
            bottom=ft.BorderSide(2, "#58A6FF"),
            left=ft.BorderSide(2, "#58A6FF"),
            right=ft.BorderSide(2, "#58A6FF"),
        ),
        content=ft.Column(
            spacing=4,
            controls=[
                oled_header_txt,
                ft.Divider(color="#00F0FF", height=2),
                oled_lines_col,
            ],
        ),
    )

    section_oled_watchdog = card_box(
        ft.Column(
            spacing=12,
            controls=[
                ft.Text(
                    "4. PANTALLA OLED SSD1306 (INFORMACIÓN DEL WATCHDOG Y SCROLL CON POTENCIÓMETRO)",
                    size=15,
                    weight=ft.FontWeight.BOLD,
                    color="#F0883E",
                ),
                ft.Row(
                    wrap=True,
                    spacing=24,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                    controls=[
                        ft.Column(
                            spacing=6,
                            controls=[
                                ft.Text("Vista en Vivo de la Pantalla OLED 128x64:", size=13, weight=ft.FontWeight.BOLD),
                                oled_screen_box,
                            ],
                        ),
                        ft.Column(
                            spacing=8,
                            controls=[
                                lbl_wdt_summary,
                                lbl_pot_info,
                                ft.Row(
                                    wrap=True,
                                    spacing=10,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        ft.Text("Probar Scroll desde PC:", size=13),
                                        sl_remote_pot,
                                        ft.Button(
                                            "Usar Potenciómetro Físico (GP28)",
                                            icon=ft.Icons.SETTINGS_INPUT_COMPONENT,
                                            on_click=on_reset_pot_auto,
                                        ),
                                    ],
                                ),
                                ft.Text("Rendimiento de Tareas en la Raspberry Pi Pico W (Watchdog):", size=13, weight=ft.FontWeight.BOLD, color="#58A6FF"),
                                tasks_table_col,
                            ],
                        ),
                    ],
                ),
                ft.Divider(color="#30363D", height=8),
                ft.Text("Calibración de Potencia y Ruedas (Puente H L298N):", size=13, weight=ft.FontWeight.BOLD),
                ft.Row(
                    wrap=True,
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        tf_cal_d,
                        tf_cal_vmax,
                        tf_cal_dz,
                        sw_inv_l,
                        sw_inv_r,
                        ft.Button("Aplicar Calibración en la Pico W", icon=ft.Icons.TUNE, on_click=on_send_calibration),
                    ],
                ),
            ],
        )
    )

    section_logs = card_box(
        ft.Column(
            spacing=6,
            controls=[
                ft.Text("5. REGISTRO DE ACTIVIDAD Y TÓPICOS ENVIADOS", size=14, weight=ft.FontWeight.BOLD, color="#8B949E"),
                log_list,
            ],
        )
    )

    page.add(
        header_card,
        section_choreo,
        section_trajectories,
        section_arm,
        section_oled_watchdog,
        section_logs,
    )


if __name__ == "__main__":
    if hasattr(ft, "run"):
        ft.run(main)
    else:
        ft.app(target=main)
