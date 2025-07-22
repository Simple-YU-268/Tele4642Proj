"""流表管理模块 - 基于配额的动态流表控制"""

from ryu.lib.packet import packet, ethernet, ether_types
from ryu.ofproto import ofproto_v1_3
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
        """为指定设备添加许可流表 - 使用特定端口"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        # 基于Mininet拓扑的端口映射# 假设标准端口分配：h1=2, h2=3, h3=4, router=1
        
        
        # 获取设备对应的端口（基于MAC地址）
        device_port = self._getDevicePort(device_mac)
        router_port = 1  # 路由器固定端口 (s1-eth1)
        
        # 优先级400: 设备到路由器的双向ICMP（配额许可）
        match_device_to_router = parser.OFPMatch(eth_src=device_mac, eth_dst=self.router_mac, eth_type=0x0800)
        actions_device_to_router = [parser.OFPActionOutput(router_port)]
        self.addFlow(datapath, 400, match_device_to_router, actions_device_to_router)
        
        # 优先级400: 路由器到设备的双向ICMP（配额许可）
        match_router_to_device = parser.OFPMatch(eth_src=self.router_mac, eth_dst=device_mac, eth_type=0x0800)
        actions_router_to_device = [parser.OFPActionOutput(device_port)]
        self.addFlow(datapath, 400, match_router_to_device, actions_router_to_device)
        
        # 优先级300: 设备到路由器的ARP（允许）
        match_arp_to_router = parser.OFPMatch(eth_type=0x0806, eth_src=device_mac, eth_dst=self.router_mac)
        actions_arp_to_router = [parser.OFPActionOutput(router_port)]
        self.addFlow(datapath, 300, match_arp_to_router, actions_arp_to_router)
        
        # 优先级300: 路由器到设备的ARP（允许）
        match_arp_from_router = parser.OFPMatch(eth_type=0x0806, eth_src=self.router_mac, eth_dst=device_mac)
        actions_arp_from_router = [parser.OFPActionOutput(device_port)]
        self.addFlow(datapath, 300, match_arp_from_router, actions_arp_from_router)
        
        # 优先级200: 设备ARP广播（允许）
        match_arp_broadcast = parser.OFPMatch(eth_type=0x0806, eth_src=device_mac, eth_dst="ff:ff:ff:ff:ff:ff")
        actions_arp_broadcast = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
        self.addFlow(datapath, 200, match_arp_broadcast, actions_arp_broadcast)
        
        # 优先级100: 设备到设备的流量（DROP）
        match_device_to_device = parser.OFPMatch(eth_src=device_mac)
        actions_device_to_device = []  # 空动作 = DROP
        self.addFlow(datapath, 100, match_device_to_device, actions_device_to_device)
        
        # 优先级1: 默认ICMP DROP（最低优先级，仅作为最后手段）
        # 这个规则会被更具体的规则覆盖
        match_icmp_default = parser.OFPMatch(eth_type=0x0800)
        actions_icmp_default = []  # 空动作 = DROP
        self.addFlow(datapath, 1, match_icmp_default, actions_icmp_default)
    
    def _getDevicePort(self, device_mac):
        """根据MAC地址返回对应的端口"""
        port_mapping = {
            "00:00:00:00:00:01": 2,  # h1 -> s1-eth2
            "00:00:00:00:00:02": 3,  # h2 -> s1-eth3
            "00:00:00:00:00:03": 4,  # h3 -> s1-eth4
            "00:00:00:00:00:AA": 1   # router -> s1-eth1
        }
        return port_mapping.get(device_mac, ofproto_v1_3.OFPP_FLOOD)
    
    def removePermitFlowsForDevice(self, datapath, device_mac):
        """移除指定设备的ICMP许可流表 - 仅移除ICMP相关规则"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        device_port = self._getDevicePort(device_mac)
        router_port = 1
        
        # 仅删除ICMP相关的Priority 400规则
        match_device_to_router = parser.OFPMatch(eth_src=device_mac, eth_dst=self.router_mac, eth_type=0x0800)
        self.deleteFlow(datapath, 400, match_device_to_router)
        
        match_router_to_device = parser.OFPMatch(eth_src=self.router_mac, eth_dst=device_mac, eth_type=0x0800)
        self.deleteFlow(datapath, 400, match_router_to_device)
        
        self.logger.info("🚫 移除设备%s的ICMP许可流表（保留ARP）", device_mac)
    
    def clearPermitFlows(self, datapath):
        """清除所有许可流表（保留默认DROP）"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        # 删除优先级50-400的流表（保留默认DROP）
        for priority in [50, 100, 150, 200, 300, 400]:
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
