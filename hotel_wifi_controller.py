#!/usr/bin/env python3
"""
酒店WiFi网络控制器 - 基于流量配额的动态流表控制
模块化版本：默认DROP所有流量，根据配额动态下发许可流表
"""

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.app.wsgi import WSGIApplication
from ryu.lib.packet import packet, ethernet

from modules.flow_manager import FlowManager
from modules.quota_manager import QuotaManager
from modules.traffic_monitor import TrafficMonitor
from modules.api_controller import APIController


class HotelWifiController(app_manager.RyuApp):
    """主控制器类 - 基于配额的动态流表控制"""
    
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {'wsgi': WSGIApplication}

    def __init__(self, *args, **kwargs):
        super(HotelWifiController, self).__init__(*args, **kwargs)
        
        # 初始化模块化组件
        self.flowManager = FlowManager(self.logger)
        self.quotaManager = QuotaManager(self.logger, self.flowManager)
        self.trafficMonitor = TrafficMonitor(self.logger, self.quotaManager)
        
        # 注册API控制器
        wsgi = kwargs['wsgi']
        wsgi.register(APIController, {
            'quotaManager': self.quotaManager,
            'trafficMonitor': self.trafficMonitor
        })

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switchFeaturesHandler(self, ev):
        """交换机连接初始化 - 默认DROP所有流量"""
        datapath = ev.msg.datapath
        
        self.logger.info("=" * 60)
        self.logger.info("🌐 交换机连接初始化 - 默认DROP模式")
        self.logger.info("=" * 60)
        self.logger.info("📍 交换机ID: %016x", datapath.id)
        
        # 默认DROP所有流量
        self.flowManager.installDefaultDropFlows(datapath)
        
        # 根据配额下发许可流表
        self.flowManager.updateQuotaBasedFlows(datapath, self.quotaManager)
        
        self.logger.info("✅ 初始化完成 - 默认DROP，配额许可")
        self.logger.info("=" * 60)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packetInHandler(self, ev):
        """数据包处理 - 仅记录流量，不主动处理转发"""
        msg = ev.msg
        datapath = msg.datapath
        
        # 解析数据包
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]
        
        srcMac = eth.src
        dstMac = eth.dst
        inPort = msg.match['in_port']
        packet_len = len(msg.data)
        
        # 更新流量统计
        self.trafficMonitor.updateTraffic(srcMac, packet_len)
        
        # 仅记录日志，不处理转发（所有流量由预配置的流表控制）
        self.logger.debug("📦 数据包: %s → %s, 长度=%d字节, 端口=%d", 
                         srcMac, dstMac, packet_len, inPort)
