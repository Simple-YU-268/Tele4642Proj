"""流表管理模块 - 基于配额的动态流表控制"""

from ryu.lib.packet import packet, ethernet, ether_types
from ryu.ofproto import ofproto_v1_3
from ryu.ofproto.ofproto_v1_3 import OFPP_FLOOD
from ryu.ofproto.ofproto_v1_3 import OFPP_ALL

from collections import defaultdict


class FlowManager:
    """流表管理器 - 默认DROP，根据配额动态下发许可流表"""
    
    def __init__(self, logger):
        self.logger = logger
        self.macToPort = defaultdict(dict)
        self.router_mac = "00:00:00:00:00:AA"
    
    # ================================================================================
    # 基础流表安装
    # ================================================================================
    
    def installDefaultFlows(self, datapath):
        """安装基础流表结构"""
        self.logger.info("🔧 开始安装基础流表结构...")
        
        # 1. 安装默认流表（table-miss + ARP）
        self._installTableMissFlow(datapath)
        self._installArpFlows(datapath)
        
        self.logger.info("✅ 基础流表安装完成")
    
    def _installTableMissFlow(self, datapath):
        """安装table-miss流表：丢弃所有未匹配流量"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        # (0) Table-miss: drop everything else
        match = parser.OFPMatch()
        actions = []  # 空动作表示丢弃
        
        self.logger.info("🚫 安装table-miss DROP流表: 交换机=%016x", datapath.id)
        self.addFlow(datapath, 0, match, actions)
    
    def _installArpFlows(self, datapath):
        """安装ARP相关流表 - 仅一个通用ARP规则"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        # (10) Allow all ARP traffic - 通用ARP许可（提高优先级确保生效）
        match = parser.OFPMatch(eth_type=0x0806)
        actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
        
        self.logger.info("✅ 安装ARP通用许可流表: 交换机=%016x", datapath.id)
        self.addFlow(datapath, 10, match, actions)
    
    # ================================================================================
    # 配额相关流表管理
    # ================================================================================
    
    def updateQuotaBasedFlows(self, datapath, quotaManager):
        """根据配额状态更新许可流表"""
        self.logger.info("🔄 开始根据配额更新许可流表...")
        
        # 1. 清除所有现有配额相关流表（保留基础流表）
        self._clearQuotaFlows(datapath)
        
        # 2. 获取用户数据
        user_data = quotaManager.loadUserData()
        users = user_data.get('users', {})
        
        # 3. 为每个有配额的设备下发许可流表
        permit_count = 0
        for room_number, user_info in users.items():
            devices = user_info.get('devices', [])
            quota = user_info.get('quota', 0)
            used = user_info.get('used_traffic', 0)
            
            remaining = quota - used
            
            if remaining > 0:
                for device_mac in devices:
                    self._installDevicePermitFlows(datapath, device_mac)
                    permit_count += 1
                    self.logger.info("   ✅ 房间%s设备%s: 剩余%.1fGB", 
                                   room_number, device_mac, remaining / (1024**3))
        
        self.logger.info("📊 许可流表更新完成: %d个设备获得访问权限", permit_count)
    
    def _installDevicePermitFlows(self, datapath, device_mac):
        """为指定设备安装配额许可流表 - 仅IP流量，ICMP包含在IP中"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        device_port = self._getDevicePort(device_mac)
        router_port = 1  # 路由器固定端口
        
        # 优先级层次（从高到低）：
        # 400: 设备-路由器双向IP（包含ICMP，配额许可）
        # 10:  通用ARP许可（确保ARP正常工作）
        # 0:   table-miss drop（基础流表已处理）
        
        # 400: 设备到路由器的IP（包含ICMP，配额许可）
        match_h_r = parser.OFPMatch(
            eth_src=device_mac, 
            eth_dst=self.router_mac, 
            eth_type=0x0800  # IPv4（包含ICMP、TCP、UDP等）
        )
        actions_h_r = [parser.OFPActionOutput(router_port)]
        self.addFlow(datapath, 400, match_h_r, actions_h_r)
        
        # 400: 路由器到设备的IP（包含ICMP，配额许可）
        match_r_h = parser.OFPMatch(
            eth_src=self.router_mac,
            eth_dst=device_mac,
            eth_type=0x0800  # IPv4（包含ICMP、TCP、UDP等）
        )
        actions_r_h = [parser.OFPActionOutput(device_port)]
        self.addFlow(datapath, 400, match_r_h, actions_r_h)

    def _clearQuotaFlows(self, datapath):
        """清除所有配额相关流表（保留基础流表）"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        # 删除优先级400的流表（保留优先级0-1的基础流表）
        match_any = parser.OFPMatch()
        mod = parser.OFPFlowMod(
            datapath=datapath,
            command=ofproto.OFPFC_DELETE,
            priority=400,
            match=match_any,
            out_port=ofproto.OFPP_ANY,
            out_group=ofproto.OFPG_ANY
        )
        datapath.send_msg(mod)
        
        self.logger.info("🧹 清除所有配额相关流表")
    
    # ================================================================================
    # 工具方法
    # ================================================================================
    
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
    
    def _getDevicePort(self, device_mac):
        """根据MAC地址返回对应的端口"""
        port_mapping = {
            "00:00:00:00:00:01": 2,  # h1 -> s1-eth2
            "00:00:00:00:00:02": 3,  # h2 -> s1-eth3
            "00:00:00:00:00:03": 4,  # h3 -> s1-eth4
            "00:00:00:00:00:AA": 1   # router -> s1-eth1
        }
        return port_mapping.get(device_mac, ofproto_v1_3.OFPP_FLOOD)
    
    # ================================================================================
    # 兼容旧接口（已废弃）
    # ================================================================================
    
    def installDefaultDropFlows(self, datapath):
        """兼容旧接口 - 使用新的installDefaultFlows"""
        self.logger.warning("⚠️  installDefaultDropFlows已废弃，使用installDefaultFlows")
        self.installDefaultFlows(datapath)
    
    def clearPermitFlows(self, datapath):
        """兼容旧接口 - 使用新的_clearQuotaFlows"""
        self.logger.warning("⚠️  clearPermitFlows已废弃，使用_clearQuotaFlows")
        self._clearQuotaFlows(datapath)
    
    def handlePacket(self, datapath, srcMac, dstMac, inPort, msg):
        """处理数据包转发（备用，主要逻辑在updateQuotaBasedFlows）"""
        # 此方法现在主要用于调试，实际流量由预配置的流表控制
        pass
