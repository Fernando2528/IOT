import time
import gc

class Scheduler:
    def __init__(self):
        self.tasks = []

    def add(self, task):
        self.tasks.append(task)
        self.tasks.sort(key=lambda t: t.priority)
        print('Scheduler.tasks',self.tasks)

    def run(self):
        while True:
            now = time.ticks_ms()

            for task in self.tasks:
                if time.ticks_diff(now, task.next_run) >= 0:
                    task.update_measured()
                    task.next_run = time.ticks_add(now, task.period)

            gc.collect()
            time.sleep_ms(1)


    def stats(self):
        stats_dic={}
        
        for task in self.tasks:
            #print('Scheduler.stats',task)
            stats_dic[task.name]=task.metrics.stats()
            stats_dic[task.name]['period']=task.period
        return stats_dic    
