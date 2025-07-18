from mininet.net import Mininet
from mininet.node import Controller, RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel

def hotel_wifi_topology():
    net = Mininet(controller=RemoteController)

    
    c0 = net.addController('c0', controller=RemoteController, ip='127.0.0.1', port=6653)

    
    s1 = net.addSwitch('s1')

    
    h1 = net.addHost('h1', ip='10.0.0.1')
    h2 = net.addHost('h2', ip='10.0.0.2')
    h3 = net.addHost('h3', ip='10.0.0.3')

    
    net.addLink(h1, s1)
    net.addLink(h2, s1)
    net.addLink(h3, s1)

    
    net.start()

    
    CLI(net)

    
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    hotel_wifi_topology()
