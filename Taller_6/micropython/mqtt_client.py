"""
mqtt_client.py
==============
Cliente MQTT liviano con prefijo de tópicos para MicroPython.
"""

import json
from umqtt.simple import MQTTClient


class PubSubMQTT:
    def __init__(self, client_id, broker="broker.hivemq.com", port=1883, prefix="UDFJC/iot_ws/robot0/"):
        self.client_id = client_id
        self.broker = broker
        self.port = port
        self.prefix = prefix

        self.client = MQTTClient(
            client_id=self.client_id,
            server=self.broker,
            port=self.port,
            keepalive=60,
        )
        self.is_connected = False

    def connect(self):
        self.client.connect()
        self.is_connected = True
        print(f"[MQTT] Conectado al broker {self.broker} como '{self.client_id}'")

    def publish(self, local_topic, data):
        if not self.is_connected:
            return

        full_topic = self.prefix + local_topic
        payload = json.dumps(data) if isinstance(data, (dict, list)) else str(data)
        self.client.publish(full_topic.encode("utf-8"), payload.encode("utf-8"))

    def check_msg(self):
        if self.is_connected:
            self.client.check_msg()
