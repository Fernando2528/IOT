"""
motion_controller.py
====================
Controlador principal de Coreografía y Estados de Movimiento (`CarrobotMotionTask`)
para el Proyecto de Segundo Corte (`robot12`).

Implementa la especificación completa `motionTopics.md` y sincronización con el Gemelo Virtual:
1. Tópico `motion/state`:
   - Recibe `{"v_dm/s", "w_deg/s", "alpha0_deg", "alpha1_deg", "alpha2_deg", "duration_s"}`.
   - Convierte `v_dm/s` a m/s (`* 0.1`) y `w_deg/s` a rad/s (`* pi / 180`).
   - Comanda el chasis diferencial (`CAR`) durante `duration_s` segundos.
   - Interpola suavemente los ángulos de los servomotores del brazo (`alpha1_deg` y `alpha2_deg`)
     desde su ángulo inicial hasta el ángulo asignado durante la demora `duration_s` asignada.
2. Tópico `motion/sequence`:
   - Soporta `"action": "create"` (guarda secuencia; si incluye `"run_at": "now"`, la inicia de inmediato),
     `"action": "delete"`, `"action": "schedule"` (`"run_at": "now"` o marca ISO-8601) y `"action": "execute_now"`.
   - Incluye pre-cargadas en memoria las coreografías oficiales `"even"` (`even.json`, correspondiente
     a `robot12`) y `"odd"` (`odd.json`).
"""

import json
import math
import time
from task import Task
import util

EVEN_DEFAULT_STATES = [
    {"v_dm/s": 0, "w_deg/s": 45, "alpha0_deg": 0, "duration_s": 2},
    {"v_dm/s": 0, "w_deg/s": -45, "alpha0_deg": -90, "alpha1_deg": 0, "duration_s": 2},
    {"v_dm/s": 1.5708, "w_deg/s": 36, "duration_s": 5},
    {"v_dm/s": 0, "w_deg/s": 0, "alpha0_deg": 90, "alpha1_deg": 67.5, "alpha2_deg": -67.5, "duration_s": 2},
    {"v_dm/s": -1.5708, "w_deg/s": 36, "duration_s": 5},
]

ODD_DEFAULT_STATES = [
    {"v_dm/s": 0, "w_deg/s": 45, "alpha0_deg": 0, "duration_s": 2},
    {"v_dm/s": 0, "w_deg/s": -45, "alpha0_deg": 90, "alpha1_deg": 67.5, "alpha2_deg": -67.5, "duration_s": 2},
    {"v_dm/s": -1.5708, "w_deg/s": 36, "duration_s": 5},
    {"v_dm/s": 0, "w_deg/s": 0, "alpha0_deg": -90, "alpha1_deg": 0, "alpha2_deg": 0, "duration_s": 2},
    {"v_dm/s": 1.5708, "w_deg/s": 36, "duration_s": 5},
]


class CarrobotMotionTask(Task):
    def __init__(
        self,
        scheduler,
        pubsub,
        car,
        servo_alpha1=None,
        servo_alpha2=None,
        servo_alpha0=None,
        period_ms: int = 20,
    ):
        self.pubsub = pubsub
        self.car = car
        self.servo_alpha1 = servo_alpha1
        self.servo_alpha2 = servo_alpha2
        self.servo_alpha0 = servo_alpha0

        # Ángulos actuales del brazo (en grados lógicos del modelo)
        self.angles = {
            "alpha0_deg": 0.0,
            "alpha1_deg": 0.0,
            "alpha2_deg": 0.0,
        }
        self.start_angles = dict(self.angles)
        self.target_angles = dict(self.angles)

        # Diccionario de secuencias guardadas (pre-cargado con even y odd)
        self.sequences = {
            "even": [dict(s) for s in EVEN_DEFAULT_STATES],
            "odd": [dict(s) for s in ODD_DEFAULT_STATES],
        }

        # Estado de ejecución actual
        self.active_step = None
        self.step_start_ms = 0
        self.step_duration_ms = 0

        self.active_sequence_name = None
        self.active_sequence_queue = []
        self.active_sequence_index = 0
        self.active_sequence_total = 0

        # Programación diferida por timestamp ISO-8601 (`run_at`)
        self.scheduled_sequence_name = None
        self.scheduled_target_ms = None

        # Suscripciones a los tópicos oficiales de `motionTopics.md` y legacy `RPi/*`
        self.pubsub.subscribe("motion/state", self._on_motion_state)
        self.pubsub.subscribe("motion/sequence", self._on_motion_sequence)
        self.pubsub.subscribe("RPi/state", self._on_motion_state)
        self.pubsub.subscribe("RPi/sequence", self._on_motion_sequence)

        super().__init__(scheduler, period_ms=period_ms, priority=1, name="MotionCtrl")
        print("[MotionCtrl] Suscrito a 'motion/state' y 'motion/sequence' (even/odd listas).")

    def _parse_payload(self, msg):
        if isinstance(msg, dict):
            return msg
        if isinstance(msg, (bytes, bytearray)):
            msg = msg.decode("utf-8")
        if isinstance(msg, str):
            try:
                return json.loads(msg)
            except Exception:
                return None
        return None

    def _normalize_step(self, raw: dict) -> dict:
        """
        Normaliza un paso de `motion/state` o `motion/sequence`.
        Valores por defecto según `motionTopics.md`:
          - `v_dm/s`, `w_deg/s`: 0.0 si no se especifican.
          - `alpha0_deg`, `alpha1_deg`, `alpha2_deg`: 0.0 si no se especifican en `motion/state`,
            o conservan su valor si el paso de secuencia no los menciona.
          - `duration_s`: 1.0 s por defecto.
        """
        v_dm_s = float(raw.get("v_dm/s", raw.get("v", 0.0)))
        w_deg_s = float(raw.get("w_deg/s", raw.get("w", 0.0)))
        duration_s = max(0.01, float(raw.get("duration_s", raw.get("time", 1.0))))

        alpha0_deg = float(raw.get("alpha0_deg", 0.0))
        alpha1_deg = float(raw.get("alpha1_deg", 0.0))
        alpha2_deg = float(raw.get("alpha2_deg", 0.0))

        return {
            "v_dm/s": v_dm_s,
            "w_deg/s": w_deg_s,
            "v_m_s": v_dm_s * 0.1,
            "w_rad_s": math.radians(w_deg_s),
            "alpha0_deg": alpha0_deg,
            "alpha1_deg": alpha1_deg,
            "alpha2_deg": alpha2_deg,
            "duration_s": duration_s,
        }

    def _apply_servos(self, a0_deg: float, a1_deg: float, a2_deg: float):
        self.angles["alpha0_deg"] = a0_deg
        self.angles["alpha1_deg"] = a1_deg
        self.angles["alpha2_deg"] = a2_deg

        if self.servo_alpha0 is not None:
            self.servo_alpha0.set_logical_angle(a0_deg)
        if self.servo_alpha1 is not None:
            self.servo_alpha1.set_logical_angle(a1_deg)
        if self.servo_alpha2 is not None:
            self.servo_alpha2.set_logical_angle(a2_deg)

    def _start_step(self, step: dict, seq_name: str = "state", idx: int = 1, total: int = 1):
        self.active_step = step
        now = time.ticks_ms()
        self.step_start_ms = now
        self.step_duration_ms = max(10, int(step["duration_s"] * 1000))

        self.start_angles = dict(self.angles)
        self.target_angles = {
            "alpha0_deg": step["alpha0_deg"],
            "alpha1_deg": step["alpha1_deg"],
            "alpha2_deg": step["alpha2_deg"],
        }

        label = f"{seq_name}[{idx}/{total}]"
        self.car.move(
            v=step["v_m_s"],
            w=step["w_rad_s"],
            t=step["duration_s"],
            label=label,
            keep_duration=True,
        )

        self._publish_motion_status(
            state="running",
            sequence=seq_name,
            step=idx,
            total_steps=total,
            current=step,
            message=(
                f"Ejecutando {label}: v={step['v_dm/s']:.2f} dm/s, w={step['w_deg/s']:.1f}°/s, "
                f"a1={step['alpha1_deg']:.1f}°, a2={step['alpha2_deg']:.1f}°, T={step['duration_s']:.2f}s"
            ),
        )

    def _start_sequence_now(self, name: str):
        states = self.sequences.get(name)
        if not states:
            self._publish_motion_status(
                state="error",
                sequence=name,
                step=0,
                total_steps=0,
                current=None,
                message=f"La secuencia '{name}' no existe o está vacía.",
            )
            return

        self.scheduled_sequence_name = None
        self.scheduled_target_ms = None
        self.active_sequence_name = name
        self.active_sequence_queue = [self._normalize_step(s) for s in states]
        self.active_sequence_total = len(self.active_sequence_queue)
        self.active_sequence_index = 1

        first_step = self.active_sequence_queue.pop(0)
        self._start_step(
            first_step,
            seq_name=name,
            idx=self.active_sequence_index,
            total=self.active_sequence_total,
        )

    def _schedule_sequence(self, name: str, run_at):
        if name not in self.sequences:
            self._publish_motion_status(
                state="error",
                sequence=name,
                step=0,
                total_steps=0,
                current=None,
                message=f"Secuencia desconocida '{name}'. Créala primero.",
            )
            return

        run_at_str = str(run_at or "now").strip()
        if run_at_str.lower() in ("now", "immediately", ""):
            self._start_sequence_now(name)
            return

        target_epoch = util.parse_iso8601_to_epoch(run_at_str)
        now_epoch = time.time()
        # Si el reloj RTC de la Pico está sincronizado (año >= 2024 -> epoch > 1700000000)
        if target_epoch is not None and now_epoch > 1_700_000_000:
            delay_ms = max(0, int((target_epoch - now_epoch) * 1000))
        elif target_epoch is not None:
            # Si no hubo NTP pero enviaron un número de segundos o fecha cercana
            delay_ms = 0
        else:
            try:
                delay_ms = max(0, int(float(run_at_str) * 1000))
            except Exception:
                delay_ms = 0

        if delay_ms <= 0:
            self._start_sequence_now(name)
        else:
            self.scheduled_sequence_name = name
            self.scheduled_target_ms = time.ticks_add(time.ticks_ms(), delay_ms)
            self._publish_motion_status(
                state="scheduled",
                sequence=name,
                step=0,
                total_steps=len(self.sequences[name]),
                current=None,
                message=f"Secuencia '{name}' programada para iniciar en {delay_ms / 1000.0:.1f} s ({run_at_str})",
            )

    def _on_motion_state(self, topic=None, msg=None):
        data = self._parse_payload(msg)
        if not isinstance(data, dict):
            return
        try:
            # Cancelar cualquier secuencia en curso y ejecutar el estado inmediato
            self.active_sequence_name = None
            self.active_sequence_queue = []
            step = self._normalize_step(data)
            self._start_step(step, seq_name="state", idx=1, total=1)
        except Exception as err:
            print("[MotionCtrl] Error en motion/state:", err)

    def _on_motion_sequence(self, topic=None, msg=None):
        data = self._parse_payload(msg)
        if not isinstance(data, dict):
            return

        action = str(data.get("action", "")).strip().lower()
        name = str(data.get("name", "")).strip()

        if action == "create":
            states = data.get("states")
            if not name or not isinstance(states, list) or len(states) == 0:
                print("[MotionCtrl] 'create' requiere 'name' y 'states' no vacío.")
                return
            self.sequences[name] = [dict(s) for s in states]
            print(f"[MotionCtrl] Secuencia '{name}' guardada ({len(states)} estados).")

            run_at = data.get("run_at")
            if run_at is not None:
                self._schedule_sequence(name, run_at)
            else:
                self._publish_motion_status(
                    state="created",
                    sequence=name,
                    step=0,
                    total_steps=len(states),
                    current=None,
                    message=f"Secuencia '{name}' guardada ({len(states)} pasos).",
                )

        elif action == "delete":
            if name in self.sequences:
                del self.sequences[name]
            if self.active_sequence_name == name:
                self.active_sequence_name = None
                self.active_sequence_queue = []
                self.active_step = None
                self.car.stop(f"Secuencia '{name}' eliminada")
            if self.scheduled_sequence_name == name:
                self.scheduled_sequence_name = None
                self.scheduled_target_ms = None
            self._publish_motion_status(
                state="deleted",
                sequence=name,
                step=0,
                total_steps=0,
                current=None,
                message=f"Secuencia '{name}' eliminada.",
            )

        elif action in ("schedule", "execute_now"):
            run_at = "now" if action == "execute_now" else data.get("run_at", "now")
            self._schedule_sequence(name, run_at)

    def update(self):
        now = time.ticks_ms()

        # 1. Revisar si hay una secuencia programada (`schedule`) lista para arrancar
        if self.scheduled_sequence_name and self.scheduled_target_ms is not None:
            if time.ticks_diff(now, self.scheduled_target_ms) >= 0:
                seq_to_run = self.scheduled_sequence_name
                self.scheduled_sequence_name = None
                self.scheduled_target_ms = None
                self._start_sequence_now(seq_to_run)

        # 2. Actualizar interpolación del brazo y temporizador del paso activo
        if self.active_step is None:
            return

        elapsed_ms = time.ticks_diff(now, self.step_start_ms)
        ratio = min(1.0, max(0.0, float(elapsed_ms) / float(self.step_duration_ms)))

        # Interpolación lineal de los ángulos del brazo durante `duration_s` (idéntico al Gemelo Virtual)
        a0 = self.start_angles["alpha0_deg"] + (self.target_angles["alpha0_deg"] - self.start_angles["alpha0_deg"]) * ratio
        a1 = self.start_angles["alpha1_deg"] + (self.target_angles["alpha1_deg"] - self.start_angles["alpha1_deg"]) * ratio
        a2 = self.start_angles["alpha2_deg"] + (self.target_angles["alpha2_deg"] - self.start_angles["alpha2_deg"]) * ratio
        self._apply_servos(a0, a1, a2)

        # 3. Verificar si terminó el paso actual
        if elapsed_ms >= self.step_duration_ms:
            self._apply_servos(
                self.target_angles["alpha0_deg"],
                self.target_angles["alpha1_deg"],
                self.target_angles["alpha2_deg"],
            )
            if self.active_sequence_queue:
                self.active_sequence_index += 1
                next_step = self.active_sequence_queue.pop(0)
                self._start_step(
                    next_step,
                    seq_name=self.active_sequence_name or "seq",
                    idx=self.active_sequence_index,
                    total=self.active_sequence_total,
                )
            else:
                finished_name = self.active_sequence_name or "state"
                total_done = self.active_sequence_total or 1
                last_step = self.active_step
                self.active_step = None
                self.active_sequence_name = None
                self.car.stop(f"Fin de '{finished_name}'")
                self._publish_motion_status(
                    state="completed",
                    sequence=finished_name,
                    step=total_done,
                    total_steps=total_done,
                    current=last_step,
                    message=f"Finalizado '{finished_name}' ({total_done} pasos completados).",
                )

    def _publish_motion_status(self, state: str, sequence: str, step: int, total_steps: int, current: dict | None, message: str):
        payload = {
            "state": state,
            "sequence": sequence,
            "step": step,
            "total_steps": total_steps,
            "v_dm/s": round(current["v_dm/s"], 4) if current else 0.0,
            "w_deg/s": round(current["w_deg/s"], 2) if current else 0.0,
            "alpha0_deg": round(self.angles["alpha0_deg"], 2),
            "alpha1_deg": round(self.angles["alpha1_deg"], 2),
            "alpha2_deg": round(self.angles["alpha2_deg"], 2),
            "duration_s": round(current["duration_s"], 2) if current else 0.0,
            "saved_sequences": list(self.sequences.keys()),
            "message": message,
        }
        self.pubsub.publish("motion/status", payload)
        print(f"[MotionCtrl:{state.upper()}] {message}")
