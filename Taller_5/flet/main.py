"""
flet.main
=========
Consola Central de Seguridad IoT - Control de Acceso y Sistema de Alarma.
Desarrollada en Flet nativo para el Taller 5.
Integra:
- Entrada Infrarroja (Recepción desde Pico WH en GP2 o teclado numérico virtual).
- Entrada Digital de Puerta (Recepción desde sensor en GP1 o simulación en UI).
- Salida Digital de Sirena (Sincronización con el LED onboard de la Pico WH vía MQTT).
- Lógica de estados, control de clave, intrusión y registro de auditoría.
"""

from datetime import datetime
import json
import random
import threading
import time
import flet as ft
from flet.mqtt import MqttManager


def main(page: ft.Page):
    page.title = "Consola Central de Seguridad IoT - Flet"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 20
    page.scroll = ft.ScrollMode.ALWAYS

    # ----------------------------------------------------
    # VARIABLES DE ESTADO Y SEGURIDAD
    # ----------------------------------------------------
    secret_code = "1111"
    alarma_armada = False
    puerta_abierta = False
    sirena = False
    buffer_clave = ""
    pass_change_mode = "IDLE"  # 'IDLE', 'VERIFY_OLD', 'ENTER_NEW'

    client_id = f"flet_alarm_center_{random.randint(1000, 9999)}"
    prefix = "UDFJC/iot_ws/robot0/"

    # ----------------------------------------------------
    # 1. Cabecera y Banner de Alerta Superior
    # ----------------------------------------------------
    lbl_broker = ft.Text("● Desconectado", color=ft.Colors.RED_400, weight=ft.FontWeight.BOLD)
    btn_connect = ft.Button(content="Conectar MQTT", icon=ft.Icons.POWER_SETTINGS_NEW)

    header_row = ft.Row([
        ft.Column([
            ft.Text("CONSOLA CENTRAL DE SEGURIDAD (HOST CONTROLLER)", size=20, weight=ft.FontWeight.BOLD),
            ft.Text("Taller 5 - Control de Acceso, GPIOs y Receptor Infrarrojo", size=12, color=ft.Colors.GREY_400),
        ]),
        ft.Row([lbl_broker, btn_connect], spacing=12),
    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    # Banner Dinámico de Estado
    banner_text = ft.Text(
        "🛡️ SISTEMA DESARMADO",
        size=18,
        weight=ft.FontWeight.BOLD,
        color=ft.Colors.GREEN_400,
        text_align=ft.TextAlign.CENTER,
    )
    banner_subtext = ft.Text("", size=12, color=ft.Colors.WHITE70, text_align=ft.TextAlign.CENTER)

    banner_container = ft.Container(
        content=ft.Column([banner_text, banner_subtext], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        bgcolor=ft.Colors.GREEN_900,
        padding=15,
        border_radius=8,
        alignment=ft.alignment.center,
        height=85,
    )

    # ----------------------------------------------------
    # 2. Panel 1: Entrada Infrarroja (Receptor IR en Pico W)
    # ----------------------------------------------------
    digit_labels = [
        ft.Text("•", size=26, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_400)
        for _ in range(4)
    ]
    digit_boxes = [
        ft.Container(
            content=digit_labels[i],
            alignment=ft.alignment.center,
            width=50,
            height=58,
            bgcolor=ft.Colors.BLACK54,
            border=ft.Border(
                top=ft.BorderSide(2, ft.Colors.GREY_700),
                right=ft.BorderSide(2, ft.Colors.GREY_700),
                bottom=ft.BorderSide(2, ft.Colors.GREY_700),
                left=ft.BorderSide(2, ft.Colors.GREY_700),
            ),
            border_radius=6,
        )
        for i in range(4)
    ]

    lbl_key_hint = ft.Text("Apunta el control a GP2 o usa el teclado para ingresar 4 dígitos", size=11, color=ft.Colors.GREY_400)

    # Teclado Virtual para Pruebas en Pantalla
    def on_virtual_key_click(k: str):
        process_key(k)

    keypad_rows = [
        ft.Row([
            ft.Button(content="1", width=50, on_click=lambda e: on_virtual_key_click("1")),
            ft.Button(content="2", width=50, on_click=lambda e: on_virtual_key_click("2")),
            ft.Button(content="3", width=50, on_click=lambda e: on_virtual_key_click("3")),
        ], spacing=6),
        ft.Row([
            ft.Button(content="4", width=50, on_click=lambda e: on_virtual_key_click("4")),
            ft.Button(content="5", width=50, on_click=lambda e: on_virtual_key_click("5")),
            ft.Button(content="6", width=50, on_click=lambda e: on_virtual_key_click("6")),
        ], spacing=6),
        ft.Row([
            ft.Button(content="7", width=50, on_click=lambda e: on_virtual_key_click("7")),
            ft.Button(content="8", width=50, on_click=lambda e: on_virtual_key_click("8")),
            ft.Button(content="9", width=50, on_click=lambda e: on_virtual_key_click("9")),
        ], spacing=6),
        ft.Row([
            ft.Button(content="*", width=50, on_click=lambda e: on_virtual_key_click("*")),
            ft.Button(content="0", width=50, on_click=lambda e: on_virtual_key_click("0")),
            ft.Button(content="#", width=50, on_click=lambda e: on_virtual_key_click("#")),
        ], spacing=6),
    ]

    card_ir = ft.Card(
        content=ft.Container(
            content=ft.Column([
                ft.Text("ENTRADA IR (PICO W - GP2)", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_300),
                ft.Row(digit_boxes, alignment=ft.MainAxisAlignment.CENTER),
                lbl_key_hint,
                ft.Divider(),
                ft.Text("Teclado Virtual de Pruebas:", size=12, color=ft.Colors.GREY_400),
                ft.Column(keypad_rows, spacing=6, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            ], spacing=10),
            padding=16,
        ),
        width=300,
    )

    # ----------------------------------------------------
    # 3. Panel 2: Estado de Variables y Acciones
    # ----------------------------------------------------
    tag_pass = ft.Text("clave_seguridad = '1111'", size=12, color=ft.Colors.PURPLE_200, weight=ft.FontWeight.BOLD)
    tag_armada = ft.Text("alarma_armada = False (DESARMADA)", size=12, color=ft.Colors.GREEN_400, weight=ft.FontWeight.BOLD)
    tag_puerta = ft.Text("puerta_abierta = False (CERRADA)", size=12, color=ft.Colors.GREEN_400, weight=ft.FontWeight.BOLD)
    tag_sirena = ft.Text("sirena = False (APAGADA)", size=12, color=ft.Colors.GREY_400, weight=ft.FontWeight.BOLD)
    tag_led = ft.Text("led_fisico = 0 (APAGADO)", size=12, color=ft.Colors.GREY_400, weight=ft.FontWeight.BOLD)

    btn_toggle_door = ft.Button(content="Simular: ABRIR PUERTA", icon=ft.Icons.DOOR_SLIDING)
    btn_change_pass = ft.Button(content="🔑 CAMBIAR CLAVE", icon=ft.Icons.KEY)
    btn_reset = ft.Button(content="🔄 REINICIAR SISTEMA", icon=ft.Icons.REFRESH)

    card_vars = ft.Card(
        content=ft.Container(
            content=ft.Column([
                ft.Text("ESTADO DE VARIABLES EN TIEMPO REAL", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_300),
                ft.Container(content=tag_pass, bgcolor=ft.Colors.BLACK54, padding=6, border_radius=4),
                ft.Container(content=tag_armada, bgcolor=ft.Colors.BLACK54, padding=6, border_radius=4),
                ft.Container(content=tag_puerta, bgcolor=ft.Colors.BLACK54, padding=6, border_radius=4),
                ft.Container(content=tag_sirena, bgcolor=ft.Colors.BLACK54, padding=6, border_radius=4),
                ft.Container(content=tag_led, bgcolor=ft.Colors.BLACK54, padding=6, border_radius=4),
                ft.Divider(),
                btn_toggle_door,
                ft.Row([btn_change_pass, btn_reset], wrap=True),
            ], spacing=8),
            padding=16,
        ),
        width=360,
    )

    # ----------------------------------------------------
    # 4. Panel 3: Verificación de Requisitos
    # ----------------------------------------------------
    rule1 = ft.Text("1. [ ] Clave IR activa / desactiva alarma", size=12, color=ft.Colors.GREY_400)
    rule2 = ft.Text("2. [ ] Alarma activa + Puerta abierta -> Sirena", size=12, color=ft.Colors.GREY_400)
    rule3 = ft.Text("3. [ ] Clave equivocada -> Dispara sirena", size=12, color=ft.Colors.GREY_400)
    rule4 = ft.Text("4. [ ] Alarma desactivada + Puerta -> Sin sirena", size=12, color=ft.Colors.GREY_400)
    rule5 = ft.Text("5. [ ] Cambio de clave: Validar actual -> Nueva", size=12, color=ft.Colors.GREY_400)

    card_rules = ft.Card(
        content=ft.Container(
            content=ft.Column([
                ft.Text("REQUISITOS DEL SISTEMA DE SEGURIDAD", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_300),
                rule1,
                rule2,
                rule3,
                rule4,
                rule5,
            ], spacing=8),
            padding=16,
        ),
        width=340,
    )

    # ----------------------------------------------------
    # 5. Terminal de Eventos y Registro
    # ----------------------------------------------------
    logs_view = ft.ListView(expand=True, spacing=4, auto_scroll=True, height=150)

    def add_log(tag: str, msg: str, color=ft.Colors.WHITE70):
        hora = datetime.now().strftime("%H:%M:%S")
        entry = ft.Row([
            ft.Text(f"[{hora}]", size=11, color=ft.Colors.GREY_500, weight=ft.FontWeight.BOLD),
            ft.Text(f"[{tag}]", size=11, color=color, weight=ft.FontWeight.BOLD),
            ft.Text(msg, size=11, color=ft.Colors.WHITE, expand=True),
        ], spacing=8)
        logs_view.controls.append(entry)
        if len(logs_view.controls) > 100:
            logs_view.controls.pop(0)

    card_logs = ft.Card(
        content=ft.Container(
            content=ft.Column([
                ft.Text("REGISTRO DE EVENTOS (AUDITORÍA)", size=14, weight=ft.FontWeight.BOLD),
                logs_view,
            ], spacing=6),
            padding=12,
        ),
        expand=True,
    )

    # ----------------------------------------------------
    # SINCRONIZACIÓN DE HARDWARE Y DASHBOARD
    # ----------------------------------------------------
    def sync_hardware_siren():
        val = 1 if sirena else 0
        payload = {"value": val}
        # Notificar a la Pico WH para encender/apagar el LED sirena
        mqtt.publish(prefix + "GPIOOut/LED", payload)
        mqtt.publish(prefix + "led/LED", payload)

    def update_dashboard(reason: str):
        nonlocal pass_change_mode

        # 1. Banner Principal
        if sirena:
            banner_text.value = "🚨 ⚠️ ALARMA ¡INTRUSIÓN! (SIRENA DISPARADA)"
            banner_text.color = ft.Colors.RED_100
            banner_subtext.value = reason.upper()
            banner_container.bgcolor = ft.Colors.RED_900
        elif alarma_armada:
            banner_text.value = "🔒 SISTEMA ARMADO (VIGILANDO PUERTA Y PERÍMETRO)"
            banner_text.color = ft.Colors.BLUE_100
            banner_subtext.value = reason
            banner_container.bgcolor = ft.Colors.BLUE_900
        elif pass_change_mode != "IDLE":
            banner_text.value = "🔑 CAMBIO DE CLAVE EN PROCESO"
            banner_text.color = ft.Colors.PURPLE_100
            banner_subtext.value = reason
            banner_container.bgcolor = ft.Colors.PURPLE_900
        else:
            banner_text.value = "🛡️ SISTEMA DESARMADO (ACCESO LIBRE)"
            banner_text.color = ft.Colors.GREEN_100
            banner_subtext.value = reason
            banner_container.bgcolor = ft.Colors.GREEN_900

        # 2. Etiquetas de variables
        tag_pass.value = f"clave_seguridad = '{secret_code}'"

        arm_txt = "ARMADA" if alarma_armada else "DESARMADA"
        tag_armada.value = f"alarma_armada = {alarma_armada} ({arm_txt})"
        tag_armada.color = ft.Colors.BLUE_400 if alarma_armada else ft.Colors.GREEN_400

        puerta_txt = "ABIERTA" if puerta_abierta else "CERRADA"
        color_p = ft.Colors.RED_400 if (puerta_abierta and alarma_armada) else (ft.Colors.AMBER_400 if puerta_abierta else ft.Colors.GREEN_400)
        tag_puerta.value = f"puerta_abierta = {puerta_abierta} ({puerta_txt})"
        tag_puerta.color = color_p
        btn_toggle_door.content = "Simular: CERRAR PUERTA" if puerta_abierta else "Simular: ABRIR PUERTA"

        sirena_txt = "DISPARADA" if sirena else "APAGADA"
        tag_sirena.value = f"sirena = {sirena} ({sirena_txt})"
        tag_sirena.color = ft.Colors.RED_400 if sirena else ft.Colors.GREY_400

        led_val = 1 if sirena else 0
        led_txt = "ENCENDIDO" if led_val == 1 else "APAGADO"
        tag_led.value = f"led_fisico (Pico WH) = {led_val} ({led_txt})"
        tag_led.color = ft.Colors.RED_400 if led_val == 1 else ft.Colors.GREY_400

        # 3. Resaltar Requisitos
        for r in [rule1, rule2, rule3, rule4, rule5]:
            r.color = ft.Colors.GREY_400

        if "Clave cambiada" in reason:
            rule5.color = ft.Colors.PURPLE_300
        elif "Clave correcta" in reason:
            rule1.color = ft.Colors.GREEN_400
        elif "INTRUSIÓN" in reason or (alarma_armada and puerta_abierta and sirena):
            rule2.color = ft.Colors.RED_400
        elif "INCORRECTA" in reason:
            rule3.color = ft.Colors.RED_400
        elif not alarma_armada and puerta_abierta and not sirena:
            rule4.color = ft.Colors.AMBER_400

        add_log("ESTADO", reason, ft.Colors.CYAN_300)
        page.update()

    # ----------------------------------------------------
    # LÓGICA DE PROCESAMIENTO IR Y CLAVE
    # ----------------------------------------------------
    def reset_digits_ui():
        for i in range(4):
            digit_labels[i].value = "•"
            digit_labels[i].color = ft.Colors.GREY_400
            digit_boxes[i].border = ft.Border(
                top=ft.BorderSide(2, ft.Colors.GREY_700),
                right=ft.BorderSide(2, ft.Colors.GREY_700),
                bottom=ft.BorderSide(2, ft.Colors.GREY_700),
                left=ft.BorderSide(2, ft.Colors.GREY_700),
            )
        page.update()

    def flash_digits(color):
        for i in range(4):
            digit_boxes[i].border = ft.Border(
                top=ft.BorderSide(2, color),
                right=ft.BorderSide(2, color),
                bottom=ft.BorderSide(2, color),
                left=ft.BorderSide(2, color),
            )
        page.update()

        def restore():
            time.sleep(0.6)
            reset_digits_ui()

        threading.Thread(target=restore, daemon=True).start()

    def process_key(key: str):
        nonlocal buffer_clave, pass_change_mode, secret_code, alarma_armada, sirena

        # Solo aceptar dígitos 0-9
        if key not in "0123456789":
            return

        buffer_clave += key
        count = len(buffer_clave)

        color_border = ft.Colors.PURPLE_400 if pass_change_mode != "IDLE" else ft.Colors.CYAN_400
        for i in range(4):
            if i < count:
                digit_labels[i].value = buffer_clave[i]
                digit_labels[i].color = color_border
                digit_boxes[i].border = ft.Border(
                    top=ft.BorderSide(2, color_border),
                    right=ft.BorderSide(2, color_border),
                    bottom=ft.BorderSide(2, color_border),
                    left=ft.BorderSide(2, color_border),
                )
            else:
                digit_labels[i].value = "•"
                digit_labels[i].color = ft.Colors.GREY_400

        add_log("IR", f"Dígito: '{key}' | Búfer: [{buffer_clave}]", ft.Colors.GREEN_300)
        page.update()

        if count == 4:
            code = buffer_clave
            buffer_clave = ""

            # CASO A: Verificando clave anterior para autorizar cambio
            if pass_change_mode == "VERIFY_OLD":
                if code == secret_code:
                    pass_change_mode = "ENTER_NEW"
                    flash_digits(ft.Colors.GREEN_400)
                    lbl_key_hint.value = "PASO 2/2: Ingrese la NUEVA clave de 4 dígitos"
                    lbl_key_hint.color = ft.Colors.GREEN_400
                    update_dashboard("Clave actual validada. Ingrese los 4 nuevos dígitos.")
                else:
                    pass_change_mode = "IDLE"
                    sirena = True
                    flash_digits(ft.Colors.RED_400)
                    sync_hardware_siren()
                    update_dashboard(f"¡CLAVE ERRÓNEA ({code}) EN CAMBIO! Sirena DISPARADA")

            # CASO B: Guardando nueva clave
            elif pass_change_mode == "ENTER_NEW":
                secret_code = code
                pass_change_mode = "IDLE"
                flash_digits(ft.Colors.GREEN_400)
                lbl_key_hint.value = "Apunta el control a GP2 o usa el teclado para ingresar 4 dígitos"
                lbl_key_hint.color = ft.Colors.GREY_400
                update_dashboard(f"Clave cambiada con éxito a '{secret_code}'")

            # CASO C: Operación normal (Activar/Desactivar alarma)
            else:
                if code == secret_code:
                    if alarma_armada or sirena:
                        alarma_armada = False
                        sirena = False
                        causa = "Clave correcta: Sistema DESARMADO / Sirena apagada"
                    else:
                        alarma_armada = True
                        sirena = False
                        causa = "Clave correcta: Sistema ARMADO (Vigilando)"
                else:
                    sirena = True
                    causa = f"¡CLAVE INCORRECTA ({code})! Sirena DISPARADA"

                flash_digits(ft.Colors.RED_400 if sirena else ft.Colors.GREEN_400)
                sync_hardware_siren()
                update_dashboard(causa)

    # ----------------------------------------------------
    # ACCIONES DE BOTONES
    # ----------------------------------------------------
    def toggle_door(e):
        nonlocal puerta_abierta, sirena
        puerta_abierta = not puerta_abierta

        if puerta_abierta and alarma_armada:
            sirena = True
            causa = "¡INTRUSIÓN! PUERTA 1 ABIERTA con alarma armada"
        else:
            txt_p = "ABIERTA" if puerta_abierta else "CERRADA"
            causa = f"Puerta {txt_p} (Alarma desarmada)"

        sync_hardware_siren()
        update_dashboard(causa)

    btn_toggle_door.on_click = toggle_door

    def request_password_change(e):
        nonlocal pass_change_mode, buffer_clave
        if sirena:
            add_log("AVISO", "Primero desactive la sirena ingresando la clave actual.", ft.Colors.AMBER_400)
            return

        pass_change_mode = "VERIFY_OLD"
        buffer_clave = ""
        reset_digits_ui()
        lbl_key_hint.value = "PASO 1/2: Ingrese la CLAVE ACTUAL de 4 dígitos"
        lbl_key_hint.color = ft.Colors.PURPLE_300
        update_dashboard("Modo cambio de clave: Digite la clave actual")

    btn_change_pass.on_click = request_password_change

    def reset_system(e):
        nonlocal secret_code, alarma_armada, puerta_abierta, sirena, buffer_clave, pass_change_mode
        secret_code = "1111"
        alarma_armada = False
        puerta_abierta = False
        sirena = False
        buffer_clave = ""
        pass_change_mode = "IDLE"
        reset_digits_ui()
        sync_hardware_siren()
        update_dashboard("SISTEMA REINICIADO (Clave por defecto: '1111')")

    btn_reset.on_click = reset_system

    # ----------------------------------------------------
    # CLIENTE MQTT
    # ----------------------------------------------------
    def on_conn_change(connected: bool, info: str):
        if connected:
            lbl_broker.value = "● HiveMQ Online"
            lbl_broker.color = ft.Colors.GREEN_400
            btn_connect.content = "Desconectar"
            btn_connect.icon = ft.Icons.POWER_OFF
            mqtt.subscribe(prefix + "#")
            add_log("SISTEMA", f"Conectado a MQTT y suscrito a {prefix}#", ft.Colors.GREEN_300)
        else:
            lbl_broker.value = "● Desconectado"
            lbl_broker.color = ft.Colors.RED_400
            btn_connect.content = "Conectar MQTT"
            btn_connect.icon = ft.Icons.POWER_SETTINGS_NEW
        page.update()

    def on_mqtt_msg(topic: str, data: dict | str):
        nonlocal puerta_abierta, sirena
        local_topic = topic[len(prefix):] if topic.startswith(prefix) else topic

        # 1. Tecla del receptor IR desde la Pico WH
        if local_topic == "alarm/key":
            key_val = data.get("key", "") if isinstance(data, dict) else str(data)
            process_key(str(key_val))

        # 2. Entrada digital de puerta física desde la Pico WH (GP1)
        elif local_topic in ("GPIOIn/GP1", "gpio/GP1"):
            raw_val = data.get("value", 0) if isinstance(data, dict) else int(data)
            puerta_abierta = (raw_val == 1)

            if puerta_abierta and alarma_armada:
                sirena = True
                causa = "¡INTRUSIÓN DETECTADA POR SENSOR GP1! PUERTA ABIERTA"
            else:
                causa = f"Sensor GP1 reporta puerta {'ABIERTA' if puerta_abierta else 'CERRADA'}"

            sync_hardware_siren()
            update_dashboard(causa)

    mqtt = MqttManager(
        client_id=client_id,
        on_connect_cb=on_conn_change,
        on_message_cb=on_mqtt_msg,
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
            header_row,
            banner_container,
            ft.Row([card_ir, card_vars, card_rules], wrap=True, vertical_alignment=ft.CrossAxisAlignment.START),
            card_logs,
        ], spacing=16)
    )

    # Iniciar conexión MQTT de forma automática
    mqtt.connect()


if __name__ == "__main__":
    ft.run(main)
