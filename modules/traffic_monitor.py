"""流量监控模块 - 基于配额的流量统计，仅使用user_data.json"""
import json
import os
from collections import defaultdict
import time
class TrafficMonitor:
    """流量监控模块 - 用于记录和管理流量统计信息"""
    def __init__(self, logger, user_data_file='user_data.json'):
        self.logger = logger
        self.traffic_stats = defaultdict(int)  # 存储流量统计
        self.start_time = time.time()
        self.user_data_file = user_data_file
        self.users_data = self.load_user_data()  # 加载用户数据
    def load_user_data(self):
        """加载用户数据"""
        if os.path.exists(self.user_data_file):
            with open(self.user_data_file, 'r') as f:
                return json.load(f)
        else:
            self.logger.error("用户数据文件不存在！")
            return {"users": {}, "sessions": {}}
    def updateTraffic(self, srcMac, packet_length):
        """更新流量统计"""
        self.traffic_stats[srcMac] += packet_length
        # 对应用户 ID 和设备进行匹配
        user_id = self.get_user_id_by_mac(srcMac)
        if user_id and user_id in self.users_data["users"]:
            self.users_data["users"][user_id]["used_traffic"] += packet_length
            self.save_user_data()  # 保存用户数据到 JSON 文件
        # 每隔一定时间打印一次流量统计
        if time.time() - self.start_time > 5:  # 每5s记录一次
            self.logTrafficStats()
            self.start_time = time.time()
    def get_user_id_by_mac(self, mac):
        """根据 MAC 地址获取用户 ID"""
        for user_id, user_info in self.users_data["users"].items():
            if mac in user_info.get("devices", []):
                return user_id
        return None
    def logTrafficStats(self):
        """记录流量统计"""
        self.logger.info("=" * 60)
        self.logger.info("📈 流量统计信息:")
        for mac, bytes_transferred in self.traffic_stats.items():
            self.logger.info("   🔗 源MAC: %s, 传输字节数: %d", mac, bytes_transferred)
        self.logger.info("=" * 60)
    def save_user_data(self):
        """保存用户数据到 JSON 文件"""
        with open(self.user_data_file, 'w') as f:
            json.dump(self.users_data, f, indent=4)
            self.logger.info("用户已用流量已更新并保存到 %s", self.user_data_file)
    def resetStats(self):
        """重置流量统计"""
        self.traffic_stats.clear()
        self.logger.info("📊 流量统计已重置.")