"""
flet.main
=========
Interfaz Gráfica del Taller 4 (Flet).
Resuelve el Mini-reto: "Modificar la interfaz para mostrar información de manera más útil".
Visualiza:
1. Salud de la Raspberry Pi Pico WH y estado del Watchdog.
2. Desempeño y tiempos de ejecución de las tareas del Scheduler en microsegundos (µs).
3. Uso de memoria RAM y temperatura interna.
4. Experimentación interactiva (control de actuadores y provocación de lag controlado).
"""

from datetime import datetime
import random
import time
import flet as ft
from flet.mqtt import MqttManager


def main(page: ft.Page):
    page.title = "Taller 4 - Monitor de Scheduler & Watchdog"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 20
    page.scroll = ft.ScrollMode.ALWAYS

    client_id = f"flet_taller4_{random.randint(1000, 9999)}"
    prefix = "UDFJC/iot_ws/robot0/"

    # Variables de estado
    last_heartbeat_time = None

    # ----------------------------------------------------
    # SECCIÓN 1: Conexión y Estado del Watchdog
    # ----------------------------------------------------
    icon_conn = ft.Icon(ft.Icons.CLOUD_OFF, color=ft.Colors.RED_400, size=22)
    txt_conn = ft.Text("Desconectado de HiveMQ", color=ft.Colors.RED_400, weight=ft.FontWeight.W_600)
    btn_connect = ft.Button(content="Conectar", icon=ft.Icons.POWER_SETTINGS_NEW)

    txt_watchdog_status = ft.Text("Watchdog: Esperando latido...", size=13, color=ft.Colors.GREY_400)
    icon_watchdog = ft.Icon(ft.Icons.HEALTH_AND_SAFETY, color=ft.Colors.GREY_500, size=20)

    # ----------------------------------------------------
    # SECCIÓN 2: Métricas de Salud del Microcontrolador
    # ----------------------------------------------------
    txt_heartbeat = ft.Text("0", size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_300)
    txt_temp = ft.Text("-- °C", size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_300)
    txt_rssi = ft.Text("-- dBm", size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_300)

    txt_ram_info = ft.Text("RAM: -- KB libres", size=12, color=ft.Colors.GREY_300)
    progress_ram = ft.ProgressBar(value=0.0, width=280, color=ft.Colors.BLUE_400)

    card_health = ft.Card(
        content=ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.ANALYTICS, color=ft.Colors.CYAN_300),
                    ft.Text("1. Salud del Sistema (Watchdog)", size=16, weight=ft.FontWeight.BOLD),
                ], spacing=8),
                ft.Row([
                    ft.Container(
                        content=ft.Column([
                            ft.Text("Heartbeat", size=11, color=ft.Colors.GREY_400),
                            txt_heartbeat,
                        ]),
                        padding=10,
                        bgcolor=ft.Colors.WHITE10,
                        border_radius=8,
                        expand=True,
                    ),
                    ft.Container(
                        content=ft.Column([
                            ft.Text("Temp Pico", size=11, color=ft.Colors.GREY_400),
                            txt_temp,
                        ]),
                        padding=10,
                        bgcolor=ft.Colors.WHITE10,
                        border_radius=8,
                        expand=True,
                    ),
                    ft.Container(
                        content=ft.Column([
                            ft.Text("Wi-Fi RSSI", size=11, color=ft.Colors.GREY_400),
                            txt_rssi,
                        ]),
                        padding=10,
                        bgcolor=ft.Colors.WHITE10,
                        border_radius=8,
                        expand=True,
                    ),
                ], spacing=10),
                txt_ram_info,
                progress_ram,
            ], spacing=12),
            padding=16,
        ),
        width=380,
    )

    # ----------------------------------------------------
    # SECCIÓN 3: Desempeño de Tareas del Scheduler (µs)
    # ----------------------------------------------------
    tasks_list_view = ft.ListView(expand=True, spacing=8, height=180)

    def render_task_card(name: str, period_ms: int, avg_us: float, max_us: float, min_us: float):
        # Alerta visual si una tarea tarda demasiado (más de 5000 µs = 5 ms)
        is_slow = max_us > 5000
        border_color = ft.Colors.RED_400 if is_slow else ft.Colors.TRANSPARENT
        status_label = "⚠️ LENTO" if is_slow else "⚡ OK"
        status_color = ft.Colors.RED_300 if is_slow else ft.Colors.GREEN_300

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text(f"Tarea: {name}", weight=ft.FontWeight.BOLD, size=13, color=ft.Colors.WHITE),
                    ft.Text(f"Periodo: {period_ms} ms", size=11, color=ft.Colors.CYAN_200),
                    ft.Text(status_label, size=11, color=status_color, weight=ft.FontWeight.BOLD),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Row([
                    ft.Text(f"Promedio: {avg_us:.1f} µs", size=11, color=ft.Colors.GREY_300),
                    ft.Text(f"Mín: {min_us:.0f} µs", size=11, color=ft.Colors.GREY_400),
                    ft.Text(f"Máx: {max_us:.0f} µs", size=11, color=ft.Colors.AMBER_300, weight=ft.FontWeight.BOLD),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ], spacing=4),
            bgcolor=ft.Colors.WHITE10,
            border=ft.Border(
                top=ft.BorderSide(1, border_color),
                right=ft.BorderSide(1, border_color),
                bottom=ft.BorderSide(1, border_color),
                left=ft.BorderSide(1, border_color),
            ) if is_slow else None,
            padding=8,
            border_radius=8,
        )

    card_scheduler = ft.Card(
        content=ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.SCHEDULE, color=ft.Colors.AMBER_400),
                    ft.Text("2. Perfilador de Tareas (Scheduler)", size=16, weight=ft.FontWeight.BOLD),
                ], spacing=8),
                ft.Text("Tiempos de ejecución medidos en microsegundos (ticks_us):", size=12, color=ft.Colors.GREY_400),
                tasks_list_view,
            ], spacing=10),
            padding=16,
        ),
        width=460,
    )

    # ----------------------------------------------------
    # SECCIÓN 4: Control de Actuadores y Experimentos
    # ----------------------------------------------------
    def toggle_led(val: int):
        mqtt.publish(prefix + "led/LED", {"value": val})
        add_log("CONTROL", f"Comando enviado a LED -> {val}", ft.Colors.BLUE_300)

    btn_led_on = ft.Button(content="Encender LED", icon=ft.Icons.LIGHTBULB, on_click=lambda e: toggle_led(1))
    btn_led_off = ft.Button(content="Apagar LED", icon=ft.Icons.LIGHTBULB_OUTLINE, on_click=lambda e: toggle_led(0))

    def simulate_delay(ms: int):
        mqtt.publish(prefix + "cmd/lag", {"ms": ms})
        add_log("EXP", f"Inyectando retraso deliberado de {ms} ms en la Pico WH", ft.Colors.AMBER_400)

    btn_lag = ft.Button(
        content="Inyectar Lag (80 ms)",
        icon=ft.Icons.WARNING_AMBER,
        on_click=lambda e: simulate_delay(80),
    )

    card_control = ft.Card(
        content=ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.TUNE, color=ft.Colors.GREEN_400),
                    ft.Text("3. Control & Experimento", size=16, weight=ft.FontWeight.BOLD),
                ], spacing=8),
                ft.Text("Actuador Físico (Pico WH):", size=12, color=ft.Colors.GREY_400),
                ft.Row([btn_led_on, btn_led_off], wrap=True),
                ft.Divider(),
                ft.Text("Demostrar el impacto de tareas lentas:", size=12, color=ft.Colors.GREY_400),
                btn_lag,
                ft.Text("Observa el pico de tiempo máximo en la tarea 'estado_actuadores'.", size=11, color=ft.Colors.GREY_500),
            ], spacing=10),
            padding=16,
        ),
        width=320,
    )

    # ----------------------------------------------------
    # SECCIÓN 5: Registro de Eventos
    # ----------------------------------------------------
    logs_view = ft.ListView(expand=True, spacing=4, auto_scroll=True, height=160)

    def add_log(tag: str, msg: str, color=ft.Colors.WHITE70):
        hora = datetime.now().strftime("%H:%M:%S")
        entry = ft.Row([
            ft.Text(f"[{hora}]", size=11, color=ft.Colors.GREY_500, weight=ft.FontWeight.BOLD),
            ft.Text(f"[{tag}]", size=11, color=color, weight=ft.FontWeight.BOLD),
            ft.Text(msg, size=11, color=ft.Colors.WHITE70, expand=True),
        ], spacing=8)
        logs_view.controls.append(entry)
        if len(logs_view.controls) > 80:
            logs_view.controls.pop(0)

    card_logs = ft.Card(
        content=ft.Container(
            content=ft.Column([
                ft.Text("Registro de Eventos y Telemetría", size=14, weight=ft.FontWeight.BOLD),
                logs_view,
            ], spacing=6),
            padding=12,
        ),
        expand=True,
    )

    # ----------------------------------------------------
    # Lógica de Mensajería MQTT
    # ----------------------------------------------------
    def on_connection_state(connected: bool, message: str):
        if connected:
            icon_conn.name = ft.Icons.CLOUD_DONE
            icon_conn.color = ft.Colors.GREEN_400
            txt_conn.value = "En línea (HiveMQ)"
            txt_conn.color = ft.Colors.GREEN_400
            btn_connect.content = "Desconectar"
            btn_connect.icon = ft.Icons.POWER_OFF
            mqtt.subscribe(prefix + "#")
            add_log("SISTEMA", f"Conectado y suscrito a {prefix}#", ft.Colors.GREEN_300)
        else:
            icon_conn.name = ft.Icons.CLOUD_OFF
            icon_conn.color = ft.Colors.RED_400
            txt_conn.value = message
            txt_conn.color = ft.Colors.RED_400
            btn_connect.content = "Conectar"
            btn_connect.icon = ft.Icons.POWER_SETTINGS_NEW
        page.update()

    def on_message_received(topic: str, data: dict | str):
        nonlocal last_heartbeat_time

        # Telemetría del Watchdog y Scheduler
        if topic.endswith("watchdog/stats") and isinstance(data, dict):
            last_heartbeat_time = time.time()
            icon_watchdog.color = ft.Colors.GREEN_400
            txt_watchdog_status.value = "Watchdog: Activo y respondiendo"
            txt_watchdog_status.color = ft.Colors.GREEN_300

            # 1. Actualizar Salud
            txt_heartbeat.value = str(data.get("heartbeat", 0))
            txt_temp.value = f"{data.get('temp_c', 0)} °C"
            txt_rssi.value = f"{data.get('wifi_rssi', 0)} dBm"

            mem_free = data.get("mem_free_bytes", 0)
            mem_alloc = data.get("mem_alloc_bytes", 0)
            total_ram = mem_free + mem_alloc
            if total_ram > 0:
                txt_ram_info.value = f"RAM: {mem_free // 1024} KB libres de {total_ram // 1024} KB"
                progress_ram.value = min(max(mem_alloc / total_ram, 0.0), 1.0)

            # 2. Actualizar Perfilador de Tareas
            tasks_stats = data.get("tasks_stats", {})
            tasks_list_view.controls.clear()
            for t_name, t_info in tasks_stats.items():
                period = t_info.get("period_ms", 0)
                avg_u = t_info.get("avg", 0)
                max_u = t_info.get("max", 0)
                min_u = t_info.get("min", 0)
                tasks_list_view.controls.append(
                    render_task_card(t_name, period, avg_u, max_u, min_u)
                )

            add_log("TELEMETRÍA", f"Heartbeat #{data.get('heartbeat')}: Salud y estadísticas actualizadas", ft.Colors.CYAN_300)

        else:
            add_log("RX", f"[{topic}] -> {data}", ft.Colors.WHITE70)

        page.update()

    mqtt = MqttManager(
        client_id=client_id,
        on_connect_cb=on_connection_state,
        on_message_cb=on_message_received,
    )

    def handle_btn_connect(e):
        if not mqtt.is_connected:
            txt_conn.value = "Conectando..."
            txt_conn.color = ft.Colors.AMBER_400
            page.update()
            mqtt.connect()
        else:
            mqtt.disconnect()

    btn_connect.on_click = handle_btn_connect

    # Montaje General
    page.add(
        ft.Column([
            ft.Row([
                ft.Column([
                    ft.Text("⚡ TALLER 4: SCHEDULER & MONITOR DE TAREAS", size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_300),
                    ft.Text("Multitarea no bloqueante, perfilado de microsegundos y supervisión con Watchdog", size=13, color=ft.Colors.GREY_400),
                ]),
                ft.Row([
                    ft.Row([icon_watchdog, txt_watchdog_status]),
                    ft.Row([icon_conn, txt_conn]),
                    btn_connect,
                ], spacing=16),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Row([card_health, card_scheduler, card_control], wrap=True, vertical_alignment=ft.CrossAxisAlignment.START),
            card_logs,
        ], spacing=16)
    )


if __name__ == "__main__":
    ft.run(main)
