"""
simulador_car_pc.py
===================
Simulador del Robot CAR para ejecutar directamente en el computador (Windows / PC)
sin necesidad de tener conectada la Raspberry Pi Pico.

Permite probar y verificar la interacción completa con la interfaz Flet:
- Conecta a HiveMQ bajo el prefijo "UDFJC/iot_ws/robot0/".
- Recibe comandos de trayectoria: recta 1m, 1/4 círculo derecha/izquierda o (v, w, t).
- Calcula en tiempo real la cinemática inversa: v_l = v - w*d, v_r = v + w*d.
- Simula la ejecución temporal y responde con la telemetría exacta esperada por Flet.
"""

import json
import math
import os
import sys
import threading
import time
import paho.mqtt.client as mqtt

# Asegurar importación de kinematics
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from common.kinematics import DifferentialKinematics

BROKER = "broker.hivemq.com"
PORT = 1883
PREFIX = "UDFJC/iot_ws/robot0/"

TOPIC_CAR = f"{PREFIX}CAR"
TOPIC_CAR_CMD = f"{PREFIX}CAR/cmd"
TOPIC_CAR_STOP = f"{PREFIX}CAR/stop"
TOPIC_CAR_CONFIG = f"{PREFIX}CAR/config"
TOPIC_CAR_STATUS = f"{PREFIX}CAR/status"
TOPIC_STATUS = f"{PREFIX}status"
TOPIC_SERVO_ANGLE = f"{PREFIX}servo/angle"
TOPIC_SERVO_STATUS = f"{PREFIX}servo/status"


class SimulatedCarPC:
    def __init__(self, d=0.0675, v_max=0.25):
        self.kinematics = DifferentialKinematics(half_track_d=d, v_max=v_max)
        self.d = d
        self.v_max = v_max
        self.deadzone = 0.28
        self.servo_angle = 90.0

        self.current_state = "IDLE"
        self.active_timer = None

        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="simulador_car_pc_udfjc",
        )
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    def on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            print("\n=======================================================")
            print("💻 SIMULADOR DE ROBOT CAR ACTIVO EN EL COMPUTADOR")
            print("=======================================================")
            print(f"[+] Conectado al Broker: {BROKER}:{PORT}")
            print(f"[+] Prefijo de comunicación: {PREFIX}")
            print(f"[+] Parámetros físicos: d={self.d} m, v_max={self.v_max} m/s")
            print("=======================================================")
            print("👉 Ahora puedes abrir la interfaz Flet (python main.py)")
            print("   y presionar los botones para ver los comandos aquí en vivo.\n")

            client.subscribe(TOPIC_CAR)
            client.subscribe(TOPIC_CAR_CMD)
            client.subscribe(TOPIC_CAR_STOP)
            client.subscribe(TOPIC_CAR_CONFIG)
            client.subscribe(TOPIC_SERVO_ANGLE)

            # Notificar que el simulador está listo
            self.publish_status("ready", "Simulador PC CAR en línea y listo para recibir comandos")
        else:
            print(f"[!] Error de conexión MQTT: {rc}")

    def on_message(self, client, userdata, msg):
        topic = msg.topic
        raw = msg.payload.decode("utf-8", errors="replace")
        try:
            data = json.loads(raw)
        except Exception:
            data = {"value": raw}

        if topic == TOPIC_SERVO_ANGLE:
            ang = float(data.get("angle", data.get("value", 90.0)))
            self.servo_angle = ang
            pulse_us = 500 + (ang / 180.0) * 2000
            duty_u16 = int((pulse_us / 20000.0) * 65535)
            print(f"[SERVO SIM] Ángulo recibido: {ang:.1f}° | Pulso: {pulse_us:.0f} µs | duty_u16: {duty_u16}")
            self.client.publish(
                TOPIC_SERVO_STATUS,
                json.dumps({
                    "gpio": "GP12 (SIM)",
                    "angle": ang,
                    "pulse_us": round(pulse_us, 1),
                    "duty_u16": duty_u16,
                }),
            )
            return

        if topic == TOPIC_CAR_STOP or data.get("action") == "stop":
            self.stop_movement("Parada de emergencia ejecutada")
            return

        if topic == TOPIC_CAR_CONFIG:
            if "d" in data:
                self.d = float(data["d"])
                self.kinematics.d = self.d
            if "v_max" in data:
                self.v_max = float(data["v_max"])
                self.kinematics.v_max = self.v_max
            print(f"[CONFIG] Parámetros actualizados: d={self.d}m, v_max={self.v_max}m/s")
            self.publish_status("configured", f"Configuración guardada: d={self.d}m, v_max={self.v_max}m/s")
            return

        # Procesamiento de comandos de movimiento
        action = str(data.get("action", "")).lower()
        if action == "straight":
            dist = float(data.get("distance", 1.0))
            v = float(data.get("v", 0.20))
            t = abs(dist) / abs(v)
            self.execute_movement(v=v, w=0.0, t=t, label=f"Línea recta {dist:.2f}m")
        elif action == "arc":
            radius = float(data.get("radius", 1.0))
            direction = str(data.get("direction", "right")).lower()
            angle_deg = float(data.get("angle_deg", 90.0))
            angle_rad = math.radians(abs(angle_deg))
            v = float(data.get("v", 0.20))
            w_mag = v / max(0.05, radius)
            t = angle_rad / w_mag
            w = -w_mag if direction in ("right", "derecha") else +w_mag
            dir_txt = "Derecha" if w < 0 else "Izquierda"
            self.execute_movement(v=v, w=w, t=t, label=f"Arco {angle_deg:.0f}° R={radius:.2f}m ({dir_txt})")
        elif "v" in data and "w" in data and "t" in data:
            v = float(data["v"])
            w = float(data["w"])
            t = float(data["t"])
            label = str(data.get("label", f"Comando (v={v:.2f}, w={w:.2f}, t={t:.2f}s)"))
            self.execute_movement(v=v, w=w, t=t, label=label)

    def execute_movement(self, v: float, w: float, t: float, label: str):
        if self.active_timer and self.active_timer.is_alive():
            self.active_timer.cancel()

        v_l, v_r = self.kinematics.inverse(v, w)
        pwm_l = max(-1.0, min(1.0, v_l / self.v_max))
        pwm_r = max(-1.0, min(1.0, v_r / self.v_max))
        duty_l = int(abs(pwm_l) * 65535) * (1 if pwm_l >= 0 else -1)
        duty_r = int(abs(pwm_r) * 65535) * (1 if pwm_r >= 0 else -1)

        print("\n-------------------------------------------------------")
        print(f"▶️ [COMANDO RECIBIDO]: {label}")
        print(f"   Velocidad lineal:    v = {v:+.3f} m/s")
        print(f"   Velocidad angular:   w = {w:+.3f} rad/s")
        print(f"   Tiempo asignado:     t = {t:.2f} s")
        print(f"   Cinemática Inversa:  v_l = {v_l:+.3f} m/s  (PWM: {pwm_l*100:+.1f}%, duty: {duty_l})")
        print(f"                        v_r = {v_r:+.3f} m/s  (PWM: {pwm_r*100:+.1f}%, duty: {duty_r})")
        print(f"   Arco central total:  S = {abs(v)*t:.3f} m")
        print(f"   Ángulo total girado: Δα = {math.degrees(w*t):+.1f}°")
        print("-------------------------------------------------------")

        self.current_state = "IN_PROGRESS"
        self.publish_status(
            state="in_progress",
            message=f"{label} en ejecución ({t:.2f}s)",
            v=v,
            w=w,
            t=t,
            v_l=v_l,
            v_r=v_r,
            duty_l=duty_l,
            duty_r=duty_r,
        )

        def finish():
            print(f"✅ [COMPLETADO]: {label} finalizado con éxito.\n")
            self.current_state = "IDLE"
            self.publish_status(
                state="completed",
                message=f"Completado: {label}",
                v=0.0,
                w=0.0,
                t=0.0,
                v_l=0.0,
                v_r=0.0,
                duty_l=0,
                duty_r=0,
            )

        self.active_timer = threading.Timer(t, finish)
        self.active_timer.start()

    def stop_movement(self, reason: str):
        if self.active_timer and self.active_timer.is_alive():
            self.active_timer.cancel()
        self.current_state = "STOPPED"
        print(f"🛑 [PARADA]: {reason}\n")
        self.publish_status("stopped", reason, v=0.0, w=0.0, t=0.0, v_l=0.0, v_r=0.0)

    def publish_status(self, state: str, message: str, v=0.0, w=0.0, t=0.0, v_l=0.0, v_r=0.0, duty_l=0, duty_r=0):
        payload = {
            "state": state,
            "message": message,
            "v": round(v, 4),
            "w": round(w, 4),
            "t": round(t, 2),
            "v_l": round(v_l, 4),
            "v_r": round(v_r, 4),
            "d": self.d,
            "v_max": self.v_max,
            "duty_l": duty_l,
            "duty_r": duty_r,
            "timestamp": int(time.time() * 1000),
        }
        self.client.publish(TOPIC_CAR_STATUS, json.dumps(payload))
        self.client.publish(TOPIC_STATUS, json.dumps(payload))

    def run(self):
        self.client.connect(BROKER, PORT, 60)
        self.client.loop_forever()


if __name__ == "__main__":
    sim = SimulatedCarPC()
    try:
        sim.run()
    except KeyboardInterrupt:
        print("\n[Simulador detenido por el usuario]")
