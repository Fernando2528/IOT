"""
pubsub_mqtt.py
==============
Transporte MQTT no bloqueante para Raspberry Pi Pico W.
Soporta el prefijo oficial de Coreografía (`UDFJC/carrrobot/robot12/`) y
alias compatibles (`UDFJC/carrobot/robot12/`, `UDFJC/iot_ws/robot12/`) para
garantizar interoperabilidad total con el Gemelo Virtual Individual,
la Coreografía Grupal y la interfaz Flet.
"""

import json
from task import Task

try:
    from umqtt.simple import MQTTClient
except ImportError:
    MQTTClient = None


class PubSubMQTT(Task):
    def __init__(
        self,
        client_id: str,
        broker: str,
        scheduler,
        node,
        port: int = 1883,
        period_ms: int = 35,
        prefix: str = "UDFJC/carrrobot/robot12/",
        alias_prefixes=None,
    ):
        super().__init__(scheduler, period_ms, priority=1, name="PubSubMQTT")
        self.client_id = client_id
        self.broker = broker
        self.port = port
        self.node = node
        self.prefix = prefix if prefix.endswith("/") else prefix + "/"

        # Prefijos adicionales escuchados por si el usuario usa 'carrobot' (2 r) o 'carrrobot' (3 r)
        default_aliases = [
            "UDFJC/carrrobot/robot12/",
            "UDFJC/carrobot/robot12/",
            "UDFJC/iot_ws/robot12/",
        ]
        raw_aliases = alias_prefixes if alias_prefixes is not None else default_aliases
        self.prefixes = []
        for p in [self.prefix] + list(raw_aliases):
            p_norm = p if p.endswith("/") else p + "/"
            if p_norm not in self.prefixes:
                self.prefixes.append(p_norm)

        self.active_prefix = self.prefix
        self.connected = False
        self.client = None

        self._connect_broker()
        node.add_transport(self)

    def _connect_broker(self):
        if MQTTClient is None:
            return False
        try:
            self.client = MQTTClient(
                client_id=self.client_id,
                server=self.broker,
                port=self.port,
                keepalive=60,
            )
            self.client.set_callback(self.handle_pub)
            self.client.connect()
            self.connected = True
            print(f"[MQTT] Conectado a {self.broker}:{self.port} | Prefijo: {self.prefix}")
            for topic in self.node.subscriptions:
                self.subscribe(topic)
            return True
        except Exception as err:
            self.connected = False
            print("[MQTT] Error conectando al broker:", err)
            return False

    def publish(self, topic: str, data):
        if not self.connected or self.client is None:
            return
        try:
            payload = json.dumps(data) if isinstance(data, (dict, list)) else str(data)
            full_topic = (self.active_prefix + topic).encode("utf-8")
            self.client.publish(full_topic, payload.encode("utf-8"))
            # Si el prefijo activo cambió a un alias, publicar también en el primario
            if self.active_prefix != self.prefix:
                self.client.publish((self.prefix + topic).encode("utf-8"), payload.encode("utf-8"))
        except Exception as err:
            print(f"[MQTT] Error publicando en {topic}:", err)
            self.connected = False

    def subscribe(self, topic: str):
        if not self.connected or self.client is None:
            return
        for pref in self.prefixes:
            try:
                self.client.subscribe((pref + topic).encode("utf-8"))
            except Exception as err:
                print(f"[MQTT] Error suscribiendo {pref + topic}:", err)

    def update(self):
        if not self.connected:
            self._connect_broker()
            return
        try:
            for _ in range(10):
                op = self.client.check_msg()
                if op is None:
                    break
        except Exception as err:
            print("[MQTT] Conexión interrumpida, reconectando...", err)
            self.connected = False

    def handle_pub(self, topic_bytes, payload_bytes):
        topic = topic_bytes.decode("utf-8")
        local_topic = None

        for pref in self.prefixes:
            if topic.startswith(pref):
                local_topic = topic[len(pref) :]
                self.active_prefix = pref
                break

        if local_topic is None:
            return

        try:
            msg_str = payload_bytes.decode("utf-8")
            data = json.loads(msg_str)
        except Exception:
            data = payload_bytes.decode("utf-8") if isinstance(payload_bytes, bytes) else payload_bytes

        # Evitar bucle infinito con publicaciones propias de telemetría
        if local_topic in ("watchdog/stats", "node/send_second_ts", "CAR/status", "status", "oled/status", "motion/status"):
            return

        self.node.local_publish(local_topic, data)
