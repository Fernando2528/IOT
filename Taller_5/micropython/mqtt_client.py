"""
mqtt_client.py
==============
Cliente MQTT liviano con soporte de suscripciones múltiples para MicroPython.
"""

import json
from umqtt.simple import MQTTClient


class PubSubMQTT:
    def __init__(self, client_id, broker="broker.hivemq.com", port=1883, prefix="UDFJC/iot_ws/robot0/"):
        self.client_id = client_id
        self.broker = broker
        self.port = port
        self.prefix = prefix
        self.subscriptions = {}  # topic -> callback

        self.client = MQTTClient(
            client_id=self.client_id,
            server=self.broker,
            port=self.port,
            keepalive=60,
        )
        self.client.set_callback(self._on_message)
        self.is_connected = False

    def connect(self):
        self.client.connect()
        self.is_connected = True
        print(f"[MQTT] Conectado al broker {self.broker} como '{self.client_id}'")

    def subscribe(self, local_topic, callback):
        full_topic = self.prefix + local_topic
        self.subscriptions[local_topic] = callback
        self.subscriptions[full_topic] = callback

        if self.is_connected:
            self.client.subscribe(full_topic.encode("utf-8"))
            print(f"[MQTT] Suscrito a '{full_topic}'")

    def publish(self, local_topic, data):
        if not self.is_connected:
            return

        full_topic = self.prefix + local_topic
        payload = json.dumps(data) if isinstance(data, (dict, list)) else str(data)
        self.client.publish(full_topic.encode("utf-8"), payload.encode("utf-8"))

    def check_msg(self):
        if self.is_connected:
            self.client.check_msg()

    def _on_message(self, topic_bytes, msg_bytes):
        topic = topic_bytes.decode("utf-8")
        payload = msg_bytes.decode("utf-8")

        # Remover prefijo si existe
        local_topic = topic[len(self.prefix):] if topic.startswith(self.prefix) else topic

        try:
            data = json.loads(payload)
        except Exception:
            data = payload

        # Buscar callback correspondiente
        cb = self.subscriptions.get(local_topic) or self.subscriptions.get(topic)
        if cb:
            cb(topic, data)
