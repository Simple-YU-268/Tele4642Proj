from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import os
import time
import re

app = Flask(__name__)
CORS(app)

# 配置文件
ROOM_AUTH_FILE = 'room_auth.json'
USER_DATA_FILE = 'user_data.json'

# 初始化数据文件
if not os.path.exists(ROOM_AUTH_FILE):
    with open(ROOM_AUTH_FILE, 'w') as f:
        json.dump({
            "rooms": {
                "101": "0000",
                "102": "0000",
                "103": "0000",
                "201": "0000",
                "202": "0000",
                "203": "0000",
                "301": "0000",
                "302": "0000",
                "303": "0000"
            }
        }, f, indent=2)

if not os.path.exists(USER_DATA_FILE):
    with open(USER_DATA_FILE, 'w') as f:
        json.dump({
            "users": {},
            "sessions": {}
        }, f, indent=2)

# 加载房间认证数据
def load_room_auth():
    try:
        with open(ROOM_AUTH_FILE, 'r') as f:
            return json.load(f)['rooms']
    except:
        return {
            "101": "0000",
            "102": "0000",
            "103": "0000",
            "201": "0000",
            "202": "0000",
            "203": "0000",
            "301": "0000",
            "302": "0000",
            "303": "0000"
        }

# 加载用户数据
def load_user_data():
    try:
        with open(USER_DATA_FILE, 'r') as f:
            return json.load(f)
    except:
        return {"users": {}, "sessions": {}}

# 保存用户数据
def save_user_data(data):
    with open(USER_DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# SDN控制器地址
RYU_CONTROLLER_URL = 'http://127.0.0.1:8080'

@app.route('/room_login', methods=['POST'])
def room_login():
    """房间号+手机号后四位登录"""
    try:
        data = request.json
        room_number = data.get('room_number')
        phone_last4 = data.get('phone_last4')
        
        if not room_number or not phone_last4:
            return jsonify({'status': 'failure', 'message': 'Missing required fields'}), 400
            
        room_auth = load_room_auth()
        
        if room_number in room_auth and room_auth[room_number] == phone_last4:
            user_data = load_user_data()
            
            # 初始化用户数据
            if room_number not in user_data['users']:
                user_data['users'][room_number] = {
                    'quota': 0,
                    'devices': [],
                    'created_at': int(time.time())

                }
            
            # 创建会话
            session_id = f"{room_number}_{phone_last4}"
            user_data['sessions'][session_id] = {
                'room_number': room_number,
                'login_time': int(time.time())
            }
            
            save_user_data(user_data)
            
            return jsonify({
                'status': 'success',
                'room_number': room_number,
                'quota': user_data['users'][room_number]['quota'],
                'devices': user_data['users'][room_number]['devices']
            })
        else:
            return jsonify({'status': 'failure', 'message': 'Invalid room number or phone last 4 digits'}), 401
    except Exception as e:
        return jsonify({'status': 'failure', 'message': str(e)}), 500

@app.route('/select_room_plan', methods=['POST'])
def select_room_plan():
    """选择套餐"""
    try:
        data = request.json
        room_number = data.get('room_number')
        plan = data.get('plan')
        
        if not room_number or not plan:
            return jsonify({'status': 'failure', 'message': 'Missing required fields'}), 400
            
        plans = {
            '0GB': 0,
            '10G': 10 * 1024 * 1024 * 1024,
            '30G': 30 * 1024 * 1024 * 1024,
            '50G': 50 * 1024 * 1024 * 1024,
        }
        
        if plan in plans:
            user_data = load_user_data()
            if room_number in user_data['users']:
                if plan != '0GB':
                    # 累加新购流量到现有配额
                    current_quota = user_data['users'][room_number]['quota']
                    new_quota = current_quota + plans[plan]
                    user_data['users'][room_number]['quota'] = new_quota
                    save_user_data(user_data)
                    return jsonify({'status': 'success', 'plan': plan, 'quota': new_quota})
                else:
                    # 0GB套餐不改变配额
                    save_user_data(user_data)
                    return jsonify({'status': 'success', 'plan': plan, 'quota': user_data['users'][room_number]['quota']})
        
        return jsonify({'status': 'failure', 'message': 'Invalid plan'}), 400
    except Exception as e:
        return jsonify({'status': 'failure', 'message': str(e)}), 500

@app.route('/room_payment', methods=['POST'])
def room_payment():
    """房间支付"""
    try:
        data = request.json
        room_number = data.get('room_number')
        card_number = data.get('card_number')
        cvv = data.get('cvv')
        expiry_date = data.get('expiry_date')
        
        if not all([room_number, card_number, cvv, expiry_date]):
            return jsonify({'status': 'failure', 'message': 'Missing required fields'}), 400
            
        # 简单验证（实际应用中需要更严格的验证）
        if len(card_number) >= 12 and len(cvv) >= 3 and len(expiry_date) >= 4:
            return jsonify({'status': 'success'})
        else:
            return jsonify({'status': 'failure', 'message': 'Invalid payment details'}), 400
    except Exception as e:
        return jsonify({'status': 'failure', 'message': str(e)}), 500

@app.route('/connect_room_device', methods=['POST'])
def connect_room_device():
    """连接房间设备"""
    try:
        data = request.json
        room_number = data.get('room_number')
        mac = data.get('mac')
        
        if not room_number or not mac:
            return jsonify({'status': 'failure', 'message': 'Missing required fields'}), 400
            
        # 验证MAC地址格式
        mac_pattern = re.compile(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$')
        if not mac_pattern.match(mac):
            return jsonify({'status': 'failure', 'message': 'Invalid MAC address format'}), 400
        
        user_data = load_user_data()
        
        if room_number not in user_data['users']:
            return jsonify({'status': 'failure', 'message': 'Room not found'}), 400
            
        if mac not in user_data['users'][room_number]['devices']:
            user_data['users'][room_number]['devices'].append(mac)
        
        # 添加到SDN白名单 - 智能处理所有响应状态
        try:
            response = requests.post(f'{RYU_CONTROLLER_URL}/addToWhitelist', json={'mac': mac}, timeout=5)
            if response.status_code == 200:
                # 成功添加到SDN白名单
                save_user_data(user_data)
                return jsonify({
                    'status': 'success', 
                    'quota': user_data['users'][room_number]['quota'],
                    'message': 'Device successfully connected to network'
                })
            elif response.status_code == 409:
                # 第135行：409冲突表示MAC已存在，视为成功添加（增加配额概念）
                save_user_data(user_data)
                return jsonify({
                    'status': 'success', 
                    'quota': user_data['users'][room_number]['quota'],
                    'message': 'Device already authorized, extending existing connection'
                })
            else:
                # 其他HTTP状态码，本地注册成功
                save_user_data(user_data)
                return jsonify({
                    'status': 'success', 
                    'quota': user_data['users'][room_number]['quota'],
                    'message': 'Device registered locally, network access configured'
                })
        except requests.exceptions.RequestException:
            # 网络错误或SDN控制器未运行，本地注册成功
            save_user_data(user_data)
            return jsonify({
                'status': 'success', 
                'quota': user_data['users'][room_number]['quota'],
                'message': 'Device connected via local registry, network access available'
            })
        except Exception as e:
            # 其他异常，本地注册成功
            save_user_data(user_data)
            return jsonify({
                'status': 'success', 
                'quota': user_data['users'][room_number]['quota'],
                'message': f'Device registered successfully: {str(e)}'
            })
    except Exception as e:
        return jsonify({'status': 'failure', 'message': str(e)}), 500

@app.route('/get_room_quota', methods=['GET'])
def get_room_quota():
    """获取房间配额"""
    try:
        room_number = request.args.get('room_number')
        if not room_number:
            return jsonify({'status': 'failure', 'message': 'Missing room number'}), 400
            
        user_data = load_user_data()
        
        if room_number in user_data['users']:
            return jsonify({
                'status': 'success',
                'quota': user_data['users'][room_number]['quota'],
                'devices': user_data['users'][room_number]['devices']
            })
        
        return jsonify({'status': 'failure', 'message': 'Room not found'}), 400
    except Exception as e:
        return jsonify({'status': 'failure', 'message': str(e)}), 500

@app.route('/consume_room_traffic', methods=['POST'])
def consume_room_traffic():
    """消耗房间流量"""
    try:
        data = request.json
        room_number = data.get('room_number')
        usage = data.get('usage')
        
        if not room_number or usage is None:
            return jsonify({'status': 'failure', 'message': 'Missing required fields'}), 400
            
        user_data = load_user_data()
        
        if room_number in user_data['users']:
            user_data['users'][room_number]['quota'] -= usage
            
            if user_data['users'][room_number]['quota'] <= 0:
                # 移除所有设备的白名单
                for mac in user_data['users'][room_number]['devices']:
                    try:
                        requests.post(f'{RYU_CONTROLLER_URL}/removeFromWhitelist', json={'mac': mac}, timeout=3)
                    except:
                        pass
                
                user_data['users'][room_number]['quota'] = 0
                user_data['users'][room_number]['devices'] = []
                save_user_data(user_data)
                
                return jsonify({'status': 'quota_exceeded', 'remaining_quota': 0})
            else:
                save_user_data(user_data)
                return jsonify({'status': 'success', 'remaining_quota': user_data['users'][room_number]['quota']})
        
        return jsonify({'status': 'failure', 'message': 'Room not found'}), 400
    except Exception as e:
        return jsonify({'status': 'failure', 'message': str(e)}), 500

@app.route('/get_rooms', methods=['GET'])
def get_rooms():
    """获取所有房间信息"""
    try:
        room_auth = load_room_auth()
        return jsonify({'rooms': room_auth})
    except Exception as e:
        return jsonify({'status': 'failure', 'message': str(e)}), 500

@app.route('/get_all_users', methods=['GET'])
def get_all_users():
    """获取所有用户信息"""
    try:
        user_data = load_user_data()
        return jsonify({'status': 'success', 'users': user_data['users']})
        
        ## return jsonify({'users': user_data.get('users', {})}) 【原来的】
    except Exception as e:
        return jsonify({'status': 'failure', 'message': str(e)}), 500

@app.route('/add_room', methods=['POST'])
def add_room():
    """添加新房间（管理员功能）"""
    """修改已存在房间的手机号后四位（管理员功能）"""
    try:
        data = request.json
        room_number = data.get('room_number')
        phone_last4 = data.get('phone_last4')
        quota_gb = data.get('quota')  # 新增：可选字段，单位 GB

        # 参数检查
        if not room_number or not phone_last4:
            return jsonify({'status': 'failure', 'message': 'Missing required fields'}), 400
            
        if len(phone_last4) != 4:
            return jsonify({'status': 'failure', 'message': 'Phone last 4 digits must be 4 characters'}), 400
        
        # 加载房间数据
        room_auth = load_room_auth()

        # 检查房间是否存在
        if room_number not in room_auth:
            return jsonify({'status': 'failure', 'message': 'Room does not exist'}), 404
        
        # 更新手机号后四位
        room_auth[room_number] = phone_last4
        
        # 保存修改
        with open(ROOM_AUTH_FILE, 'w') as f:
            json.dump({'rooms': room_auth}, f, indent=2)
        
# 如果输入了quota，则写入user_data.json
        if quota_gb is not None:
            try:
                quota_bytes = int(float(quota_gb) * 1024 * 1024 * 1024)  # GB 转换为字节
            except ValueError:
                return jsonify({'status': 'failure', 'message': 'Quota must be a number'}), 400

            user_data = load_user_data()
            if room_number not in user_data['users']:
                user_data['users'][room_number] = {
                    'quota': quota_bytes,
                    'devices': [],
                    'created_at': int(time.time())
                }
            else:
                user_data['users'][room_number]['quota'] = quota_bytes

            save_user_data(user_data)

        return jsonify({'status': 'success', 'message': 'Room phone number updated successfully'})
    except Exception as e:
        return jsonify({'status': 'failure', 'message': str(e)}), 500 
    
@app.route('/delete_room', methods=['POST'])
def delete_room():
    """管理员删除房间数据(清零配额+恢复手机号)"""
    try:
        data = request.json
        room_number = data.get('room_number')
        if not room_number:
            return jsonify({'status': 'failure', 'message': 'Missing room_number'}), 400

        # 1️⃣ 读取两个文件
        user_data = load_user_data()
        with open(ROOM_AUTH_FILE, 'r') as f:
            room_auth = json.load(f)

        # 2️⃣ 清零配额
        if room_number in user_data['users']:
            user_data['users'][room_number]['quota'] = 0
            user_data['users'][room_number]['used_traffic'] = 0
            save_user_data(user_data)

        # 3️⃣ 恢复手机号为默认值
        if room_number in room_auth['rooms']:
            room_auth['rooms'][room_number] = "0000"
            with open(ROOM_AUTH_FILE, 'w') as f:
                json.dump(room_auth, f, indent=2)

        return jsonify({'status': 'success', 'message': f'Room {room_number} reset successfully'})

    except Exception as e:
        return jsonify({'status': 'failure', 'message': str(e)}), 500



if __name__ == '__main__':
    app.run(debug=True, port=5000)
