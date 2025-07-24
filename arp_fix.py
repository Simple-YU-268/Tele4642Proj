#!/usr/bin/env python3
"""
ARP无回应问题修复工具
解决"有ARP发送但没有回应"的问题
"""

import subprocess
import time

def run_cmd(cmd):
    """运行命令"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except Exception as e:
        return "", str(e), 1

def fix_arp_issue():
    """修复ARP无回应问题"""
    print("🚨 修复ARP无回应问题...")
    print("=" * 60)
    
    # 1. 检查并修复ARP流表
    print("1️⃣ 检查ARP流表...")
    stdout, stderr, code = run_cmd("ovs-ofctl dump-flows s1")
    
    if code != 0:
        print("❌ 无法连接到s1交换机，启动Mininet...")
        print("💡 请在新终端运行: python mininettopo.py")
        return
    
    # 检查是否有ARP规则
    if "arp" not in stdout.lower() and "0806" not in stdout:
        print("❌ 缺少ARP规则，正在添加...")
        run_cmd("ovs-ofctl add-flow s1 'priority=100,arp,actions=FLOOD'")
        print("✅ 已添加ARP规则")
    else:
        print("✅ ARP规则已存在")
    
    # 2. 检查MAC地址冲突
    print("\n2️⃣ 检查MAC地址...")
    mac_map = {}
    for host in ['h1', 'h2', 'h3', 'router']:
        stdout, stderr, code = run_cmd(f"mnexec -a {host} ip link show")
        if code == 0:
            for line in stdout.split('\n'):
                if 'link/ether' in line:
                    mac = line.split()[1]
                    mac_map[host] = mac
                    print(f"   {host}: {mac}")
    
    # 3. 检查IP配置
    print("\n3️⃣ 检查IP配置...")
    for host in ['h1', 'h2', 'h3', 'router']:
        stdout, stderr, code = run_cmd(f"mnexec -a {host} ip addr show")
        if code == 0:
            for line in stdout.split('\n'):
                if '10.0.0.' in line and 'inet' in line:
                    print(f"   {host}: {line.strip()}")
    
    # 4. 强制ARP学习
    print("\n4️⃣ 强制ARP学习...")
    for host in ['h1', 'h2', 'h3']:
        # 清除ARP缓存
        run_cmd(f"mnexec -a {host} ip neigh flush all")
        # 强制ARP请求
        run_cmd(f"mnexec -a {host} ping -c 1 -W 2 10.0.0.254")
    
    # 5. 检查ARP表
    print("\n5️⃣ 检查ARP表...")
    for host in ['h1', 'h2', 'h3', 'router']:
        stdout, stderr, code = run_cmd(f"mnexec -a {host} arp -n")
        if code == 0:
            print(f"\n📱 {host} ARP表:")
            for line in stdout.split('\n'):
                if '10.0.0.' in line:
                    print(f"   {line}")
    
    # 6. 测试连通性
    print("\n6️⃣ 测试ARP连通性...")
    tests = [
        ("h1", "10.0.0.254"),
        ("h2", "10.0.0.254"),
        ("h3", "10.0.0.254"),
        ("h1", "10.0.0.2"),
        ("h2", "10.0.0.1")
    ]
    
    for src, dst in tests:
        stdout, stderr, code = run_cmd(f"mnexec -a {src} ping -c 1 -W 2 {dst}")
        if code == 0:
            print(f"✅ {src} → {dst}: 成功")
        else:
            print(f"❌ {src} → {dst}: 失败")
    
    print("\n" + "=" * 60)
    print("🔧 额外修复步骤:")
    print("1. 手动检查: ovs-ofctl dump-flows s1")
    print("2. 手动添加ARP: ovs-ofctl add-flow s1 'priority=100,arp,actions=FLOOD'")
    print("3. 检查路由器: mnexec -a router iptables -L")
    print("4. 检查IP转发: mnexec -a router cat /proc/sys/net/ipv4/ip_forward")

if __name__ == "__main__":
    fix_arp_issue()
