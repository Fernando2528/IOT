"""
node.py
=======
Bus local de publicación/suscripción (PicoROS Node) compatible con múltiples transportes
(como PubSubMQTT) y callbacks flexibles.
"""

import random
import sys
import util


class Node:
    def __init__(self, prefix="UDFJC/iot_ws/robot0/", node_name=None):
        self.prefix = prefix
        self.subscriptions = {}
        self.node_name = node_name or f"emb_node_{random.randint(1000, 9999)}"
        self.transports = []
        self.subscribe("node/get_second_ts", self.handle_get_second_ts)

    def add_transport(self, transport):
        self.transports.append(transport)
        for topic in self.subscriptions:
            transport.subscribe(topic)

    def publish(self, topic, msg):
        ts = util.time_float()
        for t in self.transports:
            t.publish(topic, msg)
        self.local_publish(topic, msg, ts=ts)

    def local_publish(self, topic, msg, ts=None):
        callbacks = self.subscriptions.get(topic, set())
        for c in list(callbacks):
            try:
                c(topic, msg)
            except TypeError:
                try:
                    c(topic=topic, msg=msg)
                except Exception as e:
                    sys.print_exception(e)
            except Exception as e:
                print(f"[Node] Error en callback de {topic}:", e)
                sys.print_exception(e)

    def subscribe(self, topic, callback):
        self.subscriptions.setdefault(topic, set()).add(callback)
        for t in self.transports:
            t.subscribe(topic)
        print(f"[Node] Suscrito a tópico local: '{topic}'")

    def handle_get_second_ts(self, topic, msg):
        if isinstance(msg, dict):
            self.publish(
                "node/send_second_ts",
                {
                    "topic": msg.get("topic"),
                    "first_ts": msg.get("first_ts"),
                    "second_ts": util.time_float(),
                    "sended": msg.get("sended"),
                },
            )
