"""Flow table Manager - Default DROP, dynamically issue permission flow tables based on quotas"""
from ryu.lib.packet import packet, ethernet, ether_types
from ryu.ofproto import ofproto_v1_3
from ryu.ofproto.ofproto_v1_3 import OFPP_FLOOD
from ryu.ofproto.ofproto_v1_3 import OFPP_ALL

from collections import defaultdict


class FlowManager:
    """Flow table Manager - Default DROP, dynamically issue permission flow tables based on quotas"""
    
    def __init__(self, logger):
        self.logger = logger
        self.macToPort = defaultdict(dict)
        self.router_mac = "00:00:00:00:00:AA"
    
    # ================================================================================
    # install basic flow
    # ================================================================================
    
    def installDefaultFlows(self, datapath):
        """install basic flow"""
        self.logger.info("basic flow install start...")
        
        # 1. install default flowtable（table-miss + ARP）
        self._installTableMissFlow(datapath)
        self._installArpFlows(datapath)
        
        self.logger.info("finish default flowtable")
    
    def _installTableMissFlow(self, datapath):
        """table-miss：drop all"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        # (0) Table-miss: drop everything else
        match = parser.OFPMatch()
        actions = []  # [] means drop
        
        self.logger.info("install table-miss DROP: switch=%016x", datapath.id)
        self.addFlow(datapath, 0, match, actions)
    
    def _installArpFlows(self, datapath):
        """ARP flow"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
              
        # (1) Allow all ARP traffic
        match = parser.OFPMatch(eth_type=0x0806)
        actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
        
        self.logger.info("install ARP flow: switch=%016x", datapath.id)
        self.addFlow(datapath, 1, match, actions)
    
    # ================================================================================
    # Quota based flow manage
    # ================================================================================
    
    def updateQuotaBasedFlows(self, datapath, quotaManager):
        """update quota based flow"""
        self.logger.info("start update quota based flow...")
        
        # 1. drop current quota based flow (retain basic flow)
        self._clearQuotaFlows(datapath)
        
        user_data = quotaManager.loadUserData()
        users = user_data.get('users', {})

        permit_count = 0
        for room_number, user_info in users.items():
            devices = user_info.get('devices', [])
            quota = user_info.get('quota', 0)
            used = user_info.get('used_traffic', 0)
            
            remaining = quota - used
            
            if remaining > 0:
                for device_mac in devices:
                    self._installDevicePermitFlows(datapath, device_mac)
                    permit_count += 1
                    self.logger.info(" room %s device %s: ramain %.1fGB", 
                                   room_number, device_mac, remaining / (1024**3))
        
        self.logger.info("finish update quota based flow: %d devices gain access", permit_count)
    
    def _installDevicePermitFlows(self, datapath, device_mac):
        """Install the quota permit flow table for the specified equipment - only IP"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        device_port = self._getDevicePort(device_mac)
        router_port = 1 
        
        # Priority hierarchy (from high to low) :
        # 400:  Device-Router bidirectional IP (including ICMP, quota permission)
        # 1:    ARP (The basic flow table has been processed)
        # 0:    table-miss drop (The basic flow table has been processed)
        # 10:   General ARP Permission (the basic flow table has been processed)
        match_anyarp = parser.OFPMatch(eth_type=0x0806)
        actions_anyarp = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
        self.addFlow(datapath, 10, match_anyarp, actions_anyarp)

        # 400: IP from the device to the router (including ICMP, quota permission)
        match_h_r = parser.OFPMatch(
            eth_src=device_mac, 
            eth_dst=self.router_mac, 
            eth_type=0x0800  # IPv4
        )
        actions_h_r = [parser.OFPActionOutput(router_port)]
        self.addFlow(datapath, 400, match_h_r, actions_h_r)

        # 400: The IP address from the router to the device (including ICMP and quota permission)
        match_r_h = parser.OFPMatch(
            eth_src=self.router_mac,
            eth_dst=device_mac,
            eth_type=0x0800  # IPv4
        )
        actions_r_h = [parser.OFPActionOutput(device_port)]
        self.addFlow(datapath, 400, match_r_h, actions_r_h)
        self.logger.info("install quota permit flow: device=%s, port=%d", device_mac, device_port)
    def _clearQuotaFlows(self, datapath):
        """clear all quota based flow (retain basic flow)"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        # Delete the flow table with priority 400 (retain the base flow table with priority 0-1)
        match_any = parser.OFPMatch()
        mod = parser.OFPFlowMod(
            datapath=datapath,
            command=ofproto.OFPFC_DELETE,
            priority=400,
            match=match_any,
            out_port=ofproto.OFPP_ANY,
            out_group=ofproto.OFPG_ANY
        )
        datapath.send_msg(mod)
        
        self.logger.info("clear all quota based flow")
     
    # ================================================================================
    # Methods
    # ================================================================================
    
    def addFlow(self, datapath, priority, match, actions, bufferId=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        if actions: 
            inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
            action_str = str(actions)
        else:  # DROP
            inst = []
            action_str = "DROP"
        
        if bufferId:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=bufferId,
                                    priority=priority, match=match, instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst)
        
        # Record the installation information of the flow table in detail
        self.logger.info("=" * 60)
        self.logger.info("install flow information:")
        self.logger.info("switch: %016x", datapath.id)
        self.logger.info("priority: %d", priority)
        self.logger.info("match: %s", match)
        self.logger.info("action: %s", action_str)
        self.logger.info("bufferId: %s", bufferId if bufferId else "None")
        self.logger.info("=" * 60)
        
        datapath.send_msg(mod)
    
    def deleteFlow(self, datapath, priority, match):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        mod = parser.OFPFlowMod(
            datapath=datapath,
            command=ofproto.OFPFC_DELETE,
            priority=priority,
            match=match,
            out_port=ofproto.OFPP_ANY,
            out_group=ofproto.OFPG_ANY
        )
        
        datapath.send_msg(mod)
        self.logger.info("delete flow: priority=%d, match=%s", priority, match)
    
    def _getDevicePort(self, device_mac):
        """mac <--> port"""
        port_mapping = {
            "00:00:00:00:00:01": 2,  # h1 -> s1-eth2
            "00:00:00:00:00:02": 3,  # h2 -> s1-eth3
            "00:00:00:00:00:03": 4,  # h3 -> s1-eth4
            "00:00:00:00:00:0a": 5,  # h4 -> s1-eth5
            "00:00:00:00:00:0b": 6,  # h5 -> s1-eth6
            "00:00:00:00:00:0c": 7,  # h6 -> s1-eth7
            "00:00:00:00:00:15": 8,  # h7 -> s1-eth8
            "00:00:00:00:00:16": 9,  # h8 -> s1-eth9
            "00:00:00:00:00:17": 10, # h9 -> s1-eth10
            "00:00:00:00:00:AA": 1   # router -> s1-eth1
        }
        return port_mapping.get(device_mac, ofproto_v1_3.OFPP_FLOOD)
    
