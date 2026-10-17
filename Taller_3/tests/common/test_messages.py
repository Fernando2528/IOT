"""
tests.common.test_messages
==========================
Pruebas unitarias para validar los contratos de datos y la función create_schedule.
"""

import json
import time
from common.messages import (
    create_command,
    create_schedule,
    create_status,
    validate_schedule_message,
)


def test_schedule_at_specific_time():
    """Prueba base exigida por la especificación del taller."""
    msg = create_schedule("test_name", 5.5)

    assert len(msg) == 4
    assert "action" in msg
    assert "name" in msg
    assert "next_exec_epoch_s" in msg
    assert "next_exec_ns" in msg
    assert msg["action"] == "schedule"
    assert msg["name"] == "test_name"
    assert isinstance(msg["next_exec_epoch_s"], int)
    assert msg["next_exec_epoch_s"] > time.time()
    assert isinstance(msg["next_exec_ns"], int)
    assert 0 <= msg["next_exec_ns"] < 1_000_000_000


def test_schedule_json_serialization():
    """Garantiza que el mensaje sea 100% compatible con JSON (requisito de transporte MQTT)."""
    msg = create_schedule("tarea_led", 10.0)
    json_str = json.dumps(msg)

    # Debe ser un string válido y reconstruible
    recovered = json.loads(json_str)
    assert recovered == msg
    assert recovered["action"] == "schedule"
    assert recovered["name"] == "tarea_led"


def test_schedule_validation_helper():
    """Valida la función de verificación de contrato de datos."""
    valid_msg = create_schedule("sensor_read", 2.0)
    assert validate_schedule_message(valid_msg) is True

    # Mensaje incompleto (falta una clave)
    invalid_msg = {"action": "schedule", "name": "bad"}
    assert validate_schedule_message(invalid_msg) is False

    # Mensaje con acción incorrecta
    invalid_action = valid_msg.copy()
    invalid_action["action"] = "otro"
    assert validate_schedule_message(invalid_action) is False

    # Mensaje no dict
    assert validate_schedule_message("string_no_valido") is False


def test_command_and_status_creation():
    """Valida la creación de mensajes de comando y estado."""
    cmd = create_command(action="set", value=1, target="led")
    assert cmd["action"] == "set"
    assert cmd["target"] == "led"
    assert cmd["value"] == 1
    assert "timestamp_epoch_s" in cmd

    status = create_status(device_id="pico_wh_01", state="online", details={"temp": 24.5})
    assert status["action"] == "status"
    assert status["device"] == "pico_wh_01"
    assert status["state"] == "online"
    assert status["details"]["temp"] == 24.5
