"""
task.py
=======
Clase Task base.
"""

import time


class Task:
    def __init__(self, scheduler, period_ms, name=None, priority=1):
        self.scheduler = scheduler
        self.period = period_ms
        self.priority = priority
        self.name = name or self.__class__.__name__
        self.next_run = time.ticks_ms()

        if scheduler:
            scheduler.add(self)

    def update(self):
        pass
