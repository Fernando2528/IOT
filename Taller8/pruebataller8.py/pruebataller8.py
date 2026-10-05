import json
import machine
import time
from machine import Pin, PWM
from task import Task


# ==========================================================
# TAREA DE CONTROL CINEMÁTICO DE MOTORES CON L298N (5V)
# ==========================================================
class MotorTask(Task):
    def __init__(self, scheduler, pubsub, period_ms=50):
        self.pubsub = pubsub
        
        # --- Parámetros mecánicos y cinemáticos ---
        self.L = 0.15         # Distancia entre ruedas (trocha en metros, ej: 15 cm)
        self.VEL_BASE = 0.18  # Velocidad estimada (m/s) ajustada para L298N a ~3.3V efectivos

        # --- LED integrado para verificación visual ---
        try:
            self.led = Pin("LED", Pin.OUT)
        except Exception:
            self.led = Pin(25, Pin.OUT)
        self.led.value(0)

        # --- Pines de Dirección del L298N ---
        self.in1 = Pin(2, Pin.OUT)  # IN1 -> GP2 (Motor Izquierdo)
        self.in2 = Pin(3, Pin.OUT)  # IN2 -> GP3 (Motor Izquierdo)
        self.in3 = Pin(4, Pin.OUT)  # IN3 -> GP4 (Motor Derecho)
        self.in4 = Pin(5, Pin.OUT)  # IN4 -> GP5 (Motor Derecho)

        # --- Pines de Velocidad PWM (ENA y ENB) ---
        # NOTA: Debes retirar los jumpers negros de ENA y ENB en el L298N
        self.pwm_a = PWM(Pin(6))    # ENA -> GP6 (PWM Motor Izquierdo)
        self.pwm_b = PWM(Pin(7))    # ENB -> GP7 (PWM Motor Derecho)
        self.pwm_a.freq(1000)
        self.pwm_b.freq(1000)

        # Estado inicial
        self.detener()
        self.state = "IDLE"
        self.move_end_ms = 0
        self.accion_actual = "ninguna"

        # Suscripción al tópico de comandos MQTT
        if hasattr(self.pubsub, "subscribe"):
            self.pubsub.subscribe("cmd", self.on_command)
        elif hasattr(self.pubsub, "register_callback"):
            self.pubsub.register_callback("cmd", self.on_command)

        super().__init__(scheduler, period_ms=period_ms)
        print("Tarea MotorTask (L298N) iniciada y suscrita a 'cmd'")

    def set_motores(self, vel_izq, vel_der):
        """
        Aplica velocidad normalizada (-1.0 a 1.0).
        Controla los puentes H del L298N y el duty cycle en ENA/ENB.
        """
        # Motor Izquierdo (IN1, IN2, ENA)
        self.in1.value(vel_izq > 0)
        self.in2.value(vel_izq < 0)
        self.pwm_a.duty_u16(int(abs(vel_izq) * 65535))

        # Motor Derecho (IN3, IN4, ENB)
        self.in3.value(vel_der > 0)
        self.in4.value(vel_der < 0)
        self.pwm_b.duty_u16(int(abs(vel_der) * 65535))

        # LED encendido si hay movimiento activo
        hay_movimiento = abs(vel_izq) > 0 or abs(vel_der) > 0
        self.led.value(1 if hay_movimiento else 0)

    def detener(self):
        self.in1.value(0)
        self.in2.value(0)
        self.in3.value(0)
        self.in4.value(0)
        self.pwm_a.duty_u16(0)
        self.pwm_b.duty_u16(0)
        self.led.value(0)

    def on_command(self, topic, payload):
        """Recepción y parseo de comandos MQTT."""
        try:
            if isinstance(payload, (bytes, str)):
                data = json.loads(payload)
            else:
                data = payload

            action = data.get("action", "")

            # 1. Movimiento en línea recta
            if action == "straight":
                distancia = float(data.get("distance", 1.0))
                duracion_s = distancia / self.VEL_BASE
                self.duracion_ms = int(duracion_s * 1000)

                # Compensación L298N: 88% de potencia para vencer la fricción
                self.set_motores(0.88, 0.88)
                self.move_end_ms = time.ticks_add(time.ticks_ms(), self.duracion_ms)
                self.state = "MOVING"
                self.accion_actual = f"Recta {distancia}m"

                self._notificar("in_progress", f"Iniciando avance recto ({distancia}m)")

            # 2. Movimiento en arco circular
            elif action == "arc":
                direccion = data.get("direction", "left")
                radio = float(data.get("radius", 1.0))

                # Arco de 90 grados (pi / 2 rad)
                pi_medios = 3.14159 / 2
                d_ext = pi_medios * (radio + (self.L / 2))
                d_int = pi_medios * (radio - (self.L / 2))

                # Rueda externa a 90% de potencia
                v_ext = 0.90
                v_int = v_ext * (d_int / d_ext)
                duracion_s = d_ext / self.VEL_BASE
                self.duracion_ms = int(duracion_s * 1000)

                if direccion == "left":
                    self.set_motores(v_int, v_ext)
                else:
                    self.set_motores(v_ext, v_int)

                self.move_end_ms = time.ticks_add(time.ticks_ms(), self.duracion_ms)
                self.state = "MOVING"
                self.accion_actual = f"Arco 1/4 {direccion}"

                self._notificar("in_progress", f"Iniciando arco {direccion} R={radio}m")

            # 3. Parada de emergencia
            elif action == "stop":
                self.detener()
                self.state = "IDLE"
                self._notificar("stopped", "Detención forzada de motores")

        except Exception as err:
            print("Error en comando:", err)
            self._notificar("error", str(err))

    def update(self):
        """Revisión periódica ejecutada por el Scheduler sin bloquear."""
        if self.state == "MOVING":
            if time.ticks_diff(time.ticks_ms(), self.move_end_ms) >= 0:
                self.detener()
                self.state = "IDLE"
                self._notificar("completed", f"Completado: {self.accion_actual}")
                self.accion_actual = "ninguna"

    def _notificar(self, estado, mensaje):
        payload = {
            "state": estado,
            "message": mensaje,
            "timestamp": time.ticks_ms()
        }
        self.pubsub.publish("status", payload)
        print(f"[MotorTask L298N] {mensaje}")


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
    NODE_NAME = f"emb_robot_{unique_hw}_{session_salt}"
    PREFIX = "UDFJC/iot_ws/robot0/"

    scheduler = Scheduler()
    print("Iniciando conexión de red...")

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

    # Tarea de control de motores L298N cada 50 ms
    MotorTask(scheduler=scheduler, pubsub=node, period_ms=50)

    print(f"Robot L298N activo bajo ID: '{NODE_NAME}'. Ejecutando scheduler...")
    scheduler.run()