import gc
from machine import ADC

import util
from task import Task


class WatchdogTask(Task):
    def __init__(self, scheduler, pubsub, wifi, period_ms=1000):
        super().__init__(scheduler, period_ms)
        self.pubsub = pubsub
        self.wifi=wifi
        self.sended=0
        #pubsub.subscribe("watchdog/received",self.handle_message_received )

    def update(self):
            self.sended+=1
            data={  "first_ts":  util.time_float(),
                    "mem_free_bytes": gc.mem_free(),
                    "mem_used_bytes": gc.mem_alloc(),
                    "rssi":self.wifi.wlan.status('rssi'),
                    "sended": self.sended,
                    "temperature_c": f"{27 - (ADC(4).read_u16()* 3.3 / 65535 - 0.706) / 0.001721:.2f}"
                    #"ack_ts": 12345678,
                    #"sent_ts": 12345600
                }|self.scheduler.stats()
            #print('WatchdogTask',data)
            self.pubsub.publish(
                "watchdog/stats",
                data
            )
