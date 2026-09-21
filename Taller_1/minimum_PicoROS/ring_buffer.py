class RingBuffer:
    def __init__(self, size=10, unit="us"):
        self.size = size
        self.data = [0] * size
        self.index = 0
        #self.last = 0
        self.count = 0
        self.full = False
        self.unit=unit
        

    def append(self, value):
        #print('append',value)
        self.data[self.index] = value
        self.count = self.count + 1
        self.index = self.count % self.size

        if self.index == 0:
            self.full = True
        
        #if not self.full:
        #    self.last += 1

    def get(self):
        if not self.full:
            return self.data[:self.index]
        return self.data[self.index:] + self.data[:self.index]

    def get_disord(self):
        if not self.full:
            return self.data[:self.index]
        return self.data

    def __len__(self):
        return self.size if self.full else self.index
    
    def stats(self):
        #print('stats1')
        data = self.get_disord()
        ret_dic=  {
            "len": len(data),
            "count": self.count,
            "unit": self.unit
        }

        #print('stats2',data)
        if not data:
            return ret_dic
        #print('stats3',data)
        return ret_dic | {
            "min": min(data),
            "max": max(data),
            "avg": sum(data) / len(data)
        }
