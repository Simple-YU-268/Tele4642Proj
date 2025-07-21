"""配额管理模块 - 数据使用完切断联网"""

import json
import os
from threading import Lock


class QuotaManager:
    """配额管理器 - 监控用户数据使用情况并控制网络访问"""
    
    def __init__(self, logger, flow_manager, whitelist_manager):
        self.logger = logger
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
    
    def getUserTraffic(self, mac_address):
        """从user_data.json获取用户的流量使用情况"""
        user_data = self.loadUserData()
        
        for room_number, user_info in user_data.get('users', {}).items():
            if mac_address in user_info.get('devices', []):
                return {
                    'room_number': room_number,
                    'quota': user_info.get('quota', 0),
                    'used': user_info.get('used_traffic', 0)
                }
        
        return None
    
    def updateUserTraffic(self, mac_address, bytes_count):
        """更新用户在user_data.json中的流量使用"""
        user_data = self.loadUserData()
        
        for room_number, user_info in user_data.get('users', {}).items():
            if mac_address in user_info.get('devices', []):
                current_used = user_info.get('used_traffic', 0)
                user_info['used_traffic'] = current_used + bytes_count
                
                self.saveUserData(user_data)
                self.logger.debug("Updated user %s traffic: +%d bytes (total: %d)", 
                                room_number, bytes_count, user_info['used_traffic'])
                return True
        
        return False
    
    def checkUserQuota(self, mac_address):
        """检查用户配额是否已用完"""
        user_info = self.getUserTraffic(mac_address)
        if not user_info:
            return True  # 未找到用户，允许访问
        
        quota = user_info['quota']
        used = user_info['used']
        
        self.logger.debug("User %s: quota=%d, used=%d", 
                        user_info['room_number'], quota, used)
        
        if quota > 0 and used >= quota:
            self.logger.warning("User %s quota exceeded: %d/%d bytes", 
                              user_info['room_number'], used, quota)
            return False  # 配额已用完
        
        return True  # 配额未用完
    
    def blockUser(self, datapath, mac_address):
        """阻止用户网络访问（同时阻止上行和下行流量）"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        # 阻止上行流量（该MAC作为源地址）
        match_up = parser.OFPMatch(eth_src=mac_address)
        actions = []  # 空动作表示丢弃
        self.flowManager.addFlow(datapath, 1000, match_up, actions)
        
        # 阻止下行流量（该MAC作为目的地址）
        match_down = parser.OFPMatch(eth_dst=mac_address)
        self.flowManager.addFlow(datapath, 1000, match_down, actions)
        
        # 从白名单中移除
        self.whitelistManager.removeFromWhitelist(mac_address)
        
        self.logger.info("Blocked user with MAC: %s (both uplink and downlink)", mac_address)

    def unblockUser(self, datapath, mac_address):
        """解除用户网络访问限制（删除之前设置的drop流表）"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        # 删除阻止上行流量的流表项
        match_up = parser.OFPMatch(eth_src=mac_address)
        self.flowManager.deleteFlow(datapath, 1000, match_up)
        
        # 删除阻止下行流量的流表项
        match_down = parser.OFPMatch(eth_dst=mac_address)
        self.flowManager.deleteFlow(datapath, 1000, match_down)
        
        # 重新添加到白名单
        self.whitelistManager.addToWhitelist(mac_address)
        
        self.logger.info("Unblocked user with MAC: %s (removed drop flows)", mac_address)
    
    def monitorQuotaUsage(self, datapath, mac_address, bytes_count):
        """监控用户配额使用情况"""
        # 更新流量使用
        self.updateUserTraffic(mac_address, bytes_count)
        
        # 检查配额
        if not self.checkUserQuota(mac_address):
            self.blockUser(datapath, mac_address)
            return False
        return True
    
    def getUserQuotaInfo(self, mac_address):
        """获取用户配额信息"""
        return self.getUserTraffic(mac_address)
    
    def resetUserTraffic(self, mac_address):
        """重置用户流量使用（用于测试或新周期）"""
        user_data = self.loadUserData()
        
        for room_number, user_info in user_data.get('users', {}).items():
            if mac_address in user_info.get('devices', []):
                user_info['used_traffic'] = 0
                self.saveUserData(user_data)
                self.logger.info("Reset traffic for user %s", room_number)
                return True
        
        return False
