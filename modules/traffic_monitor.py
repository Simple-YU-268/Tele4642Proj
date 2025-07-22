"""流量监控模块 - 基于配额的流量统计"""

import json
import os
import time
from threading import Lock
from collections import defaultdict


class TrafficMonitor:
    """设备流量监控器 - 与配额系统集成"""
    
    def __init__(self, logger, quota_manager):
        self.logger = logger
        self.quotaManager = quota_manager
        self.deviceTraffic = defaultdict(int)
        self.dailyTraffic = defaultdict(int)
        self.lock = Lock()
        self.statsFile = 'traffic_stats.json'
        self.loadTrafficStats()
    
    def loadTrafficStats(self):
        """从文件加载流量统计"""
        try:
            if os.path.exists(self.statsFile):
                with open(self.statsFile, 'r') as f:
                    data = json.load(f)
                    self.deviceTraffic = defaultdict(int, data.get('total', {}))
                    self.dailyTraffic = defaultdict(int, data.get('daily', {}))
        except Exception as e:
            self.logger.error("Error loading traffic stats: %s", str(e))
    
    def saveTrafficStats(self):
        """保存流量统计到文件"""
        try:
            with self.lock:
                with open(self.statsFile, 'w') as f:
                    json.dump({
                        'total': dict(self.deviceTraffic),
                        'daily': dict(self.dailyTraffic),
                        'lastUpdate': time.time()
                    }, f, indent=2)
        except Exception as e:
            self.logger.error("Error saving traffic stats: %s", str(e))
    
    def updateTraffic(self, mac, bytesCount):
        """更新设备流量统计并同步到配额系统"""
        with self.lock:
            self.deviceTraffic[mac] += bytesCount
            self.dailyTraffic[mac] += bytesCount
            
            # 同步更新配额系统的流量使用
            self.quotaManager.updateUserTraffic(mac, bytesCount)
            
            self.logger.debug("Device %s traffic updated: +%d bytes", mac, bytesCount)
            self.saveTrafficStats()
    
    def getTraffic(self, mac=None):
        """获取设备流量统计"""
        with self.lock:
            if mac:
                return {
                    'total': self.deviceTraffic.get(mac, 0),
                    'daily': self.dailyTraffic.get(mac, 0)
                }
            return {
                'total': dict(self.deviceTraffic),
                'daily': dict(self.dailyTraffic)
            }
    
    def resetDailyTraffic(self):
        """重置每日流量统计"""
        with self.lock:
            self.dailyTraffic.clear()
            self.saveTrafficStats()
            self.logger.info("Daily traffic statistics reset")
    
    def getTopUsers(self, limit=10):
        """获取流量使用最多的用户"""
        with self.lock:
            sortedUsers = sorted(self.deviceTraffic.items(), 
                               key=lambda x: x[1], reverse=True)[:limit]
            return sortedUsers
    
    def getQuotaBasedTraffic(self):
        """获取基于配额的流量统计"""
        quota_status = self.quotaManager.getQuotaStatus()
        traffic_data = {}
        
        for mac, quota_info in quota_status.items():
            traffic_data[mac] = {
                'traffic': {
                    'total': self.deviceTraffic.get(mac, 0),
                    'daily': self.dailyTraffic.get(mac, 0)
                },
                'quota': quota_info
            }
        
        return traffic_data
