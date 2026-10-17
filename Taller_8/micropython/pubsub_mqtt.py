"""
pubsub_mqtt.py
==============
Transporte MQTT no bloqueante integrado como tarea periódica (Task) del Scheduler.
"""

import json
from umqtt.simple import MQTTClient
from task import Task


class PubSubMQTT(Task):
    def __init__(
        self,
        client_id,
        broker,
        scheduler,
        node,
        port=1883,
        period_ms=50,
        prefix="UDFJC/iot_ws/robot0/",
    ):
        super().__init__(scheduler, period_ms=period_ms, priority=0, name="PubSubMQTT")
        self.node = node
        self.prefix = prefix
        self.broker = broker
        self.port = port
        self.client_id = client_id

        self.client = MQTTClient(client_id=client_id, server=broker, port=port, keepalive=60)
        self.client.set_callback(self.handle_pub)
        self.client.connect()
        print(f"[PubSubMQTT] Conectado a {broker}:{port} como '{client_id}' (Prefijo: {prefix})")

        node.add_transport(self)

    def publish(self, topic, data):
        try:
            payload = json.dumps(data) if isinstance(data, dict) else str(data)
            full_topic = (self.prefix + topic).encode("utf-8")
            self.client.publish(full_topic, payload.encode("utf-8"))
        except Exception as e:
            print("[PubSubMQTT] Error al publicar:", e)

    def subscribe(self, topic):
        try:
            full_topic = (self.prefix + topic).encode("utf-8")
            self.client.subscribe(full_topic)
        except Exception as e:
            print("[PubSubMQTT] Error al suscribir:", e)

    def update(self):
        try:
            for _ in range(10):
                op = self.client.check_msg()
                if op is None:
                    break
        except Exception as e:
            print("[PubSubMQTT] Error en check_msg:", e)

    def handle_pub(self, topic_bytes, payload_bytes):
        topic = topic_bytes.decode("utf-8")
        if not topic.startswith(self.prefix):
            return
        local_topic = topic[len(self.prefix) :]
        raw = payload_bytes.decode("utf-8")
        try:
            data = json.loads(raw)
        except Exception:
            data = raw
        self.node.local_publish(local_topic, data)
