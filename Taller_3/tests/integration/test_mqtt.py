"""
tests.integration.test_mqtt
===========================
Prueba de integración del flujo de transporte MQTT:
Valida que los mensajes creados con create_schedule se serialicen,
se transmitan vía MQTT (o a través de su abstracción de cliente)
y se reciban/decodifiquen preservando el contrato de datos.
"""

import json
from unittest.mock import MagicMock
from common.messages import create_schedule, validate_schedule_message


class MockMQTTBroker:
    """Simulador de broker MQTT local para pruebas de integración determinísticas y rápidas."""

    def __init__(self):
        self.subscribers = {}

    def subscribe(self, topic: str, callback):
        self.subscribers.setdefault(topic, []).append(callback)

    def publish(self, topic: str, payload_bytes: bytes):
        for sub_topic, callbacks in self.subscribers.items():
            # Soporte simple para exact match o wildcard '#'
            if sub_topic == topic or sub_topic == "#" or (sub_topic.endswith("/#") and topic.startswith(sub_topic[:-1])):
                for cb in callbacks:
                    cb(topic, payload_bytes)


def test_mqtt_schedule_integration_flow():
    """Valida el ciclo completo de publicación y suscripción de un schedule."""
    broker = MockMQTTBroker()
    received_messages = []

    def on_message_callback(topic, payload_bytes):
        payload_str = payload_bytes.decode("utf-8")
        data = json.loads(payload_str)
        received_messages.append({"topic": topic, "data": data})

    # 1. Suscribirse al tópico de tareas
    topic = "UDFJC/iot_ws/robot0/schedule"
    broker.subscribe(topic, on_message_callback)

    # 2. Generar mensaje usando el contrato definido
    schedule_msg = create_schedule("blink_led_sequence", delay_s=3.0)
    payload_to_send = json.dumps(schedule_msg).encode("utf-8")

    # 3. Publicar mensaje
    broker.publish(topic, payload_to_send)

    # 4. Aserciones de integración
    assert len(received_messages) == 1
    rx = received_messages[0]

    assert rx["topic"] == topic
    assert validate_schedule_message(rx["data"]) is True
    assert rx["data"]["name"] == "blink_led_sequence"
    assert rx["data"]["next_exec_epoch_s"] >= schedule_msg["next_exec_epoch_s"]


def test_mqtt_paho_payload_encoding():
    """Valida la compatibilidad directa con la firma de Paho MQTT Message."""
    msg_dict = create_schedule("telemetry_request", 1.0)
    raw_payload = json.dumps(msg_dict).encode("utf-8")

    # Simular objeto MQTTMessage de Paho
    mock_msg = MagicMock()
    mock_msg.topic = "UDFJC/iot_ws/robot0/schedule"
    mock_msg.payload = raw_payload

    decoded_payload = json.loads(mock_msg.payload.decode("utf-8"))
    assert validate_schedule_message(decoded_payload) is True
    assert decoded_payload["action"] == "schedule"
