from mininet.net import Mininet
from mininet.node import Controller, RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel

def hotel_wifi_topology():
    net = Mininet(controller=RemoteController)

    # add controller
    c0 = net.addController('c0', controller=RemoteController, ip='127.0.0.1', port=6653)

    # add switch
    s1 = net.addSwitch('s1')

    # add host (Assign a fixed MAC address)
    h1 = net.addHost('h1', ip='10.0.0.1/24', mac='00:00:00:00:00:01')
    h2 = net.addHost('h2', ip='10.0.0.2/24', mac='00:00:00:00:00:02')
    h3 = net.addHost('h3', ip='10.0.0.3/24', mac='00:00:00:00:00:03')
    h4 = net.addHost('h4', ip='10.0.0.11/24', mac='00:00:00:00:00:0a')
    h5 = net.addHost('h5', ip='10.0.0.12/24', mac='00:00:00:00:00:0b')
    h6 = net.addHost('h6', ip='10.0.0.13/24', mac='00:00:00:00:00:0c')
    h7 = net.addHost('h7', ip='10.0.0.21/24', mac='00:00:00:00:00:15')
    h8 = net.addHost('h8', ip='10.0.0.22/24', mac='00:00:00:00:00:16')
    h9 = net.addHost('h9', ip='10.0.0.23/24', mac='00:00:00:00:00:17')

    # add router (replace server)
    router = net.addHost('router', ip='10.0.0.254/24', mac='00:00:00:00:00:AA')
    
    # addlink
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

    # net start
    net.start()
    
    # Configure the default gateway of the host to point to the router
    h1.cmd('route add default gw 10.0.0.254')
    h2.cmd('route add default gw 10.0.0.254')
    h3.cmd('route add default gw 10.0.0.254')
    h4.cmd('route add default gw 10.0.0.254')
    h5.cmd('route add default gw 10.0.0.254')
    h6.cmd('route add default gw 10.0.0.254')
    h7.cmd('route add default gw 10.0.0.254')
    h8.cmd('route add default gw 10.0.0.254')
    h9.cmd('route add default gw 10.0.0.254')
    
    # ifconfig: Make sure the interface is active
    router.cmd('ifconfig router-eth0 10.0.0.254/24 hw ether 00:00:00:00:00:AA up')
    # Enable the IP forwarding 
    router.cmd('echo 1 > /proc/sys/net/ipv4/ip_forward')
    # ARP policy: don't ignore external ARP request
    router.cmd('echo 0 > /proc/sys/net/ipv4/conf/all/arp_ignore')
    # ARP policy: allow any source ARP
    router.cmd('echo 0 > /proc/sys/net/ipv4/conf/all/arp_announce')
    # clear ARP cache
    router.cmd('ip neigh flush all')
    
    # Configure the DNS server
    h1.cmd('echo "nameserver 8.8.8.8" > /etc/resolv.conf')
    h2.cmd('echo "nameserver 8.8.8.8" > /etc/resolv.conf')
    h3.cmd('echo "nameserver 8.8.8.8" > /etc/resolv.conf')
    h4.cmd('echo "nameserver 8.8.8.8" > /etc/resolv.conf')
    h5.cmd('echo "nameserver 8.8.8.8" > /etc/resolv.conf')
    h6.cmd('echo "nameserver 8.8.8.8" > /etc/resolv.conf')
    h7.cmd('echo "nameserver 8.8.8.8" > /etc/resolv.conf')
    h8.cmd('echo "nameserver 8.8.8.8" > /etc/resolv.conf')
    h9.cmd('echo "nameserver 8.8.8.8" > /etc/resolv.conf')

    # start CLI
    CLI(net)

    # stop net
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    hotel_wifi_topology()
