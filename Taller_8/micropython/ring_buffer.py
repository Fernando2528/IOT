"""
ring_buffer.py
==============
Buffer circular ligero para métricas de tiempo de ejecución del Scheduler en MicroPython.
"""

import math


class RingBuffer:
    def __init__(self, size=20):
        self.size = size
        self.data = [0] * size
        self.index = 0
        self.count = 0

    def append(self, value):
        self.data[self.index] = value
        self.index = (self.index + 1) % self.size
        if self.count < self.size:
            self.count += 1

    def get_all(self):
        return self.data[: self.count]

    def stats(self):
        if self.count == 0:
            return {"n": 0, "mean": 0.0, "std": 0.0, "max": 0, "min": 0}
        vals = self.get_all()
        n = len(vals)
        mean = sum(vals) / n
        variance = sum((x - mean) ** 2 for x in vals) / n
        return {
            "n": n,
            "mean": round(mean, 2),
            "std": round(math.sqrt(variance), 2),
            "max": max(vals),
            "min": min(vals),
        }
