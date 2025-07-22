from mininet.net import Mininet
from mininet.node import Controller, RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel

def hotel_wifi_topology():
    net = Mininet(controller=RemoteController)

    # 添加控制器
    c0 = net.addController('c0', controller=RemoteController, ip='127.0.0.1', port=6653)

    # 添加交换机
    s1 = net.addSwitch('s1')

    # 添加主机（分配固定MAC地址）
    h1 = net.addHost('h1', ip='10.0.0.1/24', mac='00:00:00:00:00:01')
    h2 = net.addHost('h2', ip='10.0.0.2/24', mac='00:00:00:00:00:02')
    h3 = net.addHost('h3', ip='10.0.0.3/24', mac='00:00:00:00:00:03')

    # 添加路由器（代替服务器）
    router = net.addHost('router', ip='6.6.6.6/24', mac='00:00:00:00:00:AA')
    
    # 连接所有节点
    net.addLink(h1, s1)
    net.addLink(h2, s1)
    net.addLink(h3, s1)
    net.addLink(router, s1)

    # 启动网络
    net.start()
    
    # 配置主机的默认网关指向路由器
    h1.cmd('route add default gw 6.6.6.6')
    h2.cmd('route add default gw 6.6.6.6')
    h3.cmd('route add default gw 6.6.6.6')
    
    # 配置路由器路由（仅启用IP转发，无NAT - 封闭系统）
    router.cmd('echo 1 > /proc/sys/net/ipv4/ip_forward')
    
    # 配置DNS服务器（可选，用于内部测试）
    h1.cmd('echo "nameserver 8.8.8.8" > /etc/resolv.conf')
    h2.cmd('echo "nameserver 8.8.8.8" > /etc/resolv.conf')
    h3.cmd('echo "nameserver 8.8.8.8" > /etc/resolv.conf')

    # 启动CLI
    CLI(net)

    # 停止网络
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    hotel_wifi_topology()
