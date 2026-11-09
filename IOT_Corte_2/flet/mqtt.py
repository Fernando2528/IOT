"""
mqtt.py
=======
Cliente MQTT para la interfaz de PC en Flet (Proyecto Segundo Corte: Coreografía).
Permite publicar y suscribirse dinámicamente bajo el prefijo del robot (`UDFJC/carrrobot/robot12/`)
y calcular estadísticas de red en vivo.
"""

import json
import random
import paho.mqtt.client as mqtt


class MqttClient:
    def __init__(
        self,
        broker: str = "broker.hivemq.com",
        port: int = 1883,
        base_prefix: str = "UDFJC/carrrobot",
        robot_id: int | str = 12,
    ):
        self.broker = broker
        self.port = port
        self.base_prefix = base_prefix.strip().strip("/")
        self.robot_id = str(robot_id).strip()
        self.prefix = f"{self.base_prefix}/robot{self.robot_id}/"

        self.connected = False
        self.on_message_cb = None
        self.on_status_cb = None

        client_id = f"flet_coreo_r{self.robot_id}_{random.randint(1000, 9999)}"
        try:
            self.client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=client_id,
            )
        except AttributeError:
            self.client = mqtt.Client(client_id=client_id)

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    def set_prefix(self, base_prefix: str, robot_id: int | str):
        """Actualiza el prefijo base y el ID del robot en caliente y re-suscribe."""
        if self.connected:
            try:
                self.client.unsubscribe(f"{self.prefix}#")
            except Exception:
                pass
        self.base_prefix = base_prefix.strip().strip("/")
        self.robot_id = str(robot_id).strip()
        self.prefix = f"{self.base_prefix}/robot{self.robot_id}/"
        if self.connected:
            self.client.subscribe(f"{self.prefix}#")

    def start(self):
        try:
            self.client.connect_async(self.broker, self.port, keepalive=60)
            self.client.loop_start()
        except Exception as err:
            if self.on_status_cb:
                self.on_status_cb(False, f"Error de conexión: {err}")

    def stop(self):
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:
            pass

    def publish(self, suffix_topic: str, payload: dict | list | str):
        suffix = suffix_topic.lstrip("/")
        full_topic = f"{self.prefix}{suffix}"
        data = json.dumps(payload) if isinstance(payload, (dict, list)) else str(payload)
        self.client.publish(full_topic, data)
        return full_topic

    def _on_connect(self, client, userdata, flags, rc, *args):
        self.connected = rc == 0
        if self.connected:
            client.subscribe(f"{self.prefix}#")
            if self.on_status_cb:
                self.on_status_cb(True, f"Conectado ({self.broker}) -> {self.prefix}")
        else:
            if self.on_status_cb:
                self.on_status_cb(False, f"Error MQTT rc={rc}")

    def _on_disconnect(self, client, userdata, *args):
        self.connected = False
        if self.on_status_cb:
            self.on_status_cb(False, "Desconectado del broker MQTT")

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        if not topic.startswith(self.prefix):
            return
        local_topic = topic[len(self.prefix) :]
        raw = msg.payload.decode("utf-8", errors="replace")
        try:
            data = json.loads(raw)
        except Exception:
            data = {"raw": raw}

        if self.on_message_cb:
            self.on_message_cb(local_topic, data)
