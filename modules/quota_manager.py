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
