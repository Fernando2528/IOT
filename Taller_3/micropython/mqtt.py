"""
micropython.mqtt
================
Cliente MQTT modular para MicroPython (Raspberry Pi Pico WH).
Encapsula umqtt.simple para gestionar conexión, suscripciones y callbacks.
"""

import json
from umqtt.simple import MQTTClient


class MicroMQTTClient:
    def __init__(self, client_id, broker, port=1883, on_message=None):
        self.client_id = client_id
        self.broker = broker
        self.port = port
        self.on_message_cb = on_message

        self.client = MQTTClient(
            client_id=self.client_id,
            server=self.broker,
            port=self.port,
            keepalive=60,
        )
        self.client.set_callback(self._internal_callback)
        self.is_connected = False

    def _internal_callback(self, topic_bytes, msg_bytes):
        topic = topic_bytes.decode("utf-8")
        payload = msg_bytes.decode("utf-8")

        # Intentar parsear como JSON si viene formateado
        try:
            data = json.loads(payload)
        except Exception:
            data = payload

        if self.on_message_cb:
            self.on_message_cb(topic, data)

    def connect(self):
        self.client.connect()
        self.is_connected = True

    def subscribe(self, topic):
        if self.is_connected:
            self.client.subscribe(topic.encode("utf-8"))

    def publish(self, topic, data):
        if not self.is_connected:
            return

        if isinstance(data, (dict, list)):
            payload = json.dumps(data)
        else:
            payload = str(data)

        self.client.publish(topic.encode("utf-8"), payload.encode("utf-8"))

    def check_msg(self):
        """Llamar periódicamente desde el bucle principal (no bloqueante)."""
        if self.is_connected:
            self.client.check_msg()
