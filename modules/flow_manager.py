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
        """添加流表项"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        
        if bufferId:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=bufferId,
                                    priority=priority, match=match, instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst)
        
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
        """智能流表控制：只在首次或配额变化时下发许可流表"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        # 路由器MAC地址
        router_mac = "00:00:00:00:00:AA"
        
        # 动态从user_info中检查设备
        if user_info:
            # 检查该MAC是否在任何房间的设备列表中
            for room_number, room_info in user_info.items():
                if room_number != 'router' and srcMac in room_info.get('devices', []):
                    quota = room_info.get('quota', 0)
                    
                    # 检查是否已有许可流表（通过检查MAC地址表）
                    existing_flows = self.getMacTable(datapath.id)
                    
                    # 配额状态变化检测
                    has_quota = quota > 0
                    has_flow = srcMac in existing_flows
                    
                    if has_quota and not has_flow:
                        # 首次有配额 - 添加许可流表
                        
                        # 1. 主机→路由器
                        match_host_to_router = parser.OFPMatch(eth_src=srcMac, eth_dst=router_mac)
                        actions_host_to_router = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
                        self.addFlow(datapath, 100, match_host_to_router, actions_host_to_router)
                        
                        # 2. 路由器→主机
                        match_router_to_host = parser.OFPMatch(eth_src=router_mac, eth_dst=srcMac)
                        actions_router_to_host = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
                        self.addFlow(datapath, 100, match_router_to_host, actions_router_to_host)
                        
                        # 3. 主机→其他网络
                        match_host_out = parser.OFPMatch(eth_src=srcMac)
                        actions_host_out = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
                        self.addFlow(datapath, 100, match_host_out, actions_host_out)
                        
                        # 4. 其他网络→主机
                        match_host_in = parser.OFPMatch(eth_dst=srcMac)
                        actions_host_in = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
                        self.addFlow(datapath, 100, match_host_in, actions_host_in)
                        
                        self.logger.info("Added permit flows for host %s in room %s", srcMac, room_number)
                        self.handlePacket(datapath, srcMac, dstMac, inPort, msg)
                        
                    elif not has_quota and has_flow:
                        # 配额用完 - 删除许可流表
                        self.deleteFlow(datapath, 100, parser.OFPMatch(eth_src=srcMac))
                        self.deleteFlow(datapath, 100, parser.OFPMatch(eth_dst=srcMac))
                        self.deleteFlow(datapath, 100, parser.OFPMatch(eth_src=srcMac, eth_dst=router_mac))
                        self.deleteFlow(datapath, 100, parser.OFPMatch(eth_src=router_mac, eth_dst=srcMac))
                        
                        self.logger.info("Removed permit flows for host %s in room %s", srcMac, room_number)
                        
                    elif has_quota and has_flow:
                        # 已有许可流表，直接处理数据包
                        self.handlePacket(datapath, srcMac, dstMac, inPort, msg)
                        
                    else:
                        # 无配额且无流表，默认drop
                        self.logger.debug("Device %s in room %s has no quota and no flows", srcMac, room_number)
                        
                    break
        else:
            # 无用户信息 - 默认drop
            self.logger.debug("No user info for device %s", srcMac)
