import time

from ring_buffer import RingBuffer

class Task:
    def __init__(self, scheduler, period_ms, priority=1,name=None):
        self.period = period_ms
        self.priority = priority
        self.name = name or self.__class__.__name__
        self.next_run = time.ticks_ms()
        self.scheduler=scheduler
        scheduler.add(self)
        self.metrics=RingBuffer();

    def update(self):
        pass

    def update_measured(self):
        #if not self.enable_metrics:
        #    self.update()
        #    return

        start = time.ticks_us()
        self.update()
        end = time.ticks_us()

        #print('update_measured',self.metrics)
        #if self.metrics:
        self.metrics.append(time.ticks_diff(end, start))

