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
# 1. SENSOR IR: CAPTURA DIRECTA Y PUBLICACIÓN DE TECLAS
# ==========================================================
class IRReaderTask(Task):
    def __init__(self, scheduler, pubsub, gpio_ir=2, cooldown_ms=250):
        self.pubsub = pubsub
        self.ir = Pin(gpio_ir, Pin.IN, Pin.PULL_UP)
        self.cooldown_ms = cooldown_ms
        self.last_press = 0
        super().__init__(scheduler, period_ms=3)
        print(f"Lector IR activo en GP{gpio_ir}. Listo para capturar control...")

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

    def update(self):
        if self.ir.value() == 1:
            return

        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_press) < self.cooldown_ms:
            return

        cmd_hex = self._decode_nec()
        if not cmd_hex or cmd_hex not in IR_KEYMAP:
            return

        self.last_press = now
        digit = IR_KEYMAP[cmd_hex]

        print(f"[IR] Tecla detectada: '{digit}' -> Enviando a la interfaz")
        self.pubsub.publish("alarm/key", {"key": digit})


# ==========================================================
# 2. ACTUADOR DE SIRENA (LED ONBOARD BLINDADO)
# ==========================================================
class LEDSirenActuator:
    def __init__(self, pubsub):
        self.pubsub = pubsub
        self.pin = Pin("LED", Pin.OUT)
        self.pin.value(0)
        # Suscripción segura compatible con cualquier firma de argumentos
        self.pubsub.subscribe("led/LED", self._on_led_cmd)

    def _on_led_cmd(self, *args, **kwargs):
        try:
            msg = args[0] if len(args) > 0 else kwargs.get("msg", {})
            if isinstance(msg, (str, bytes)):
                data = json.loads(msg)
            elif isinstance(msg, dict):
                data = msg
            else:
                data = {"value": int(msg)}

            val = int(data.get("value", 0))
            self.pin.value(val)
            estado_txt = "ENCENDIDO (Sirena Activa)" if val == 1 else "APAGADO"
            print(f"[ACTUADOR] LED físico ajustado a: {val} -> {estado_txt}")
        except Exception as e:
            print("[ACTUADOR] Error al procesar comando LED:", e)


# ==========================================================
# LANZADOR PRINCIPAL
# ==========================================================
if __name__ == "__main__":
    from node import Node
    from pubsub_mqtt import PubSubMQTT
    from scheduler import Scheduler
    from watchdog_task import WatchdogTask
    from wifi_manager import WiFiManager

    SSID = "PruebaPi"
    PASSWORD = "444555666777"
    MQTT_BROKER = "broker.hivemq.com"

    unique_hw = machine.unique_id().hex()[-4:]
    session_salt = str(time.ticks_ms() % 10000)
    NODE_NAME = f"emb_{unique_hw}_{session_salt}"
    PREFIX = "UDFJC/iot_ws/robot0/"

    scheduler = Scheduler()
    wifi = WiFiManager(ssid=SSID, password=PASSWORD)
    node = Node(prefix=PREFIX, node_name=NODE_NAME)

    mqtt_task = PubSubMQTT(
        client_id=NODE_NAME,
        broker=MQTT_BROKER,
        scheduler=scheduler,
        node=node,
        period_ms=100,
        prefix=PREFIX,
    )

    WatchdogTask(scheduler=scheduler, pubsub=node, wifi=wifi, period_ms=9000)

    # Componentes de entrada y salida
    IRReaderTask(scheduler, node, gpio_ir=2, cooldown_ms=250)
    LEDSirenActuator(node)

    print(f"Pico W lista como periférico de E/S con ID '{NODE_NAME}'. Ejecutando...")
    scheduler.run()