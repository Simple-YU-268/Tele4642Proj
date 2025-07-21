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
        """数据包处理入口 - 基于用户数据的动态白名单"""
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
        
        # 动态检查：基于user_data.json中的设备列表
        user_info = self.quotaManager.getUserQuotaInfo(srcMac)
        if not user_info:
            # MAC地址不在任何房间的设备列表中
            self.logger.info("MAC %s not registered to any room. Dropping packet.", srcMac)
            return
            
        # 检查用户配额（流量为0时阻止，不为0时允许）
        if user_info['quota'] > 0:
            # 用户有配额，允许访问并监控流量
            if not self.quotaManager.monitorQuotaUsage(datapath, srcMac, len(msg.data)):
                self.logger.info("User %s quota exceeded. Blocking access.", srcMac)
                return
        else:
            # 用户配额为0，阻止访问
            self.logger.info("User %s has no quota. Blocking access.", srcMac)
            self.quotaManager.blockUser(datapath, srcMac)
            return
            
        # 处理数据包转发
        self.flowManager.handlePacket(datapath, srcMac, dstMac, inPort, msg)
