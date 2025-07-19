"""配额管理模块 - 数据使用完切断联网"""

import json
import os
from threading import Lock


class QuotaManager:
    """配额管理器 - 监控用户数据使用情况并控制网络访问"""
    
    def __init__(self, logger, traffic_monitor, flow_manager, whitelist_manager):
        self.logger = logger
        self.trafficMonitor = traffic_monitor
        self.flowManager = flow_manager
        self.whitelistManager = whitelist_manager
        
        self.userDataFile = 'user_data.json'
        self.lock = Lock()
        
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
    
    def saveUserData(self, data):
        """保存用户数据"""
        try:
            with self.lock:
                with open(self.userDataFile, 'w') as f:
                    json.dump(data, f, indent=2)
        except Exception as e:
            self.logger.error("Error saving user data: %s", str(e))
    
    def checkUserQuota(self, mac_address):
        """检查用户配额是否已用完"""
        user_data = self.loadUserData()
        
        # 查找MAC地址对应的用户
        for room_number, user_info in user_data.get('users', {}).items():
            if mac_address in user_info.get('devices', []):
                used_traffic = self.trafficMonitor.getTraffic(mac_address)
                total_used = used_traffic.get('total', 0)
                quota = user_info.get('quota', 0)
                
                self.logger.debug("User %s: quota=%d, used=%d", room_number, quota, total_used)
                
                if quota > 0 and total_used >= quota:
                    self.logger.warning("User %s quota exceeded: %d/%d bytes", 
                                      room_number, total_used, quota)
                    return False  # 配额已用完
                
                return True  # 配额未用完
        
        return True  # 未找到用户，允许访问
    
    def blockUser(self, datapath, mac_address):
        """阻止用户网络访问"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        # 添加阻止该MAC地址的流表项
        match = parser.OFPMatch(eth_src=mac_address)
        actions = []  # 空动作表示丢弃
        
        # 高优先级阻止流表
        self.flowManager.addFlow(datapath, 1000, match, actions)
        
        # 从白名单中移除
        self.whitelistManager.removeFromWhitelist(mac_address)
        
        self.logger.info("Blocked user with MAC: %s", mac_address)
    
    def monitorQuotaUsage(self, datapath, mac_address):
        """监控用户配额使用情况"""
        if not self.checkUserQuota(mac_address):
            self.blockUser(datapath, mac_address)
            return False
        return True
    
    def getUserQuotaInfo(self, mac_address):
        """获取用户配额信息"""
        user_data = self.loadUserData()
        
        for room_number, user_info in user_data.get('users', {}).items():
            if mac_address in user_info.get('devices', []):
                used_traffic = self.trafficMonitor.getTraffic(mac_address)
                return {
                    'room_number': room_number,
                    'quota': user_info.get('quota', 0),
                    'used': used_traffic.get('total', 0),
                    'remaining': max(0, user_info.get('quota', 0) - used_traffic.get('total', 0))
                }
        
        return None
