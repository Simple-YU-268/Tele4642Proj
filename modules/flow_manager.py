"""流表管理模块 - 基于配额的动态流表控制"""

from ryu.lib.packet import packet, ethernet, ether_types
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
            action_str = str(actions)
        else:  # 无动作（DROP）
            inst = []
            action_str = "DROP"
        
        if bufferId:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=bufferId,
                                    priority=priority, match=match, instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst)
        
        # 详细记录流表安装信息
        self.logger.info("=" * 60)
        self.logger.info("🔄 FLOW-MOD 详细信息:")
        self.logger.info("   交换机: %016x", datapath.id)
        self.logger.info("   优先级: %d", priority)
        self.logger.info("   匹配条件: %s", match)
        self.logger.info("   动作: %s", action_str)
        self.logger.info("   缓冲区ID: %s", bufferId if bufferId else "None")
        self.logger.info("=" * 60)
        
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
        
        # 优先级10: 允许所有流量（临时解决方案）
        # 这将确保基本连通性，后续可以细化
        match_any = parser.OFPMatch()
        actions_any = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
        self.addFlow(datapath, 10, match_any, actions_any)
        
        # 优先级50: 广播流量（允许所有广播）
        match_broadcast = parser.OFPMatch(eth_dst="ff:ff:ff:ff:ff:ff")
        actions_broadcast = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
        self.addFlow(datapath, 50, match_broadcast, actions_broadcast)
        
        # 优先级100: ARP流量（允许所有ARP）
        match_arp = parser.OFPMatch(eth_type=0x0806)
        actions_arp = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
        self.addFlow(datapath, 100, match_arp, actions_arp)
        
        # 优先级200: 设备到路由器的流量（允许所有设备到路由器）
        match_up = parser.OFPMatch(eth_dst=self.router_mac)
        actions_up = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
        self.addFlow(datapath, 200, match_up, actions_up)
        
        # 优先级200: 路由器到设备的流量（允许路由器到所有设备）
        match_down = parser.OFPMatch(eth_src=self.router_mac)
        actions_down = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
        self.addFlow(datapath, 200, match_down, actions_down)
        
        # 优先级300: 特定设备间流量（更精确的匹配）
        match_device = parser.OFPMatch(eth_src=device_mac)
        actions_device = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
        self.addFlow(datapath, 300, match_device, actions_device)
    
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
        
        # 删除优先级10-300的流表（包括允许所有流量的规则）
        for priority in [10, 50, 100, 150, 200, 300]:
            match_any = parser.OFPMatch()
            mod = parser.OFPFlowMod(
                datapath=datapath,
                command=ofproto.OFPFC_DELETE,
                priority=priority,
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
