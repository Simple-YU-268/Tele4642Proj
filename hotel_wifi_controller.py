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
from ryu.lib.packet import packet, ethernet, ipv4, arp
from ryu.lib import hub

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
            'trafficMonitor': self.trafficMonitor,
            'controller': self
        })
        
        # 存储当前连接的交换机
        self.datapaths = {}
        
        # 启动周期性配额更新任务
        self.logger.info("🔄 启动周期性配额更新任务...")
        self.threads.append(hub.spawn(self._periodic_quota_update))

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switchFeaturesHandler(self, ev):
        """交换机连接初始化 - 默认DROP所有流量"""
        datapath = ev.msg.datapath
        
        self.logger.info("=" * 60)
        self.logger.info("🌐 交换机连接初始化 - 默认DROP模式")
        self.logger.info("=" * 60)
        self.logger.info("📍 交换机ID: %016x", datapath.id)
        
        # 默认DROP所有流量
        #self.flowManager.installDefaultDropFlows(datapath)


        # 安装基础流表 - table-miss + ARP
        self.flowManager.installDefaultFlows(datapath)
        self.logger.info("🔧 安装基础流表 - table-miss + ARP")
        #self.flowManager._installTableMissFlow(datapath)
        #self.flowManager._installArpFlows(datapath)
        #self.logger.info("✅ 基础流表安装完成 - 默认DROP，通用ARP许可")
        
        # 根据配额下发许可流表
        self.flowManager.updateQuotaBasedFlows(datapath, self.quotaManager)
        
        self.logger.info("✅ 初始化完成 - 默认DROP，配额许可")
        self.logger.info("=" * 60)
        
        # 记录交换机连接
        self.datapaths[datapath.id] = datapath

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packetInHandler(self, ev):
        """数据包处理 - 仅记录流量，不处理转发（由预配置流表控制）"""
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
        
        # 仅记录数据包信息，不处理转发（由预配置流表控制）
        packet_type = "UNKNOWN"
        
        if eth.ethertype == 0x0806:
            packet_type = "ARP"
        elif eth.ethertype == 0x0800:
            packet_type = "IPv4"
        elif eth.ethertype == 0x86DD:
            packet_type = "IPv6"
        else:
            packet_type = f"OTHER(0x{eth.ethertype:04x})"
        
        # 记录数据包信息（不处理转发）
        self.logger.info("=" * 80)
        self.logger.info("📊 PACKET-IN 监控记录:")
        self.logger.info("   📍 交换机: %016x", datapath.id)
        self.logger.info("   🔗 源MAC: %s", srcMac)
        self.logger.info("   🔗 目的MAC: %s", dstMac)
        self.logger.info("   🔌 入端口: %d", inPort)
        self.logger.info("   📏 包长度: %d字节", packet_len)
        self.logger.info("   🏷️  类型: %s", packet_type)
        
        # 如果是IPv4，显示IP信息
        if eth.ethertype == 0x0800:
            ip_pkt = pkt.get_protocol(ipv4.ipv4)
            if ip_pkt:
                self.logger.info("   🌐 源IP: %s", ip_pkt.src)
                self.logger.info("   🌐 目的IP: %s", ip_pkt.dst)
                self.logger.info("   🔧 协议: %s", ip_pkt.proto)
        
        self.logger.info("🎯 流量已记录 - 由预配置流表控制")
        self.logger.info("=" * 80)

       

    def _periodic_quota_update(self):
        """每5秒执行一次配额更新任务"""
        while True:
            hub.sleep(5)  # 每5秒执行一次
            
            if not self.datapaths:
                continue
                
            self.logger.info("=" * 60)
            self.logger.info("🔄 周期性配额更新任务开始")
            self.logger.info("=" * 60)
            
            # 为每个连接的交换机更新配额流表
            for dpid, datapath in self.datapaths.items():
                try:
                    self.logger.info("📍 更新交换机 %016x 的配额流表", dpid)
                    self.flowManager.updateQuotaBasedFlows(datapath, self.quotaManager)
                    self.logger.info("✅ 交换机 %016x 配额流表更新完成", dpid)
                except Exception as e:
                    self.logger.error("❌ 更新交换机 %016x 配额流表失败: %s", dpid, str(e))
            
            self.logger.info("=" * 60)
            self.logger.info("✅ 周期性配额更新任务完成")
            self.logger.info("=" * 60)
            # 启动周期性任务

