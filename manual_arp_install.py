#!/usr/bin/env python3
"""
手动ARP流表安装工具
解决ARP流表未自动安装的问题
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

def install_arp_flows():
    """手动安装ARP流表"""
    print("🔧 手动安装ARP流表...")
    print("=" * 50)
    
    # 1. 检查交换机是否存在
    stdout, stderr, code = run_cmd("ovs-vsctl list-br")
    if code != 0 or "s1" not in stdout:
        print("❌ s1交换机不存在")
        print("💡 请先启动Mininet: python mininettopo.py")
        return
    
    # 2. 清除现有流表
    print("1️⃣ 清除现有流表...")
    run_cmd("ovs-ofctl del-flows s1")
    
    # 3. 安装基础流表
    print("2️⃣ 安装基础流表...")
    
    # 优先级0: 默认DROP
    run_cmd("ovs-ofctl add-flow s1 'priority=0,actions=drop'")
    
    # 优先级1: ARP许可
    run_cmd("ovs-ofctl add-flow s1 'priority=1,arp,actions=FLOOD'")
    
    # 优先级400: 设备到路由器IP（示例规则）
    run_cmd("ovs-ofctl add-flow s1 'priority=400,eth_src=00:00:00:00:00:01,eth_dst=00:00:00:00:00:AA,eth_type=0x0800,actions=output:1'")
    run_cmd("ovs-ofctl add-flow s1 'priority=400,eth_src=00:00:00:00:00:AA,eth_dst=00:00:00:00:00:01,eth_type=0x0800,actions=output:2'")
    
    run_cmd("ovs-ofctl add-flow s1 'priority=400,eth_src=00:00:00:00:00:02,eth_dst=00:00:00:00:00:AA,eth_type=0x0800,actions=output:1'")
    run_cmd("ovs-ofctl add-flow s1 'priority=400,eth_src=00:00:00:00:00:AA,eth_dst=00:00:00:00:00:02,eth_type=0x0800,actions=output:3'")
    
    run_cmd("ovs-ofctl add-flow s1 'priority=400,eth_src=00:00:00:00:00:03,eth_dst=00:00:00:00:00:AA,eth_type=0x0800,actions=output:1'")
    run_cmd("ovs-ofctl add-flow s1 'priority=400,eth_src=00:00:00:00:00:AA,eth_dst=00:00:00:00:00:03,eth_type=0x0800,actions=output:4'")
    
    # 4. 验证安装
    print("3️⃣ 验证流表安装...")
    stdout, stderr, code = run_cmd("ovs-ofctl dump-flows s1")
    if code == 0:
        print("✅ 已安装的流表:")
        for line in stdout.split('\n'):
            if line.strip():
                print(f"   {line}")
    
    # 5. 测试ARP
    print("4️⃣ 测试ARP...")
    print("🧪 测试h1 → router ARP...")
    run_cmd("mnexec -a h1 ping -c 1 10.0.0.254")
    
    print("🧪 测试h2 → router ARP...")
    run_cmd("mnexec -a h2 ping -c 1 10.0.0.254")
    
    print("🧪 测试h3 → router ARP...")
    run_cmd("mnexec -a h3 ping -c 1 10.0.0.254")
    
    print("\n✅ ARP流表安装完成！")
    print("🔍 检查ARP表: mnexec -a h1 arp -n")

if __name__ == "__main__":
    install_arp_flows()
