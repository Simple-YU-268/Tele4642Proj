#!/usr/bin/env python3
"""
ARP调试工具 - 专门解决ARP无响应问题
"""

import subprocess
import time
import os

def run_command(cmd):
    """运行系统命令并返回输出"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except Exception as e:
        return "", str(e), 1

def check_arp_flows():
    """检查ARP相关的OpenFlow流表"""
    print("🔍 检查ARP流表状态...")
    print("=" * 50)
    
    # 检查s1交换机的流表
    stdout, stderr, code = run_command("ovs-ofctl dump-flows s1")
    if code == 0:
        lines = stdout.split('\n')
        arp_lines = [line for line in lines if 'arp' in line.lower() or '0806' in line]
        
        if arp_lines:
            print("✅ 发现ARP流表规则:")
            for line in arp_lines:
                print(f"   {line}")
        else:
            print("❌ 未发现ARP流表规则")
            
            # 检查是否有eth_type=0x0806的规则
            eth_lines = [line for line in lines if 'eth_type=0x806' in line or 'eth_type=0x0806' in line]
            if eth_lines:
                print("✅ 发现eth_type=0x0806规则:")
                for line in eth_lines:
                    print(f"   {line}")
            else:
                print("❌ 未发现eth_type=0x0806规则")
    else:
        print(f"❌ 无法获取流表: {stderr}")

def check_switch_ports():
    """检查交换机端口状态"""
    print("\n🔍 检查交换机端口...")
    print("=" * 50)
    
    stdout, stderr, code = run_command("ovs-ofctl show s1")
    if code == 0:
        print("✅ 交换机端口状态:")
        lines = stdout.split('\n')
        for line in lines:
            if 'addr' in line or 'port' in line.lower():
                print(f"   {line.strip()}")
    else:
        print(f"❌ 无法获取端口信息: {stderr}")

def check_arp_table():
    """检查ARP表"""
    print("\n🔍 检查ARP缓存...")
    print("=" * 50)
    
    # 检查Mininet主机ARP表
    hosts = ['h1', 'h2', 'h3', 'router']
    for host in hosts:
        stdout, stderr, code = run_command(f"mnexec -a {host} arp -n")
        if code == 0:
            print(f"📱 {host} ARP表:")
            lines = stdout.split('\n')
            for line in lines:
                if '10.0.0.' in line:
                    print(f"   {line}")
        else:
            print(f"❌ 无法获取{host}的ARP表")

def test_arp_ping():
    """测试ARP连通性"""
    print("\n🔍 测试ARP连通性...")
    print("=" * 50)
    
    # 测试h1到router的ARP
    print("🧪 测试h1 → router ARP...")
    stdout, stderr, code = run_command("mnexec -a h1 ping -c 1 -W 1 10.0.0.254")
    if code == 0:
        print("✅ h1 → router ARP成功")
        lines = stdout.split('\n')
        for line in lines:
            if 'bytes from' in line:
                print(f"   {line}")
    else:
        print("❌ h1 → router ARP失败")
        print(f"   错误: {stderr}")
    
    # 测试h1到h2的ARP
    print("\n🧪 测试h1 → h2 ARP...")
    stdout, stderr, code = run_command("mnexec -a h1 ping -c 1 -W 1 10.0.0.2")
    if code == 0:
        print("✅ h1 → h2 ARP成功")
    else:
        print("❌ h1 → h2 ARP失败")

def check_mac_addresses():
    """检查MAC地址"""
    print("\n🔍 检查MAC地址...")
    print("=" * 50)
    
    hosts = ['h1', 'h2', 'h3', 'router']
    for host in hosts:
        stdout, stderr, code = run_command(f"mnexec -a {host} ip link show")
        if code == 0:
            lines = stdout.split('\n')
            for line in lines:
                if 'link/ether' in line:
                    mac = line.split()[1]
                    print(f"📱 {host}: {mac}")

def main():
    """主函数"""
    print("🚨 ARP调试工具 - 解决ARP无响应问题")
    print("=" * 60)
    
    # 检查Mininet是否运行
    stdout, stderr, code = run_command("pgrep -f mininet")
    if code != 0:
        print("❌ Mininet未运行，请先启动:")
        print("   sudo python mininettopo.py")
        return
    
    check_arp_flows()
    check_switch_ports()
    check_mac_addresses()
    check_arp_table()
    test_arp_ping()
    
    print("\n" + "=" * 60)
    print("🔧 如果ARP失败，请尝试:")
    print("1. 在Mininet CLI中: h1 ping -c 1 10.0.0.254")
    print("2. 手动清除ARP缓存: mnexec -a h1 ip neigh flush all")
    print("3. 检查控制器日志: tail -f /tmp/ryu.log")
    print("4. 重新安装ARP流表: ovs-ofctl add-flow s1 'priority=1,arp,actions=FLOOD'")

if __name__ == "__main__":
    main()
