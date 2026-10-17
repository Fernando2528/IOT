"""
watchdog_task.py
================
Tarea de supervisión (Watchdog + Heartbeat + Telemetría del Scheduler) para la Pico W.
"""

import gc
import time
from task import Task

try:
    from machine import WDT
except ImportError:
    WDT = None


class WatchdogTask(Task):
    def __init__(self, scheduler, pubsub, wifi=None, period_ms=5000, enable_hw_wdt=False):
        super().__init__(scheduler, period_ms=period_ms, priority=10, name="WatchdogTask")
        self.pubsub = pubsub
        self.wifi = wifi
        self.wdt = WDT(timeout=8000) if (enable_hw_wdt and WDT is not None) else None

    def update(self):
        if self.wdt:
            self.wdt.feed()

        if self.wifi and not self.wifi.is_connected():
            self.wifi.connect()

        gc.collect()
        self.pubsub.publish(
            "watchdog",
            {
                "uptime_ms": time.ticks_ms() if hasattr(time, "ticks_ms") else 0,
                "free_ram": gc.mem_free() if hasattr(gc, "mem_free") else 0,
                "tasks": self.scheduler.stats(),
            },
        )
