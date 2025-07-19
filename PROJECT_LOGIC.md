# 酒店WiFi网络控制器 - 项目逻辑梳理

## 项目概述
这是一个基于SDN的酒店WiFi网络管理系统，使用Ryu控制器实现网络访问控制、用户认证、流量监控和配额管理。

## 核心架构

### 1. 主控制器 (hotel_wifi_controller.py)
- **功能**: 协调所有模块的核心控制器
- **基于**: Ryu SDN框架
- **事件处理**: 
  - 交换机连接初始化
  - 数据包处理入口

### 2. 模块架构

#### 2.1 白名单管理器 (whitelist_manager.py)
- **功能**: 管理允许访问网络的设备MAC地址
- **接口**:
  - `isAllowed(mac)`: 检查设备是否允许访问
  - `addToWhitelist(mac, room_number)`: 添加设备到白名单
  - `removeFromWhitelist(mac)`: 从白名单移除设备

#### 2.2 流量监控器 (traffic_monitor.py)
- **功能**: 监控每个设备的网络流量使用情况
- **数据存储**: traffic_stats.json
- **接口**:
  - `updateTraffic(mac, bytes)`: 更新设备流量统计
  - `getTraffic(mac)`: 获取设备流量信息
  - `getTopUsers(limit)`: 获取流量使用最多的用户

#### 2.3 流表管理器 (flow_manager.py)
- **功能**: 管理OpenFlow流表，控制数据包转发
- **接口**:
  - `installDefaultFlow(datapath)`: 安装默认流表
  - `addFlow(datapath, priority, match, actions)`: 添加流表项
  - `handlePacket(...)`: 处理数据包转发

#### 2.4 配额管理器 (quota_manager.py) - 新增
- **功能**: 监控用户数据配额，使用完自动切断网络
- **数据存储**: user_data.json
- **接口**:
  - `checkUserQuota(mac)`: 检查用户配额是否用完
  - `blockUser(datapath, mac)`: 阻止用户网络访问
  - `monitorQuotaUsage(datapath, mac)`: 监控配额使用

#### 2.5 API控制器 (api_controller.py)
- **功能**: 提供RESTful API接口
- **端点**:
  - `/api/traffic`: 获取流量统计
  - `/api/topUsers`: 获取流量使用最多的用户
  - `/api/whitelist`: 管理白名单

### 3. 数据流逻辑

#### 3.1 用户注册流程
1. 用户通过网页表单注册 (index_room_auth.html)
2. Flask服务器验证房间号和手机号 (flask_room_auth.py)
3. 将设备MAC添加到白名单
4. 初始化用户配额信息到user_data.json

#### 3.2 网络访问控制流程
1. 设备发送数据包
2. 主控制器接收数据包
3. 白名单检查：如果不在白名单，丢弃数据包
4. 流量监控：更新设备流量统计
5. 配额检查：检查用户配额是否用完
6. 如果配额用完：阻止网络访问
7. 如果配额未用完：正常转发数据包

#### 3.3 配额管理流程
1. 每次数据包处理时检查配额
2. 计算已使用流量 vs 总配额
3. 如果超过配额：
   - 添加高优先级流表阻止该MAC
   - 从白名单移除该设备
   - 记录日志
4. 用户可购买额外配额恢复访问

### 4. 数据文件说明

#### 4.1 user_data.json
```json
{
  "users": {
    "房间号": {
      "quota": 配额字节数,
      "devices": ["MAC地址列表"],
      "created_at": 创建时间戳
    }
  },
  "sessions": {
    "会话ID": {
      "room_number": "房间号",
      "login_time": 登录时间戳
    }
  }
}
```

#### 4.2 traffic_stats.json
```json
{
  "total": {
    "MAC地址": 总使用字节数
  },
  "daily": {
    "MAC地址": 当日使用字节数
  },
  "lastUpdate": 最后更新时间戳
}
```

#### 4.3 room_auth.json
房间认证信息（房间号与手机号后4位对应关系）

#### 4.4 whitelist.json
白名单设备列表

### 5. 网络控制机制

#### 5.1 白名单机制
- 只有白名单中的设备可以访问网络
- 通过MAC地址识别设备

#### 5.2 流量控制机制
- 实时监控每个设备的流量使用
- 基于用户配额进行流量限制
- 超过配额自动切断网络

#### 5.3 流表控制
- 使用OpenFlow协议控制交换机
- 高优先级流表项用于阻止特定MAC地址
- 动态添加/删除流表项

### 6. 扩展功能

#### 6.1 配额购买
- 用户可通过网页购买额外流量
- 实时更新配额信息
- 自动恢复网络访问

#### 6.2 管理界面
- admin_panel.html 提供管理界面
- 实时查看用户流量使用情况
- 手动管理用户配额和设备

#### 6.3 流量统计
- 实时流量监控
- 历史数据统计
- 流量使用排行

## 使用场景

1. **酒店WiFi管理**: 为每个房间分配网络配额
2. **按流量计费**: 根据实际使用量收费
3. **公平使用**: 防止单个用户占用过多带宽
4. **安全管理**: 通过白名单控制设备接入
