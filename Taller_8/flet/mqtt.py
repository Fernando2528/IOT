"""
flet/mqtt.py
============
Gestor de comunicaciones MQTT asíncrono (Paho MQTT v2) para la interfaz Flet del Taller 8.
"""

import json
from typing import Callable
import paho.mqtt.client as mqtt


class MqttManager:
    def __init__(
        self,
        client_id: str,
        on_connect_cb: Callable[[bool, str], None] | None = None,
        on_message_cb: Callable[[str, dict | str], None] | None = None,
    ):
        self.client_id = client_id
        self.on_connect_cb = on_connect_cb
        self.on_message_cb = on_message_cb

        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=self.client_id,
        )
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.is_connected = False

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            self.is_connected = True
            if self.on_connect_cb:
                self.on_connect_cb(True, "Conectado al broker")
        else:
            self.is_connected = False
            if self.on_connect_cb:
                self.on_connect_cb(False, f"Error de conexión: {rc}")

    def _on_disconnect(self, client, userdata, flags, rc, properties=None):
        self.is_connected = False
        if self.on_connect_cb:
            self.on_connect_cb(False, "Desconectado del broker")

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        raw = msg.payload.decode("utf-8", errors="replace")
        try:
            data = json.loads(raw)
        except Exception:
            data = raw

        if self.on_message_cb:
            self.on_message_cb(topic, data)

    def connect(self, broker: str = "broker.hivemq.com", port: int = 1883):
        self.client.connect(broker, port, keepalive=60)
        self.client.loop_start()

    def disconnect(self):
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:
            pass
        self.is_connected = False

    def subscribe(self, topic: str):
        if self.is_connected:
            self.client.subscribe(topic)

    def publish(self, topic: str, payload_obj: dict | str):
        if not self.is_connected:
            return
        payload = (
            json.dumps(payload_obj)
            if isinstance(payload_obj, dict)
            else str(payload_obj)
        )
        self.client.publish(topic, payload)
