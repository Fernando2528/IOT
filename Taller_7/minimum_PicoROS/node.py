import json
import random
import sys

import util

class Node:
    def __init__(self,  prefix='UDFJC/emb1/robot0/', node_name=None):
        #self.sock = socket_client
        #self.sock.add_action("PUB", self.handle_pub)
        #self.sock.add_action("SUB", self.handle_sub)
        self.prefix=prefix
        self.subscriptions = {}  # topic -> set(callback)
        #self.subscribe("node/new_sub",self.handle_new_sub )
        self.node_name  = node_name or prefix+str(random.randint(0,2**32-1))
        self.transports = []
        self.subscribe("node/get_second_ts",self.handle_get_second_ts )
        

    def add_transport(self, transport):
        self.transports.append(transport)
        for topic in self.subscriptions:
            transport.subscribe(topic)
            

    def publish(self, topic, msg):
        ts=util.time_float()
        for t in self.transports:
            t.publish(topic,msg)
#         self.broker_publish(topic,data,ts=ts)
        self.local_publish(topic,msg,ts=ts)
#        
#     def broker_publish(self,topic,data,ts=None):
#         self.sock.ensure()
# 
#         pkt = {
#             "action": "PUB",
#             "topic": self.prefix+topic,
#             "data": data,
#             "ts_node":ts
#         }
# 
#         self.sock.send_json(pkt)
# 
# 
    def local_publish(self,topic,msg,ts=None):   
        callbacks = self.subscriptions.get(topic, set())

        print(f"[INFO] [{ts}] [PUB {topic}] : {len(callbacks)} callbacks")

        for c in list(callbacks):
            #if c != origin:
                try:
                    #print('node msg',type(msg))
                    c(topic=topic,msg=msg)
                except Exception as e:
                    callbacks.remove(c)
                    print('msg error',msg)
                    print("Remove from topic",topic,"callback",c,"error")
                    #traceback.print_exc()
                    sys.print_exception(e)


    def subscribe(self, topic,callback ):#topic without prefix
        self.subscriptions.setdefault(topic, set()).add(callback)
        for t in self.transports:
            t.subscribe(topic)

        #self.sock.ensure()

        #pkt = {
        #    "action": "SUB",
        #    "topic": self.prefix+topic,
        #}
        #self.sock.send_json(pkt)
        print(f"[INFO] [] [SUB {callback}] : [{topic}]")

        self.publish(
            "node/new_sub",
            {
           "action": "SUB",
           "topic": self.prefix+topic,
        })
#             {
#                 "topic": topic, 
#                 "origin":self.node_name,
#                 "ts": util.time_float(),
#             }
#        )

    def handle_get_second_ts(self, topic,msg):
        #print('handle_get_second_ts 0',type(msg))
        #msg=json.loads(msg)
        #print('handle_get_second_ts 1',type(msg))

        #print('WatchdogTask.handle_get_second_ts',type(msg),msg.get("first_ts",None))
        t0 = util.time_float()
        #print("ENTER", t0)
       
        self.publish(
            "node/send_second_ts",
            {
                "topic": msg.get("topic"), 
                "first_ts":  msg.get("first_ts"),
                "second_ts": util.time_float(),
                "sended": msg.get("sended")
            }
        )

        t1 = util.time_float()
        #print("EXIT", t1, "elapsed", str(float(t1) - float(t0)))
#     def handle_pub(self, msg):
#         topic = msg['topic']
# 
#         if not topic.startswith(self.prefix):
#             return  # ignore чужое
# 
#         local_topic = topic[len(self.prefix):]
# 
#         #prnt('Node.handle_pub', local_topic)
# 
#         self.local_publish(local_topic, msg['data'])
# 
#     def handle_sub(self,msg):
#         print('Node.handle_sub ignored',msg)

#     def handle_get_second_ts(self, data):
#         msg=json.loads(data)
#         print('WatchdogTask.handle_get_second_ts',type(msg),msg.get("first_ts",None))
#         
#         self.publish(
#             "node/send_second_ts",
#             {
#                 "topic": msg.get("topic"), 
#                 "first_ts":  msg.get("first_ts"),
#                 "second_ts": time_float(),
#             }
#         )
