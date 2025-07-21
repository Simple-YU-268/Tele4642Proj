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
