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
        """最终配额控制 - 路由器无配额，主机有配额才能通信"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        # 路由器MAC地址
        router_mac = "00:00:00:00:00:AA"
        
        # 获取用户数据
        try:
            if not user_info or not isinstance(user_info, dict):
                self.logger.warning("❌ 无效的用户数据格式")
                return
                
            users = user_info.get('users', {})
            if not isinstance(users, dict):
                self.logger.warning("❌ 无效的用户列表格式")
                return
            
            # 检查源MAC的配额
            src_has_quota = False
            src_quota = 0
            
            # 检查目的MAC的配额
            dst_has_quota = False
            dst_quota = 0
            
            for room_number, room_info in users.items():
                if not isinstance(room_info, dict):
                    continue
                    
                devices = room_info.get('devices', [])
                if not isinstance(devices, list):
                    continue
                
                # 检查源MAC
                if srcMac in devices:
                    src_quota = room_info.get('quota', 0)
                    src_has_quota = src_quota > 0
                
                # 检查目的MAC
                if dstMac in devices:
                    dst_quota = room_info.get('quota', 0)
                    dst_has_quota = dst_quota > 0
            
            # 路由器特殊处理
            if dstMac == router_mac:
                # 主机→路由器：只有主机有配额才允许
                if src_has_quota:
                    self.logger.info("🚀 添加主机→路由器许可流表: %s → %s", srcMac, dstMac)
                    
                    # 主机→路由器
                    match_to_router = parser.OFPMatch(eth_src=srcMac, eth_dst=router_mac)
                    actions_to_router = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
                    self.addFlow(datapath, 100, match_to_router, actions_to_router)
                    
                    # 路由器→主机
                    match_from_router = parser.OFPMatch(eth_src=router_mac, eth_dst=srcMac)
                    actions_from_router = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
                    self.addFlow(datapath, 100, match_from_router, actions_from_router)
                    
                    self.logger.info("✅ 成功添加主机↔路由器许可流表: %s ↔ %s", srcMac, router_mac)
                    self.handlePacket(datapath, srcMac, dstMac, inPort, msg)
                    return
                else:
                    self.logger.warning("⚠️  主机 %s 无配额，无法访问路由器", srcMac)
                    return
            
            # 主机间通信
            elif src_has_quota and dst_has_quota:
                # 双向都有配额
                self.logger.info("🚀 添加主机间许可流表: %s ↔ %s", srcMac, dstMac)
                
                # 源→目的
                match_src_dst = parser.OFPMatch(eth_src=srcMac, eth_dst=dstMac)
                actions_src_dst = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
                self.addFlow(datapath, 100, match_src_dst, actions_src_dst)
                
                # 目的→源
                match_dst_src = parser.OFPMatch(eth_src=dstMac, eth_dst=srcMac)
                actions_dst_src = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
                self.addFlow(datapath, 100, match_dst_src, actions_dst_src)
                
                self.logger.info("✅ 成功添加主机间许可流表: %s ↔ %s", srcMac, dstMac)
                self.handlePacket(datapath, srcMac, dstMac, inPort, msg)
                return
            else:
                # 无配额，记录原因
                if not src_has_quota:
                    self.logger.warning("⚠️  源设备 %s 无配额", srcMac)
                if not dst_has_quota and dstMac != router_mac:
                    self.logger.warning("⚠️  目的设备 %s 无配额", dstMac)
                return
                
        except Exception as e:
            self.logger.error("❌ 处理流量控制时出错: %s", str(e))
            
        # 默认丢弃
        self.logger.warning("⚠️  丢弃数据包: %s → %s", srcMac, dstMac)

    def initializeSwitchFlows(self, datapath, quotaManager):
        """交换机初始化 - 下发现有设备的流表"""
        # 安装默认流表
        self.installDefaultFlow(datapath)
        
        # 立即检查并下发现有设备的流表
        self.logger.info("🚀 立即检查并下发现有设备的流表...")
        
        # 从quotaManager获取用户数据
        if hasattr(quotaManager, 'loadUserData'):
            user_data = quotaManager.loadUserData()
        else:
            # 兼容旧版本，直接读取文件
            import json
            try:
                with open('user_data.json', 'r') as f:
                    user_data = json.load(f)
            except:
                user_data = {'users': {}}
        
        users = user_data.get('users', {})
        
        # 路由器MAC地址
        router_mac = "00:00:00:00:00:AA"
        
        # 为每个有配额的设备下发流表
        for room_number, room_info in users.items():
            devices = room_info.get('devices', [])
            quota = room_info.get('quota', 0)
            
            if quota > 0:
                for device_mac in devices:
                    self.logger.info("   📊 为设备 %s 下发许可流表 (配额: %.1fGB)", 
                                   device_mac, quota / (1024**3))
                    
                    # 立即下发流表
                    parser = datapath.ofproto_parser
                    ofproto = datapath.ofproto
                    
                    # 主机→路由器
                    match_to_router = parser.OFPMatch(eth_src=device_mac, eth_dst=router_mac)
                    actions_to_router = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
                    self.addFlow(datapath, 100, match_to_router, actions_to_router)
                    
                    # 路由器→主机
                    match_from_router = parser.OFPMatch(eth_src=router_mac, eth_dst=device_mac)
                    actions_from_router = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
                    self.addFlow(datapath, 100, match_from_router, actions_from_router)
                    
                    # 主机→其他网络
                    match_host_out = parser.OFPMatch(eth_src=device_mac)
                    actions_host_out = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
                    self.addFlow(datapath, 100, match_host_out, actions_host_out)
                    
                    # 其他网络→主机
                    match_host_in = parser.OFPMatch(eth_dst=device_mac)
                    actions_host_in = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
                    self.addFlow(datapath, 100, match_host_in, actions_host_in)
        
        self.logger.info("✅ 初始流表下发完成")
