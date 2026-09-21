import json
import machine
import time
from machine import Pin
from task import Task

IR_KEYMAP = {
    "0xc": "1",
    "0x18": "2",
    "0x5e": "3",
    "0x8": "4",
    "0x1c": "5",
    "0x5a": "6",
    "0x42": "7",
    "0x52": "8",
    "0x4a": "9",
    "0x16": "0",
}


# ==========================================================
# CONTROLADOR CENTRAL DE ALARMA, PUERTA Y SIRENA
# ==========================================================
class SecurityAlarmSystem(Task):
    def __init__(
        self,
        scheduler,
        pubsub,
        gpio_ir=2,
        gpio_door=1,
        secret_code="1111",
        cooldown_ms=300,
    ):
        self.pubsub = pubsub
        self.ir = Pin(gpio_ir, Pin.IN, Pin.PULL_UP)
        self.door = Pin(gpio_door, Pin.IN, Pin.PULL_DOWN)
        self.siren_led = Pin("LED", Pin.OUT)
        self.siren_led.value(0)

        self.secret_code = secret_code
        self.cooldown_ms = cooldown_ms
        self.last_press = 0
        self.buffer = ""

        # Estados: 'DISARMED', 'ARMED', 'TRIGGERED'
        self.state = "DISARMED"
        self.last_door_val = -1

        super().__init__(scheduler, period_ms=3)
        print(f"Sistema de Seguridad iniciado. Clave: '{secret_code}'")

    def _decode_nec(self):
        t0 = time.ticks_us()
        while self.ir.value() == 0:
            if time.ticks_diff(time.ticks_us(), t0) > 15000:
                return None

        t1 = time.ticks_us()
        while self.ir.value() == 1:
            if time.ticks_diff(time.ticks_us(), t1) > 10000:
                return None
        t_high = time.ticks_diff(time.ticks_us(), t1)

        if not (3000 < t_high < 6000):
            return None

        bits = []
        for _ in range(32):
            t_bit = time.ticks_us()
            while self.ir.value() == 0:
                if time.ticks_diff(time.ticks_us(), t_bit) > 2500:
                    return None

            t_space = time.ticks_us()
            while self.ir.value() == 1:
                if time.ticks_diff(time.ticks_us(), t_space) > 3000:
                    return None
            dur = time.ticks_diff(time.ticks_us(), t_space)
            bits.append(1 if dur > 1000 else 0)

        cmd = 0
        for j in range(8):
            cmd |= bits[16 + j] << j

        return hex(cmd)

    def set_siren(self, state: int):
        self.siren_led.value(state)
        self.pubsub.publish("led/LED", {"value": state})

    def publish_status(self, reason: str):
        print(f"[ESTADO] {self.state} | Sirena: {self.siren_led.value()} | Causa: {reason}")
        self.pubsub.publish(
            "alarm/status",
            {
                "state": self.state,
                "siren": self.siren_led.value(),
                "reason": reason,
            },
        )

    def update(self):
        now = time.ticks_ms()

        # 1. Monitoreo de Sensor de Puerta (GP1)
        door_val = self.door.value()
        if door_val != self.last_door_val:
            self.last_door_val = door_val
            estado_puerta = "ABIERTA" if door_val == 1 else "CERRADA"
            print(f"[PUERTA] Sensor GP1: {estado_puerta}")
            self.pubsub.publish(
                "alarm/door", {"open": door_val, "status": estado_puerta}
            )

            # Si la puerta se abre con la alarma armada -> Disparar sirena
            if door_val == 1 and self.state == "ARMED":
                self.state = "TRIGGERED"
                self.set_siren(1)
                self.publish_status("¡INTRUSIÓN! Puerta abierta con alarma armada")

        # 2. Monitoreo de Entrada IR (GP2)
        if self.ir.value() == 1:
            return

        if time.ticks_diff(now, self.last_press) < self.cooldown_ms:
            return

        cmd_hex = self._decode_nec()
        if not cmd_hex or cmd_hex not in IR_KEYMAP:
            return

        self.last_press = now
        digit = IR_KEYMAP[cmd_hex]
        self.buffer += digit

        print(f"[IR] Tecla: '{digit}' | Cadena: [{self.buffer}] ({len(self.buffer)}/4)")
        self.pubsub.publish(
            "alarm/key",
            {
                "key": digit,
                "digits": len(self.buffer),
                "buffer": self.buffer,
            },
        )

        # 3. Evaluación de clave de 4 dígitos
        if len(self.buffer) == 4:
            entered_code = self.buffer
            self.buffer = ""

            if entered_code == self.secret_code:
                if self.state == "DISARMED":
                    self.state = "ARMED"
                    self.set_siren(0)
                    self.publish_status("Clave correcta: Sistema ARMADO")
                else:
                    self.state = "DISARMED"
                    self.set_siren(0)
                    self.publish_status(
                        "Clave correcta: Alarma DESACTIVADA / Silenciada"
                    )
            else:
                self.state = "TRIGGERED"
                self.set_siren(1)
                self.publish_status(
                    f"¡ALERTA! Clave incorrecta ingresada ({entered_code})"
                )


# ==========================================================
# LANZADOR PRINCIPAL Y BLINDAJE DE RED
# ==========================================================
if __name__ == "__main__":
    from node import Node
    from pubsub_mqtt import PubSubMQTT
    from scheduler import Scheduler
    from watchdog_task import WatchdogTask
    from wifi_manager import WiFiManager

    # Funciones de recuperación ante desconexiones de socket
    _orig_mqtt_publish = PubSubMQTT.publish
    _orig_mqtt_update = PubSubMQTT.update

    def _reconnect_client(instance):
        try:
            print("\n[MQTT] Socket cerrado por el broker. Reconectando...")
            try:
                instance.mqtt.sock.close()
            except Exception:
                pass
            instance.mqtt.connect()
            instance.mqtt.subscribe(instance.prefix + "#")
            print("[MQTT] Reconexión exitosa.")
            return True
        except Exception as e:
            print(f"[MQTT] Reintento fallido ({e}). Se reintentará en el siguiente ciclo.")
            return False

    def _safe_mqtt_publish(self, topic, msg):
        try:
            _orig_mqtt_publish(self, topic, msg)
        except OSError as err:
            print(f"\n[AVISO MQTT] Error en socket al publicar ({err}).")
            if _reconnect_client(self):
                try:
                    _orig_mqtt_publish(self, topic, msg)
                except Exception:
                    pass

    def _safe_mqtt_update(self):
        try:
            _orig_mqtt_update(self)
        except OSError as err:
            print(f"\n[AVISO MQTT] Error en socket al recibir ({err}).")
            _reconnect_client(self)

    # Reemplazo de métodos para capturar fallos de red
    PubSubMQTT.publish = _safe_mqtt_publish
    PubSubMQTT.update = _safe_mqtt_update

    SSID = "PruebaPi"
    PASSWORD = "444555666777"
    MQTT_BROKER = "broker.hivemq.com"

    unique_id = machine.unique_id().hex()[-4:]
    NODE_NAME = f"emb_node_{unique_id}"
    PREFIX = "UDFJC/iot_ws/robot0/"

    scheduler = Scheduler()
    print("Scheduler inicializado")

    wifi = WiFiManager(ssid=SSID, password=PASSWORD)
    node = Node(prefix=PREFIX, node_name=NODE_NAME)

    PubSubMQTT(
        client_id=NODE_NAME,
        broker=MQTT_BROKER,
        scheduler=scheduler,
        node=node,
        period_ms=100,
        prefix=PREFIX,
    )

    WatchdogTask(scheduler=scheduler, pubsub=node, wifi=wifi, period_ms=9000)

    SecurityAlarmSystem(
        scheduler,
        node,
        gpio_ir=2,
        gpio_door=1,
        secret_code="1111",
        cooldown_ms=300,
    )

    print("Sistema de alarma con recuperación de red listo.")
    scheduler.run()