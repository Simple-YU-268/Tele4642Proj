# 酒店WiFi网络控制器 - 项目逻辑梳理（更新版）

## 项目概述
这是一个基于SDN的酒店WiFi网络管理系统，使用Ryu控制器实现基于流量配额的动态网络访问控制。新逻辑采用"默认DROP，按需许可"的安全模型。

## 核心架构（模块化设计）

### 1. 主控制器 (hotel_wifi_controller.py)
- **功能**: 协调所有模块的核心控制器
- **基于**: Ryu SDN框架
- **新特性**: 移除白名单机制，移除路由器特殊地位

### 2. 模块架构

#### 2.1 流表管理器 (flow_manager.py)
- **功能**: 管理OpenFlow流表，实现默认DROP + 配额许可
- **核心方法**:
  - `installDefaultDropFlows()`: 默认DROP所有流量
  - `updateQuotaBasedFlows()`: 根据配额动态更新许可流表
  - `addPermitFlowsForDevice()`: 为设备添加许可流表
  - `removePermitFlowsForDevice()`: 移除设备许可流表

#### 2.2 配额管理器 (quota_manager.py)
- **功能**: 监控用户数据配额，管理流量购买
- **数据存储**: user_data.json
- **核心方法**:
  - `getDevicesWithQuota()`: 获取有剩余配额的设备
  - `addQuotaForDevice()`: 为设备增加配额（购买流量）
  - `getQuotaStatus()`: 获取配额状态

#### 2.3 流量监控器 (traffic_monitor.py)
- **功能**: 监控每个设备的网络流量使用情况
- **数据存储**: traffic_stats.json
- **集成**: 与配额系统实时同步
- **核心方法**:
  - `updateTraffic()`: 更新流量统计并同步到配额
  - `getQuotaBasedTraffic()`: 获取基于配额的流量统计

#### 2.4 API控制器 (api_controller.py)
- **功能**: 提供RESTful API接口
- **端点**:
  - `/api/quota/status`: 获取配额状态
  - `/api/quota/add`: 增加配额（购买流量）
  - `/api/quota/reset`: 重置流量使用
  - `/api/quota/update-flows`: 手动更新流表

## 新数据流逻辑

### 3.1 系统启动流程
1. 交换机连接初始化
2. 下发默认DROP流表（优先级0）
3. 检查user_data.json中的配额状态
4. 为有剩余配额的设备下发许可流表（优先级200）

### 3.2 许可流表规则
- **规则1**: `eth_src=设备MAC, eth_dst=路由器MAC` → 允许转发
- **规则2**: `eth_src=路由器MAC, eth_dst=设备MAC` → 允许转发

### 3.3 流量控制机制
- **默认状态**: 所有流量DROP
- **许可状态**: 有配额的设备可以通信
- **配额用完**: 自动移除许可流表，回到DROP状态
- **购买流量**: 重新下发许可流表

### 3.4 配额管理流程
1. 每次数据包处理时更新流量统计
2. 实时检查配额剩余量
3. 配额用完时自动切断网络
4. 用户可通过API购买额外配额
5. 购买后自动恢复网络访问

## 4. 数据文件说明

### 4.1 user_data.json
```json
{
  "users": {
    "房间号": {
      "quota": 配额字节数,
      "devices": ["MAC地址列表"],
      "created_at": 创建时间戳,
      "used_traffic": 已使用字节数
    }
  }
}
```

### 4.2 traffic_stats.json
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

## 5. 网络控制机制

### 5.1 流表优先级
- **优先级200**: 许可流表（设备↔路由器）
- **优先级0**: 默认DROP流表（阻止所有流量）

### 5.2 动态控制
- **实时更新**: 配额变化时立即更新流表
- **自动恢复**: 购买流量后自动恢复访问
- **流量统计**: 实时记录每个设备的使用情况

## 6. 使用场景

### 6.1 酒店WiFi管理
- 为每个房间分配网络配额
- 按流量计费模式
- 防止单个用户占用过多带宽

### 6.2 测试验证
- 启动控制器和Mininet
- 验证默认DROP行为
- 测试配额用完自动断网
- 测试购买流量恢复访问

## 7. 启动命令

```bash
# 启动控制器
ryu-manager hotel_wifi_controller.py

# 启动Mininet
python mininettopo.py

# 测试API
curl http://localhost:8080/api/quota/status
curl -X POST http://localhost:8080/api/quota/add \
  -H "Content-Type: application/json" \
  -d '{"mac": "00:00:00:00:00:01", "gb": 5}'
```

## 8. 模块依赖关系
```
hotel_wifi_controller.py
├── modules/flow_manager.py
├── modules/quota_manager.py
├── modules/traffic_monitor.py
└── modules/api_controller.py
