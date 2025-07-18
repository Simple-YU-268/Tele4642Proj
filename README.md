# 酒店WiFi网络控制器 - 完整系统

## 项目概述

这是一个基于SDN的酒店WiFi网络管理系统，提供完整的用户认证、流量控制、房间管理和管理员监控功能。系统采用模块化设计，支持房间号+手机号认证、套餐选择、设备MAC地址绑定、流量配额管理等功能。

## 项目结构

```
hotel-wifi-controller/
├── 核心系统文件
│   ├── hotel_wifi_controller.py      # 主SDN控制器
│   ├── modules/                      # 功能模块
│   │   ├── __init__.py
│   │   ├── whitelist_manager.py     # 白名单管理
│   │   ├── traffic_monitor.py       # 流量监控
│   │   ├── flow_manager.py          # 流表管理
│   │   └── api_controller.py        # REST API
│   ├── mininettopo.py               # Mininet网络拓扑
│   ├── whitelist.json               # MAC白名单配置
│   ├── traffic_stats.json           # 流量统计文件
│
├── 房间认证系统
│   ├── flask_room_auth.py           # Flask认证服务器
│   ├── room_auth.json              # 房间认证配置
│   ├── user_data.json              # 用户数据存储
│
├── Web界面
│   ├── index_room_auth.html        # 用户认证界面
│   ├── admin_panel.html            # 管理员控制面板
│
└── 其他文件
    ├── flaskFinal.py               # 备用Flask服务器
    ├── ryuFinal.py                 # 备用Ryu控制器
    ├── indexFinal.html             # 备用Web界面
    └── testquota.py                # 配额测试脚本
```

## 系统功能

### 1. 用户认证系统
- **房间号+手机号后四位认证**
- **套餐选择**（免费/10GB/30GB/50GB）
- **在线支付集成**
- **设备MAC地址绑定**
- **流量配额管理**

### 2. 管理员功能
- **房间管理**（添加/删除房间）
- **MAC地址白名单管理**
- **实时流量监控**
- **系统状态仪表板**
- **数据导出功能**

### 3. SDN网络控制
- **OpenFlow流表管理**
- **MAC地址学习**
- **流量统计收集**
- **实时设备监控**

## 安装和运行

### 前置要求
```bash
# 安装Python依赖
pip install flask flask-cors requests ryu

# 安装Mininet（Ubuntu/Debian）
sudo apt-get install mininet
```

### 启动步骤

#### 1. 启动SDN控制器
```bash
# 启动主控制器
ryu-manager hotel_wifi_controller.py

# 或使用备用控制器
ryu-manager ryuFinal.py
```

#### 2. 启动房间认证服务器
```bash
# 启动Flask认证服务器
python flask_room_auth.py

# 服务器将在 http://localhost:5000 运行
```

#### 3. 启动Mininet网络
```bash
# 启动网络拓扑
sudo python mininettopo.py
```

#### 4. 访问Web界面
- **用户认证**: http://localhost:5000/static/index_room_auth.html
- **管理员面板**: http://localhost:5000/static/admin_panel.html

## API接口文档

### 房间认证API (端口5000)

#### 房间登录
```bash
POST /room_login
Content-Type: application/json

{
    "room_number": "101",
    "phone_last4": "1234"
}
```

#### 选择套餐
```bash
POST /select_room_plan
Content-Type: application/json

{
    "room_number": "101",
    "plan": "30G"
}
```

#### 支付处理
```bash
POST /room_payment
Content-Type: application/json

{
    "room_number": "101",
    "card_number": "1234567890123456",
    "cvv": "123",
    "expiry_date": "12/25"
}
```

#### 连接设备
```bash
POST /connect_room_device
Content-Type: application/json

{
    "room_number": "101",
    "mac": "00:11:22:33:44:55"
}
```

#### 获取配额
```bash
GET /get_room_quota?room_number=101
```

#### 消耗流量
```bash
POST /consume_room_traffic
Content-Type: application/json

{
    "room_number": "101",
    "usage": 10485760
}
```

### SDN控制器API (端口8080)

#### 白名单管理
```bash
# 获取白名单
GET /whitelist

# 添加MAC地址
POST /addToWhitelist
{"mac": "00:11:22:33:44:55"}

# 移除MAC地址
POST /removeFromWhitelist
{"mac": "00:11:22:33:44:55"}
```

#### 流量查询
```bash
# 获取所有流量统计
GET /traffic

# 获取特定MAC流量
GET /traffic?mac=00:11:22:33:44:55

# 获取流量排行
GET /topUsers?limit=10
```

## 配置文件说明

### 房间认证配置 (room_auth.json)
```json
{
  "rooms": {
    "101": "1234",
    "102": "5678",
    "201": "3456"
  }
}
```

### 用户数据 (user_data.json)
```json
{
  "users": {
    "101": {
      "quota": 10737418240,
      "devices": ["00:11:22:33:44:55", "AA:BB:CC:DD:EE:FF"],
      "created_at": 1234567890
    }
  },
  "sessions": {
    "101_1234": {
      "room_number": "101",
      "login_time": 1234567890
    }
  }
}
```

### MAC白名单 (whitelist.json)
```json
{
  "whitelist": [
    "00:11:22:33:44:55",
    "AA:BB:CC:DD:EE:FF"
  ]
}
```

### 流量统计 (traffic_stats.json)
```json
{
  "total": {
    "00:11:22:33:44:55": 104857600
  },
  "daily": {
    "00:11:22:33:44:55": 52428800
  },
  "lastUpdate": 1234567890.0
}
```

## 使用流程

### 用户连接流程
1. 连接酒店WiFi网络
2. 访问认证页面 (自动重定向)
3. 输入房间号和手机号后四位
4. 选择数据套餐
5. 完成支付（付费套餐）
6. 绑定设备MAC地址
7. 开始上网

### 管理员操作流程
1. 访问管理员面板
2. 添加新房间和认证码
3. 监控网络流量
4. 管理MAC白名单
5. 查看系统统计

## 扩展功能

### 1. 数据库集成
- 支持MySQL/PostgreSQL
- 用户行为分析
- 历史数据存储

### 2. 高级认证
- 短信验证码
- 邮箱验证
- 社交媒体登录

### 3. 计费系统
- 多币种支持
- 发票生成
- 退款处理

### 4. 网络优化
- QoS流量控制
- 带宽限制
- 内容过滤

## 故障排除

### 常见问题

#### 1. 控制器无法启动
```bash
# 检查端口占用
netstat -tulnp | grep :8080

# 重启控制器
pkill -f ryu-manager
ryu-manager hotel_wifi_controller.py
```

#### 2. Flask服务器错误
```bash
# 检查依赖
pip list | grep flask

# 重新安装
pip install flask flask-cors requests
```

#### 3. 网络连接问题
```bash
# 检查Mininet
sudo mn --test pingall

# 检查OpenFlow连接
ovs-vsctl show
```

## 性能优化

### 1. 缓存策略
- Redis缓存热点数据
- CDN加速静态资源
- 数据库查询优化

### 2. 监控告警
- 系统资源监控
- 网络异常告警
- 用户行为分析

### 3. 扩展部署
- Docker容器化
- Kubernetes集群
- 负载均衡配置

## 开发指南

### 添加新功能
1. 在对应模块中添加功能代码
2. 更新API接口
3. 修改Web界面
4. 更新配置文件
5. 测试功能完整性

### 代码规范
- 遵循PEP 8 Python编码规范
- 使用类型注解
- 添加单元测试
- 编写API文档

## 许可证

MIT License - 详见LICENSE文件
