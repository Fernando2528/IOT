"""
node.py
=======
Bus de publicación/suscripción PicoROS.
Incluye soporte nativo para `node/get_second_ts` -> `node/send_second_ts`
requerido por el panel de estadísticas de red (Latencia y Jitter RFC)
del Gemelo Virtual (`PubSub_client_web.html`).
"""

import random
import sys
import util


class Node:
    def __init__(self, prefix="UDFJC/carrrobot/robot12/", node_name=None):
        self.prefix = prefix if prefix.endswith("/") else prefix + "/"
        self.subscriptions = {}
        self.node_name = node_name or (self.prefix + str(random.randint(0, 2**32 - 1)))
        self.transports = []
        self.subscribe("node/get_second_ts", self.handle_get_second_ts)

    def add_transport(self, transport):
        self.transports.append(transport)
        for topic in self.subscriptions:
            transport.subscribe(topic)

    def publish(self, topic: str, msg):
        ts = util.time_float()
        for t in self.transports:
            t.publish(topic, msg)
        self.local_publish(topic, msg, ts=ts)

    def local_publish(self, topic: str, msg, ts=None):
        callbacks = self.subscriptions.get(topic, set())
        for c in list(callbacks):
            try:
                c(topic=topic, msg=msg)
            except Exception as e:
                print(f"[Node] Error en callback de '{topic}':", e)
                if hasattr(sys, "print_exception"):
                    sys.print_exception(e)

    def subscribe(self, topic: str, callback):
        self.subscriptions.setdefault(topic, set()).add(callback)
        for t in self.transports:
            t.subscribe(topic)

    def handle_get_second_ts(self, topic=None, msg=None):
        """Responde al ping de marca de tiempo del Gemelo Virtual Web para cálculo de RTT y Jitter."""
        if not isinstance(msg, dict):
            return
        self.publish(
            "node/send_second_ts",
            {
                "topic": msg.get("topic"),
                "first_ts": msg.get("first_ts"),
                "second_ts": float(util.time_float()),
                "sended": msg.get("sended"),
            },
        )
