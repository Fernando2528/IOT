"""
mqtt_client.py
==============
Cliente MQTT liviano adaptado para el Scheduler en MicroPython.
"""

import json
from umqtt.simple import MQTTClient


class MicroMQTTClient:
    def __init__(self, client_id, broker="broker.hivemq.com", port=1883, on_message=None):
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
        self.client.set_callback(self._callback)
        self.is_connected = False

    def _callback(self, topic_bytes, msg_bytes):
        topic = topic_bytes.decode("utf-8")
        payload = msg_bytes.decode("utf-8")
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

        payload = json.dumps(data) if isinstance(data, (dict, list)) else str(data)
        self.client.publish(topic.encode("utf-8"), payload.encode("utf-8"))

    def check_msg(self):
        if self.is_connected:
            self.client.check_msg()
