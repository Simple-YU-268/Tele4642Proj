#!/usr/bin/env python3
"""
酒店WiFi网络控制器 - 模块化版本
主控制器模块
"""

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.app.wsgi import WSGIApplication

from modules.whitelist_manager import WhitelistManager
from modules.traffic_monitor import TrafficMonitor
from modules.flow_manager import FlowManager
from modules.quota_manager import QuotaManager
from modules.api_controller import APIController


class HotelWifiController(app_manager.RyuApp):
    """主控制器类 - 协调各模块工作"""
    
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {'wsgi': WSGIApplication}

    def __init__(self, *args, **kwargs):
        super(HotelWifiController, self).__init__(*args, **kwargs)
        
        # 初始化核心模块 - 不再使用白名单文件，改为基于用户数据的动态白名单
        self.whitelistManager = WhitelistManager(self.logger)
        self.trafficMonitor = TrafficMonitor(self.logger)
        self.flowManager = FlowManager(self.logger)
        self.quotaManager = QuotaManager(self.logger, self.flowManager, 
                                       self.whitelistManager)
        
        # 注册API控制器
        wsgi = kwargs['wsgi']
        wsgi.register(APIController, {
            'whitelistManager': self.whitelistManager,
            'trafficMonitor': self.trafficMonitor
        })

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switchFeaturesHandler(self, ev):
        """交换机连接初始化"""
        datapath = ev.msg.datapath
        self.flowManager.installDefaultFlow(datapath)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packetInHandler(self, ev):
        """数据包处理入口 - 基于流表优先级的流量控制"""
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        # 解析数据
        from ryu.lib.packet import packet, ethernet
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]
        
        srcMac = eth.src
        dstMac = eth.dst
        inPort = msg.match['in_port']
        dpid = datapath.id
        
        # 基于流表优先级的流量控制
        user_info = self.quotaManager.getUserQuotaInfo(srcMac)
        
        if user_info:
            # 已注册设备
            if user_info['quota'] > 0:
                # 有配额 - 高优先级允许流表
                match = parser.OFPMatch(eth_src=srcMac)
                actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
                self.flowManager.addFlow(datapath, 100, match, actions)
                
                # 更新流量使用
                if not self.quotaManager.monitorQuotaUsage(datapath, srcMac, len(msg.data)):
                    # 配额用完 - 添加阻止流表
                    match = parser.OFPMatch(eth_src=srcMac)
                    actions = []  # 空动作表示丢弃
                    self.flowManager.addFlow(datapath, 200, match, actions)
                    self.logger.info("User %s quota exceeded. Added block flow.", srcMac)
                    return
            else:
                # 配额为0 - 中优先级阻止流表
                match = parser.OFPMatch(eth_src=srcMac)
                actions = []  # 空动作表示丢弃
                self.flowManager.addFlow(datapath, 200, match, actions)
                self.logger.info("User %s has no quota. Added block flow.", srcMac)
                return
        else:
            # 未注册设备 - 低优先级允许流表（默认行为）
            match = parser.OFPMatch(eth_src=srcMac)
            actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
            self.flowManager.addFlow(datapath, 50, match, actions)
            self.logger.info("MAC %s not registered. Added default allow flow.", srcMac)
            
        # 处理数据包转发
        self.flowManager.handlePacket(datapath, srcMac, dstMac, inPort, msg)
