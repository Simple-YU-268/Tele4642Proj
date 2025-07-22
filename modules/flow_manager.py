"""流表管理模块 - 基于配额的动态流表控制"""

from ryu.lib.packet import packet, ethernet
from collections import defaultdict


class FlowManager:
    """流表管理器 - 默认DROP，根据配额动态下发许可流表"""
    
    def __init__(self, logger):
        self.logger = logger
        self.macToPort = defaultdict(dict)
        self.router_mac = "00:00:00:00:00:AA"
    
    def installDefaultDropFlows(self, datapath):
        """安装默认DROP流表 - 阻止所有流量"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        # 默认DROP所有流量
        match = parser.OFPMatch()
        actions = []  # 空动作表示丢弃
        
        self.logger.info("🚫 安装默认DROP流表: 交换机=%016x", datapath.id)
        self.addFlow(datapath, 0, match, actions)
    
    def addFlow(self, datapath, priority, match, actions, bufferId=None):
        """添加流表项"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        if actions:  # 有动作
            inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        else:  # 无动作（DROP）
            inst = []
        
        if bufferId:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=bufferId,
                                    priority=priority, match=match, instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst)
        
        self.logger.info("📊 添加流表: 交换机=%016x, 优先级=%d, 匹配=%s, 动作=%s", 
                        datapath.id, priority, match, "DROP" if not actions else actions)
        
        datapath.send_msg(mod)
    
    def deleteFlow(self, datapath, priority, match):
        """删除流表项"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        mod = parser.OFPFlowMod(
            datapath=datapath,
            command=ofproto.OFPFC_DELETE,
            priority=priority,
            match=match,
            out_port=ofproto.OFPP_ANY,
            out_group=ofproto.OFPG_ANY
        )
        
        datapath.send_msg(mod)
        self.logger.info("🗑️  删除流表: 优先级=%d, 匹配=%s", priority, match)
    
    def updateQuotaBasedFlows(self, datapath, quotaManager):
        """根据配额状态更新许可流表"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        # 获取用户数据
        user_data = quotaManager.loadUserData()
        users = user_data.get('users', {})
        
        self.logger.info("🔄 根据配额更新许可流表...")
        
        # 清除所有现有许可流表（保留默认DROP）
        self.clearPermitFlows(datapath)
        
        # 为每个有配额的设备下发许可流表
        permit_count = 0
        for room_number, user_info in users.items():
            devices = user_info.get('devices', [])
            quota = user_info.get('quota', 0)
            used = user_info.get('used_traffic', 0)
            
            remaining = quota - used
            
            if remaining > 0:
                for device_mac in devices:
                    self.addPermitFlowsForDevice(datapath, device_mac)
                    permit_count += 1
                    self.logger.info("   ✅ 房间%s设备%s: 剩余%.1fGB", 
                                   room_number, device_mac, remaining / (1024**3))
        
        self.logger.info("📊 许可流表更新完成: %d个设备获得访问权限", permit_count)
    
    def addPermitFlowsForDevice(self, datapath, device_mac):
        """为指定设备添加许可流表"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        # 优先级200: 设备到路由器的流量
        match_up = parser.OFPMatch(eth_src=device_mac, eth_dst=self.router_mac)
        actions_up = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
        self.addFlow(datapath, 200, match_up, actions_up)
        
        # 优先级200: 路由器到设备的流量
        match_down = parser.OFPMatch(eth_src=self.router_mac, eth_dst=device_mac)
        actions_down = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
        self.addFlow(datapath, 200, match_down, actions_down)
    
    def removePermitFlowsForDevice(self, datapath, device_mac):
        """移除指定设备的许可流表"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        # 删除设备到路由器的流表
        match_up = parser.OFPMatch(eth_src=device_mac, eth_dst=self.router_mac)
        self.deleteFlow(datapath, 200, match_up)
        
        # 删除路由器到设备的流表
        match_down = parser.OFPMatch(eth_src=self.router_mac, eth_dst=device_mac)
        self.deleteFlow(datapath, 200, match_down)
        
        self.logger.info("🚫 移除设备%s的许可流表", device_mac)
    
    def clearPermitFlows(self, datapath):
        """清除所有许可流表（保留默认DROP）"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        # 删除优先级200的流表（许可流表）
        match_any = parser.OFPMatch()
        mod = parser.OFPFlowMod(
            datapath=datapath,
            command=ofproto.OFPFC_DELETE,
            priority=200,
            match=match_any,
            out_port=ofproto.OFPP_ANY,
            out_group=ofproto.OFPG_ANY
        )
        
        datapath.send_msg(mod)
        self.logger.info("🧹 清除所有许可流表")
    
    def handlePacket(self, datapath, srcMac, dstMac, inPort, msg):
        """处理数据包转发（备用，主要逻辑在updateQuotaBasedFlows）"""
        # 此方法现在主要用于调试，实际流量由预配置的流表控制
        pass
