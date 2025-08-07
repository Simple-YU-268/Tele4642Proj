"""Traffic Monitoring - Quota-based traffic tracking using user_data.json"""

import json
import os
import time
from threading import RLock
from collections import defaultdict


class TrafficMonitor:
    """Device traffic monitor - works with quota system and stores data in user_data.json"""
    

    def __init__(self, logger, quota_manager):
        self.logger = logger
        self.quotaManager = quota_manager
        self.userDataFile = 'user_data.json'
        self.lock = RLock()
        self.lastTimeUsed = self._loadInitialTraffic() # Cached traffic data loaded at startup
    
    def loadUserData(self):
        """Load user data from JSON file"""
        try:
            if os.path.exists(self.userDataFile):
                with open(self.userDataFile, 'r') as f:
                    return json.load(f)
            return {"users": {}, "sessions": {}}
        except Exception as e:
            self.logger.error("Error loading user data: %s", str(e))
            return {"users": {}, "sessions": {}}

    def _loadInitialTraffic(self):
        """Load initial traffic data into lastTimeUsed at startup"""
        try:
            user_data = self.loadUserData()
            initial_traffic = {}
            for room_number, user_info in user_data.get('users', {}).items():
                devices = user_info.get('devices', [])
                used_traffic = user_info.get('used_traffic', 0)
                
                for device_mac in devices:
                    initial_traffic[device_mac] = {
                        'used_traffic': used_traffic,
                        'room': room_number,
                        'reset_flag': False
                    }
            
            return initial_traffic
        except Exception as e:
            self.logger.error("Error loading initial traffic: %s", str(e))
            return {}
    
    def accumulateFlowStats(self, datapath):
        """Send a request(get flow counter) according to the OpenFlow protocol"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        for mac_address in self.lastTimeUsed.keys():
            match = parser.OFPMatch()
            req = parser.OFPFlowStatsRequest(datapath, 0, ofproto.OFPTT_ALL,
                                        ofproto.OFPP_ANY, ofproto.OFPG_ANY,
                                        0, 0, match)
            datapath.send_msg(req)
        
    def accumulatePortStats(self, datapath, port_no):
        """Send OpenFlow port stats request to the switch"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        req = parser.OFPPortStatsRequest(datapath, 0, port_no)
        datapath.send_msg(req)

    def processFlowStatsReply(self, ev):
        """Handle the flow stats reply event"""
        body = ev.msg.body
        self.updateUsedDataFromStats(body)
            
    def processPortStatsReply(self, ev):
        """Handle the port stats reply event"""
        body = ev.msg.body
        self.logger.debug("Received port stats: %s", body)

    def updateUsedDataFromStats(self, flow_stats_response):
        """Update used traffic data from flow stats response"""
        with self.lock:
            try:
                user_data = self.loadUserData()
                for stat in flow_stats_response:
                    # get src/dst MAC
                    mac_dst = stat.match.get('eth_dst')
                    mac_src = stat.match.get('eth_src')
                    byte_count = stat.byte_count
                    
                    for room, info in user_data.get('users', {}).items():
                        devices = info.get('devices', [])
                        matched_mac = None
                        if mac_dst in devices:
                            matched_mac = mac_dst
                        elif mac_src in devices:
                            matched_mac = mac_src
                        if matched_mac:
                            current_traffic = info.get('used_traffic', 0)
                            new_traffic = current_traffic + byte_count
                            self.logger.info("byte_count:\n%s\n", byte_count)
                            self.lastTimeUsed[matched_mac]['used_traffic'] = new_traffic
                            break
            except Exception as e:
                self.logger.error("Error updating used_data from stats: %s", str(e))

    def saveChangedData(self):
        """Save current used traffic (from lastTimeUsed) into JSON file"""
        with self.lock:
            try:
                user_data = self.loadUserData()
                for mac_address, info in self.lastTimeUsed.items():
                    room_number = info['room']
                    reset_flag = user_data['users'][room_number].get('reset_flag', False)
                    if reset_flag is True:
                        last_used_traffic = 0
                        info['used_traffic'] = 0   # Also reset traffic in lastTimeUsed
                        user_data['users'][room_number]['reset_flag'] = False
                    else:
                        last_used_traffic = info['used_traffic']
                    if room_number in user_data.get('users', {}):
                        user_data['users'][room_number]['used_traffic'] = last_used_traffic
                self.saveUserData(user_data)
                self.logger.info("All traffic data saved successfully")

            except Exception as e:
                self.logger.error("Error Saving used_data from stats: %s", str(e))

    def saveUserData(self, data):
        """Write user data to JSON file (thread-safe)"""
        try:
            with self.lock:
                with open(self.userDataFile, 'w') as f:
                    json.dump(data, f, indent=2)
        except Exception as e:
            self.logger.error("Error saving user data: %s", str(e))

 