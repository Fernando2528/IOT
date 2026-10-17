"""
scheduler.py
============
Scheduler cooperativo no bloqueante.
Organiza la ejecución ordenada de múltiples tareas periódicas sin recurrir a sleep()
prolongados ni a un RTOS pesado, permitiendo atender sensores, red y actuadores concurrentemente.
"""

import time
import gc


class Scheduler:
    def __init__(self):
        self.tasks = []

    def add(self, task):
        self.tasks.append(task)
        # Ordenar por prioridad (menor número = mayor prioridad)
        self.tasks.sort(key=lambda t: t.priority)

    def run(self):
        """Bucle principal no bloqueante del microcontrolador."""
        while True:
            now = time.ticks_ms()

            for task in self.tasks:
                if time.ticks_diff(now, task.next_run) >= 0:
                    task.update_measured()
                    # Programar siguiente ejecución
                    task.next_run = time.ticks_add(now, task.period)

            gc.collect()
            time.sleep_ms(1)

    def stats(self):
        """Genera un resumen estructurado del desempeño y latencia de todas las tareas."""
        report = {}
        for task in self.tasks:
            st = task.metrics.stats()
            st["period_ms"] = task.period
            report[task.name] = st
        return report
