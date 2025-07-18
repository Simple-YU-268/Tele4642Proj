import time

import requests



email = "test@example.com"

usage_per_interval = 5 * 1024 * 1024 * 1024  # 5GB in bytes



while True:

    response = requests.post('http://127.0.0.1:5000/consume_traffic', json={'email': email, 'usage': usage_per_interval})

    result = response.json()

    if result['status'] == 'quota_exceeded':

        print(f"Quota exceeded. Remaining quota: {result['remaining_quota']}")

        break

    elif result['status'] == 'success':

        print(f"Remaining quota: {result['remaining_quota']} bytes")

    else:

        print("Failed to consume traffic")

    time.sleep(10)