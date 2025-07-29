"""流量监控模块 - 基于配额的流量统计，仅使用user_data.json"""

import json
import os
import time
from threading import Lock
from collections import defaultdict







class TrafficMonitor:
    """设备流量监控器 - 与配额系统集成，流量数据存储在user_data.json中"""
    

    def __init__(self, logger, quota_manager):
        self.logger = logger
        self.quotaManager = quota_manager
        self.userDataFile = 'user_data.json'
        self.lock = Lock()
        self.lastTimeUsed = self._loadInitialTraffic()  # 程序运行期间不变的变量
    
    def loadUserData(self):
        """加载用户数据"""
        try:
            if os.path.exists(self.userDataFile):
                with open(self.userDataFile, 'r') as f:
                    return json.load(f)
            return {"users": {}, "sessions": {}}
        except Exception as e:
            self.logger.error("Error loading user data: %s", str(e))
            return {"users": {}, "sessions": {}}

    def _loadInitialTraffic(self):
        """程序启动时加载初始流量数据到lastTimeUsed变量（运行期间不变）"""
        try:
            user_data = self.loadUserData()
            initial_traffic = {}
            
            for room_number, user_info in user_data.get('users', {}).items():
                devices = user_info.get('devices', [])
                used_traffic = user_info.get('used_traffic', 0)
                
                for device_mac in devices:
                    initial_traffic[device_mac] = {
                        'used_traffic': used_traffic,
                        'room': room_number
                    }
            
            return initial_traffic
        except Exception as e:
            self.logger.error("Error loading initial traffic: %s", str(e))
            return {}
    
    def accumulateFlowStats(self, datapath, mac_address):
        """使用OpenFlow协议读取设备流量统计并累加到lastTimeUsed"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        # 创建flow stats请求
        match = parser.OFPMatch(eth_src=mac_address)
        req = parser.OFPFlowStatsRequest(datapath, 0, ofproto.OFPTT_ALL,
                                       ofproto.OFPP_ANY, ofproto.OFPG_ANY,
                                       0, 0, match)
        
        # 发送请求并处理响应
        datapath.send_msg(req)
        
    def accumulatePortStats(self, datapath, port_no):
        """使用OpenFlow协议读取端口流量统计"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        # 创建port stats请求
        req = parser.OFPPortStatsRequest(datapath, 0, port_no)
        datapath.send_msg(req)

    def processFlowStatsReply(self, ev):
        """处理flow stats响应事件"""
        body = ev.msg.body
        self.updateUsedDataFromStats(body)
    
    def processPortStatsReply(self, ev):
        """处理port stats响应事件"""
        body = ev.msg.body
        # 可以在这里处理端口统计信息
        self.logger.debug("Received port stats: %s", body)

    def updateUsedDataFromStats(self, flow_stats_response):
        """根据flow stats响应更新JSON中的used_data"""
        try:
            user_data = self.loadUserData()
            
            for stat in flow_stats_response:
                if 'eth_src' in stat.match:
                    mac_address = stat.match['eth_src']
                    packet_count = stat.packet_count
                    byte_count = stat.byte_count
                    
                    # 累加流量到lastTimeUsed
                    if mac_address in self.lastTimeUsed:
                        current_traffic = self.lastTimeUsed[mac_address]['used_traffic']
                        new_traffic = current_traffic + byte_count
                        
                        # 更新对应房间的used_traffic
                        room_number = self.lastTimeUsed[mac_address]['room']
                        if room_number in user_data.get('users', {}):
                            user_data['users'][room_number]['used_traffic'] = new_traffic
            
            # 保存更新后的数据
            self.saveUserData(user_data)
            self.logger.info("Updated used_data from flow statistics")
            
        except Exception as e:
            self.logger.error("Error updating used_data from stats: %s", str(e))
    
    def saveUserData(self, data):
        """保存用户数据"""
        try:
            with self.lock:
                with open(self.userDataFile, 'w') as f:
                    json.dump(data, f, indent=2)
        except Exception as e:
            self.logger.error("Error saving user data: %s", str(e))

 