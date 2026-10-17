"""
scheduler.py
============
Planificador cooperativo no bloqueante para Raspberry Pi Pico W.
Ejecuta las tareas periódicas (CAR, MQTT, Watchdog, Sensores) sin bloquear el CPU.
"""

import gc
import time


class Scheduler:
    def __init__(self):
        self.tasks = []

    def add(self, task):
        self.tasks.append(task)
        self.tasks.sort(key=lambda t: t.priority)
        print("[Scheduler] Tarea registrada:", task.name, f"({task.period} ms)")

    def step(self):
        """Ejecuta un ciclo de evaluación de todas las tareas listas."""
        now = time.ticks_ms()
        for task in self.tasks:
            if time.ticks_diff(now, task.next_run) >= 0:
                task.update_measured()
                task.next_run = time.ticks_add(now, task.period)

    def run(self):
        print("[Scheduler] Iniciando bucle cooperativo en tiempo real...")
        ticks_gc = 0
        while True:
            self.step()
            ticks_gc += 1
            if ticks_gc >= 200:
                ticks_gc = 0
                gc.collect()
            time.sleep_ms(1)

    def stats(self):
        stats_dic = {}
        for task in self.tasks:
            stats_dic[task.name] = task.metrics.stats()
            stats_dic[task.name]["period"] = task.period
        return stats_dic
