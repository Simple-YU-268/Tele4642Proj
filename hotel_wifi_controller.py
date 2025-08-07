#!/usr/bin/env python3
"""
Hotel WiFi Network Controller - Dynamic Flow Control Based on Traffic Quota
Modular Version: Default DROP all traffic, dynamically install flow rules based on quota
"""

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.app.wsgi import WSGIApplication
from ryu.lib.packet import packet, ethernet, ipv4, arp
from ryu.lib import hub

from modules.flow_manager import FlowManager
from modules.quota_manager import QuotaManager
from modules.traffic_monitor import TrafficMonitor
from modules.api_controller import APIController
from threading import Event

class HotelWifiController(app_manager.RyuApp):
    """Main Controller Class - Dynamic Flow Control Based on Quota"""
    
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {'wsgi': WSGIApplication}

    def __init__(self, *args, **kwargs):
        super(HotelWifiController, self).__init__(*args, **kwargs)
        
        # Initialize modular components
        self.flowManager = FlowManager(self.logger)
        self.quotaManager = QuotaManager(self.logger, self.flowManager)
        self.trafficMonitor = TrafficMonitor(self.logger, self.quotaManager)
        
        # Register the API controller
        wsgi = kwargs['wsgi']
        wsgi.register(APIController, {
            'quotaManager': self.quotaManager,
            'trafficMonitor': self.trafficMonitor,
            'controller': self
        })
        
        # Store currently connected datapaths (switches)
        self.datapaths = {}
        # Semaphore, indicating the completion of flow statistics
        self.monitor_done = Event()  
        # Start periodic traffic monitoring task
        self.logger.info("Start periodic traffic monitoring task")
        self.threads.append(hub.spawn(self._periodic_traffic_monitor))

        # Start periodic quota update task
        self.logger.info("Start periodic quota update task")
        self.threads.append(hub.spawn(self._periodic_quota_update))

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switchFeaturesHandler(self, ev):
        """Initialize switch connect - default: Drop all"""
        datapath = ev.msg.datapath
        
        self.logger.info("=" * 60)
        self.logger.info("Initialize switch: %016x", datapath.id)
        
        # install basic flow - table-miss + ARP
        self.flowManager.installDefaultFlows(datapath)
        self.logger.info("install basic flow - table-miss + ARP")
        
        # send flow based on quota
        self.flowManager.updateQuotaBasedFlows(datapath, self.quotaManager)
        
        self.logger.info("initialization completed - default DROP, quota permission")
        self.logger.info("=" * 60)
        
        # record sw connection
        self.datapaths[datapath.id] = datapath

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packetInHandler(self, ev):
        """Data packet process - only record traffic, not handle forwarding"""
        msg = ev.msg
        datapath = msg.datapath
        
        # Parsing Data Packets
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]
        
        srcMac = eth.src
        dstMac = eth.dst
        inPort = msg.match['in_port']
        packet_len = len(msg.data)
        
        # only record traffic
        packet_type = "UNKNOWN"
        
        if eth.ethertype == 0x0806:
            packet_type = "ARP"
        elif eth.ethertype == 0x0800:
            packet_type = "IPv4"
        elif eth.ethertype == 0x86DD:
            packet_type = "IPv6"
        else:
            packet_type = f"OTHER(0x{eth.ethertype:04x})"
        
        self.logger.info("=" * 80)
        self.logger.info("PACKET-IN monitor record:")
        self.logger.info("switches: %016x", datapath.id)
        self.logger.info("src_MAC: %s", srcMac)
        self.logger.info("dst_MAC: %s", dstMac)
        self.logger.info("inPort: %d", inPort)
        self.logger.info("packet_len: %d字节", packet_len)
        self.logger.info("packet_type: %s", packet_type)
        
        # if packet_type is IPv4，show IP information
        if eth.ethertype == 0x0800:
            ip_pkt = pkt.get_protocol(ipv4.ipv4)
            if ip_pkt:
                self.logger.info("ip_pkt.src: %s", ip_pkt.src)
                self.logger.info("ip_pkt.dst: %s", ip_pkt.dst)
                self.logger.info("ip_pkt.proto: %s", ip_pkt.proto)
        
        self.logger.info("traffic has been recorded")
        self.logger.info("=" * 80)

    def _periodic_traffic_monitor(self):
        """traffic_monitor Once per second - request flow/port counter"""
        while True:
            hub.sleep(0.11)  # Once per 0.11 second
            # if datapaths = {}, Skip the current loop and re-enter the next loop
            if not self.datapaths:  
                continue
                
            self.logger.info("=" * 60)
            self.logger.info("Start periodic traffic monitor")
            
            # Iterate through each dpid to send the request
            for dpid, datapath in self.datapaths.items():
                try:
                    self.logger.info("request of FlowStats of switch %016x", dpid)
                    self.trafficMonitor.accumulateFlowStats(datapath)
                except Exception as e:
                    self.logger.error("! Flowrequest failed: %s", str(e))
            self.monitor_done.set()  # quota update can continue       
            self.logger.info("Finish periodic traffic monitor")
            self.logger.info("=" * 60)

    def _periodic_quota_update(self):
        """quota_update Once per 5s"""
        while True:
            self.monitor_done.wait()  # waiting for monitor
            hub.sleep(1.71)  # Once per 1.71 seconds
            if not self.datapaths:
                continue
            self.logger.info("=" * 60)
            self.logger.info("Start periodic quota update")
            self.trafficMonitor.saveChangedData()
            
            # update quota_based_flow based on dpid
            for dpid, datapath in self.datapaths.items():
                try:
                    self.logger.info("update quota_based_flow of sw %016x", dpid)
                    self.flowManager.updateQuotaBasedFlows(datapath, self.quotaManager)
                    self.logger.info("update flow of sw %016x successful! ", dpid)
                except Exception as e:
                    self.logger.error("update flow of sw %016x faild: %s", dpid, str(e))
            self.monitor_done.clear()  # clear event，next time should wait again
            self.logger.info("=" * 60)
            self.logger.info("Finish periodic quota update")
            self.logger.info("=" * 60)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def flowStatsReplyHandler(self, ev):
        """process flow stats reply"""
        self.trafficMonitor.processFlowStatsReply(ev)

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def portStatsReplyHandler(self, ev):
        """process port stats reply"""
        self.trafficMonitor.processPortStatsReply(ev)
