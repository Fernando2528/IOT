"""
scheduler.py
============
Planificador cooperativo no bloqueante. Ejecuta las tareas periódicas
y recolecta estadísticas de uso de CPU para el Watchdog y la pantalla OLED.
"""

import gc
import time


class Scheduler:
    def __init__(self):
        self.tasks = []

    def add(self, task):
        self.tasks.append(task)
        self.tasks.sort(key=lambda t: t.priority)

    def run(self):
        while True:
            now = time.ticks_ms()
            for task in self.tasks:
                if time.ticks_diff(now, task.next_run) >= 0:
                    try:
                        task.update_measured()
                    except Exception as err:
                        print(f"[Scheduler] Error en tarea {task.name}:", err)
                    task.next_run = time.ticks_add(now, task.period)
            gc.collect()
            time.sleep_ms(1)

    def stats(self):
        stats_dic = {}
        for task in self.tasks:
            st = task.metrics.stats()
            st["period"] = task.period
            stats_dic[task.name] = st
        return stats_dic
