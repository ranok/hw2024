from netfilterqueue import NetfilterQueue
from dataclasses import dataclass
import threading
import logging
from datetime import datetime, timedelta
from scapy.all import *

logger = logging.getLogger(__name__)

@dataclass
class PSDEvent:
    src_ip: str
    timestamp: datetime

class PSD:
    """Port Scan detection module. To get this going, run:
    $ sudo iptables -A INPUT -m psd -j NFQUEUE --queue-num 1
    This needs:
    $ sudo setcap CAP_NET_ADMIN=+eip "$(readlink -f bin/python)"
    to work.
    """
    NF_QUEUE=1

    def __init__(self, event_queue, event_wait=timedelta(minutes=10)):
        self.event_queue = event_queue
        self.last_triggered = None
        self.event_wait = event_wait # Dont trigger until this much time as passed since last notify

    def start(self):
        self.t = threading.Thread(target=self.bind_and_wait)
        self.t.start()


    def process_pkt(self, nf_packet):
        if not self.last_triggered or self.last_triggered < (datetime.now() - self.event_wait):
            self.last_triggered = datetime.now()
            pkt = IP(nf_packet.get_payload())
            src_ip = "Unknown"
            if IP in pkt:
                src_ip = str(pkt[IP].src)

            logger.info(f"Port scan detected from {src_ip}!")
            self.event_queue.put(PSDEvent(src_ip, datetime.now()))
            nf_packet.drop()

    def bind_and_wait(self):
        nfqueue = NetfilterQueue()
        nfqueue.bind(self.NF_QUEUE, self.process_pkt)
        try:
            nfqueue.run()
        except KeyboardInterrupt:
            print('')

        nfqueue.unbind()