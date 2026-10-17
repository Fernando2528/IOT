"""
ring_buffer.py
==============
Buffer circular de tamaño fijo para registrar métricas de tiempo de ejecución
sin fragmentar la memoria RAM en MicroPython.
"""

class RingBuffer:
    def __init__(self, size=10, unit="us"):
        self.size = size
        self.data = [0] * size
        self.count = 0
        self.full = False
        self.unit = unit

    def append(self, value):
        index = self.count % self.size
        self.data[index] = value
        self.count += 1
        if self.count >= self.size:
            self.full = True

    def get_data(self):
        if not self.full:
            return self.data[:self.count]
        return self.data

    def stats(self):
        samples = self.get_data()
        res = {
            "count": self.count,
            "unit": self.unit,
            "samples": len(samples),
        }
        if not samples:
            res["min"] = 0
            res["max"] = 0
            res["avg"] = 0
            return res

        res["min"] = min(samples)
        res["max"] = max(samples)
        res["avg"] = round(sum(samples) / len(samples), 1)
        return res
