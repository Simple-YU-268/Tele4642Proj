#!/usr/bin/env python3
"""
静态ARP流表安装工具 - 在Ryu中写死ARP规则
直接通过OpenFlow协议安装ARP流表，不依赖动态发现
"""

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3


class StaticARPInstaller(app_manager.RyuApp):
    """静态ARP流表安装器 - 写死ARP规则"""
    
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(StaticARPInstaller, self).__init__(*args, **kwargs)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        """交换机连接时立即安装静态ARP流表"""
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        self.logger.info("=" * 60)
        self.logger.info("🔧 安装静态ARP流表 - 写死规则")
        self.logger.info("=" * 60)

        # 1. 优先级0: 默认DROP所有流量
        match = parser.OFPMatch()
        actions = []
        self.add_flow(datapath, 0, match, actions)
        self.logger.info("✅ 优先级0: 默认DROP")

        # 2. 优先级1: 允许所有ARP流量（写死规则）
        match = parser.OFPMatch(eth_type=0x0806)  # ARP协议
        actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
        self.add_flow(datapath, 1, match, actions)
        self.logger.info("✅ 优先级1: ARP FLOOD")

        # 3. 优先级100: 特定MAC到路由器的IP流量
        # h1 -> router
        match = parser.OFPMatch(
            eth_src="00:00:00:00:00:01",
            eth_dst="00:00:00:00:00:AA",
            eth_type=0x0800
        )
        actions = [parser.OFPActionOutput(1)]
        self.add_flow(datapath, 100, match, actions)
        self.logger.info("✅ 优先级100: h1->router IP")

        # router -> h1
        match = parser.OFPMatch(
            eth_src="00:00:00:00:00:AA",
            eth_dst="00:00:00:00:00:01",
            eth_type=0x0800
        )
        actions = [parser.OFPActionOutput(2)]
        self.add_flow(datapath, 100, match, actions)
        self.logger.info("✅ 优先级100: router->h1 IP")

        # h2 -> router
        match = parser.OFPMatch(
            eth_src="00:00:00:00:00:02",
            eth_dst="00:00:00:00:00:AA",
            eth_type=0x0800
        )
        actions = [parser.OFPActionOutput(1)]
        self.add_flow(datapath, 100, match, actions)
        self.logger.info("✅ 优先级100: h2->router IP")

        # router -> h2
        match = parser.OFPMatch(
            eth_src="00:00:00:00:00:AA",
            eth_dst="00:00:00:00:00:02",
            eth_type=0x0800
        )
        actions = [parser.OFPActionOutput(3)]
        self.add_flow(datapath, 100, match, actions)
        self.logger.info("✅ 优先级100: router->h2 IP")

        # h3 -> router
        match = parser.OFPMatch(
            eth_src="00:00:00:00:00:03",
            eth_dst="00:00:00:00:00:AA",
            eth_type=0x0800
        )
        actions = [parser.OFPActionOutput(1)]
        self.add_flow(datapath, 100, match, actions)
        self.logger.info("✅ 优先级100: h3->router IP")

        # router -> h3
        match = parser.OFPMatch(
            eth_src="00:00:00:00:00:AA",
            eth_dst="00:00:00:00:00:03",
            eth_type=0x0800
        )
        actions = [parser.OFPActionOutput(4)]
        self.add_flow(datapath, 100, match, actions)
        self.logger.info("✅ 优先级100: router->h3 IP")

        self.logger.info("=" * 60)
        self.logger.info("✅ 静态ARP流表安装完成")
        self.logger.info("=" * 60)

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        """添加流表项"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]

        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match, instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst)
        datapath.send_msg(mod)


if __name__ == '__main__':
    from ryu.cmd import manager
    manager.main(['--ofp-tcp-listen-port', '6653', 'static_arp_flows'])
