"""配额管理模块 - 基于流量配额的动态控制"""

import json
import os
from threading import Lock


class QuotaManager:
    """配额管理器 - 监控用户数据使用情况并动态控制流表"""
    
    def __init__(self, logger, flow_manager):
        self.logger = logger
        self.flowManager = flow_manager
        
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
    
    def getDevicesWithQuota(self):
        """获取所有有剩余配额的设备"""
        user_data = self.loadUserData()
        devices_with_quota = []
        
        for room_number, user_info in user_data.get('users', {}).items():
            devices = user_info.get('devices', [])
            quota = user_info.get('quota', 0)
            used = user_info.get('used_traffic', 0)
            
            remaining = quota - used
            if remaining > 0:
                for device_mac in devices:
                    devices_with_quota.append({
                        'mac': device_mac,
                        'room': room_number,
                        'remaining': remaining
                    })
        
        return devices_with_quota
    
    def addQuotaForDevice(self, mac_address, additional_bytes):
        """为设备增加配额（购买流量）"""
        user_data = self.loadUserData()
        
        for room_number, user_info in user_data.get('users', {}).items():
            if mac_address in user_info.get('devices', []):
                current_quota = user_info.get('quota', 0)
                user_info['quota'] = current_quota + additional_bytes
                
                self.saveUserData(user_data)
                self.logger.info("为房间%s设备%s增加配额: +%.1fGB", 
                               room_number, mac_address, additional_bytes / (1024**3))
                
                # 触发流表更新
                self._triggerFlowUpdate()
                return True
        
        return False
    
    def updateUserTraffic(self, mac_address, bytes_count):
        """更新用户流量使用并检查配额状态"""
        user_data = self.loadUserData()
        flow_update_needed = False
        
        for room_number, user_info in user_data.get('users', {}).items():
            if mac_address in user_info.get('devices', []):
                if user_info.get('reset', False):
                    self.logger.info("跳过房间%s设备%s的一次流量更新（刚重置）", room_number, mac_address)
                    user_info['reset'] = False  # ✅ 清除标志
                    self.saveUserData(user_data)
                    return True
                current_used = user_info.get('used_traffic', 0)
                user_info['used_traffic'] = current_used + bytes_count
                
                # 检查配额是否用完
                quota = user_info.get('quota', 0)
                used = user_info.get('used_traffic', 0)
                remaining = quota - used
                
                if remaining <= 0 and remaining + bytes_count > 0:
                    # 配额从有到无，需要更新流表
                    self.logger.warning("⚠️ 房间%s设备%s配额已用完: %.1fGB/%.1fGB", 
                                      room_number, mac_address, 
                                      used / (1024**3), quota / (1024**3))
                    flow_update_needed = True
                self.saveUserData(user_data)
                
                # 如果需要更新流表
                if flow_update_needed:
                    self._triggerFlowUpdate()
                
                return True
        
        return False
    
    def resetDeviceTraffic(self, mac_address):
        """重置设备流量使用"""
        user_data = self.loadUserData()
        
        for room_number, user_info in user_data.get('users', {}).items():
            if mac_address in user_info.get('devices', []):
                user_info['used_traffic'] = 0
                user_info['reset'] = True  # ✅ 设置跳过标志
                self.saveUserData(user_data)
                self.logger.info("重置房间%s设备%s的流量使用", room_number, mac_address)
                return True
        
        return False
    
    def getQuotaStatus(self):
        """获取所有设备的配额状态"""
        user_data = self.loadUserData()
        status = {}
        
        for room_number, user_info in user_data.get('users', {}).items():
            devices = user_info.get('devices', [])
            quota = user_info.get('quota', 0)
            used = user_info.get('used_traffic', 0)
            
            for device_mac in devices:
                status[device_mac] = {
                    'room': room_number,
                    'quota': quota,
                    'used': used,
                    'remaining': quota - used,
                    'has_quota': (quota - used) > 0
                }
        
        return status
    
    def _triggerFlowUpdate(self):
        """触发流表更新"""
        # 这里需要获取当前连接的交换机并更新流表
        # 由于无法直接获取交换机列表，我们记录日志
        self.logger.info("🔄 配额状态变化，需要更新流表")
        # 在实际应用中，这里应该调用flowManager.updateQuotaBasedFlows
        # 但需要通过控制器获取当前连接的交换机
