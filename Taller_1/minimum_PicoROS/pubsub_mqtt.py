import json
from umqtt.simple import MQTTClient

from task import Task
import util


class PubSubMQTT(Task):
    def __init__(self, client_id, broker,  scheduler, node,port=1883, period_ms=100 , 
                 prefix="UDFJC/emb1/robot0/"):
        super().__init__(scheduler, period_ms)
        #self.host = host
        #self.port = port
        self.node = node
        self.prefix = prefix

        self.client = MQTTClient(client_id=client_id, server=broker, port=port)
        self.client.set_callback(self.handle_pub)
        self.client.connect()

        node.add_transport(self)

    def publish(self, topic, data):
        if isinstance(data, dict):
            data=json.dumps(data)
        else:
            print(f"PubSubMQTT.publish {topic} no JSON, type: {type(data)}")
        self.client.publish(
            (self.prefix + topic).encode(),
            data
        )
#         ts = util.time_float()
# 
#         # Keep the timestamp if you need it
#         if isinstance(data, dict):
#             payload = dict(data)
#             payload.setdefault("ts_node", ts)
#         else:
#             payload = data
# 
#         self.client.publish(
#             (self.prefix + topic).encode(),
#             util.to_json(payload).encode()
#         )

    def subscribe(self, topic):
        self.client.subscribe(
            (self.prefix + topic).encode()
        )
        #print(f"[INFOPubSubMQTT] [SUB] [{topic}]")

    def update(self):
        """Call periodically from the main loop."""
        #self.client.check_msg()
        n = 0
        while True:
            op = self.client.check_msg()
            if op is None:
                break
            n += 1
        if n:
            print("MQTT.update processed", n, "MQTT packets")

    def handle_pub(self, topic, payload):

        topic = topic.decode()

        if not topic.startswith(self.prefix):
            return

        local_topic = topic[len(self.prefix):]

        try:
            # 1. Decode bytes payload into a string
            msg_str = payload.decode('utf-8')
            
            # 2. Parse the string into a Python dictionary
            data = json.loads(msg_str)
            #data = util.from_json(payload.decode())
        except Exception:
            print(f"PubSubMQTT.handle_pub {local_topic} no JSON, len: {len(payload)}")

            data = payload

        self.node.local_publish(local_topic, data)