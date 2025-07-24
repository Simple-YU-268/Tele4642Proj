#!/usr/bin/env python3
"""
动态配额流表管理器 - 根据流量剩余自动增删流表
实时监控配额状态，动态调整流表规则
"""

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet
import json
import time
import threading


class DynamicQuotaFlowManager(app_manager.RyuApp):
    """动态配额流表管理器"""
    
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    
    def __init__(self, *args, **kwargs):
        super(DynamicQuotaFlowManager, self).__init__(*args, **kwargs)
        
        # 配置参数
        self.router_mac = "00:00:00:00:00:AA"
        self.router_port = 1
        self.device_ports = {
            "00:00:00:00:00:01": 2,  # h1
            "00:00:00:00:00:02": 3,  # h2
            "00:00:00:00:00:03": 4   # h3
        }
        
        # 配额文件路径
        self.quota_file = "user_data.json"
        
        # 监控线程
        self.monitor_thread = None
        self.running = False
        
        # 当前配额状态缓存
        self.current_quota = {}
        
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        """交换机连接时初始化基础流表"""
        datapath = ev.msg.datapath
        
        self.logger.info("=" * 60)
        self.logger.info("🌐 动态配额流表管理器启动")
        self.logger.info("=" * 60)
        
        # 安装基础流表
        self._install_base_flows(datapath)
        
        # 启动配额监控线程
        self.start_quota_monitor(datapath)
        
    def _install_base_flows(self, datapath):
        """安装基础流表（ARP + 默认DROP）"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        # 优先级0: 默认DROP
        match = parser.OFPMatch()
        actions = []
        self.add_flow(datapath, 0, match, actions)
        self.logger.info("✅ 基础流表: 默认DROP")
        
        # 优先级1: ARP通用许可
        match = parser.OFPMatch(eth_type=0x0806)
        actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
        self.add_flow(datapath, 1, match, actions)
        self.logger.info("✅ 基础流表: ARP许可")
        
    def start_quota_monitor(self, datapath):
        """启动配额监控线程"""
        if not self.running:
            self.running = True
            self.monitor_thread = threading.Thread(
                target=self._monitor_quota_loop,
                args=(datapath,),
                daemon=True
            )
            self.monitor_thread.start()
            self.logger.info("🔄 配额监控线程已启动")
    
    def _monitor_quota_loop(self, datapath):
        """配额监控主循环"""
        while self.running:
            try:
                # 读取配额数据
                quota_data = self._load_quota_data()
                
                # 检查配额变化并更新流表
                self._update_flows_based_on_quota(datapath, quota_data)
                
                # 每5秒检查一次
                time.sleep(5)
                
            except Exception as e:
                self.logger.error("❌ 配额监控错误: %s", str(e))
                time.sleep(10)
    
    def _load_quota_data(self):
        """加载配额数据"""
        try:
            with open(self.quota_file, 'r') as f:
                data = json.load(f)
                return data.get('users', {})
        except Exception as e:
            self.logger.warning("⚠️ 无法加载配额文件: %s", str(e))
            return {}
    
    def _update_flows_based_on_quota(self, datapath, quota_data):
        """根据配额状态更新流表"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        # 清除旧的配额相关流表（保留基础流表）
        self._clear_quota_flows(datapath)
        
        # 为每个有配额的设备安装许可流表
        active_devices = 0
        
        for room_number, user_info in quota_data.items():
            devices = user_info.get('devices', [])
            quota = user_info.get('quota', 0)
            used = user_info.get('used_traffic', 0)
            
            remaining = quota - used
            
            for device_mac in devices:
                if remaining > 0:
                    # 有配额，添加许可流表
                    self._add_permit_flows(datapath, device_mac)
                    active_devices += 1
                    self.logger.info("✅ 设备%s: 剩余%.1fGB", 
                                   device_mac, remaining / (1024**3))
                else:
                    # 配额耗尽，不添加许可流表（仅保留ARP）
                    self.logger.info("🚫 设备%s: 配额耗尽", device_mac)
        
        if active_devices > 0:
            self.logger.info("📊 已激活%d个设备的IP流量许可", active_devices)
    
    def _add_permit_flows(self, datapath, device_mac):
        """为设备添加许可流表"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        if device_mac not in self.device_ports:
            return
            
        device_port = self.device_ports[device_mac]
        
        # 设备到路由器的IP流量
        match = parser.OFPMatch(
            eth_src=device_mac,
            eth_dst=self.router_mac,
            eth_type=0x0800
        )
        actions = [parser.OFPActionOutput(self.router_port)]
        self.add_flow(datapath, 100, match, actions)
        
        # 路由器到设备的IP流量
        match = parser.OFPMatch(
            eth_src=self.router_mac,
            eth_dst=device_mac,
            eth_type=0x0800
        )
        actions = [parser.OFPActionOutput(device_port)]
        self.add_flow(datapath, 100, match, actions)
    
    def _clear_quota_flows(self, datapath):
        """清除配额相关流表（保留基础流表）"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        # 删除优先级100的流表（保留优先级0-1的基础流表）
        match = parser.OFPMatch()
        mod = parser.OFPFlowMod(
            datapath=datapath,
            command=ofproto.OFPFC_DELETE,
            priority=100,
            match=match,
            out_port=ofproto.OFPP_ANY,
            out_group=ofproto.OFPG_ANY
        )
        datapath.send_msg(mod)
    
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
    
    def stop(self):
        """停止监控线程"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join()


if __name__ == '__main__':
    from ryu.cmd import manager
    manager.main(['--ofp-tcp-listen-port', '6653', 'dynamic_quota_flows'])
