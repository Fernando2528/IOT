"""
task.py & scheduler.py
======================
Infraestructura de tareas cooperativas para Taller 8/7.
"""

import time
import gc


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
                    task.update()
                    task.next_run = time.ticks_add(now, task.period)

            gc.collect()
            time.sleep_ms(1)
