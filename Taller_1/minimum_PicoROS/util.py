import time

def time_float():
        t_ns_str = str(time.time_ns())
        return t_ns_str[:-9]+"."+t_ns_str[-9:-3]