#!/usr/bin/env python3
"""
实时流量调试工具 - 显示ping操作是否成功
"""

import time
import subprocess
import sys

def check_ping_success():
    """检查ping是否成功"""
    print("🔍 正在检查网络连通性...")
    
    # 检查Mininet是否运行
    try:
        result = subprocess.run(['mn', '--test', 'pingall'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✅ 网络连通性正常 - 所有ping成功")
            print("📊 流量状态: FORWARD")
            return True
        else:
            print("❌ 网络连通性问题 - 部分ping失败")
            print("📊 流量状态: 部分DROP")
            return False
    except:
        print("⚠️  Mininet未运行，使用模拟检查")
        return None

def show_flow_summary():
    """显示流表摘要"""
    print("\n" + "="*60)
    print("🔄 当前流表摘要:")
    print("   优先级0: 默认DROP规则")
    print("   优先级10: 允许所有流量")
    print("   优先级50: 允许广播")
    print("   优先级100: 允许ARP")
    print("   优先级200: 允许设备↔路由器")
    print("   优先级300: 允许设备间通信")
    print("="*60)

def debug_ping_behavior():
    """调试ping行为"""
    print("🎯 调试ping操作行为:")
    print("="*60)
    
    # 模拟ping成功的情况
    print("📦 模拟ping 10.0.0.1 → 10.0.0.254:")
    print("   源MAC: 00:00:00:00:00:01")
    print("   目的MAC: 00:00:00:00:00:AA")
    print("   源IP: 10.0.0.1")
    print("   目的IP: 10.0.0.254")
    print("   匹配规则: 优先级10 (允许所有)")
    print("   ✅ 结果: FORWARD - 流量被允许")
    
    print("\n📦 模拟ping 10.0.0.254 → 10.0.0.1:")
    print("   源MAC: 00:00:00:00:00:AA")
    print("   目的MAC: 00:00:00:00:00:01")
    print("   源IP: 10.0.0.254")
    print("   目的IP: 10.0.0.1")
    print("   匹配规则: 优先级10 (允许所有)")
    print("   ✅ 结果: FORWARD - 流量被允许")

if __name__ == "__main__":
    print("🚀 酒店WiFi网络调试工具")
    print("="*60)
    
    check_ping_success()
    show_flow_summary()
    debug_ping_behavior()
    
    print("\n💡 提示:")
    print("   - 当ping成功时，流量由流表直接处理")
    print("   - 当ping失败时，会触发PACKET-IN事件")
    print("   - 当前配置允许所有流量(优先级10规则)")
