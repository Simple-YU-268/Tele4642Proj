# 酒店WiFi网络控制器 - 模块化版本

## 项目结构

```
hotel-wifi-controller/
├── hotel_wifi_controller.py      # 主控制器
├── modules/                      # 功能模块
│   ├── __init__.py
│   ├── whitelist_manager.py     # 白名单管理
│   ├── traffic_monitor.py       # 流量监控
│   ├── flow_manager.py          # 流表管理
│   └── api_controller.py        # REST API
├── mininettopo.py               # Mininet拓扑
├── whitelist.json               # 白名单配置文件
├── traffic_stats.json           # 流量统计文件
└── README.md                    # 项目说明
```

## 模块说明

### 1. 主控制器 (hotel_wifi_controller.py)
- 协调各模块工作
- 处理OpenFlow事件
- 模块间通信中心

### 2. 白名单管理 (whitelist_manager.py)
- MAC地址白名单管理
- 持久化存储
- 线程安全操作

### 3. 流量监控 (traffic_monitor.py)
- 实时流量统计
- 历史数据存储
- 流量排行功能

### 4. 流表管理 (flow_manager.py)
- 流表项管理
- MAC地址学习
- 数据包转发

### 5. REST API (api_controller.py)
- 白名单管理接口
- 流量查询接口
- 标准RESTful设计

## 安装和运行

### 1. 启动控制器
```bash
ryu-manager hotel_wifi_controller.py
```

### 2. 启动Mininet拓扑
```bash
sudo python mininettopo.py
```

### 3. API使用示例

#### 添加MAC地址到白名单
```bash
curl -X POST -H "Content-Type: application/json" -d '{"mac":"00:11:22:33:44:55"}' http://localhost:8080/addToWhitelist
```

#### 移除MAC地址
```bash
curl -X POST -H "Content-Type: application/json" -d '{"mac":"00:11:22:33:44:55"}' http://localhost:8080/removeFromWhitelist
```

#### 获取白名单
```bash
curl http://localhost:8080/whitelist
```

#### 获取流量统计
```bash
curl http://localhost:8080/traffic?mac=00:11:22:33:44:55
```

#### 获取流量排行
```bash
curl http://localhost:8080/topUsers?limit=5
```

## 配置说明

### 白名单配置 (whitelist.json)
```json
{
  "whitelist": [
    "00:11:22:33:44:55",
    "aa:bb:cc:dd:ee:ff"
  ]
}
```

### 流量统计 (traffic_stats.json)
```json
{
  "total": {
    "00:11:22:33:44:55": 1048576
  },
  "daily": {
    "00:11:22:33:44:55": 524288
  },
  "lastUpdate": 1234567890.0
}
```

## 扩展指南

### 添加新模块
1. 在modules目录创建新模块文件
2. 实现所需功能类
3. 在主控制器中导入和初始化
4. 更新API控制器（如需要）

### 自定义功能
- 继承现有模块类进行扩展
- 添加新的REST API端点
- 集成数据库支持
- 添加Web管理界面

## 性能优化

### 多线程支持
- 所有模块使用线程锁保证并发安全
- 异步文件I/O操作

### 内存管理
- 使用defaultdict优化内存使用
- 定期清理过期数据

### 扩展性
- 支持多交换机环境
- 水平扩展能力
- 插件式架构设计
