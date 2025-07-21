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
        """交换机连接初始化 - 立即检查并下发流表"""
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        
        # 打印交换机信息
        self.logger.info("=" * 60)
        self.logger.info("🌐 交换机连接初始化")
        self.logger.info("=" * 60)
        self.logger.info("📍 交换机ID: %016x", datapath.id)
        self.logger.info("🔧 OpenFlow版本: %s", ofproto.OFP_VERSION)
        self.logger.info("📊 端口数量: %d", len(datapath.ports))
        
        # 打印所有端口信息
        self.logger.info("📋 端口详情:")
        for port_no, port in datapath.ports.items():
            self.logger.info("   🔗 端口%d: %s (MAC: %s)", 
                           port.port_no, port.name.decode(), port.hw_addr)
        
        # 安装默认流表
        self.flowManager.installDefaultFlow(datapath)
        
        # 立即检查并下发现有设备的流表
        self.logger.info("🚀 立即检查并下发现有设备的流表...")
        user_data = self.quotaManager.loadUserData()
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
                    
                    # 主机→路由器
                    match_to_router = parser.OFPMatch(eth_src=device_mac, eth_dst=router_mac)
                    actions_to_router = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
                    self.flowManager.addFlow(datapath, 100, match_to_router, actions_to_router)
                    
                    # 路由器→主机
                    match_from_router = parser.OFPMatch(eth_src=router_mac, eth_dst=device_mac)
                    actions_from_router = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
                    self.flowManager.addFlow(datapath, 100, match_from_router, actions_from_router)
                    
                    # 主机→其他网络
                    match_host_out = parser.OFPMatch(eth_src=device_mac)
                    actions_host_out = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
                    self.flowManager.addFlow(datapath, 100, match_host_out, actions_host_out)
                    
                    # 其他网络→主机
                    match_host_in = parser.OFPMatch(eth_dst=device_mac)
                    actions_host_in = [parser.OFPPActionOutput(ofproto.OFPP_FLOOD)]
                    self.flowManager.addFlow(datapath, 100, match_host_in, actions_host_in)
        
        self.logger.info("✅ 初始流表下发完成")
        self.logger.info("=" * 60)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packetInHandler(self, ev):
        """数据包处理入口 - 每次ping都输出详细信息"""
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
        
        # 每次数据包都输出详细信息
        self.logger.info("📦 数据包: %s → %s, 端口=%d, 交换机=%016x", 
                        srcMac, dstMac, inPort, dpid)
        
        # 检查配额状态
        if user_info:
            quota_gb = user_info.get('quota', 0) / (1024**3)
            used_gb = user_info.get('used_traffic', 0) / (1024**3)
            self.logger.info("💾 配额状态: %.1fGB/%.1fGB 已使用", used_gb, quota_gb)
        else:
            self.logger.info("⚠️  未注册设备: %s", srcMac)
        
        # 委托给flow_manager处理所有流表操作
        self.flowManager.handleTrafficControl(
            datapath, srcMac, dstMac, inPort, msg, user_info
        )
