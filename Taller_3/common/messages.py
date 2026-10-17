"""
common.messages
===============
Módulo agnóstico de plataforma (funciona en Python estándar y MicroPython).
Define el protocolo y las estructuras de datos JSON compartidas entre:
- La aplicación gráfica (Flet)
- El microcontrolador (Raspberry Pi Pico WH)
- El framework de pruebas (Pytest)
"""

import time


def create_schedule(name: str, delay_s: float) -> dict:
    """
    Crea un mensaje estructurado para programar una tarea futura.

    Args:
        name: Identificador o nombre descriptivo de la tarea.
        delay_s: Retardo en segundos tras los cuales debe ejecutarse la tarea.

    Returns:
        dict: Diccionario JSON-ready con exactamente 4 claves:
            - action: "schedule"
            - name: Nombre de la tarea
            - next_exec_epoch_s: Segundo epoch (entero) de la ejecución prevista
            - next_exec_ns: Parte en nanosegundos (0 <= ns < 1_000_000_000)
    """
    now_ns = time.time_ns()
    next_exec_ns = now_ns + int(delay_s * 1_000_000_000)

    return {
        "action": "schedule",
        "name": name,
        "next_exec_epoch_s": next_exec_ns // 1_000_000_000,
        "next_exec_ns": next_exec_ns % 1_000_000_000,
    }


def create_command(action: str, value: int | str | dict, target: str = "led") -> dict:
    """
    Crea un mensaje estructurado de comando para un actuador.

    Args:
        action: Acción a realizar (ej. "set", "toggle", "ping").
        value: Valor del comando (ej. 1 para ON, 0 para OFF).
        target: Actuador destino (ej. "led", "motor", "relay").
    """
    return {
        "action": action,
        "target": target,
        "value": value,
        "timestamp_epoch_s": time.time_ns() // 1_000_000_000,
    }


def create_status(device_id: str, state: str, details: dict | None = None) -> dict:
    """
    Crea un mensaje estructurado de reporte de estado o telemetría.

    Args:
        device_id: Identificador único del dispositivo (ej. "pico_wh_1").
        state: Estado del sistema (ej. "online", "idle", "executing", "error").
        details: Diccionario opcional con variables o lecturas de sensores.
    """
    payload = {
        "action": "status",
        "device": device_id,
        "state": state,
        "timestamp_epoch_s": time.time_ns() // 1_000_000_000,
    }
    if details:
        payload["details"] = details
    return payload


def validate_schedule_message(msg: dict) -> bool:
    """
    Verifica si un diccionario cumple rigurosamente con el contrato del mensaje 'schedule'.
    Retorna True si cumple todas las reglas, False en caso contrario.
    """
    if not isinstance(msg, dict):
        return False

    required_keys = {"action", "name", "next_exec_epoch_s", "next_exec_ns"}
    if set(msg.keys()) != required_keys:
        return False

    if msg["action"] != "schedule":
        return False

    if not isinstance(msg["name"], str) or not msg["name"].strip():
        return False

    if not isinstance(msg["next_exec_epoch_s"], int) or msg["next_exec_epoch_s"] < 0:
        return False

    if not isinstance(msg["next_exec_ns"], int) or not (0 <= msg["next_exec_ns"] < 1_000_000_000):
        return False

    return True
