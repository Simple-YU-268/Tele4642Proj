"""Quota Management Module - Dynamic control based on traffic quota"""

import json
import os
from threading import Lock


class QuotaManager:
    """Manages user quotas and controls flow rules dynamically"""
    
    def __init__(self, logger, flow_manager):
        self.logger = logger
        self.flowManager = flow_manager
        
        self.userDataFile = 'user_data.json'
        self.lock = Lock()
        
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
    
    def saveUserData(self, data):
        """Save user data to JSON file (thread-safe)"""
        try:
            with self.lock:
                with open(self.userDataFile, 'w') as f:
                    json.dump(data, f, indent=2)
        except Exception as e:
            self.logger.error("Error saving user data: %s", str(e))
    
    def getDevicesWithQuota(self):
        """Get all devices that still have remaining quota"""
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
        """Add quota(buy traffic)"""
        user_data = self.loadUserData()
        
        for room_number, user_info in user_data.get('users', {}).items():
            if mac_address in user_info.get('devices', []):
                current_quota = user_info.get('quota', 0)
                user_info['quota'] = current_quota + additional_bytes
                
                self.saveUserData(user_data)
                self.logger.info("Added quota to room %s, device %s: +%.1fGB", 
                               room_number, mac_address, additional_bytes / (1024**3))
                
                # Trigger flow table update
                self._triggerFlowUpdate()
                return True
        
        return False
    
    def updateUserTraffic(self, mac_address, bytes_count):
        """updateUserTraffic"""
        user_data = self.loadUserData()
        flow_update_needed = False
        
        for room_number, user_info in user_data.get('users', {}).items():
            if mac_address in user_info.get('devices', []):
                if user_info.get('reset', False):
                    self.logger.info("Skip a traffic update for room %s device %s (just reset)", room_number, mac_address)
                    user_info['reset'] = False  # reset flag from json file
                    self.saveUserData(user_data)
                    return True
                current_used = user_info.get('used_traffic', 0)
                user_info['used_traffic'] = current_used + bytes_count
                
                # check remaining =or!= 0
                quota = user_info.get('quota', 0)
                used = user_info.get('used_traffic', 0)
                remaining = quota - used
                
                if remaining <= 0 and remaining + bytes_count > 0:
                    # quota 0->1, update flow
                    self.logger.warning("⚠️ room%s device %s quota is used up: %.1fGB/%.1fGB", 
                                      room_number, mac_address, 
                                      used / (1024**3), quota / (1024**3))
                    flow_update_needed = True
                self.saveUserData(user_data)
                
                if flow_update_needed:
                    self._triggerFlowUpdate()
                
                return True
        
        return False
    
    def resetDeviceTraffic(self, mac_address):
        """reset used_traffic"""
        user_data = self.loadUserData()
        
        for room_number, user_info in user_data.get('users', {}).items():
            if mac_address in user_info.get('devices', []):
                user_info['used_traffic'] = 0
                user_info['reset'] = True
                self.saveUserData(user_data)
                self.logger.info("reset room %s device %s used_traffic", room_number, mac_address)
                return True
        
        return False
    
    def getQuotaStatus(self):
        """get all quota status"""
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
        """update flow"""
        # Here, it is necessary to obtain the currently connected switch and update the flow table
        # Since we cannot directly obtain the list of switches, we record logs
        self.logger.info("quota changed, need update flow")
        # In practical applications, flowManager.updateQuotaBasedFlows should be called here
        # However, the currently connected switch needs to be obtained through the controller
