from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)


accounts = {
    'test@example.com': 'password123',
    'test2@example.com': '123'
}

plans = {
    '0GB': 0,
    '10G': 10 * 1024 * 1024 * 1024,
    '30G': 30 * 1024 * 1024 * 1024,
    '50G': 50 * 1024 * 1024 * 1024,
}


user_devices = {}
user_quota = {}


RYU_CONTROLLER_URL = 'http://127.0.0.1:8080'

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    if accounts.get(email) == password:
        if email not in user_devices:
            user_devices[email] = []
        if email not in user_quota:
            user_quota[email] = 0
   
        return jsonify({'status': 'success', 'quota': user_quota[email], 'devices': user_devices[email]})
    else:
        return jsonify({'status': 'failure'}), 401

@app.route('/select_plan', methods=['POST'])
def select_plan():
    data = request.json
    email = data.get('email')
    plan = data.get('plan')
    if plan in plans:
        if plan != '0GB':
            user_quota[email] += plans[plan] 
        return jsonify({'status': 'success', 'plan': plan, 'quota': user_quota[email]})
    else:
        return jsonify({'status': 'failure'}), 400

@app.route('/payment', methods=['POST'])
def payment():
    data = request.json
    card_number = data.get('card_number')
    cvv = data.get('cvv')
    expiry_date = data.get('expiry_date')
    email = data.get('email')
  
    if card_number and cvv and expiry_date:
        return jsonify({'status': 'success', 'quota': user_quota[email]})
    else:
        return jsonify({'status': 'failure'}), 400

@app.route('/connect_device', methods=['POST'])
def connect_device():
    data = request.json
    email = data.get('email')
    mac = data.get('mac')
    if email in user_devices:
        if mac not in user_devices[email]:
            user_devices[email].append(mac)
     
        response = requests.post(f'{RYU_CONTROLLER_URL}/add_to_whitelist', json={'mac': mac})
        if response.status_code == 200:
            return jsonify({'status': 'success'})
        else:
            return jsonify({'status': 'failure'}), 500
    else:
        return jsonify({'status': 'failure'}), 400

@app.route('/consume_traffic', methods=['POST'])
def consume_traffic():
    data = request.json
    email = data.get('email')
    usage = data.get('usage')
    if email in user_quota:
        user_quota[email] -= usage
        if user_quota[email] <= 0:
            
            macs = user_devices[email]
            for mac in macs:
                requests.post(f'{RYU_CONTROLLER_URL}/remove_from_whitelist', json={'mac': mac})
            user_quota[email] = 0  
            return jsonify({'status': 'quota_exceeded', 'remaining_quota': 0})
        else:
            return jsonify({'status': 'success', 'remaining_quota': user_quota[email]})
    else:
        return jsonify({'status': 'failure'}), 400

@app.route('/get_quota', methods=['GET'])
def get_quota():
    email = request.args.get('email')
    if email in user_quota:
        return jsonify({'status': 'success', 'quota': user_quota[email]})
    else:
        return jsonify({'status': 'failure'}), 400

if __name__ == '__main__':
    app.run(debug=True)
