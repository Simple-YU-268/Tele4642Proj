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
    h1 = net.addHost('h1')
    h2 = net.addHost('h2')
    h3 = net.addHost('h3')
    h4 = net.addHost('h4')
    h5 = net.addHost('h5')
    h6 = net.addHost('h6')
    h7 = net.addHost('h7')
    h8 = net.addHost('h8')
    h9 = net.addHost('h9')

    # 添加路由器（代替服务器）
    router = net.addHost('router')
    
    # 连接所有节点
    net.addLink(h1, s1, port1=0, port2=2)
    net.addLink(h2, s1, port1=0, port2=3)
    net.addLink(h3, s1, port1=0, port2=4)
    net.addLink(h4, s1, port1=0, port2=5)
    net.addLink(h5, s1, port1=0, port2=6)
    net.addLink(h6, s1, port1=0, port2=7)
    net.addLink(h7, s1, port1=0, port2=8)
    net.addLink(h8, s1, port1=0, port2=9)
    net.addLink(h9, s1, port1=0, port2=10)
    net.addLink(router, s1, port1=0, port2=1)
    

    

    # 启动网络
    net.start()
    
    # ---------------- VLAN 配置 ----------------
    # Router trunk
    s1.cmd("ovs-vsctl set port s1-eth1 trunks=101,102,103,201,202,203,301,302,303")
    
    # Host access ports
    s1.cmd("ovs-vsctl set port s1-eth2 tag=101")
    s1.cmd("ovs-vsctl set port s1-eth3 tag=102")
    s1.cmd("ovs-vsctl set port s1-eth4 tag=103")
    s1.cmd("ovs-vsctl set port s1-eth5 tag=201")
    s1.cmd("ovs-vsctl set port s1-eth6 tag=202")
    s1.cmd("ovs-vsctl set port s1-eth7 tag=203")
    s1.cmd("ovs-vsctl set port s1-eth8 tag=301")
    s1.cmd("ovs-vsctl set port s1-eth9 tag=302")
    s1.cmd("ovs-vsctl set port s1-eth10 tag=303")

    # ---------------- Host IP 配置 ----------------
    h1.cmd("ip addr flush dev h1-eth0")
    h1.cmd("ip addr add 10.0.11.1/24 dev h1-eth0")
    h2.cmd("ip addr flush dev h2-eth0")
    h2.cmd("ip addr add 10.0.12.2/24 dev h2-eth0")
    h3.cmd("ip addr flush dev h3-eth0")
    h3.cmd("ip addr add 10.0.13.3/24 dev h3-eth0")
    h4.cmd("ip addr flush dev h4-eth0")
    h4.cmd("ip addr add 10.0.21.11/24 dev h4-eth0")
    h5.cmd("ip addr flush dev h5-eth0")
    h5.cmd("ip addr add 10.0.22.12/24 dev h5-eth0")
    h6.cmd("ip addr flush dev h6-eth0")
    h6.cmd("ip addr add 10.0.23.13/24 dev h6-eth0")
    h7.cmd("ip addr flush dev h7-eth0")
    h7.cmd("ip addr add 10.0.31.21/24 dev h7-eth0")
    h8.cmd("ip addr flush dev h8-eth0")
    h8.cmd("ip addr add 10.0.32.22/24 dev h8-eth0")
    h9.cmd("ip addr flush dev h9-eth0")
    h9.cmd("ip addr add 10.0.33.23/24 dev h9-eth0")


    # ---------------- Router VLAN 子接口配置 ----------------
    router.cmd("ip link add link router-eth0 name router.101 type vlan id 101")
    router.cmd("ip addr add 10.0.11.254/24 dev router.101")
    router.cmd("ip link set up router.101")

    router.cmd("ip link add link router-eth0 name router.102 type vlan id 102")
    router.cmd("ip addr add 10.0.12.254/24 dev router.102")
    router.cmd("ip link set up router.102")

    router.cmd("ip link add link router-eth0 name router.103 type vlan id 103")
    router.cmd("ip addr add 10.0.13.254/24 dev router.103")
    router.cmd("ip link set up router.103")

    router.cmd("ip link add link router-eth0 name router.201 type vlan id 201")
    router.cmd("ip addr add 10.0.21.254/24 dev router.201")
    router.cmd("ip link set up router.201")

    router.cmd("ip link add link router-eth0 name router.202 type vlan id 202")
    router.cmd("ip addr add 10.0.22.254/24 dev router.202")
    router.cmd("ip link set up router.202")

    router.cmd("ip link add link router-eth0 name router.203 type vlan id 203")
    router.cmd("ip addr add 10.0.23.254/24 dev router.203")
    router.cmd("ip link set up router.203")

    router.cmd("ip link add link router-eth0 name router.301 type vlan id 301")
    router.cmd("ip addr add 10.0.31.254/24 dev router.301")
    router.cmd("ip link set up router.301")

    router.cmd("ip link add link router-eth0 name router.302 type vlan id 302")
    router.cmd("ip addr add 10.0.32.254/24 dev router.302")
    router.cmd("ip link set up router.302")

    router.cmd("ip link add link router-eth0 name router.303 type vlan id 303")
    router.cmd("ip addr add 10.0.33.254/24 dev router.303")
    router.cmd("ip link set up router.303")

    
    # 配置主机的默认网关指向路由器
    h1.cmd('ip route add default via 10.0.11.254')
    h2.cmd('ip route add default via 10.0.12.254')
    h3.cmd('ip route add default via 10.0.13.254')
    h4.cmd('ip route add default via 10.0.21.254')
    h5.cmd('ip route add default via 10.0.22.254')
    h6.cmd('ip route add default via 10.0.23.254')
    h7.cmd('ip route add default via 10.0.31.254')
    h8.cmd('ip route add default via 10.0.32.254')
    h9.cmd('ip route add default via 10.0.33.254')
    
    # 配置路由器接口和ARP
    router.cmd('ifconfig router-eth0 hw ether 00:00:00:00:00:AA up')
    router.cmd('echo 1 > /proc/sys/net/ipv4/ip_forward')
    router.cmd('echo 0 > /proc/sys/net/ipv4/conf/all/arp_ignore')
    router.cmd('echo 0 > /proc/sys/net/ipv4/conf/all/arp_announce')
    
    # 确保ARP缓存清理
    router.cmd('ip neigh flush all')
    
    # 配置DNS服务器
    h1.cmd('echo "nameserver 8.8.8.8" > /etc/resolv.conf')
    h2.cmd('echo "nameserver 8.8.8.8" > /etc/resolv.conf')
    h3.cmd('echo "nameserver 8.8.8.8" > /etc/resolv.conf')
    h4.cmd('echo "nameserver 8.8.8.8" > /etc/resolv.conf')
    h5.cmd('echo "nameserver 8.8.8.8" > /etc/resolv.conf')
    h6.cmd('echo "nameserver 8.8.8.8" > /etc/resolv.conf')
    h7.cmd('echo "nameserver 8.8.8.8" > /etc/resolv.conf')
    h8.cmd('echo "nameserver 8.8.8.8" > /etc/resolv.conf')
    h9.cmd('echo "nameserver 8.8.8.8" > /etc/resolv.conf')

    # 启动CLI
    CLI(net)

    # 停止网络
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    hotel_wifi_topology()
