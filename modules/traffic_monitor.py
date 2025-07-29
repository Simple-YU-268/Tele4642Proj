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
    
    def updateTraffic(self, mac, bytesCount):
        """更新设备流量统计并同步到配额系统"""
        user_data = self.loadUserData()
        
        # 更新配额系统的流量使用
        self.quotaManager.updateUserTraffic(mac, bytesCount)
        
        self.logger.debug("Device %s traffic updated: +%d bytes", mac, bytesCount)
    
    def getTraffic(self, mac=None):
        """获取设备流量统计"""
        user_data = self.loadUserData()
        traffic_data = {}
        
        for room_number, user_info in user_data.get('users', {}).items():
            devices = user_info.get('devices', [])
            used_traffic = user_info.get('used_traffic', 0)
            
            for device_mac in devices:
                if mac is None or mac == device_mac:
                    traffic_data[device_mac] = {
                        'total': used_traffic,
                        'daily': used_traffic,  # 简化为总流量
                        'room': room_number
                    }
        
        return traffic_data if mac is None else traffic_data.get(mac, {})
    
    def resetDailyTraffic(self):
        """重置每日流量统计 - 现在重置所有流量使用"""
        user_data = self.loadUserData()
        
        for room_number, user_info in user_data.get('users', {}).items():
            user_info['used_traffic'] = 0
        
        self.saveUserData(user_data)
        self.logger.info("All traffic usage reset")
    
    def getTopUsers(self, limit=10):
        """获取流量使用最多的用户"""
        user_data = self.loadUserData()
        users = []
        
        for room_number, user_info in user_data.get('users', {}).items():
            devices = user_info.get('devices', [])
            used_traffic = user_info.get('used_traffic', 0)
            
            for device_mac in devices:
                users.append((device_mac, used_traffic, room_number))
        
        # 按流量使用量排序
        users.sort(key=lambda x: x[1], reverse=True)
        return users[:limit]
    
    def getQuotaBasedTraffic(self):
        """获取基于配额的流量统计"""
        quota_status = self.quotaManager.getQuotaStatus()
        traffic_data = {}
        
        for mac, quota_info in quota_status.items():
            traffic_data[mac] = {
                'traffic': {
                    'total': quota_info.get('used', 0),
                    'daily': quota_info.get('used', 0)  # 简化为总流量
                },
                'quota': quota_info
            }
        
        return traffic_data