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
        self.baseQuota = self.loadUserData()

    
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
                used_traffic = user_info.get('used_traffic', 0)
                vlan_id = user_info.get('vlan_id', None)
                
                if vlan_id:
                    initial_traffic[vlan_id] = {
                        'used_traffic': used_traffic,
                        'room': room_number
                    }
            
            return initial_traffic
        except Exception as e:
            self.logger.error("Error loading initial traffic: %s", str(e))
            return {}
    
    def accumulateFlowStats(self, datapath):
        """请求交换机的所有流量统计（VLAN模式）"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch()  # 请求所有流表统计
        req = parser.OFPFlowStatsRequest(datapath, 0, ofproto.OFPTT_ALL,
                                            ofproto.OFPP_ANY, ofproto.OFPG_ANY,
                                            0, 0, match)
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
        #self.logger.info("Flow Entry:\n%s\n", body)
        self.updateUsedDataFromStats(body)
            
    def processPortStatsReply(self, ev):
        """处理port stats响应事件"""
        body = ev.msg.body
        # 可以在这里处理端口统计信息
        self.logger.debug("Received port stats: %s", body)

    def updateUsedDataFromStats(self, flow_stats_response):
        """根据flow stats响应更新JSON中的used_traffic (VLAN模式)"""
        try:
            self.baseQuota = self.loadUserData()
            for stat in flow_stats_response:
                # 检查是否包含 VLAN 信息
                if 'vlan_vid' in stat.match:
                    vlan_id = stat.match.get('vlan_vid') & 0x0fff  # 取真实 VLAN ID (去掉 OpenFlow 标志位)
                    byte_count = stat.byte_count

                    # 累加流量到 lastTimeUsed
                    if vlan_id in self.lastTimeUsed:
                        current_traffic = self.lastTimeUsed[vlan_id].get('used_traffic', 0)
                        new_traffic = current_traffic + byte_count
                        self.lastTimeUsed[vlan_id]['used_traffic'] = new_traffic

                        # 同步更新到 baseQuota
                        room = self.lastTimeUsed[vlan_id]['room']
                        if room in self.baseQuota.get('users', {}):
                            self.baseQuota['users'][room]['used_traffic'] = new_traffic

            # 写入文件
            self.saveUserData(self.baseQuota)

        except Exception as e:
            self.logger.error("Error updating used_traffic from stats: %s", str(e))

    def saveChangedData(self):
        """根据当前lastTimeUsed中的流量值写入JSON（不再重复叠加）"""
        try:
            self.baseQuota = self.loadUserData()

            for vlan_id, info in self.lastTimeUsed.items():
                room_number = info['room']
                last_used_traffic = info['used_traffic']
                if room_number in self.baseQuota.get('users', {}):
                    self.baseQuota['users'][room_number]['used_traffic'] = last_used_traffic


                self.saveUserData(self.baseQuota)
                self.logger.info("✅ 所有数据保存完毕")

        except Exception as e:
            self.logger.error("Error Saving used_data from stats: %s", str(e))

    def saveUserData(self, data):
        """保存用户数据"""
        try:
            with self.lock:
                with open(self.userDataFile, 'w') as f:
                    json.dump(data, f, indent=2)
        except Exception as e:
            self.logger.error("Error saving user data: %s", str(e))

 