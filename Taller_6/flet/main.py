"""
flet.main
=========
Dashboard de Monitoreo de Batería 18650, ADC y Divisor de Voltaje.
Taller 6 de IoT.
Integra:
- Lectura en vivo de AnalogIn_u16/GP28 desde la Raspberry Pi Pico WH.
- Reconstrucción del voltaje analógico y voltaje real de la batería.
- Configuración de resistencias del divisor de voltaje (R1 y R2).
- Tabla interactiva de comparación de mediciones (Multímetro vs ADC vs Flet).
- Estimación del porcentaje de carga (SoC) de la celda de Litio 18650.
"""

from datetime import datetime
import json
import random
import flet as ft
from flet.mqtt import MqttManager


def main(page: ft.Page):
    page.title = "Taller 6 - Monitoreo de Batería 18650 & ADC"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 20
    page.scroll = ft.ScrollMode.ALWAYS

    client_id = f"flet_battery_monitor_{random.randint(1000, 9999)}"
    prefix = "UDFJC/iot_ws/robot0/"

    # Variables de estado
    raw_u16 = 0
    v_pin = 0.0
    v_bat = 0.0
    soc_percent = 0.0

    # ----------------------------------------------------
    # 1. Cabecera y Conexión MQTT
    # ----------------------------------------------------
    lbl_broker = ft.Text("● Desconectado", color=ft.Colors.RED_400, weight=ft.FontWeight.BOLD)
    btn_connect = ft.Button(content="Conectar MQTT", icon=ft.Icons.POWER_SETTINGS_NEW)

    header = ft.Row([
        ft.Column([
            ft.Text("🔋 SISTEMA DE MONITOREO DE BATERÍA & ADC (TP4056)", size=20, weight=ft.FontWeight.BOLD),
            ft.Text("Cadena de transducción: Fenómeno físico → Divisor de Voltaje → ADC → MQTT → Dashboard", size=12, color=ft.Colors.GREY_400),
        ]),
        ft.Row([lbl_broker, btn_connect], spacing=12),
    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    # ----------------------------------------------------
    # 2. Configuración del Divisor de Voltaje
    # ----------------------------------------------------
    r1_input = ft.TextField(label="R1 superior (kΩ)", value="10.0", width=140)
    r2_input = ft.TextField(label="R2 inferior (kΩ)", value="10.0", width=140)
    txt_divider_factor = ft.Text("Factor de división: 2.00x", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_300)

    def get_divider_factor():
        try:
            r1 = float(r1_input.value)
            r2 = float(r2_input.value)
            return (r1 + r2) / r2
        except Exception:
            return 2.0

    def on_resistors_changed(e):
        factor = get_divider_factor()
        txt_divider_factor.value = f"Factor de división: {factor:.2f}x"
        recalculate_battery()
        page.update()

    r1_input.on_change = on_resistors_changed
    r2_input.on_change = on_resistors_changed

    card_divider = ft.Card(
        content=ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.SETTINGS_INPUT_COMPONENT, color=ft.Colors.CYAN_300),
                    ft.Text("1. Parámetros del Divisor de Voltaje", size=15, weight=ft.FontWeight.BOLD),
                ], spacing=8),
                ft.Text("V_pin = V_bat * (R2 / (R1 + R2))  →  V_bat = V_pin * ((R1 + R2) / R2)", size=11, color=ft.Colors.GREY_400),
                ft.Row([r1_input, r2_input], spacing=10),
                txt_divider_factor,
            ], spacing=10),
            padding=16,
        ),
        width=360,
    )

    # ----------------------------------------------------
    # 3. Panel de Batería en Vivo (Voltímetro y Porcentaje)
    # ----------------------------------------------------
    icon_battery = ft.Icon(ft.Icons.BATTERY_UNKNOWN, size=46, color=ft.Colors.GREY_400)
    txt_v_bat = ft.Text("0.00 V", size=32, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_300)
    txt_v_pin = ft.Text("En pin GP28: 0.00 V", size=13, color=ft.Colors.GREY_400)
    txt_raw_adc = ft.Text("ADC RAW (u16): 0", size=12, color=ft.Colors.PURPLE_300, weight=ft.FontWeight.BOLD)

    progress_soc = ft.ProgressBar(value=0.0, width=320, color=ft.Colors.GREEN_400)
    txt_soc = ft.Text("Carga estimada: 0%", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
    txt_status_bat = ft.Text("Esperando datos de la Pico WH...", size=12, color=ft.Colors.GREY_400)

    card_battery = ft.Card(
        content=ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.ELECTRIC_BOLT, color=ft.Colors.AMBER_400),
                    ft.Text("2. Medición en Tiempo Real (Batería 18650)", size=15, weight=ft.FontWeight.BOLD),
                ], spacing=8),
                ft.Row([
                    icon_battery,
                    ft.Column([
                        txt_v_bat,
                        txt_v_pin,
                        txt_raw_adc,
                    ], spacing=2),
                ], spacing=16),
                ft.Divider(),
                ft.Row([txt_soc, txt_status_bat], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                progress_soc,
            ], spacing=10),
            padding=16,
        ),
        width=420,
    )

    # ----------------------------------------------------
    # 4. Tabla de Comparación de Mediciones (Del Taller)
    # ----------------------------------------------------
    input_bat_multi = ft.TextField(label="V_batería (Multímetro)", value="", width=140, hint_text="Ej: 3.82")
    input_div_multi = ft.TextField(label="V_divisor (Multímetro)", value="", width=140, hint_text="Ej: 1.91")

    txt_tbl_div_calc = ft.Text("-- V", weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_300)
    txt_tbl_pico_u16 = ft.Text("--", weight=ft.FontWeight.BOLD, color=ft.Colors.PURPLE_300)
    txt_tbl_flet_v = ft.Text("-- V", weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400)
    txt_error_pct = ft.Text("Error: -- %", size=12, color=ft.Colors.AMBER_300, weight=ft.FontWeight.BOLD)

    def calculate_table_metrics(e):
        try:
            v_bat_m = float(input_bat_multi.value)
            factor = get_divider_factor()
            v_div_calc = v_bat_m / factor
            txt_tbl_div_calc.value = f"{v_div_calc:.3f} V"

            if v_bat > 0:
                err = abs(v_bat - v_bat_m) / v_bat_m * 100.0
                txt_error_pct.value = f"Error relativo Flet vs Multímetro: {err:.2f}%"
        except Exception:
            pass
        page.update()

    btn_calc_error = ft.Button(content="Calcular Error", icon=ft.Icons.CALCULATE, on_click=calculate_table_metrics)

    card_table = ft.Card(
        content=ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.TABLE_CHART, color=ft.Colors.GREEN_400),
                    ft.Text("3. Tabla de Comparación de Mediciones", size=15, weight=ft.FontWeight.BOLD),
                ], spacing=8),
                ft.Text("Complete los valores medidos con el multímetro en el laboratorio:", size=11, color=ft.Colors.GREY_400),
                ft.Row([input_bat_multi, input_div_multi, btn_calc_error], wrap=True),
                ft.Container(
                    content=ft.Column([
                        ft.Row([ft.Text("Divisor — valor calculado:", size=12, color=ft.Colors.GREY_300), txt_tbl_div_calc], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Row([ft.Text("Pico ADC — lectura u16:", size=12, color=ft.Colors.GREY_300), txt_tbl_pico_u16], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Row([ft.Text("Flet — voltaje publicado:", size=12, color=ft.Colors.GREY_300), txt_tbl_flet_v], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        txt_error_pct,
                    ], spacing=6),
                    bgcolor=ft.Colors.BLACK54,
                    padding=10,
                    border_radius=8,
                ),
            ], spacing=10),
            padding=16,
        ),
        width=440,
    )

    # ----------------------------------------------------
    # 5. Registro de Eventos
    # ----------------------------------------------------
    logs_view = ft.ListView(expand=True, spacing=4, auto_scroll=True, height=140)

    def add_log(tag: str, msg: str, color=ft.Colors.WHITE70):
        hora = datetime.now().strftime("%H:%M:%S")
        entry = ft.Row([
            ft.Text(f"[{hora}]", size=11, color=ft.Colors.GREY_500, weight=ft.FontWeight.BOLD),
            ft.Text(f"[{tag}]", size=11, color=color, weight=ft.FontWeight.BOLD),
            ft.Text(msg, size=11, color=ft.Colors.WHITE, expand=True),
        ], spacing=8)
        logs_view.controls.append(entry)
        if len(logs_view.controls) > 80:
            logs_view.controls.pop(0)

    card_logs = ft.Card(
        content=ft.Container(
            content=ft.Column([
                ft.Text("Registro de Telemetría ADC", size=14, weight=ft.FontWeight.BOLD),
                logs_view,
            ], spacing=6),
            padding=12,
        ),
        expand=True,
    )

    # ----------------------------------------------------
    # Procesamiento Matemático del ADC y Batería
    # ----------------------------------------------------
    def recalculate_battery():
        nonlocal v_pin, v_bat, soc_percent

        if raw_u16 > 0:
            # Voltaje en el pin de la Pico (ADC de 0 a 3.3V con rango de 16 bits 0-65535)
            v_pin = (raw_u16 / 65535.0) * 3.3
            factor = get_divider_factor()
            v_bat = v_pin * factor

            # Porcentaje para batería 18650 (Rango útil: 3.0V = 0%, 4.2V = 100%)
            soc_percent = max(0.0, min(100.0, ((v_bat - 3.0) / (4.2 - 3.0)) * 100.0))

            txt_v_bat.value = f"{v_bat:.2f} V"
            txt_v_pin.value = f"En pin GP28: {v_pin:.3f} V"
            txt_raw_adc.value = f"ADC RAW (u16): {raw_u16}"
            txt_tbl_pico_u16.value = str(raw_u16)
            txt_tbl_flet_v.value = f"{v_bat:.3f} V"

            txt_soc.value = f"Carga estimada: {soc_percent:.0f}%"
            progress_soc.value = soc_percent / 100.0

            if v_bat >= 4.0:
                txt_status_bat.value = "Batería Llena (Carga completa)"
                txt_status_bat.color = ft.Colors.GREEN_400
                progress_soc.color = ft.Colors.GREEN_400
                icon_battery.name = ft.Icons.BATTERY_FULL
                icon_battery.color = ft.Colors.GREEN_400
            elif v_bat >= 3.6:
                txt_status_bat.value = "Batería Nominal (Estado OK)"
                txt_status_bat.color = ft.Colors.CYAN_300
                progress_soc.color = ft.Colors.CYAN_300
                icon_battery.name = ft.Icons.BATTERY_5_BAR
                icon_battery.color = ft.Colors.CYAN_300
            elif v_bat >= 3.2:
                txt_status_bat.value = "Batería Media / Descargando"
                txt_status_bat.color = ft.Colors.AMBER_400
                progress_soc.color = ft.Colors.AMBER_400
                icon_battery.name = ft.Icons.BATTERY_3_BAR
                icon_battery.color = ft.Colors.AMBER_400
            else:
                txt_status_bat.value = "⚠️ Batería Crítica - Recargar con TP4056"
                txt_status_bat.color = ft.Colors.RED_400
                progress_soc.color = ft.Colors.RED_400
                icon_battery.name = ft.Icons.BATTERY_ALERT
                icon_battery.color = ft.Colors.RED_400

    # ----------------------------------------------------
    # Callbacks de MQTT
    # ----------------------------------------------------
    def on_conn_state(connected: bool, info: str):
        if connected:
            lbl_broker.value = "● HiveMQ Online"
            lbl_broker.color = ft.Colors.GREEN_400
            btn_connect.content = "Desconectar"
            btn_connect.icon = ft.Icons.POWER_OFF
            mqtt.subscribe(prefix + "AnalogIn_u16/#")
            mqtt.subscribe(prefix + "#")
            add_log("SISTEMA", f"Conectado y escuchando telemetría en {prefix}AnalogIn_u16/#", ft.Colors.GREEN_300)
        else:
            lbl_broker.value = "● Desconectado"
            lbl_broker.color = ft.Colors.RED_400
            btn_connect.content = "Conectar MQTT"
            btn_connect.icon = ft.Icons.POWER_SETTINGS_NEW
        page.update()

    def on_message_rx(topic: str, data: dict | str):
        nonlocal raw_u16
        local_topic = topic[len(prefix):] if topic.startswith(prefix) else topic

        if "AnalogIn_u16" in local_topic:
            val = data.get("value", 0) if isinstance(data, dict) else int(data)
            raw_u16 = int(val)
            recalculate_battery()
            add_log("ADC", f"Lectura RAW GP28: {raw_u16} → V_bat calculada: {v_bat:.2f} V ({soc_percent:.0f}%)", ft.Colors.CYAN_300)
            page.update()

    mqtt = MqttManager(
        client_id=client_id,
        on_connect_cb=on_conn_state,
        on_message_cb=on_message_rx,
    )

    def toggle_mqtt(e):
        if not mqtt.is_connected:
            lbl_broker.value = "Conectando..."
            lbl_broker.color = ft.Colors.AMBER_400
            page.update()
            mqtt.connect()
        else:
            mqtt.disconnect()

    btn_connect.on_click = toggle_mqtt

    # Montaje General
    page.add(
        ft.Column([
            header,
            ft.Row([card_battery, card_divider], wrap=True, vertical_alignment=ft.CrossAxisAlignment.START),
            card_table,
            card_logs,
        ], spacing=16)
    )

    mqtt.connect()


if __name__ == "__main__":
    ft.run(main)
