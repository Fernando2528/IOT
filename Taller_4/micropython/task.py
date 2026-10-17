"""
task.py
=======
Abstracción de Tarea periódica cooperativa para MicroPython.
Implementa el principio: "Medir antes de optimizar" midiendo el tiempo
exacto de ejecución en microsegundos (ticks_us) de cada ciclo.
"""

import time
from ring_buffer import RingBuffer


class Task:
    def __init__(self, scheduler, period_ms, name=None, priority=1, function=None):
        self.scheduler = scheduler
        self.period = period_ms
        self.priority = priority
        self.name = name or self.__class__.__name__
        self.function = function
        self.next_run = time.ticks_ms()
        self.metrics = RingBuffer(size=10, unit="us")

        if scheduler:
            scheduler.add(self)

    def update(self):
        """Sobrescribir en subclases o invocar la función asociada."""
        if self.function:
            self.function()

    def update_measured(self):
        """Ejecuta la tarea y mide el tiempo transcurrido en microsegundos."""
        start = time.ticks_us()
        self.update()
        end = time.ticks_us()
        elapsed = time.ticks_diff(end, start)
        self.metrics.append(elapsed)
