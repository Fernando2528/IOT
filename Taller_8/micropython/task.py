"""
task.py
=======
Clase base Task para ejecución cooperativa periódica en el Scheduler.
"""

import time
from ring_buffer import RingBuffer


class Task:
    def __init__(self, scheduler, period_ms=50, priority=1, name=None):
        self.period = int(period_ms)
        self.priority = priority
        self.name = name or self.__class__.__name__
        self.next_run = time.ticks_ms() if hasattr(time, "ticks_ms") else 0
        self.scheduler = scheduler
        self.metrics = RingBuffer()
        if scheduler is not None:
            scheduler.add(self)

    def update(self):
        pass

    def update_measured(self):
        if hasattr(time, "ticks_us"):
            start = time.ticks_us()
            self.update()
            end = time.ticks_us()
            self.metrics.append(time.ticks_diff(end, start))
        else:
            self.update()
