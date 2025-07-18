"""白名单管理模块"""

import json
import os
from threading import Lock


class WhitelistManager:
    """MAC地址白名单管理器"""
    
    def __init__(self, logger):
        self.logger = logger
        self.whiteList = set()
        self.lock = Lock()
        self.configFile = 'whitelist.json'
        self.loadWhitelist()
    
    def loadWhitelist(self):
        """从文件加载白名单"""
        try:
            if os.path.exists(self.configFile):
                with open(self.configFile, 'r') as f:
                    data = json.load(f)
                    self.whiteList = set(data.get('whitelist', []))
                self.logger.info("Loaded %d MAC addresses from whitelist", len(self.whiteList))
        except Exception as e:
            self.logger.error("Error loading whitelist: %s", str(e))
    
    def saveWhitelist(self):
        """保存白名单到文件"""
        try:
            with self.lock:
                with open(self.configFile, 'w') as f:
                    json.dump({'whitelist': list(self.whiteList)}, f, indent=2)
        except Exception as e:
            self.logger.error("Error saving whitelist: %s", str(e))
    
    def addToWhitelist(self, mac):
        """添加MAC地址到白名单"""
        with self.lock:
            if mac not in self.whiteList:
                self.whiteList.add(mac)
                self.saveWhitelist()
                self.logger.info("Added MAC %s to whitelist", mac)
                return True
            return False
    
    def removeFromWhitelist(self, mac):
        """从白名单中移除MAC地址"""
        with self.lock:
            if mac in self.whiteList:
                self.whiteList.remove(mac)
                self.saveWhitelist()
                self.logger.info("Removed MAC %s from whitelist", mac)
                return True
            return False
    
    def isAllowed(self, mac):
        """检查MAC地址是否在白名单中"""
        return mac in self.whiteList
    
    def getWhitelist(self):
        """获取当前白名单"""
        return list(self.whiteList)
