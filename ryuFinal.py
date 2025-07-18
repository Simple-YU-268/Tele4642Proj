#!/usr/bin/env python3
"""
酒店WiFi网络控制器 - Ryu SDN控制器应用

这是一个基于Ryu框架的SDN控制器应用，专为酒店WiFi网络环境设计。
主要功能包括：
1. MAC地址白名单管理
2. 网络流量监控
3. RESTful API接口用于白名单管理
4. 基于OpenFlow 1.3的网络流量控制

作者: TELE4632项目团队
版本: 1.0.0
"""

# Ryu框架核心模块导入
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.app.wsgi import WSGIApplication, ControllerBase, route

# 标准库和第三方库导入
import json
from webob import Response


class HotelWifiController(app_manager.RyuApp):
    """
    酒店WiFi网络控制器主类
    
    该类实现了酒店WiFi网络的核心控制逻辑，包括：
    - 交换机连接管理
    - 数据包处理
    - MAC地址白名单管理
    - 流量监控和统计
    
    继承自RyuApp，是Ryu框架应用的标准基类
    """
    
    # 指定支持的OpenFlow协议版本
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    
    # 定义需要加载的上下文环境，这里加载WSGI应用用于提供REST API
    _CONTEXTS = {'wsgi': WSGIApplication}

    def __init__(self, *args, **kwargs):
        """
        控制器初始化方法
        
        参数:
            *args: 可变位置参数，传递给父类
            **kwargs: 可变关键字参数，包含Ryu框架提供的上下文对象
            
        初始化内容包括：
        - MAC地址到端口的映射表
        - 白名单MAC地址集合
        - 账户数据存储
        - 设备流量统计
        - WSGI应用注册
        """
        super(HotelWifiController, self).__init__(*args, **kwargs)
        
        # MAC地址到交换机端口的映射表
        # 格式: {dpid: {mac_address: port_number}}
        self.mac_to_port = {}
        
        # 白名单MAC地址集合
        # 只有在此集合中的设备才能访问网络
        self.white_list = set()
        
        # 账户数据存储（预留扩展用）
        # 格式: {mac_address: account_info}
        self.account_data = {}
        
        # 设备流量统计
        # 格式: {mac_address: total_bytes}
        self.device_traffic = {}
        
        # 注册WSGI应用，提供REST API接口
        wsgi = kwargs['wsgi']
        wsgi.register(WhitelistController, {'hotel_wifi_app': self})

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        """
        交换机特性事件处理器
        
        当交换机连接到控制器时触发，用于初始化交换机配置
        
        参数:
            ev: 事件对象，包含交换机特性信息
            
        功能:
        - 获取交换机信息
        - 设置默认流表项（table-miss flow entry）
        - 将所有未知流量发送到控制器
        """
        # 获取交换机对象
        datapath = ev.msg.datapath
        
        # 获取OpenFlow协议和解析器
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # 创建匹配所有数据包的匹配规则
        match = parser.OFPMatch()
        
        # 创建动作：将数据包发送到控制器
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        
        # 添加默认流表项，优先级为0（最低）
        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        """
        添加流表项到交换机
        
        这是一个通用方法，用于向交换机添加流表规则
        
        参数:
            datapath: 交换机对象
            priority: 流表项优先级（数值越大优先级越高）
            match: 匹配规则对象
            actions: 动作列表
            buffer_id: 缓冲区ID（可选，用于packet-in消息）
            
        功能:
        - 创建流表项指令
        - 构建流表修改消息
        - 发送消息到交换机
        """
        # 获取OpenFlow协议和解析器
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # 创建指令：应用指定的动作
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]
        
        # 根据是否提供buffer_id创建不同的流表修改消息
        if buffer_id:
            # 如果提供了buffer_id，使用它来处理缓存的数据包
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    instructions=inst)
        else:
            # 如果没有buffer_id，创建新的流表项
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst)
        
        # 发送流表修改消息到交换机
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        """
        数据包输入事件处理器
        
        当交换机收到未知数据包时触发，控制器需要决定如何处理
        
        参数:
            ev: 事件对象，包含packet-in消息
            
        处理流程:
        1. 解析数据包信息
        2. 学习MAC地址和端口映射
        3. 检查MAC地址是否在白名单中
        4. 如果在白名单中：转发数据包并添加流表项
        5. 如果不在白名单中：丢弃数据包
        """
        # 获取packet-in消息对象
        msg = ev.msg
        
        # 获取交换机对象
        datapath = msg.datapath
        
        # 获取OpenFlow协议和解析器
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        # 获取数据包进入的端口号
        in_port = msg.match['in_port']

        # 解析数据包
        pkt = packet.Packet(msg.data)
        
        # 获取以太网协议头
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        # 提取源MAC地址和目的MAC地址
        dst = eth.dst  # 目的MAC地址
        src = eth.src  # 源MAC地址

        # 获取交换机ID（Datapath ID）
        dpid = datapath.id
        
        # 确保该交换机有对应的MAC地址映射表
        self.mac_to_port.setdefault(dpid, {})
        
        # 学习MAC地址和端口的对应关系
        # 这样控制器就知道哪个MAC地址在哪个端口上
        self.mac_to_port[dpid][src] = in_port

        # 检查源MAC地址是否在白名单中
        if src in self.white_list:
            # 设备在白名单中，允许网络访问
            
            # 更新设备流量统计
            # 累加该设备发送的字节数
            self.device_traffic[src] = self.device_traffic.get(src, 0) + len(msg.data)
            self.logger.info("Device %s used %d bytes", src, self.device_traffic[src])

            # 确定数据包的输出端口
            if dst in self.mac_to_port[dpid]:
                # 如果知道目的MAC地址的位置，直接发送到对应端口
                out_port = self.mac_to_port[dpid][dst]
            else:
                # 如果不知道目的MAC地址的位置，进行洪泛（广播）
                out_port = ofproto.OFPP_FLOOD

            # 创建输出动作
            actions = [parser.OFPActionOutput(out_port)]

            # 创建匹配规则：匹配从该端口进入且目的MAC地址为该地址的数据包
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst)
            
            # 如果输出端口不是洪泛，添加流表项以提高后续处理效率
            if out_port != ofproto.OFPP_FLOOD:
                self.add_flow(datapath, 1, match, actions, msg.buffer_id)
                
                # 如果数据包已经被缓存，不需要再次发送
                if msg.buffer_id != ofproto.OFP_NO_BUFFER:
                    return
            
            # 准备要发送的数据
            data = None
            if msg.buffer_id == ofproto.OFP_NO_BUFFER:
                # 如果数据包没有被缓存，需要包含数据
                data = msg.data

            # 创建并发送packet-out消息
            out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                      in_port=in_port, actions=actions, data=data)
            datapath.send_msg(out)
        else:
            # 设备不在白名单中，拒绝网络访问
            # 数据包被静默丢弃
            self.logger.info("MAC %s not in whitelist. Dropping packet.", src)

    def add_to_whitelist(self, mac):
        """
        将MAC地址添加到白名单
        
        参数:
            mac: 要添加的MAC地址字符串
            
        功能:
        - 检查MAC地址是否已存在
        - 添加到白名单集合
        - 记录日志
        """
        if mac not in self.white_list:
            self.white_list.add(mac)
            self.logger.info("MAC %s added to whitelist.", mac)

    def remove_from_whitelist(self, mac):
        """
        从白名单中移除MAC地址
        
        参数:
            mac: 要移除的MAC地址字符串
            
        功能:
        - 检查MAC地址是否存在
        - 从白名单集合中移除
        - 记录日志
        """
        if mac in self.white_list:
            self.white_list.remove(mac)
            self.logger.info("MAC %s removed from whitelist.", mac)


class WhitelistController(ControllerBase):
    """
    REST API控制器类
    
    提供RESTful API接口用于管理MAC地址白名单
    
    支持的API端点:
    - POST /add_to_whitelist: 添加MAC地址到白名单
    - POST /remove_from_whitelist: 从白名单中移除MAC地址
    
    继承自Ryu的ControllerBase，提供Web接口功能
    """
    
    def __init__(self, req, link, data, **config):
        """
        REST控制器初始化
        
        参数:
            req: Web请求对象
            link: 链接对象
            data: 应用数据字典，包含hotel_wifi_app引用
            **config: 其他配置参数
        """
        super(WhitelistController, self).__init__(req, link, data, **config)
        
        # 获取HotelWifiController的引用，用于调用其方法
        self.hotel_wifi_app = data['hotel_wifi_app']

    @route('whitelist', '/add_to_whitelist', methods=['POST'])
    def add_to_whitelist(self, req, **kwargs):
        """
        添加MAC地址到白名单的API端点
        
        HTTP方法: POST
        请求格式: JSON格式，包含mac字段
        成功响应: 200 OK
        错误响应: 400 Bad Request（参数错误）或500 Internal Server Error（服务器错误）
        
        参数:
            req: Web请求对象
            
        返回:
            Response对象，包含状态码
        """
        try:
            # 从请求中获取JSON数据
            mac = req.json.get('mac')
            
            # 验证MAC地址参数
            if mac:
                # 调用主控制器的方法添加MAC地址
                self.hotel_wifi_app.add_to_whitelist(mac)
                
                # 返回成功响应
                return Response(status=200, content_type='application/json')
            else:
                # MAC地址参数缺失，返回400错误
                return Response(status=400, content_type='application/json')
        except Exception as e:
            # 处理任何异常，返回500错误
            self.hotel_wifi_app.logger.error("Error adding to whitelist: %s", str(e))
            return Response(status=500, content_type='application/json')

    @route('whitelist', '/remove_from_whitelist', methods=['POST'])
    def remove_from_whitelist(self, req, **kwargs):
        """
        从白名单中移除MAC地址的API端点
        
        HTTP方法: POST
        请求格式: JSON格式，包含mac字段
        成功响应: 200 OK
        错误响应: 400 Bad Request（参数错误）或500 Internal Server Error（服务器错误）
        
        参数:
            req: Web请求对象
            
        返回:
            Response对象，包含状态码
        """
        try:
            # 从请求中获取JSON数据
            mac = req.json.get('mac')
            
            # 验证MAC地址参数
            if mac:
                # 调用主控制器的方法移除MAC地址
                self.hotel_wifi_app.remove_from_whitelist(mac)
                
                # 返回成功响应
                return Response(status=200, content_type='application/json')
            else:
                # MAC地址参数缺失，返回400错误
                return Response(status=400, content_type='application/json')
        except Exception as e:
            # 处理任何异常，返回500错误
            self.hotel_wifi_app.logger.error("Error removing from whitelist: %s", str(e))
            return Response(status=500, content_type='application/json')


"""
使用说明和部署指南：

1. 启动控制器：
   ryu-manager ryuFinal.py

2. API使用示例：
   - 添加MAC地址到白名单：
     curl -X POST -H "Content-Type: application/json" -d '{"mac":"00:11:22:33:44:55"}' http://localhost:8080/add_to_whitelist
   
   - 从白名单中移除MAC地址：
     curl -X POST -H "Content-Type: application/json" -d '{"mac":"00:11:22:33:44:55"}' http://localhost:8080/remove_from_whitelist

3. 日志查看：
   控制器日志会显示设备连接、流量统计和白名单变更信息

4. 扩展建议：
   - 可以添加数据库支持持久化白名单
   - 可以增加用户认证和授权机制
   - 可以添加流量限制和QoS功能
   - 可以增加Web管理界面
"""
