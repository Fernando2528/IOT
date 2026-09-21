import rp2
from machine import Pin

from task import Task

class IrReader(Task):

    END = 0
    
    @rp2.asm_pio(set_init=rp2.PIO.OUT_LOW)
    def count1():

        # =====================================================
        # Y = on threshold
        # =====================================================

        pull(block)
        mov(y, osr)

        # =====================================================
        # Estado inicial
        # =====================================================

        jmp(pin, "on_off")

        # =====================================================
        # on
        # =====================================================

        label("off_on")

        mov(x, y)

        label("on_LOOP")

        # -----------------------------------------------------
        # Decrementamos X
        # -----------------------------------------------------

        jmp(x_dec, "on_DUMMY") #1

        
        # -----------------------------------------------------
        # Permanecemos en on hasta que aparezca off
        # -----------------------------------------------------

        label("on_SLEEP")

        jmp(pin, "on_off")
        jmp("on_SLEEP")


        # -----------------------------------------------------
        # on todavía no terminó
        # -----------------------------------------------------

        label("on_DUMMY") 

        # ¿Terminó on porque apareció off?
        jmp(pin, "on_END") #2

        # Padding
        nop()[6]           #3

        jmp("on_LOOP")     #4


        # -----------------------------------------------------
        # on ya terminó
        # -----------------------------------------------------

        label("on_END")

        mov(isr, invert(x))#
        push(noblock)
        irq(rel(0))

        jmp("on_off")


        # =====================================================
        # on → off
        # =====================================================

        label("on_off")

        # X = 0xFFFFFFFF
        mov(x, y)


        # =====================================================
        # off
        # =====================================================

        label("off_LOOP")

        # Mientras siga off seguimos contando
        jmp(x_dec, "off_DUMMY") #1

        mov(isr, null)
        push(noblock)
        irq(rel(0))

        # Si pasa on_THRESHOLD_US esperamos el cero

        label("off_SLEEP")
        jmp(pin,"off_SLEEP")
        jmp("off_on")

        label("off_DUMMY")

        nop()[7]             #2

        # ¿Seguimos off?
        jmp(pin, "off_LOOP")  #3


        # -----------------------------------------------------
        # off → on
        #
        # X contiene el contador restante.
        # Lo enviamos directamente.
        #
        # Al interpretarlo como signed32 será negativo,
        # por lo que Python puede distinguirlo de off.
        # -----------------------------------------------------

        mov(isr, x)#
        push(noblock)
        irq(rel(0))
        jmp("off_on")
        

    def __init__(
        self,
        scheduler,
        pubsub,
        pin_ir,
        sm=0,
        off0_threshold_us=1100,
        off1_threshold_us=3000,
        on_threshold_us=20000,
        pio_freq=10_000_000,
    ):
        """
        IR receiver driver.

        PIO events:

            positive  -> ON duration
            negative  -> OFF duration
            0         -> END OF FRAME

        The code is constructed using only OFF durations.

        OFF < off0_threshold_us
            -> bit 0

        OFF >= off0_threshold_us
            -> bit 1
        """
        self.pubsub=pubsub
        super().__init__(scheduler, period_ms=100)
        self.new_code = False

        self.off0_threshold_us = off0_threshold_us
        self.off1_threshold_us = off1_threshold_us
        self.on_threshold_us = on_threshold_us

        self.code = 0
        self.n_bits = 0

        self.sm = rp2.StateMachine(
            sm,
            self.count1,
            freq=pio_freq,
            jmp_pin=Pin(pin_ir, Pin.IN, Pin.PULL_UP)
        )
        self.sm.irq(handler=self._irq_handler)

        self.sm.active(1)

        # Threshold used by the PIO to detect END.
        self.sm.put(on_threshold_us)


    def _irq_handler(self, sm):

        while sm.rx_fifo():

            raw = sm.get()

            if raw == 0:
                # END
                self.last_code = self.code
                self.last_bits = self.n_bits

                self.code = 0
                self.n_bits = 0

                self.new_code = True
                continue

            elif raw & 0x8000_0000:
                continue
            else:
                value = self.on_threshold_us-raw
                if 0<value < self.off0_threshold_us:
                    bit = 0

                elif value < self.off1_threshold_us:
                    bit = 1
                else:
                    print('IrReader._irq_handler Valor fuera de rango',raw,value,self.code,self.n_bits)
                    continue
                
                self.code = (self.code << 1) | bit
                self.n_bits += 1
             
                
 
            
    def update(self):
        #print('.',end='')

        if not self.new_code:
            return

        code = self.last_code
        bits = self.last_bits

        self.new_code = False

        # Publicar aquí
        self.pubsub.publish("ir_reader/value",code)
        print(code)

# ####################
# from scheduler import Scheduler
# from node import Node
# from driver.IrReader import IrReader
# 
# 
# class MainApp:
#     def __init__(self,ssid,password,host,port):
# 
#         self.scheduler = Scheduler()
#         print('Scheduler')
#         self.pubsub = Node(prefix='UDFJC/emb1/robot0/',node_name='emb_node')
#         self.ir = IrReader(
#             scheduler=self.scheduler,
#             pubsub=self.pubsub,
#             pin_ir=22,
#         )
#         self.pubsub.subscribe("ir_reader/value",self.handle_ir_reader_value )
#         
#     def handle_ir_reader_value(self, topic, msg):
#         print("handle_ir_reader_value",msg)
# 
#     def run(self):
#         self.scheduler.run()
# 
# 
# # =========================================================
# # ENTRY POINT
# # =========================================================
# 
# ssid="PEREZ"
# password_file=".env"
# host="192.168.1.17"
# port=5051
# 
# with open(password_file) as f:
#     password = f.read().strip()
# 
# app = MainApp(ssid=ssid,password =password,host=host,port=port)
# app.run()        
#         