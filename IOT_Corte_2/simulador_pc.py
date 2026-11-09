"""
simulador_pc.py
===============
Simulador en PC del nodo embebido `robot12` (Proyecto Segundo Corte: Coreografía).
Permite probar la interfaz Flet, el Gemelo Virtual Individual (`PubSub_client_web.html`)
y el Visualizador Grupal (`robot_coreografia_mqtt.html`) desde el computador sin necesidad
de encender la batería de la Raspberry Pi Pico W.

Simula:
- Suscripción a `UDFJC/carrrobot/robot12/motion/state` y `motion/sequence`.
- Respuesta inmediata a `node/get_second_ts` -> `node/send_second_ts` (Latencia RTT y Jitter RFC).
- Publicación periódica de `watchdog/stats` con métricas de tareas (`CAR`, `MotionCtrl`, `OledWatchdog`, `PubSubMQTT`).
- Simulación de la pantalla OLED SSD1306 y scroll por potenciómetro (`oled/status`).
"""

import json
import math
import random
import threading
import time
import paho.mqtt.client as mqtt

from common.kinematics import EVEN_STATES, ODD_STATES, normalize_motion_state, parse_iso8601_to_epoch

BROKER = "broker.hivemq.com"
PORT = 1883
PREFIX = "UDFJC/carrrobot/robot12/"


class CarrobotPCSimulator:
    def __init__(self, prefix: str = PREFIX):
        self.prefix = prefix if prefix.endswith("/") else prefix + "/"
        self.sended = 0
        self.pot_u16 = 0
        self.auto_pot = True
        self.sequences = {
            "even": [dict(s) for s in EVEN_STATES],
            "odd": [dict(s) for s in ODD_STATES],
        }
        self.angles = {"alpha0_deg": 0.0, "alpha1_deg": 0.0, "alpha2_deg": 0.0}
        self.motion_summary = {
            "state": "IDLE",
            "sequence": "even",
            "step": 0,
            "total_steps": 5,
            "v_dm/s": 0.0,
            "w_deg/s": 0.0,
        }
        self.running = True

        cid = f"sim_carrobot12_{random.randint(1000, 9999)}"
        try:
            self.client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=cid,
            )
        except AttributeError:
            self.client = mqtt.Client(client_id=cid)

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def publish(self, suffix: str, payload: dict):
        self.client.publish(self.prefix + suffix, json.dumps(payload))

    def _on_connect(self, client, userdata, flags, rc, *args):
        print(f"[Simulador PC] Conectado a {BROKER}:{PORT} | Prefijo: {self.prefix}")
        for sub in ("motion/state", "motion/sequence", "node/get_second_ts", "oled/scroll", "CAR/stop", "CAR/config"):
            client.subscribe(self.prefix + sub)

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        if not topic.startswith(self.prefix):
            return
        local = topic[len(self.prefix) :]
        try:
            data = json.loads(msg.payload.decode("utf-8"))
        except Exception:
            return

        if local == "node/get_second_ts":
            self.publish(
                "node/send_second_ts",
                {
                    "topic": data.get("topic"),
                    "first_ts": data.get("first_ts"),
                    "second_ts": round(time.time(), 6),
                    "sended": data.get("sended"),
                },
            )
        elif local == "oled/scroll":
            if data.get("mode") == "auto":
                self.auto_pot = True
            elif "pot_u16" in data:
                self.auto_pot = False
                self.pot_u16 = int(data["pot_u16"])
        elif local == "motion/state":
            threading.Thread(target=self._exec_single_state, args=(data,), daemon=True).start()
        elif local == "motion/sequence":
            threading.Thread(target=self._exec_sequence_cmd, args=(data,), daemon=True).start()

    def _exec_single_state(self, raw_state: dict):
        st = normalize_motion_state(raw_state, self.angles)
        self.angles["alpha0_deg"] = st["alpha0_deg"]
        self.angles["alpha1_deg"] = st["alpha1_deg"]
        self.angles["alpha2_deg"] = st["alpha2_deg"]
        self.motion_summary.update(
            {
                "state": "RUNNING",
                "sequence": "state",
                "step": 1,
                "total_steps": 1,
                "v_dm/s": st["v_dm/s"],
                "w_deg/s": st["w_deg/s"],
            }
        )
        self.publish(
            "motion/status",
            {
                "state": "running",
                "sequence": "state",
                "step": 1,
                "total_steps": 1,
                "v_dm/s": st["v_dm/s"],
                "w_deg/s": st["w_deg/s"],
                "alpha0_deg": st["alpha0_deg"],
                "alpha1_deg": st["alpha1_deg"],
                "alpha2_deg": st["alpha2_deg"],
                "duration_s": st["duration_s"],
                "message": f"Simulando estado: v={st['v_dm/s']} dm/s, w={st['w_deg/s']}°/s, T={st['duration_s']}s",
            },
        )
        time.sleep(st["duration_s"])
        self.motion_summary["state"] = "IDLE"
        self.motion_summary["v_dm/s"] = 0.0
        self.motion_summary["w_deg/s"] = 0.0
        self.publish(
            "motion/status",
            {
                "state": "completed",
                "sequence": "state",
                "step": 1,
                "total_steps": 1,
                "v_dm/s": 0.0,
                "w_deg/s": 0.0,
                "alpha0_deg": self.angles["alpha0_deg"],
                "alpha1_deg": self.angles["alpha1_deg"],
                "alpha2_deg": self.angles["alpha2_deg"],
                "duration_s": st["duration_s"],
                "message": "Estado completado en simulador.",
            },
        )

    def _exec_sequence_cmd(self, data: dict):
        action = str(data.get("action", "")).lower()
        name = str(data.get("name", "even"))
        if action == "create":
            states = data.get("states", [])
            if states:
                self.sequences[name] = states
            if data.get("run_at") is None:
                return
        elif action == "delete":
            self.sequences.pop(name, None)
            return

        run_at = str(data.get("run_at", "now"))
        epoch = parse_iso8601_to_epoch(run_at)
        if epoch is not None:
            delay = max(0.0, epoch - time.time())
            if delay > 0:
                time.sleep(delay)

        states = self.sequences.get(name, [])
        total = len(states)
        for idx, raw in enumerate(states, start=1):
            st = normalize_motion_state(raw, self.angles)
            self.angles["alpha0_deg"] = st["alpha0_deg"]
            self.angles["alpha1_deg"] = st["alpha1_deg"]
            self.angles["alpha2_deg"] = st["alpha2_deg"]
            self.motion_summary.update(
                {
                    "state": "RUNNING",
                    "sequence": name,
                    "step": idx,
                    "total_steps": total,
                    "v_dm/s": st["v_dm/s"],
                    "w_deg/s": st["w_deg/s"],
                }
            )
            self.publish(
                "motion/status",
                {
                    "state": "running",
                    "sequence": name,
                    "step": idx,
                    "total_steps": total,
                    "v_dm/s": st["v_dm/s"],
                    "w_deg/s": st["w_deg/s"],
                    "alpha0_deg": st["alpha0_deg"],
                    "alpha1_deg": st["alpha1_deg"],
                    "alpha2_deg": st["alpha2_deg"],
                    "duration_s": st["duration_s"],
                    "message": f"Coreografía '{name}' paso [{idx}/{total}]: v={st['v_dm/s']} dm/s, w={st['w_deg/s']}°/s",
                },
            )
            time.sleep(st["duration_s"])

        self.motion_summary["state"] = "IDLE"
        self.publish(
            "motion/status",
            {
                "state": "completed",
                "sequence": name,
                "step": total,
                "total_steps": total,
                "v_dm/s": 0.0,
                "w_deg/s": 0.0,
                "alpha0_deg": self.angles["alpha0_deg"],
                "alpha1_deg": self.angles["alpha1_deg"],
                "alpha2_deg": self.angles["alpha2_deg"],
                "duration_s": 0.0,
                "message": f"Coreografía '{name}' completada ({total} pasos).",
            },
        )

    def run_forever(self):
        self.client.connect(BROKER, PORT, keepalive=60)
        self.client.loop_start()
        print("[Simulador PC] Publicando telemetría de Watchdog y OLED cada 2 segundos (Ctrl+C para salir)...")
        try:
            while self.running:
                self.sended += 1
                wdt = {
                    "first_ts": f"{time.time():.6f}",
                    "mem_free_bytes": 124512,
                    "mem_used_bytes": 39264,
                    "rssi": random.randint(-58, -51),
                    "sended": self.sended,
                    "temperature_c": f"{28.2 + random.uniform(-0.3, 0.3):.2f}",
                    "CAR": {"min": 95, "max": 380, "avg": 145.0, "period": 20},
                    "MotionCtrl": {"min": 80, "max": 310, "avg": 120.0, "period": 20},
                    "PubSubMQTT": {"min": 210, "max": 950, "avg": 390.0, "period": 35},
                    "OledWatchdog": {"min": 3200, "max": 6800, "avg": 4500.0, "period": 120},
                    "WatchdogTask": {"min": 650, "max": 1200, "avg": 820.0, "period": 2000},
                }
                self.publish("watchdog/stats", wdt)

                lines = [
                    "ID:robot12 (PAR)",
                    f"RSSI:{wdt['rssi']}dBm #{self.sended}",
                    "RAM L:121K U:38K",
                    f"Temp:{wdt['temperature_c']} C",
                    f"Est:{self.motion_summary['state']} S:{self.motion_summary['sequence']}",
                    f"Paso:{self.motion_summary['step']}/{self.motion_summary['total_steps']}",
                    f"v:{self.motion_summary['v_dm/s']:.2f}dm w:{self.motion_summary['w_deg/s']:.0f}d",
                    f"Brazo:{self.angles['alpha1_deg']:.1f}/{self.angles['alpha2_deg']:.1f}",
                    "-- TAREAS CPU --",
                    "CAR:0.7% 145us",
                    "Motion:0.6% 120us",
                    "MQTT:1.1% 390us",
                    "OLED:3.8% 4500us",
                    "WDT:0.0% 820us",
                ]
                max_scroll = max(0, len(lines) - 6)
                s_idx = min(max_scroll, int((self.pot_u16 / 65535.0) * (max_scroll + 0.99)))
                self.publish(
                    "oled/status",
                    {
                        "pot_u16": self.pot_u16,
                        "pot_pct": round(self.pot_u16 * 100.0 / 65535.0, 1),
                        "scroll_index": s_idx,
                        "max_scroll": max_scroll,
                        "total_lines": len(lines),
                        "visible_lines": lines[s_idx : s_idx + 6],
                        "all_lines": lines,
                        "i2c_info": "Simulado en PC (I2C0 0x3C)",
                    },
                )
                time.sleep(2.0)
        except KeyboardInterrupt:
            print("\n[Simulador PC] Detenido.")
        finally:
            self.client.loop_stop()
            self.client.disconnect()


if __name__ == "__main__":
    sim = CarrobotPCSimulator()
    sim.run_forever()
