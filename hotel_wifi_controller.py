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
        """数据包处理入口 - 委托给flow_manager处理"""
        msg = ev.msg
        datapath = msg.datapath
        
        # 解析数据
        from ryu.lib.packet import packet, ethernet
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]
        
        srcMac = eth.src
        dstMac = eth.dst
        inPort = msg.match['in_port']
        dpid = datapath.id
        
        # 获取用户配额信息
        user_info = self.quotaManager.getUserQuotaInfo(srcMac)
        
        # 委托给flow_manager处理所有流表操作
        self.flowManager.handleTrafficControl(
            datapath, srcMac, dstMac, inPort, msg, user_info
        )
