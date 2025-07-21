"""流表管理模块"""

from ryu.lib.packet import packet, ethernet
from collections import defaultdict


class FlowManager:
    """流表管理器"""
    
    def __init__(self, logger):
        self.logger = logger
        self.macToPort = defaultdict(dict)
    
    def installDefaultFlow(self, datapath):
        """安装默认流表项"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        
        self.addFlow(datapath, 0, match, actions)
    
    def addFlow(self, datapath, priority, match, actions, bufferId=None):
        """添加流表项 - 带日志输出"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        
        if bufferId:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=bufferId,
                                    priority=priority, match=match, instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst)
        
        # 打印流表添加信息
        self.logger.info("📊 添加流表: 交换机=%016x, 优先级=%d, 匹配=%s, 动作=%s", 
                        datapath.id, priority, match, actions)
        
        datapath.send_msg(mod)
    
    def handlePacket(self, datapath, srcMac, dstMac, inPort, msg):
        """处理数据包转发"""
        dpid = datapath.id
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        # 学习MAC地址
        self.macToPort[dpid][srcMac] = inPort
        
        # 确定输出端口
        outPort = self.macToPort[dpid].get(dstMac, ofproto.OFPP_FLOOD)
        
        # 创建动作
        actions = [parser.OFPActionOutput(outPort)]
        
        # 添加流表项（非洪泛情况）
        if outPort != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=inPort, eth_dst=dstMac)
            self.addFlow(datapath, 1, match, actions, msg.buffer_id)
            
            if msg.buffer_id != ofproto.OFP_NO_BUFFER:
                return
        
        # 发送数据包
        data = msg.data if msg.buffer_id == ofproto.OFP_NO_BUFFER else None
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=inPort, actions=actions, data=data)
        datapath.send_msg(out)
    
    def getMacTable(self, dpid):
        """获取MAC地址表"""
        return dict(self.macToPort.get(dpid, {}))
    
    def deleteFlow(self, datapath, priority, match):
        """删除流表项"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        # 创建删除流表项的消息
        mod = parser.OFPFlowMod(
            datapath=datapath,
            command=ofproto.OFPFC_DELETE,
            priority=priority,
            match=match,
            out_port=ofproto.OFPP_ANY,
            out_group=ofproto.OFPG_ANY
        )
        
        datapath.send_msg(mod)
        self.logger.info("Deleted flow with priority %d for match %s", priority, match)

    def handleTrafficControl(self, datapath, srcMac, dstMac, inPort, msg, user_info):
        """修复后的智能流表控制 - 强制添加许可流表"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        # 路由器MAC地址
        router_mac = "00:00:00:00:00:AA"
        
        # 确保user_info是字典且包含users
        if not user_info or not isinstance(user_info, dict):
            self.logger.warning("❌ 无效的用户数据格式")
            return
            
        users = user_info.get('users', {})
        if not isinstance(users, dict):
            self.logger.warning("❌ 无效的用户列表格式")
            return
            
        # 强制检查所有设备
        device_found = False
        for room_number, room_info in users.items():
            if not isinstance(room_info, dict):
                continue
                
            devices = room_info.get('devices', [])
            if not isinstance(devices, list):
                continue
                
            if srcMac in devices:
                device_found = True
                quota = room_info.get('quota', 0)
                
                # 强制配额检测
                has_quota = quota > 0
                
                if has_quota:
                    # 强制添加许可流表 - 无论是否有现有流表
                    self.logger.info("🚀 强制添加许可流表给设备 %s (配额: %d bytes)", srcMac, quota)
                    
                    # 1. 主机→路由器
                    match_to_router = parser.OFPMatch(eth_src=srcMac, eth_dst=router_mac)
                    actions_to_router = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
                    self.addFlow(datapath, 100, match_to_router, actions_to_router)
                    
                    # 2. 路由器→主机
                    match_from_router = parser.OFPMatch(eth_src=router_mac, eth_dst=srcMac)
                    actions_from_router = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
                    self.addFlow(datapath, 100, match_from_router, actions_from_router)
                    
                    # 3. 主机→其他网络
                    match_host_out = parser.OFPMatch(eth_src=srcMac)
                    actions_host_out = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
                    self.addFlow(datapath, 100, match_host_out, actions_host_out)
                    
                    # 4. 其他网络→主机
                    match_host_in = parser.OFPMatch(eth_dst=srcMac)
                    actions_host_in = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
                    self.addFlow(datapath, 100, match_host_in, actions_host_in)
                    
                    self.logger.info("✅ 成功添加许可流表给设备 %s", srcMac)
                    self.handlePacket(datapath, srcMac, dstMac, inPort, msg)
                    return
                else:
                    # 无配额，强制记录
                    self.logger.warning("⚠️  设备 %s 无配额，丢弃数据包", srcMac)
                    return
        
        if not device_found:
            # 未注册设备，强制记录
            self.logger.warning("⚠️  未注册设备 %s，丢弃数据包", srcMac)
